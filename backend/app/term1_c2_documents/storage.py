"""Private document storage outside Git and public web roots.

Security properties (accepted design §5.2):

* server-generated storage keys ``<patient_uuid>/<document_uuid>.bin``; the
  original filename is never used in a path;
* strict path containment — no traversal, no symlink / reparse point, regular
  files only (``O_NOFOLLOW`` + ``fstat``);
* atomic publication via write-to-temp + ``os.replace``;
* ``0700`` directories / ``0600`` files on POSIX (NTFS DACL on Windows is an
  owner-local operator procedure, see the runbook);
* bounded, digest-verified reads: the complete ``<= 5 MiB`` buffer is verified
  against the recorded SHA-256 **before** any HTTP status/headers/body are sent.

This module is stdlib-only and never executes document content.
"""

from __future__ import annotations

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


class StorageError(RuntimeError):
    """A storage operation failed safely."""


class IntegrityError(StorageError):
    """Stored bytes do not match the recorded immutable digest/length."""


def make_storage_key(patient_id: str, document_id: str) -> str:
    if not _UUID.match(patient_id) or not _UUID.match(document_id):
        raise StorageError("Storage key components must be UUIDs.")
    return f"{patient_id}/{document_id}.bin"


class PrivateDocStore:
    """A contained, private blob store keyed by server-generated paths."""

    def __init__(self, root: Path) -> None:
        root = Path(root)
        if not root.is_absolute():
            raise StorageError("Private document root must be an absolute path.")
        if root.is_symlink():
            raise StorageError("Private document root must not be a symlink.")
        root.mkdir(parents=True, exist_ok=True)
        try:
            os.chmod(root, 0o700)
        except OSError:
            pass  # Windows: DACL is an operator procedure.
        self._root = root.resolve()

    @property
    def root(self) -> Path:
        return self._root

    def _resolve(self, storage_key: str) -> Path:
        # Accept a final key or its staging form (worker validates staged bytes).
        if not (_KEY.match(storage_key) or _STAGING_KEY.match(storage_key)):
            raise StorageError("Malformed storage key.")
        patient_id, filename = storage_key.split("/")
        directory = self._root / patient_id
        target = directory / filename
        # Reject any symlink component (defence against reparse/junction).
        for component in (directory, target):
            if component.is_symlink():
                raise StorageError("Storage path must not contain a symlink.")
        resolved = target.resolve()
        if self._root not in resolved.parents:
            raise StorageError("Storage path escapes the private root.")
        return target

    def exists(self, storage_key: str) -> bool:
        try:
            target = self._resolve(storage_key)
        except StorageError:
            return False
        return target.is_file() and not target.is_symlink()

    def stage(self, data: bytes, storage_key: str) -> str:
        """Write bytes to a temporary staging file beside the final path.

        Returns the staging key (``<final>.tmp-<random>``). The caller promotes
        it atomically only after successful validation and authorization.
        """
        if len(data) > C.FILE_CAP_BYTES:
            raise StorageError("Staged bytes exceed the file cap.")
        target = self._resolve(storage_key)
        target.parent.mkdir(parents=True, exist_ok=True)
        try:
            os.chmod(target.parent, 0o700)
        except OSError:
            pass
        staging_name = f"{target.name}.tmp-{secrets.token_hex(8)}"
        staging_path = target.parent / staging_name
        fd = os.open(staging_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        try:
            with os.fdopen(fd, "wb") as handle:
                handle.write(data)
                handle.flush()
                os.fsync(handle.fileno())
        except BaseException:
            staging_path.unlink(missing_ok=True)
            raise
        return f"{storage_key}.tmp-{staging_name.split('.tmp-')[1]}"

    def promote(self, staging_key: str, storage_key: str) -> None:
        """Atomically publish a validated staging blob to its final key."""
        final = self._resolve(storage_key)
        staging = final.parent / Path(staging_key).name
        if staging.is_symlink() or not staging.is_file():
            raise StorageError("Staging blob is missing or unsafe.")
        os.replace(staging, final)
        try:
            os.chmod(final, 0o600)
        except OSError:
            pass

    def discard_staging(self, staging_key: str) -> None:
        try:
            final = self._resolve(storage_key_from_staging(staging_key))
            staging = final.parent / Path(staging_key).name
            staging.unlink(missing_ok=True)
        except StorageError:
            return

    def read_verified(self, storage_key: str, *, expected_sha256: str,
                      expected_size: int) -> bytes:
        """Read the complete bounded buffer and verify it before publication.

        Raises :class:`IntegrityError` on any length/digest mismatch so the
        caller can return ``409 document_integrity_mismatch`` with zero bytes
        sent. The file is opened ``O_NOFOLLOW`` and confirmed a regular file.
        """
        if not (0 <= expected_size <= C.FILE_CAP_BYTES):
            raise IntegrityError("Recorded size is out of bounds.")
        target = self._resolve(storage_key)
        flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
        try:
            fd = os.open(target, flags)
        except OSError as error:
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
        if target.is_file() and not target.is_symlink():
            target.unlink(missing_ok=True)

    def iter_files(self):
        """Yield ``(storage_key, path)`` for every regular blob (orphan scan)."""
        for patient_dir in sorted(self._root.iterdir()):
            if not patient_dir.is_dir() or patient_dir.is_symlink():
                continue
            if not _UUID.match(patient_dir.name):
                continue
            for entry in sorted(patient_dir.iterdir()):
                if entry.is_symlink() or not entry.is_file():
                    continue
                yield f"{patient_dir.name}/{entry.name}", entry


def storage_key_from_staging(staging_key: str) -> str:
    """Recover the final storage key from a staging key."""
    marker = ".bin.tmp-"
    index = staging_key.find(marker)
    if index < 0:
        raise StorageError("Not a staging key.")
    return staging_key[: index + len(".bin")]
