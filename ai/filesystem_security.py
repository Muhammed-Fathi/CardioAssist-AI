"""Cross-platform filesystem security, path containment, reparse-point detection,
and private-file / directory access-control enforcement & verification.

Platform security model:
1. **POSIX (Linux / macOS):**
   - Verifies absence of symlinks, verifies ``st_uid == os.getuid()``, enforces
     and checks ``0600`` (``(st_mode & 0o077) == 0``) for user-private files
     (signing keys, sensitive model/SHAP artifacts, evaluation ledgers), ``0700``
     for private bundle/key directories, and non-group/world-writable
     (``(st_mode & 0o022) == 0``) for ``trusted_local_root``.
2. **Windows (Python 3.12+, NTFS):**
   - Never treats ``os.chmod(0o600)`` or CRT-synthesized ``stat.st_mode`` bits as
     evidence of ACL isolation, and never calls ``os.fchmod`` (unavailable on
     Windows).
   - Rejects symlinks, NTFS junctions (``Path.is_junction()``), and Windows
     reparse points (``FILE_ATTRIBUTE_REPARSE_POINT``), as well as reserved DOS
     device filenames (``CON``, ``NUL``, ``COM1``, etc.).
   - Uses case-normalized path containment (``os.path.normcase``) across drive
     roots (e.g., ``E:\\CardioAssist_AI_GitHub_Starter`` vs ``%LOCALAPPDATA%``).
   - Enforces protected user-private NTFS DACLs (``D:PAI(...)`` blocking parent
     inheritance and granting ``FILE_ALL_ACCESS`` solely to the current process
     user SID, ``NT AUTHORITY\\SYSTEM``, and ``BUILTIN\\Administrators``) via the
     Win32 Security API (``advapi32.dll`` / ``kernel32.dll``).
   - Verifies isolation fail-closed by confirming ``FILE_PERSISTENT_ACLS`` on the
     hosting volume and inspecting the binary Security Descriptor owner SID and
     every ACE in the binary DACL via ``GetNamedSecurityInfoW``.
"""
from __future__ import annotations

import ctypes
from dataclasses import dataclass
import os
from pathlib import Path
import re
import stat
import struct
from typing import Any, Final, Sequence

SAFE_ARTIFACT_BASENAME_RE: Final[re.Pattern[str]] = re.compile(
    r"^[a-z0-9][a-z0-9._-]{1,63}$"
)
WINDOWS_RESERVED_DEVICE_RE: Final[re.Pattern[str]] = re.compile(
    r"^(con|prn|aux|nul|com[1-9]|lpt[1-9])(\..*)?$",
    re.IGNORECASE,
)

# MS-DTYP / winnt.h constants
FILE_PERSISTENT_ACLS: Final[int] = 0x00000008
SE_FILE_OBJECT: Final[int] = 1
OWNER_SECURITY_INFORMATION: Final[int] = 0x00000001
DACL_SECURITY_INFORMATION: Final[int] = 0x00000004
PROTECTED_DACL_SECURITY_INFORMATION: Final[int] = 0x80000000
SE_DACL_PRESENT: Final[int] = 0x0004
SE_DACL_PROTECTED: Final[int] = 0x1000
SDDL_REVISION_1: Final[int] = 1
TOKEN_QUERY: Final[int] = 0x0008
TOKEN_USER_CLASS: Final[int] = 1

ACCESS_ALLOWED_ACE_TYPE: Final[int] = 0x00
ACCESS_DENIED_ACE_TYPE: Final[int] = 0x01
INHERIT_ONLY_ACE_FLAG: Final[int] = 0x08

SID_LOCAL_SYSTEM: Final[str] = "S-1-5-18"
SID_BUILTIN_ADMINS: Final[str] = "S-1-5-32-544"
SID_CREATOR_OWNER: Final[str] = "S-1-3-0"
SID_BUILTIN_USERS: Final[str] = "S-1-5-32-545"

# File/directory access mask bits (winnt.h)
FILE_READ_DATA: Final[int] = 0x00000001
FILE_WRITE_DATA: Final[int] = 0x00000002
FILE_APPEND_DATA: Final[int] = 0x00000004
FILE_WRITE_EA: Final[int] = 0x00000010
FILE_DELETE_CHILD: Final[int] = 0x00000040
FILE_WRITE_ATTRIBUTES: Final[int] = 0x00000100
DELETE_ACCESS: Final[int] = 0x00010000
WRITE_DAC_ACCESS: Final[int] = 0x00040000
WRITE_OWNER_ACCESS: Final[int] = 0x00080000
GENERIC_ALL_ACCESS: Final[int] = 0x10000000
GENERIC_WRITE_ACCESS: Final[int] = 0x40000000
GENERIC_READ_ACCESS: Final[int] = 0x80000000

WINDOWS_WRITE_LIKE_MASK: Final[int] = (
    FILE_WRITE_DATA
    | FILE_APPEND_DATA
    | FILE_WRITE_EA
    | FILE_DELETE_CHILD
    | FILE_WRITE_ATTRIBUTES
    | DELETE_ACCESS
    | WRITE_DAC_ACCESS
    | WRITE_OWNER_ACCESS
    | GENERIC_WRITE_ACCESS
    | GENERIC_ALL_ACCESS
)
WINDOWS_READ_REQUIRED_BITS: Final[int] = FILE_READ_DATA | GENERIC_READ_ACCESS | GENERIC_ALL_ACCESS
WINDOWS_WRITE_REQUIRED_BITS: Final[int] = (
    FILE_WRITE_DATA | GENERIC_WRITE_ACCESS | GENERIC_ALL_ACCESS
)


@dataclass(frozen=True, slots=True)
class AccessControlVerificationResult:
    """Outcome of cross-platform ownership and permission / NTFS DACL verification."""

    ok: bool
    reason_category: str | None = None  # "owner" | "permissions" | None
    detail: str = ""


@dataclass(frozen=True, slots=True)
class ParsedWindowsAce:
    """Decoded MS-DTYP ACE header, access mask, and string SID."""

    ace_type: int
    ace_flags: int
    access_mask: int
    sid: str


def is_windows_runtime() -> bool:
    """Return True when running on native Windows (``os.name == 'nt'``)."""
    return os.name == "nt"


def is_valid_artifact_basename(filename: str) -> bool:
    """Validate safe single-component filename across POSIX and Windows NTFS."""
    if not filename or filename.endswith((".", " ")):
        return False
    if not SAFE_ARTIFACT_BASENAME_RE.match(filename):
        return False
    if WINDOWS_RESERVED_DEVICE_RE.match(filename):
        return False
    return True


def is_reparse_or_symlink(path: Path) -> bool:
    """Detect POSIX symlinks, Windows symlinks, NTFS junctions, and reparse points."""
    try:
        if path.is_symlink():
            return True
        is_junction_fn = getattr(path, "is_junction", None)
        if callable(is_junction_fn) and bool(is_junction_fn()):
            return True
        st = path.lstat()
    except FileNotFoundError:
        return False
    except OSError:
        return True

    if stat.S_ISLNK(st.st_mode):
        return True
    file_attrs = int(getattr(st, "st_file_attributes", 0))
    reparse_flag = int(getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x0400))
    return (file_attrs & reparse_flag) != 0


def _strip_extended_win_prefix(raw_path: str) -> str:
    if raw_path.startswith("\\\\?\\UNC\\"):
        return "\\\\" + raw_path[8:]
    if raw_path.startswith("\\\\?\\"):
        return raw_path[4:]
    return raw_path


def normalize_platform_path_str(path: Path) -> str:
    """Return case-normalized, separator-normalized path string for containment checks."""
    cleaned = _strip_extended_win_prefix(str(path))
    return os.path.normcase(os.path.normpath(cleaned))


def paths_equal_platform(a: Path, b: Path) -> bool:
    """Compare two resolved paths respecting platform case-sensitivity semantics."""
    return normalize_platform_path_str(a) == normalize_platform_path_str(b)


def is_strictly_within_directory(child: Path, parent: Path) -> bool:
    """Return True iff ``child`` is strictly inside ``parent`` (cross-drive & case safe)."""
    norm_child = normalize_platform_path_str(child)
    norm_parent = normalize_platform_path_str(parent)
    if norm_child == norm_parent:
        return False
    try:
        common = os.path.commonpath([norm_child, norm_parent])
    except ValueError:
        # Different Windows drive letters or UNC shares
        return False
    return common == norm_parent


def has_reparse_between(child: Path, ancestor: Path) -> bool:
    """Check ``ancestor`` through ``child`` inclusive for any symlink/junction/reparse."""
    if is_reparse_or_symlink(ancestor) or is_reparse_or_symlink(child):
        return True
    norm_ancestor = normalize_platform_path_str(ancestor)
    curr = child
    for _ in range(128):
        if is_reparse_or_symlink(curr):
            return True
        norm_curr = normalize_platform_path_str(curr)
        if norm_curr == norm_ancestor:
            return False
        if curr.parent == curr:
            break
        curr = curr.parent
    return False


def relative_posix_if_within_directory(target: Path, root: Path) -> str | None:
    """Return forward-slash relative path if ``target`` lies strictly inside ``root``."""
    resolved_root = root.resolve()
    resolved_target = target.parent.resolve() / target.name
    if not is_strictly_within_directory(resolved_target, resolved_root):
        return None
    norm_target = _strip_extended_win_prefix(os.path.normpath(str(resolved_target)))
    norm_root = _strip_extended_win_prefix(os.path.normpath(str(resolved_root)))
    try:
        rel_str = os.path.relpath(norm_target, norm_root)
    except ValueError:
        return None
    if rel_str in (".", "..") or rel_str.startswith(".." + os.sep):
        return None
    return rel_str.replace("\\", "/")


# --------------------------------------------------------------------------- #
# Pure-Python MS-DTYP binary SID & ACL parser + DACL security policy evaluator
# --------------------------------------------------------------------------- #


def parse_windows_binary_sid(raw_sid: bytes) -> str:
    """Decode an MS-DTYP binary SID buffer into canonical ``S-R-I-S...`` string form."""
    if len(raw_sid) < 8:
        raise ValueError("Truncated binary SID (< 8 bytes).")
    revision = raw_sid[0]
    sub_count = raw_sid[1]
    if revision != 1 or sub_count > 15:
        raise ValueError(f"Unsupported binary SID header (rev={revision}, count={sub_count}).")
    expected_len = 8 + 4 * sub_count
    if len(raw_sid) < expected_len:
        raise ValueError(
            f"Truncated binary SID sub-authorities (have {len(raw_sid)}, need {expected_len})."
        )
    ident_authority = int.from_bytes(raw_sid[2:8], byteorder="big", signed=False)
    subs = struct.unpack_from(f"<{sub_count}I", raw_sid, 8)
    if not subs:
        return f"S-{revision}-{ident_authority}"
    return f"S-{revision}-{ident_authority}-" + "-".join(str(s) for s in subs)


def build_windows_binary_sid(sid_str: str) -> bytes:
    """Encode a canonical ``S-1-<auth>-<sub...>`` string into MS-DTYP binary SID bytes."""
    parts = sid_str.strip().split("-")
    if len(parts) < 3 or parts[0].upper() != "S":
        raise ValueError(f"Invalid SID string '{sid_str}'.")
    revision = int(parts[1])
    authority = int(parts[2])
    subs = [int(x) for x in parts[3:]]
    if revision != 1 or len(subs) > 15 or authority < 0 or authority >= (1 << 48):
        raise ValueError(f"Out-of-range SID components in '{sid_str}'.")
    header = bytes([revision, len(subs)]) + authority.to_bytes(6, byteorder="big")
    body = struct.pack(f"<{len(subs)}I", *subs) if subs else b""
    return header + body


def parse_windows_acl_bytes(raw_acl: bytes) -> tuple[ParsedWindowsAce, ...]:
    """Decode a raw Win32 ``ACL`` byte buffer into ordered :class:`ParsedWindowsAce` items."""
    if len(raw_acl) < 8:
        raise ValueError("Truncated Win32 ACL header (< 8 bytes).")
    acl_rev, _sbz1, acl_size, ace_count, _sbz2 = struct.unpack_from("<BBHHH", raw_acl, 0)
    if acl_rev not in (2, 4) or acl_size < 8 or acl_size > len(raw_acl):
        raise ValueError(
            f"Invalid Win32 ACL header (rev={acl_rev}, size={acl_size}, buf={len(raw_acl)})."
        )

    offset = 8
    aces: list[ParsedWindowsAce] = []
    for _ in range(ace_count):
        if offset + 4 > acl_size:
            raise ValueError("Truncated ACE header inside Win32 ACL.")
        ace_type, ace_flags, ace_size = struct.unpack_from("<BBH", raw_acl, offset)
        if ace_size < 8 or offset + ace_size > acl_size:
            raise ValueError(f"Invalid ACE size {ace_size} at offset {offset}.")
        if ace_type in (ACCESS_ALLOWED_ACE_TYPE, ACCESS_DENIED_ACE_TYPE):
            (mask,) = struct.unpack_from("<I", raw_acl, offset + 4)
            sid_str = parse_windows_binary_sid(raw_acl[offset + 8 : offset + ace_size])
            aces.append(
                ParsedWindowsAce(
                    ace_type=ace_type,
                    ace_flags=ace_flags,
                    access_mask=mask,
                    sid=sid_str,
                )
            )
        else:
            # Unknown / conditional callback / object ACE types cannot be safely
            # proven non-permissive without full condition evaluation -> record raw type.
            aces.append(
                ParsedWindowsAce(
                    ace_type=ace_type,
                    ace_flags=ace_flags,
                    access_mask=GENERIC_ALL_ACCESS,
                    sid="<UNSUPPORTED_ACE_TYPE>",
                )
            )
        offset += ace_size

    return tuple(aces)


def build_windows_acl_bytes(aces: Sequence[ParsedWindowsAce]) -> bytes:
    """Construct a byte-accurate MS-DTYP binary ``ACL`` buffer (used for tests)."""
    encoded_aces = bytearray()
    for ace in aces:
        if ace.ace_type not in (ACCESS_ALLOWED_ACE_TYPE, ACCESS_DENIED_ACE_TYPE):
            raise ValueError(f"Unsupported ACE type for builder: {ace.ace_type}")
        sid_bytes = build_windows_binary_sid(ace.sid)
        ace_size = 8 + len(sid_bytes)
        encoded_aces.extend(
            struct.pack("<BBHI", ace.ace_type, ace.ace_flags, ace_size, ace.access_mask)
        )
        encoded_aces.extend(sid_bytes)
    acl_size = 8 + len(encoded_aces)
    header = struct.pack("<BBHHH", 2, 0, acl_size, len(aces), 0)
    return header + bytes(encoded_aces)


def evaluate_windows_dacl_policy(
    *,
    owner_sid: str,
    current_user_sid: str,
    caller_is_admin: bool,
    persistent_acls_supported: bool,
    dacl_present: bool,
    dacl_is_null: bool,
    aces: Sequence[ParsedWindowsAce],
    strict_private: bool,
) -> AccessControlVerificationResult:
    """Evaluate NTFS Security Descriptor ownership and DACL isolation fail-closed.

    - ``strict_private=True`` (signing keys, bundle directory & files, evaluation
      ledger): ONLY ``current_user_sid``, ``NT AUTHORITY\\SYSTEM``, and
      ``BUILTIN\\Administrators`` (plus ``CREATOR OWNER`` when ``INHERIT_ONLY``)
      may hold ANY positive access mask in an Allow ACE.
    - ``strict_private=False`` (``trusted_local_root`` container directory):
      enforces Windows equivalent of POSIX ``(st_mode & 0o022) == 0`` — no
      principal outside ``{current_user_sid, SYSTEM, Administrators}`` may hold
      write/append/create/delete/DAC/owner permissions.
    """
    if not persistent_acls_supported:
        return AccessControlVerificationResult(
            ok=False,
            reason_category="permissions",
            detail="Filesystem volume does not enforce persistent NTFS ACLs.",
        )

    trusted_owner_sids = {current_user_sid, SID_LOCAL_SYSTEM, SID_BUILTIN_ADMINS}
    if owner_sid not in trusted_owner_sids:
        return AccessControlVerificationResult(
            ok=False,
            reason_category="owner",
            detail=f"Untrusted Windows owner SID '{owner_sid}' (expected '{current_user_sid}').",
        )

    if not dacl_present or dacl_is_null:
        return AccessControlVerificationResult(
            ok=False,
            reason_category="permissions",
            detail="Security descriptor has missing or NULL DACL (grants unrestricted access).",
        )

    allowed_private_sids = {current_user_sid, SID_LOCAL_SYSTEM, SID_BUILTIN_ADMINS}
    caller_effective_sids = {current_user_sid}
    if caller_is_admin:
        caller_effective_sids.add(SID_BUILTIN_ADMINS)

    caller_granted_read = False
    caller_denied_read = False

    for ace in aces:
        if ace.ace_type not in (ACCESS_ALLOWED_ACE_TYPE, ACCESS_DENIED_ACE_TYPE):
            return AccessControlVerificationResult(
                ok=False,
                reason_category="permissions",
                detail=f"Unsupported Win32 ACE type 0x{ace.ace_type:02x} rejected fail-closed.",
            )
        if ace.access_mask == 0:
            continue

        is_inherit_only = (ace.ace_flags & INHERIT_ONLY_ACE_FLAG) != 0

        if ace.ace_type == ACCESS_DENIED_ACE_TYPE:
            if not is_inherit_only and ace.sid in caller_effective_sids:
                if (ace.access_mask & WINDOWS_READ_REQUIRED_BITS) != 0:
                    caller_denied_read = True
            continue

        # ACCESS_ALLOWED_ACE_TYPE
        if ace.sid == SID_CREATOR_OWNER and is_inherit_only:
            continue

        if strict_private:
            if ace.sid not in allowed_private_sids:
                return AccessControlVerificationResult(
                    ok=False,
                    reason_category="permissions",
                    detail=(
                        f"Unauthorized principal '{ace.sid}' holds NTFS access mask "
                        f"0x{ace.access_mask:08x} on private resource."
                    ),
                )
        else:
            if (
                ace.sid not in allowed_private_sids
                and (ace.access_mask & WINDOWS_WRITE_LIKE_MASK) != 0
            ):
                return AccessControlVerificationResult(
                    ok=False,
                    reason_category="permissions",
                    detail=(
                        f"Unauthorized principal '{ace.sid}' holds write-like NTFS mask "
                        f"0x{ace.access_mask:08x} on trusted root directory."
                    ),
                )

        if (
            not is_inherit_only
            and not caller_denied_read
            and ace.sid in caller_effective_sids
            and (ace.access_mask & WINDOWS_READ_REQUIRED_BITS) != 0
        ):
            caller_granted_read = True

    if not caller_granted_read:
        return AccessControlVerificationResult(
            ok=False,
            reason_category="permissions",
            detail="Current Windows user lacks verified effective read access in DACL.",
        )

    return AccessControlVerificationResult(ok=True)


# --------------------------------------------------------------------------- #
# Win32 ctypes bindings (loaded lazily only when os.name == "nt")
# --------------------------------------------------------------------------- #

_WIN32_API_CACHE: dict[str, Any] | None = None


def _get_win32_api() -> dict[str, Any]:
    global _WIN32_API_CACHE
    if _WIN32_API_CACHE is not None:
        return _WIN32_API_CACHE

    from ctypes import wintypes

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    advapi32 = ctypes.WinDLL("advapi32", use_last_error=True)

    kernel32.GetCurrentProcess.argtypes = []
    kernel32.GetCurrentProcess.restype = wintypes.HANDLE

    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel32.CloseHandle.restype = wintypes.BOOL

    kernel32.LocalFree.argtypes = [wintypes.HLOCAL]
    kernel32.LocalFree.restype = wintypes.HLOCAL

    kernel32.GetVolumePathNameW.argtypes = [
        wintypes.LPCWSTR,
        wintypes.LPWSTR,
        wintypes.DWORD,
    ]
    kernel32.GetVolumePathNameW.restype = wintypes.BOOL

    kernel32.GetVolumeInformationW.argtypes = [
        wintypes.LPCWSTR,
        wintypes.LPWSTR,
        wintypes.DWORD,
        ctypes.POINTER(wintypes.DWORD),
        ctypes.POINTER(wintypes.DWORD),
        ctypes.POINTER(wintypes.DWORD),
        wintypes.LPWSTR,
        wintypes.DWORD,
    ]
    kernel32.GetVolumeInformationW.restype = wintypes.BOOL

    advapi32.OpenProcessToken.argtypes = [
        wintypes.HANDLE,
        wintypes.DWORD,
        ctypes.POINTER(wintypes.HANDLE),
    ]
    advapi32.OpenProcessToken.restype = wintypes.BOOL

    advapi32.GetTokenInformation.argtypes = [
        wintypes.HANDLE,
        ctypes.c_int,
        ctypes.c_void_p,
        wintypes.DWORD,
        ctypes.POINTER(wintypes.DWORD),
    ]
    advapi32.GetTokenInformation.restype = wintypes.BOOL

    advapi32.IsValidSid.argtypes = [ctypes.c_void_p]
    advapi32.IsValidSid.restype = wintypes.BOOL

    advapi32.GetLengthSid.argtypes = [ctypes.c_void_p]
    advapi32.GetLengthSid.restype = wintypes.DWORD

    advapi32.CheckTokenMembership.argtypes = [
        wintypes.HANDLE,
        ctypes.c_void_p,
        ctypes.POINTER(wintypes.BOOL),
    ]
    advapi32.CheckTokenMembership.restype = wintypes.BOOL

    advapi32.ConvertStringSidToSidW.argtypes = [
        wintypes.LPCWSTR,
        ctypes.POINTER(ctypes.c_void_p),
    ]
    advapi32.ConvertStringSidToSidW.restype = wintypes.BOOL

    advapi32.ConvertStringSecurityDescriptorToSecurityDescriptorW.argtypes = [
        wintypes.LPCWSTR,
        wintypes.DWORD,
        ctypes.POINTER(ctypes.c_void_p),
        ctypes.POINTER(wintypes.ULONG),
    ]
    advapi32.ConvertStringSecurityDescriptorToSecurityDescriptorW.restype = wintypes.BOOL

    advapi32.GetSecurityDescriptorDacl.argtypes = [
        ctypes.c_void_p,
        ctypes.POINTER(wintypes.BOOL),
        ctypes.POINTER(ctypes.c_void_p),
        ctypes.POINTER(wintypes.BOOL),
    ]
    advapi32.GetSecurityDescriptorDacl.restype = wintypes.BOOL

    advapi32.GetSecurityDescriptorControl.argtypes = [
        ctypes.c_void_p,
        ctypes.POINTER(wintypes.WORD),
        ctypes.POINTER(wintypes.DWORD),
    ]
    advapi32.GetSecurityDescriptorControl.restype = wintypes.BOOL

    advapi32.SetNamedSecurityInfoW.argtypes = [
        wintypes.LPWSTR,
        ctypes.c_int,
        wintypes.DWORD,
        ctypes.c_void_p,
        ctypes.c_void_p,
        ctypes.c_void_p,
        ctypes.c_void_p,
    ]
    advapi32.SetNamedSecurityInfoW.restype = wintypes.DWORD

    advapi32.GetNamedSecurityInfoW.argtypes = [
        wintypes.LPCWSTR,
        ctypes.c_int,
        wintypes.DWORD,
        ctypes.POINTER(ctypes.c_void_p),
        ctypes.POINTER(ctypes.c_void_p),
        ctypes.POINTER(ctypes.c_void_p),
        ctypes.POINTER(ctypes.c_void_p),
        ctypes.POINTER(ctypes.c_void_p),
    ]
    advapi32.GetNamedSecurityInfoW.restype = wintypes.DWORD

    _WIN32_API_CACHE = {"kernel32": kernel32, "advapi32": advapi32}
    return _WIN32_API_CACHE


def _win32_sid_ptr_to_string(advapi32: Any, sid_ptr: int | None) -> str:
    if not sid_ptr or not advapi32.IsValidSid(ctypes.c_void_p(sid_ptr)):
        raise OSError("Invalid Win32 PSID pointer.")
    sid_len = int(advapi32.GetLengthSid(ctypes.c_void_p(sid_ptr)))
    if sid_len < 8 or sid_len > 128:
        raise OSError(f"Unexpected Win32 SID byte length: {sid_len}")
    return parse_windows_binary_sid(ctypes.string_at(sid_ptr, sid_len))


def _win32_current_user_sid_and_admin() -> tuple[str, bool]:
    from ctypes import wintypes

    api = _get_win32_api()
    kernel32 = api["kernel32"]
    advapi32 = api["advapi32"]

    token = wintypes.HANDLE()
    if not advapi32.OpenProcessToken(
        kernel32.GetCurrentProcess(), TOKEN_QUERY, ctypes.byref(token)
    ):
        err = ctypes.get_last_error()
        raise OSError(err, f"OpenProcessToken failed (winerr={err}).")

    try:
        needed = wintypes.DWORD(0)
        advapi32.GetTokenInformation(token, TOKEN_USER_CLASS, None, 0, ctypes.byref(needed))
        if needed.value == 0:
            err = ctypes.get_last_error()
            raise OSError(err, f"GetTokenInformation size query failed (winerr={err}).")
        buf = ctypes.create_string_buffer(needed.value)
        if not advapi32.GetTokenInformation(
            token, TOKEN_USER_CLASS, buf, needed.value, ctypes.byref(needed)
        ):
            err = ctypes.get_last_error()
            raise OSError(err, f"GetTokenInformation(TokenUser) failed (winerr={err}).")
        # TOKEN_USER starts with SID_AND_ATTRIBUTES.Sid pointer at offset 0
        user_sid_ptr = ctypes.c_void_p.from_buffer(buf).value
        user_sid = _win32_sid_ptr_to_string(advapi32, user_sid_ptr)
    finally:
        kernel32.CloseHandle(token)

    is_admin = False
    admin_sid_ptr = ctypes.c_void_p()
    if advapi32.ConvertStringSidToSidW(SID_BUILTIN_ADMINS, ctypes.byref(admin_sid_ptr)):
        try:
            member_flag = wintypes.BOOL(0)
            if advapi32.CheckTokenMembership(
                None, admin_sid_ptr, ctypes.byref(member_flag)
            ):
                is_admin = bool(member_flag.value)
        finally:
            kernel32.LocalFree(admin_sid_ptr)

    return user_sid, is_admin


def _win32_volume_supports_persistent_acls(path: Path) -> bool:
    from ctypes import wintypes

    api = _get_win32_api()
    kernel32 = api["kernel32"]
    abs_str = _strip_extended_win_prefix(os.path.abspath(path))
    vol_buf = ctypes.create_unicode_buffer(max(len(abs_str) + 16, 260))
    if not kernel32.GetVolumePathNameW(abs_str, vol_buf, len(vol_buf)):
        return False
    fs_flags = wintypes.DWORD(0)
    if not kernel32.GetVolumeInformationW(
        vol_buf.value,
        None,
        0,
        None,
        None,
        ctypes.byref(fs_flags),
        None,
        0,
    ):
        return False
    return (int(fs_flags.value) & FILE_PERSISTENT_ACLS) != 0


def _win32_apply_sddl_dacl(path: Path, sddl: str) -> None:
    from ctypes import wintypes

    api = _get_win32_api()
    kernel32 = api["kernel32"]
    advapi32 = api["advapi32"]

    sd_ptr = ctypes.c_void_p()
    sd_size = wintypes.ULONG(0)
    if not advapi32.ConvertStringSecurityDescriptorToSecurityDescriptorW(
        sddl,
        SDDL_REVISION_1,
        ctypes.byref(sd_ptr),
        ctypes.byref(sd_size),
    ):
        err = ctypes.get_last_error()
        raise OSError(err, f"SDDL conversion failed (winerr={err}).")

    try:
        dacl_present = wintypes.BOOL(0)
        dacl_ptr = ctypes.c_void_p()
        dacl_defaulted = wintypes.BOOL(0)
        if (
            not advapi32.GetSecurityDescriptorDacl(
                sd_ptr,
                ctypes.byref(dacl_present),
                ctypes.byref(dacl_ptr),
                ctypes.byref(dacl_defaulted),
            )
            or not dacl_present.value
            or not dacl_ptr.value
        ):
            raise OSError("Failed to extract non-null PACL from SDDL descriptor.")

        abs_str = _strip_extended_win_prefix(os.path.abspath(path))
        mutable_name = ctypes.create_unicode_buffer(abs_str)
        sec_info = DACL_SECURITY_INFORMATION | PROTECTED_DACL_SECURITY_INFORMATION
        rc = int(
            advapi32.SetNamedSecurityInfoW(
                mutable_name,
                SE_FILE_OBJECT,
                sec_info,
                None,
                None,
                dacl_ptr,
                None,
            )
        )
        if rc != 0:
            raise OSError(rc, f"SetNamedSecurityInfoW failed with error {rc}.")
    finally:
        if sd_ptr.value:
            kernel32.LocalFree(sd_ptr)


def _win32_set_private_dacl(path: Path, *, is_directory: bool) -> None:
    if not _win32_volume_supports_persistent_acls(path):
        raise OSError("Target Windows volume does not support persistent NTFS ACLs.")
    user_sid, _ = _win32_current_user_sid_and_admin()
    inherit = "OICI" if is_directory else ""
    sddl = (
        f"D:PAI"
        f"(A;{inherit};FA;;;{user_sid})"
        f"(A;{inherit};FA;;;SY)"
        f"(A;{inherit};FA;;;BA)"
    )
    _win32_apply_sddl_dacl(path, sddl)


def _win32_verify_path_dacl(
    path: Path, *, strict_private: bool
) -> AccessControlVerificationResult:
    from ctypes import wintypes

    try:
        persistent_acls = _win32_volume_supports_persistent_acls(path)
        if not persistent_acls:
            return AccessControlVerificationResult(
                ok=False,
                reason_category="permissions",
                detail="Hosting Windows volume does not support persistent NTFS ACLs.",
            )
        current_user_sid, caller_is_admin = _win32_current_user_sid_and_admin()

        api = _get_win32_api()
        kernel32 = api["kernel32"]
        advapi32 = api["advapi32"]

        owner_sid_ptr = ctypes.c_void_p()
        dacl_ptr = ctypes.c_void_p()
        sd_ptr = ctypes.c_void_p()
        abs_str = _strip_extended_win_prefix(os.path.abspath(path))
        rc = int(
            advapi32.GetNamedSecurityInfoW(
                abs_str,
                SE_FILE_OBJECT,
                OWNER_SECURITY_INFORMATION | DACL_SECURITY_INFORMATION,
                ctypes.byref(owner_sid_ptr),
                None,
                ctypes.byref(dacl_ptr),
                None,
                ctypes.byref(sd_ptr),
            )
        )
        if rc != 0:
            return AccessControlVerificationResult(
                ok=False,
                reason_category="permissions",
                detail=f"GetNamedSecurityInfoW failed with error {rc}.",
            )
        try:
            owner_sid = _win32_sid_ptr_to_string(advapi32, owner_sid_ptr.value)
            control = wintypes.WORD(0)
            revision = wintypes.DWORD(0)
            if not advapi32.GetSecurityDescriptorControl(
                sd_ptr, ctypes.byref(control), ctypes.byref(revision)
            ):
                return AccessControlVerificationResult(
                    ok=False,
                    reason_category="permissions",
                    detail="GetSecurityDescriptorControl failed.",
                )
            dacl_present = (int(control.value) & SE_DACL_PRESENT) != 0
            dacl_is_null = not bool(dacl_ptr.value)
            aces: tuple[ParsedWindowsAce, ...] = ()
            if dacl_present and not dacl_is_null:
                acl_hdr = ctypes.string_at(dacl_ptr.value, 8)
                _rev, _sbz1, acl_size, _ace_count, _sbz2 = struct.unpack_from(
                    "<BBHHH", acl_hdr, 0
                )
                if acl_size < 8:
                    return AccessControlVerificationResult(
                        ok=False,
                        reason_category="permissions",
                        detail="Invalid NTFS ACL header byte size.",
                    )
                raw_acl = ctypes.string_at(dacl_ptr.value, acl_size)
                aces = parse_windows_acl_bytes(raw_acl)
        finally:
            if sd_ptr.value:
                kernel32.LocalFree(sd_ptr)
    except Exception as exc:  # noqa: BLE001
        return AccessControlVerificationResult(
            ok=False,
            reason_category="permissions",
            detail=f"Windows NTFS ACL verification failed closed: {exc}",
        )

    return evaluate_windows_dacl_policy(
        owner_sid=owner_sid,
        current_user_sid=current_user_sid,
        caller_is_admin=caller_is_admin,
        persistent_acls_supported=True,
        dacl_present=dacl_present,
        dacl_is_null=dacl_is_null,
        aces=aces,
        strict_private=strict_private,
    )


# --------------------------------------------------------------------------- #
# Cross-platform public enforcement & verification operations
# --------------------------------------------------------------------------- #


def protect_private_file(path: Path) -> None:
    """Apply strict user-only permissions (POSIX ``0600`` / Windows NTFS ``D:PAI``)."""
    if is_reparse_or_symlink(path):
        raise OSError(f"Refusing to modify permissions on symlink/reparse path '{path}'.")
    if is_windows_runtime():
        _win32_set_private_dacl(path, is_directory=False)
    else:
        os.chmod(path, 0o600)


def protect_private_directory(path: Path) -> None:
    """Apply strict user-only directory permissions (POSIX ``0700`` / Windows NTFS ``D:PAI``)."""
    if is_reparse_or_symlink(path):
        raise OSError(f"Refusing to modify permissions on symlink/reparse directory '{path}'.")
    if is_windows_runtime():
        _win32_set_private_dacl(path, is_directory=True)
    else:
        os.chmod(path, 0o700)


def ensure_private_directory(path: Path) -> Path:
    """Create (if needed), harden, and verify a user-private directory fail-closed."""
    target = Path(path)
    if is_reparse_or_symlink(target):
        raise OSError(f"Directory path '{target}' must not be a symlink or junction.")
    target.mkdir(parents=True, exist_ok=True, mode=0o700)
    if is_reparse_or_symlink(target) or not target.is_dir():
        raise OSError(f"Target '{target}' is not a regular non-reparse directory.")
    protect_private_directory(target)
    check = verify_access_control(target, expect_directory=True, strict_private=True)
    if not check.ok:
        raise OSError(
            f"Failed to verify private directory protection on '{target}': {check.detail}"
        )
    return target


def verify_access_control(
    path: Path,
    *,
    expect_directory: bool,
    strict_private: bool,
) -> AccessControlVerificationResult:
    """Verify ownership and isolation on POSIX or Windows NTFS fail-closed."""
    target = Path(path)
    if is_reparse_or_symlink(target):
        return AccessControlVerificationResult(
            ok=False,
            reason_category="permissions",
            detail="Path is a symbolic link, junction, or reparse point.",
        )
    try:
        st = target.stat()
    except OSError as exc:
        return AccessControlVerificationResult(
            ok=False,
            reason_category="permissions",
            detail=f"Unable to stat target path: {exc}",
        )

    if expect_directory and not stat.S_ISDIR(st.st_mode):
        return AccessControlVerificationResult(
            ok=False,
            reason_category="permissions",
            detail="Expected a regular directory.",
        )
    if not expect_directory and not stat.S_ISREG(st.st_mode):
        return AccessControlVerificationResult(
            ok=False,
            reason_category="permissions",
            detail="Expected a regular file.",
        )

    if is_windows_runtime():
        return _win32_verify_path_dacl(target, strict_private=strict_private)

    if hasattr(os, "getuid") and st.st_uid != os.getuid():
        return AccessControlVerificationResult(
            ok=False,
            reason_category="owner",
            detail=f"POSIX UID mismatch (st_uid={st.st_uid}, getuid={os.getuid()}).",
        )
    forbidden_bits = 0o077 if strict_private else 0o022
    if (st.st_mode & forbidden_bits) != 0:
        return AccessControlVerificationResult(
            ok=False,
            reason_category="permissions",
            detail=f"POSIX mode 0o{stat.S_IMODE(st.st_mode):03o} violates mask 0o{forbidden_bits:03o}.",
        )
    return AccessControlVerificationResult(ok=True)


def write_new_private_file(path: Path, content: bytes) -> None:
    """Exclusively create ``path``, write ``content``, apply & verify private ACL/mode.

    Fails closed and unlinks ``path`` if private-file protection cannot be
    applied or verified on the active platform.
    """
    target = Path(path)
    if is_reparse_or_symlink(target):
        raise OSError(f"Refusing to create private file at reparse/symlink path '{target}'.")
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0)
    fd = os.open(target, flags, 0o600)
    try:
        with os.fdopen(fd, "wb") as handle:
            if not is_windows_runtime() and hasattr(os, "fchmod"):
                os.fchmod(handle.fileno(), 0o600)
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        if is_windows_runtime():
            protect_private_file(target)
        check = verify_access_control(
            target, expect_directory=False, strict_private=True
        )
        if not check.ok:
            raise OSError(
                f"Private-file access control verification failed on '{target}': {check.detail}"
            )
    except BaseException:
        target.unlink(missing_ok=True)
        raise


def loosen_access_for_negative_test(path: Path, *, is_directory: bool = False) -> None:
    """Test-only helper that grants local ``Users`` / group read-or-write access.

    On POSIX, sets ``0o755``/``0o777`` (dir) or ``0o644`` (file).
    On Windows NTFS, explicitly grants ``BUILTIN\\Users`` (``S-1-5-32-545``)
    read (or modify on directories) in the DACL via ``SetNamedSecurityInfoW`` so
    negative security tests exercise genuine NTFS ACL verification.
    """
    if is_windows_runtime():
        user_sid, _ = _win32_current_user_sid_and_admin()
        inherit = "OICI" if is_directory else ""
        extra_mask = "M" if is_directory else "FR"
        sddl = (
            f"D:PAI"
            f"(A;{inherit};FA;;;{user_sid})"
            f"(A;{inherit};FA;;;SY)"
            f"(A;{inherit};FA;;;BA)"
            f"(A;{inherit};{extra_mask};;;{SID_BUILTIN_USERS})"
        )
        _win32_apply_sddl_dacl(path, sddl)
    else:
        os.chmod(path, 0o775 if is_directory else 0o644)
