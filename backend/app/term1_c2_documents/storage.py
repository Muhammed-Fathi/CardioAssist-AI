"""Private document storage outside Git and public web roots.

Security properties (accepted design §5.2, corrections T2-R3):

* server-generated storage keys ``<patient_uuid>/<document_uuid>.bin``; the
  original filename is never used in a path;
* strict path containment — no traversal, no symlink / reparse point / junction
  on ANY path component, regular files only. Opening is OS-specific and safe:
  POSIX uses ``O_NOFOLLOW`` + ``fstat``; Windows opens with
  ``FILE_FLAG_OPEN_REPARSE_POINT`` and refuses any reparse point on the opened
  handle (so a junction/symlink swap cannot redirect the open), after checking
  every ancestor for reparse attributes;
* atomic publication via write-to-temp + ``os.replace``;
* backend-writer / OCR-reader permissions: POSIX directories ``0750`` and files
  ``0640`` owned by the backend account, with the OCR account granted read via a
  shared group (never write, never world). The previous ``0700``/``0600`` model
  was incompatible with a separate OCR account and is replaced. Windows uses an
  explicit DACL (owner-local operator procedure + startup verification, see the
  runbook); there is NO permissive fallback;
* bounded, digest-verified reads: the complete ``<= 5 MiB`` buffer is verified
  against the recorded SHA-256 **before** any HTTP status/headers/body are sent.

This module is stdlib-only and never executes document content.
"""

from __future__ import annotations

import ctypes
import hashlib
import os
import re
import secrets
import stat
from pathlib import Path

from . import constants as C

_UUID = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")
_KEY = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"
    r"/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\.bin$"
)
_STAGING_KEY = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"
    r"/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"
    r"\.bin\.tmp-[0-9a-f]{16}$"
)

# POSIX permission model: backend owner rw, OCR group read, no world access.
_DIR_MODE = 0o750
_FILE_MODE = 0o640

_IS_WINDOWS = os.name == "nt"
_FILE_ATTRIBUTE_REPARSE_POINT = 0x400

# Well-known SIDs of BROAD principals that must never hold sensitive rights on the
# private root (P0-02). SIDs are locale-independent, unlike icacls principal names
# which are localized on non-English Windows.
_BROAD_SIDS = frozenset({
    "S-1-1-0",        # Everyone
    "S-1-5-11",       # Authenticated Users
    "S-1-5-32-545",   # BUILTIN\Users
    "S-1-5-32-546",   # BUILTIN\Guests
    "S-1-5-4",        # INTERACTIVE
    "S-1-5-2",        # NETWORK
    "S-1-5-32-547",   # BUILTIN\Power Users
})
# Sensitive access rights: any read OR write of data/attributes, delete, or DACL
# ownership change. A broad principal holding ANY of these is a violation, so the
# check denies unintended READ as well as write (P0-02).
_SENSITIVE_RIGHTS = (
    0x00000001  # FILE_READ_DATA
    | 0x00000002  # FILE_WRITE_DATA
    | 0x00000004  # FILE_APPEND_DATA
    | 0x00000008  # FILE_READ_EA
    | 0x00000010  # FILE_WRITE_EA
    | 0x00000020  # FILE_EXECUTE / traverse
    | 0x00010000  # DELETE
    | 0x00040000  # WRITE_DAC
    | 0x00080000  # WRITE_OWNER
    | 0x10000000  # GENERIC_ALL
    | 0x40000000  # GENERIC_WRITE
    | 0x80000000  # GENERIC_READ
)
_SE_DACL_PROTECTED = 0x1000


def _acl_violation(aces: list[tuple[str, int, int]], *, dacl_protected: bool) -> str | None:
    """Pure, locale-independent DACL policy check (testable off-Windows).

    ``aces`` is a list of ``(sid_string, access_mask, ace_type)`` where
    ``ace_type`` 0 = ACCESS_ALLOWED, 1 = ACCESS_DENIED. Returns a violation
    reason, or ``None`` when the DACL is safe. Fails closed when the DACL is not
    protected against inheritance (a permissive parent could grant broad access)
    or when any broad principal holds an ALLOW ACE with sensitive read/write
    rights. Deny ACEs never grant access and are ignored.
    """
    if not dacl_protected:
        return "Private root DACL is not protected against inheritance."
    for sid, mask, ace_type in aces:
        if ace_type != 0:  # only ALLOW ACEs grant access
            continue
        if sid in _BROAD_SIDS and (mask & _SENSITIVE_RIGHTS):
            return f"Broad principal {sid} holds sensitive read/write rights on the private root."
    return None


class StorageError(RuntimeError):
    """A storage operation failed safely."""


class IntegrityError(StorageError):
    """Stored bytes do not match the recorded immutable digest/length."""


def make_storage_key(patient_id: str, document_id: str) -> str:
    if not _UUID.match(patient_id) or not _UUID.match(document_id):
        raise StorageError("Storage key components must be UUIDs.")
    return f"{patient_id}/{document_id}.bin"


def _is_reparse_or_symlink(path: Path) -> bool:
    """True if ``path`` itself is a symlink, junction or other reparse point."""
    try:
        st = os.lstat(path)
    except OSError:
        return False
    if stat.S_ISLNK(st.st_mode):
        return True
    attrs = getattr(st, "st_file_attributes", 0)
    return bool(attrs & _FILE_ATTRIBUTE_REPARSE_POINT)


def _win_open_no_reparse(path: Path, *, write: bool, create_new: bool) -> int:
    """Open a file on Windows WITHOUT following a final reparse point.

    ``FILE_FLAG_OPEN_REPARSE_POINT`` opens the reparse point itself rather than
    its target; we then inspect the opened handle's attributes and refuse any
    reparse point, so a symlink/junction swapped in after the ancestor check
    cannot silently redirect the open. Returns a CRT file descriptor.
    """
    import msvcrt
    from ctypes import wintypes

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

    class BY_HANDLE_FILE_INFORMATION(ctypes.Structure):
        _fields_ = [
            ("dwFileAttributes", wintypes.DWORD),
            ("ftCreationTime", wintypes.FILETIME),
            ("ftLastAccessTime", wintypes.FILETIME),
            ("ftLastWriteTime", wintypes.FILETIME),
            ("dwVolumeSerialNumber", wintypes.DWORD),
            ("nFileSizeHigh", wintypes.DWORD),
            ("nFileSizeLow", wintypes.DWORD),
            ("nNumberOfLinks", wintypes.DWORD),
            ("nFileIndexHigh", wintypes.DWORD),
            ("nFileIndexLow", wintypes.DWORD),
        ]

    generic = 0x40000000 if write else 0x80000000  # GENERIC_WRITE / GENERIC_READ
    share = 0x1 | 0x2 | 0x4  # READ | WRITE | DELETE
    disposition = 1 if create_new else 3  # CREATE_NEW / OPEN_EXISTING
    flags = 0x00200000 | 0x02000000  # OPEN_REPARSE_POINT | BACKUP_SEMANTICS
    kernel32.CreateFileW.restype = wintypes.HANDLE
    kernel32.CreateFileW.argtypes = [
        wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, ctypes.c_void_p,
        wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE,
    ]
    handle = kernel32.CreateFileW(str(path), generic, share, None, disposition, flags, None)
    invalid = wintypes.HANDLE(-1).value
    if handle == invalid or handle is None:
        raise StorageError(f"Cannot open storage path safely (winerr {ctypes.get_last_error()}).")
    info = BY_HANDLE_FILE_INFORMATION()
    ok = kernel32.GetFileInformationByHandle(handle, ctypes.byref(info))
    if not ok or (info.dwFileAttributes & _FILE_ATTRIBUTE_REPARSE_POINT):
        kernel32.CloseHandle(handle)
        raise StorageError("Storage path is a reparse point; refusing to follow.")
    try:
        return msvcrt.open_osfhandle(handle, os.O_BINARY | (os.O_WRONLY if write else os.O_RDONLY))
    except OSError:
        kernel32.CloseHandle(handle)
        raise


def _read_windows_dacl(path: Path) -> tuple[list[tuple[str, int, int]], bool]:
    """Return ``(aces, dacl_protected)`` for ``path`` via the Windows API.

    Each ACE is ``(sid_string, access_mask, ace_type)``. Uses
    ``GetNamedSecurityInfoW`` + ``GetAce`` + ``ConvertSidToStringSidW`` so the
    result is independent of the OS display language. Windows-only; raises
    :class:`StorageError` on any failure so the caller fails closed.
    """
    import ctypes
    from ctypes import wintypes

    advapi32 = ctypes.WinDLL("advapi32", use_last_error=True)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

    class ACE_HEADER(ctypes.Structure):
        _fields_ = [("AceType", ctypes.c_ubyte), ("AceFlags", ctypes.c_ubyte),
                    ("AceSize", wintypes.WORD)]

    class ACCESS_ALLOWED_ACE(ctypes.Structure):
        _fields_ = [("Header", ACE_HEADER), ("Mask", wintypes.DWORD),
                    ("SidStart", wintypes.DWORD)]

    class ACL_SIZE_INFORMATION(ctypes.Structure):
        _fields_ = [("AceCount", wintypes.DWORD), ("AclBytesInUse", wintypes.DWORD),
                    ("AclBytesFree", wintypes.DWORD)]

    SE_FILE_OBJECT = 1
    DACL_SECURITY_INFORMATION = 0x00000004
    advapi32.GetNamedSecurityInfoW.argtypes = [
        wintypes.LPCWSTR, ctypes.c_int, ctypes.c_uint32,
        ctypes.POINTER(ctypes.c_void_p), ctypes.POINTER(ctypes.c_void_p),
        ctypes.POINTER(ctypes.c_void_p), ctypes.POINTER(ctypes.c_void_p),
        ctypes.POINTER(ctypes.c_void_p),
    ]
    advapi32.GetNamedSecurityInfoW.restype = wintypes.DWORD
    p_dacl = ctypes.c_void_p()
    p_sd = ctypes.c_void_p()
    rc = advapi32.GetNamedSecurityInfoW(
        str(path), SE_FILE_OBJECT, DACL_SECURITY_INFORMATION,
        None, None, ctypes.byref(p_dacl), None, ctypes.byref(p_sd),
    )
    if rc != 0 or not p_sd:
        raise StorageError(f"GetNamedSecurityInfoW failed (winerr {rc}).")
    try:
        control = wintypes.WORD()
        revision = wintypes.DWORD()
        advapi32.GetSecurityDescriptorControl.argtypes = [
            ctypes.c_void_p, ctypes.POINTER(wintypes.WORD), ctypes.POINTER(wintypes.DWORD)]
        advapi32.GetSecurityDescriptorControl(p_sd, ctypes.byref(control), ctypes.byref(revision))
        dacl_protected = bool(control.value & _SE_DACL_PROTECTED)
        if not p_dacl:
            # A NULL DACL grants everyone full control: never acceptable.
            raise StorageError("Private root has a NULL DACL (unrestricted access).")
        size_info = ACL_SIZE_INFORMATION()
        advapi32.GetAclInformation.argtypes = [
            ctypes.c_void_p, ctypes.c_void_p, wintypes.DWORD, ctypes.c_int]
        advapi32.GetAclInformation(p_dacl, ctypes.byref(size_info), ctypes.sizeof(size_info), 2)
        advapi32.GetAce.argtypes = [ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(ctypes.c_void_p)]
        advapi32.ConvertSidToStringSidW.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_wchar_p)]
        advapi32.ConvertSidToStringSidW.restype = wintypes.BOOL
        kernel32.LocalFree.argtypes = [ctypes.c_void_p]
        aces: list[tuple[str, int, int]] = []
        for index in range(size_info.AceCount):
            p_ace = ctypes.c_void_p()
            if not advapi32.GetAce(p_dacl, index, ctypes.byref(p_ace)):
                raise StorageError("GetAce failed while enumerating the private root DACL.")
            ace = ctypes.cast(p_ace, ctypes.POINTER(ACCESS_ALLOWED_ACE)).contents
            ace_type = ace.Header.AceType
            if ace_type not in (0, 1):  # only ALLOWED / DENIED carry a SID+mask here
                continue
            sid_addr = ctypes.addressof(ace) + ACCESS_ALLOWED_ACE.SidStart.offset
            sid_str = ctypes.c_wchar_p()
            if not advapi32.ConvertSidToStringSidW(ctypes.c_void_p(sid_addr), ctypes.byref(sid_str)):
                raise StorageError("ConvertSidToStringSidW failed on a private root ACE.")
            try:
                aces.append((sid_str.value, int(ace.Mask), int(ace_type)))
            finally:
                kernel32.LocalFree(sid_str)
        return aces, dacl_protected
    finally:
        kernel32.LocalFree(p_sd)


class PrivateDocStore:
    """A contained, private blob store keyed by server-generated paths."""

    def __init__(self, root: Path, *, read_only: bool = False) -> None:
        """Open the private store.

        ``read_only=True`` is the OCR worker's access mode (P0-02): it NEVER
        creates, chmods or writes anything. The backend account owns the root and
        applies permissions; a separate read-only OCR account is not the owner and
        must not attempt ``mkdir``/``chmod`` (which would fail or, worse, succeed
        on a mis-owned root). The reader only verifies containment + policy and
        reads verified bytes.
        """
        root = Path(root)
        if not root.is_absolute():
            raise StorageError("Private document root must be an absolute path.")
        self._read_only = read_only
        if _is_reparse_or_symlink(root):
            raise StorageError("Private document root must not be a symlink/reparse point.")
        # Containment must hold for EVERY ancestor, not just the root: a junction
        # planted at any parent could redirect the whole store. This check is done
        # on the lexical path BEFORE resolve() collapses any reparse point (P0-02).
        self._verify_no_reparse_ancestors(root)
        if read_only:
            if not root.is_dir():
                raise StorageError("Private document root does not exist for read-only access.")
        else:
            root.mkdir(parents=True, exist_ok=True)
        self._root = root.resolve()
        if _is_reparse_or_symlink(self._root):
            raise StorageError("Private document root resolves through a reparse point.")
        # Re-verify ancestors on the resolved form as defence in depth.
        self._verify_no_reparse_ancestors(self._root)
        if not read_only:
            self._apply_dir_mode(self._root)
        self.verify_access_policy()

    @property
    def root(self) -> Path:
        return self._root

    @property
    def read_only(self) -> bool:
        return self._read_only

    def _require_writable(self) -> None:
        if self._read_only:
            raise StorageError("Private document store is opened read-only (OCR worker).")

    @staticmethod
    def _verify_no_reparse_ancestors(root: Path) -> None:
        """Refuse a root reached through ANY symlink/reparse ancestor (P0-02).

        Walking the lexical ancestors (rather than trusting ``resolve()``) means a
        junction/symlink at a parent is detected even though ``resolve()`` would
        silently collapse it and make a later containment check vacuous.
        """
        for ancestor in (root, *root.parents):
            if _is_reparse_or_symlink(ancestor):
                raise StorageError(
                    "Private document root has a symlink/reparse ancestor; refusing."
                )

    def _apply_dir_mode(self, directory: Path) -> None:
        if not _IS_WINDOWS:
            try:
                os.chmod(directory, _DIR_MODE)
            except OSError as error:
                raise StorageError("Cannot apply private directory permissions.") from error
        # Windows: the DACL is an explicit operator procedure (runbook) and is
        # verified at startup by verify_access_policy(); no permissive fallback.

    def _apply_file_mode(self, path: Path) -> None:
        if not _IS_WINDOWS:
            try:
                os.chmod(path, _FILE_MODE)
            except OSError as error:
                raise StorageError("Cannot apply private file permissions.") from error

    def verify_access_policy(self) -> None:
        """Fail closed if the private root grants world or group-write access.

        POSIX: the root must be ``0750``-style (no world bits, no group write).
        Windows: ``icacls`` must not grant ``Everyone`` / ``BUILTIN\\Users`` /
        ``Authenticated Users`` write or full control. If the ACL cannot be
        inspected the check fails closed (the operator must run the runbook).
        """
        if _IS_WINDOWS:
            self._verify_windows_acl()
            return
        st = os.stat(self._root)
        mode = stat.S_IMODE(st.st_mode)
        if mode & 0o007:
            raise StorageError("Private document root grants world access; refusing to start.")
        if mode & 0o020:
            raise StorageError("Private document root grants group write; refusing to start.")

    def _verify_windows_acl(self) -> None:
        """Verify the private root DACL by SID (locale-independent, P0-02).

        Reads the security descriptor via the Windows API, enumerates every ACE's
        SID and access mask, and applies :func:`_acl_violation`. This checks both
        unintended READ and write by broad principals and requires a protected
        (non-inheriting) DACL. Any inability to inspect the DACL fails closed.
        """
        try:
            aces, dacl_protected = _read_windows_dacl(self._root)
        except StorageError:
            raise
        except Exception as error:  # noqa: BLE001 - fail closed on any API failure
            raise StorageError("Cannot inspect private root DACL via the Windows API.") from error
        violation = _acl_violation(aces, dacl_protected=dacl_protected)
        if violation is not None:
            raise StorageError(violation)

    def _resolve(self, storage_key: str) -> Path:
        # Accept a final key or its staging form (worker validates staged bytes).
        if not (_KEY.match(storage_key) or _STAGING_KEY.match(storage_key)):
            raise StorageError("Malformed storage key.")
        patient_id, filename = storage_key.split("/")
        directory = self._root / patient_id
        target = directory / filename
        # Reject any symlink/reparse component on the path from the root down.
        for component in (directory, target):
            if _is_reparse_or_symlink(component):
                raise StorageError("Storage path must not contain a symlink/reparse point.")
        resolved = target.resolve()
        if self._root not in resolved.parents:
            raise StorageError("Storage path escapes the private root.")
        return target

    def exists(self, storage_key: str) -> bool:
        try:
            target = self._resolve(storage_key)
        except StorageError:
            return False
        return target.is_file() and not _is_reparse_or_symlink(target)

    def stage(self, data: bytes, storage_key: str) -> str:
        """Write bytes to a temporary staging file beside the final path.

        Returns the staging key (``<final>.tmp-<random>``). The caller promotes
        it atomically only after successful validation and authorization.
        """
        self._require_writable()
        if len(data) > C.FILE_CAP_BYTES:
            raise StorageError("Staged bytes exceed the file cap.")
        target = self._resolve(storage_key)
        target.parent.mkdir(parents=True, exist_ok=True)
        self._apply_dir_mode(target.parent)
        staging_name = f"{target.name}.tmp-{secrets.token_hex(8)}"
        staging_path = target.parent / staging_name
        if _IS_WINDOWS:
            fd = _win_open_no_reparse(staging_path, write=True, create_new=True)
        else:
            fd = os.open(
                staging_path,
                os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC,
                _FILE_MODE,
            )
        try:
            with os.fdopen(fd, "wb") as handle:
                handle.write(data)
                handle.flush()
                os.fsync(handle.fileno())
            self._apply_file_mode(staging_path)
        except BaseException:
            staging_path.unlink(missing_ok=True)
            raise
        return f"{storage_key}.tmp-{staging_name.split('.tmp-')[1]}"

    def promote(self, staging_key: str, storage_key: str) -> None:
        """Atomically publish a validated staging blob to its final key."""
        self._require_writable()
        final = self._resolve(storage_key)
        staging = final.parent / Path(staging_key).name
        if _is_reparse_or_symlink(staging) or not staging.is_file():
            raise StorageError("Staging blob is missing or unsafe.")
        if _is_reparse_or_symlink(final):
            raise StorageError("Final storage path is a reparse point; refusing to publish.")
        os.replace(staging, final)
        self._apply_file_mode(final)

    def discard_staging(self, staging_key: str) -> None:
        self._require_writable()
        try:
            final = self._resolve(storage_key_from_staging(staging_key))
            staging = final.parent / Path(staging_key).name
            if _is_reparse_or_symlink(staging):
                return
            staging.unlink(missing_ok=True)
        except StorageError:
            return

    def _open_read_posix(self, storage_key: str) -> int:
        """Open a blob for reading WITHOUT following any symlink (P0-02).

        Each path component is opened relative to a held directory descriptor
        with ``O_NOFOLLOW`` (``dir_fd``), so an intermediate symlink/junction
        swapped in after the lexical check cannot redirect the open: there is no
        check/open race on any ancestor. The root itself is opened ``O_NOFOLLOW``
        too, so a reparse root is refused at the syscall, not just by lstat.
        """
        if not (_KEY.match(storage_key) or _STAGING_KEY.match(storage_key)):
            raise StorageError("Malformed storage key.")
        patient_id, filename = storage_key.split("/")
        flags = os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW
        root_fd = os.open(self._root, flags | os.O_DIRECTORY)
        try:
            dir_fd = os.open(patient_id, flags | os.O_DIRECTORY, dir_fd=root_fd)
        finally:
            os.close(root_fd)
        try:
            file_fd = os.open(filename, flags, dir_fd=dir_fd)
        finally:
            os.close(dir_fd)
        return file_fd

    def read_verified(self, storage_key: str, *, expected_sha256: str,
                      expected_size: int) -> bytes:
        """Read the complete bounded buffer and verify it before publication.

        Raises :class:`IntegrityError` on any length/digest mismatch so the
        caller can return ``409 document_integrity_mismatch`` with zero bytes
        sent. The file is opened without following symlinks/reparse points and
        confirmed a regular file.
        """
        if not (0 <= expected_size <= C.FILE_CAP_BYTES):
            raise IntegrityError("Recorded size is out of bounds.")
        try:
            if _IS_WINDOWS:
                target = self._resolve(storage_key)
                fd = _win_open_no_reparse(target, write=False, create_new=False)
            else:
                fd = self._open_read_posix(storage_key)
        except (OSError, StorageError) as error:
            raise IntegrityError("Stored document is unavailable.") from error
        try:
            info = os.fstat(fd)
            if not stat.S_ISREG(info.st_mode):
                raise IntegrityError("Stored document is not a regular file.")
            if info.st_size != expected_size:
                raise IntegrityError("Stored document length mismatch.")
            with os.fdopen(fd, "rb", closefd=False) as handle:
                buf = handle.read(C.FILE_CAP_BYTES + 1)
        finally:
            os.close(fd)
        if len(buf) != expected_size:
            raise IntegrityError("Stored document length mismatch.")
        if hashlib.sha256(buf).hexdigest() != expected_sha256:
            raise IntegrityError("Stored document digest mismatch.")
        return buf

    def remove(self, storage_key: str) -> None:
        self._require_writable()
        try:
            target = self._resolve(storage_key)
        except StorageError:
            return
        if target.is_file() and not _is_reparse_or_symlink(target):
            target.unlink(missing_ok=True)

    def iter_files(self):
        """Yield ``(storage_key, path)`` for every regular blob (orphan scan)."""
        for patient_dir in sorted(self._root.iterdir()):
            if not patient_dir.is_dir() or _is_reparse_or_symlink(patient_dir):
                continue
            if not _UUID.match(patient_dir.name):
                continue
            for entry in sorted(patient_dir.iterdir()):
                if _is_reparse_or_symlink(entry) or not entry.is_file():
                    continue
                yield f"{patient_dir.name}/{entry.name}", entry


def storage_key_from_staging(staging_key: str) -> str:
    """Recover the final storage key from a staging key."""
    marker = ".bin.tmp-"
    index = staging_key.find(marker)
    if index < 0:
        raise StorageError("Not a staging key.")
    return staging_key[: index + len(".bin")]
