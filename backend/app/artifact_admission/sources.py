"""Byte-only artifact sources for offline admission checks.

A source returns raw bytes. Nothing here opens a pickle, joblib, ONNX,
safetensors or JSON model object; the validator only computes a SHA-256 over
the bytes, so a hostile artifact cannot execute code during admission.

The directory source refuses absolute paths, ``..`` segments, empty segments,
backslashes, symlinked components, non-regular files and oversized files. It
therefore cannot be pointed at training data, a protected manifest or a
patient record by a malicious descriptor.
"""

from __future__ import annotations

from pathlib import Path
from typing import Mapping, Protocol, runtime_checkable

MAX_ARTIFACT_BYTES = 512 * 1024 * 1024


class ArtifactReferenceError(Exception):
    """A source could not return safe bytes for a descriptor reference."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(f"artifact reference rejected: {code}")


@runtime_checkable
class ArtifactSource(Protocol):
    """Minimal read-only byte access used by the admission validator."""

    def read_bytes(self, ref: str) -> bytes:
        """Return the bytes for a relative reference or raise ArtifactReferenceError."""


class InMemoryArtifactSource:
    """Explicit in-memory map for tests and offline review harnesses."""

    def __init__(self, files: Mapping[str, bytes]) -> None:
        self._files = dict(files)

    def read_bytes(self, ref: str) -> bytes:
        if not isinstance(ref, str) or ref not in self._files:
            raise ArtifactReferenceError("artifact_missing")
        data = self._files[ref]
        if not isinstance(data, bytes):
            raise ArtifactReferenceError("artifact_reference_invalid")
        if not data:
            raise ArtifactReferenceError("artifact_empty")
        if len(data) > MAX_ARTIFACT_BYTES:
            raise ArtifactReferenceError("artifact_too_large")
        return data


class DirectoryArtifactSource:
    """Read bytes from regular files below one resolved root directory."""

    def __init__(self, root: Path) -> None:
        self._root = Path(root).resolve()

    def _resolve(self, ref: str) -> Path:
        if not isinstance(ref, str) or not ref:
            raise ArtifactReferenceError("artifact_reference_invalid")
        if ref.startswith(("/", "\\")) or "\\" in ref or "\x00" in ref:
            raise ArtifactReferenceError("artifact_reference_invalid")
        parts = ref.split("/")
        if any(part in {"", ".", ".."} for part in parts):
            raise ArtifactReferenceError("artifact_reference_invalid")

        candidate = self._root
        for part in parts:
            candidate = candidate / part
            if candidate.is_symlink():
                raise ArtifactReferenceError("artifact_symlink_not_permitted")

        if not candidate.is_file():
            raise ArtifactReferenceError("artifact_missing")
        resolved = candidate.resolve()
        if resolved != self._root and self._root not in resolved.parents:
            raise ArtifactReferenceError("artifact_reference_invalid")
        size = resolved.stat().st_size
        if size <= 0:
            raise ArtifactReferenceError("artifact_empty")
        if size > MAX_ARTIFACT_BYTES:
            raise ArtifactReferenceError("artifact_too_large")
        return resolved

    def read_bytes(self, ref: str) -> bytes:
        return self._resolve(ref).read_bytes()
