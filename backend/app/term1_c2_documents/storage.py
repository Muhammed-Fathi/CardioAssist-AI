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


class PrivateDocStore:
    """A contained, private blob store keyed by server-generated paths."""

    def __init__(self, root: Path) -> None:
        root = Path(root)
        if not root.is_absolute():
            raise StorageError("Private document root must be an absolute path.")
        if _is_reparse_or_symlink(root):
            raise StorageError("Private document root must not be a symlink/reparse point.")
        root.mkdir(parents=True, exist_ok=True)
        self._root = root.resolve()
        # Refuse a root whose resolved form escapes via a reparse ancestor.
        if _is_reparse_or_symlink(self._root):
            raise StorageError("Private document root resolves through a reparse point.")
        self._apply_dir_mode(self._root)
        self.verify_access_policy()

    @property
    def root(self) -> Path:
        return self._root

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
        import subprocess

        try:
            result = subprocess.run(
                ["icacls", str(self._root)], capture_output=True, text=True, timeout=15
            )
        except (OSError, subprocess.SubprocessError) as error:
            raise StorageError("Cannot inspect private root DACL (icacls unavailable).") from error
        if result.returncode != 0:
            raise StorageError("icacls failed to inspect the private root DACL.")
        forbidden_principals = ("everyone", "builtin\\users", "authenticated users", "users:")
        for line in result.stdout.lower().splitlines():
            if any(p in line for p in forbidden_principals):
                # (F) full, (M) modify, (W) write, (WD/WE) write-data/append.
                if any(perm in line for perm in ("(f)", "(m)", "(w)", "(wd)", "(we)", "(dc)")):
                    raise StorageError(
                        "Private root DACL grants a broad principal write/full access."
                    )

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
        final = self._resolve(storage_key)
        staging = final.parent / Path(staging_key).name
        if _is_reparse_or_symlink(staging) or not staging.is_file():
            raise StorageError("Staging blob is missing or unsafe.")
        if _is_reparse_or_symlink(final):
            raise StorageError("Final storage path is a reparse point; refusing to publish.")
        os.replace(staging, final)
        self._apply_file_mode(final)

    def discard_staging(self, staging_key: str) -> None:
        try:
            final = self._resolve(storage_key_from_staging(staging_key))
            staging = final.parent / Path(staging_key).name
            if _is_reparse_or_symlink(staging):
                return
            staging.unlink(missing_ok=True)
        except StorageError:
            return

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
            target = self._resolve(storage_key)
            if _IS_WINDOWS:
                fd = _win_open_no_reparse(target, write=False, create_new=False)
            else:
                fd = os.open(target, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC)
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
