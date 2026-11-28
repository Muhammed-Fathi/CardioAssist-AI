"""Owner-run Windows probe for the separate ``cai-ocr`` account.

Run this script as the restricted OCR account (not as the backend owner). It
verifies the store's Windows DACL policy, reads one known stored blob with the
recorded digest/size, proves the account cannot create a file in the private
root, and proves it cannot read each supplied sensitive file. This is an
owner-local check and is NOT evidence until the owner captures its output.
"""

from __future__ import annotations

import argparse
import ctypes
import errno
import hashlib
import os
import secrets
import stat
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.app.term1_c2_documents.storage import PrivateDocStore  # noqa: E402


def _is_access_denied(error: OSError) -> bool:
    return isinstance(error, PermissionError) or error.errno in (errno.EACCES, errno.EPERM) or getattr(
        error, "winerror", None
    ) == 5


def _windows_token_username() -> str:
    buffer = ctypes.create_unicode_buffer(512)
    size = ctypes.c_ulong(len(buffer))
    if not ctypes.windll.advapi32.GetUserNameW(buffer, ctypes.byref(size)):
        raise OSError(ctypes.get_last_error(), "GetUserNameW failed")
    return buffer.value.rsplit("\\", 1)[-1]


def _assert_read_denied(path: Path) -> None:
    try:
        info = path.stat()
    except FileNotFoundError as error:
        raise RuntimeError(f"Sensitive probe file does not exist: {path}") from error
    except OSError as error:
        # Verify the probe really exists before accepting a later read denial;
        # a typo or missing file must never become a false PASS.
        raise RuntimeError(f"Probe could not verify an existing file at {path}") from error
    if not stat.S_ISREG(info.st_mode):
        raise RuntimeError(f"Sensitive probe path is not a regular file: {path}")
    try:
        with path.open("rb") as handle:
            handle.read(1)
    except OSError as error:
        if _is_access_denied(error):
            print(f"PASS denied-read: {path.name}")
            return
        raise RuntimeError(f"Probe could not distinguish read denial for {path}") from error
    raise RuntimeError(f"Restricted account unexpectedly read sensitive file: {path}")


def _assert_root_write_denied(root: Path) -> None:
    probe = root / f".cai-ocr-write-probe-{secrets.token_hex(8)}"
    try:
        handle = probe.open("xb")
    except OSError as error:
        if _is_access_denied(error):
            print("PASS denied-write: private document root")
            return
        raise RuntimeError("Probe could not distinguish document-root write denial") from error

    # Successful exclusive creation already proves that the account can mutate
    # the root. Attempt to remove the marker for hygiene, but report FAIL even if
    # a later data write would itself be denied.
    try:
        with handle:
            handle.write(b"probe")
    except OSError:
        pass
    try:
        probe.unlink(missing_ok=True)
    except OSError:
        pass
    raise RuntimeError("Restricted account unexpectedly created a file in the private root")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--storage-key", required=True)
    parser.add_argument("--sha256", required=True)
    parser.add_argument("--size", required=True, type=int)
    parser.add_argument("--expected-user", default="cai-ocr")
    parser.add_argument(
        "--deny-read", action="append", default=[], type=Path,
        help="Existing DB/bundle/key/research file; repeat for each protected root.",
    )
    args = parser.parse_args()

    if os.name != "nt":
        raise RuntimeError("This procedure must run on native Windows.")
    actual_user = _windows_token_username().casefold()
    if actual_user != args.expected_user.casefold():
        raise RuntimeError(
            f"Expected restricted account {args.expected_user!r}; current account is {actual_user!r}."
        )
    if len(args.sha256) != 64 or any(ch not in "0123456789abcdef" for ch in args.sha256):
        raise RuntimeError("--sha256 must be lowercase SHA-256 hex.")
    if args.size <= 0:
        raise RuntimeError("--size must be positive.")
    if not args.deny_read:
        raise RuntimeError("Supply existing --deny-read probe files for DB, AI and research roots.")

    store = PrivateDocStore(args.root, read_only=True)
    blob = store.read_verified(
        args.storage_key, expected_sha256=args.sha256, expected_size=args.size
    )
    if hashlib.sha256(blob).hexdigest() != args.sha256:
        raise RuntimeError("Read-only blob digest did not match the expected identity.")
    print(f"PASS read-verified: {args.storage_key}")
    _assert_root_write_denied(store.root)
    for path in args.deny_read:
        _assert_read_denied(path)
    print(f"PASS restricted-account: {actual_user}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:  # noqa: BLE001 - concise operator-facing failure
        print(f"FAIL restricted-storage probe: {error}", file=sys.stderr)
        raise SystemExit(1) from error
