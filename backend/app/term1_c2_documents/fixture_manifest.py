"""Server-owned exact file SHA-256 fixture allowlist.

Admission trusts only this manifest: ``sha256 -> (template_id, document_kind,
media_type)``. Watermark text, filenames and client-declared template ids are
never trusted on their own. The manifest contains no expected field values, so
extraction can never be hardcoded autofill keyed off the allowlist.

The manifest is loaded once, validated strictly, and indexed by digest. A
malformed or duplicated manifest fails closed (the document surface refuses to
serve) rather than silently admitting arbitrary files.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Final, Mapping

from . import constants as C

MANIFEST_PATH: Final[Path] = Path(__file__).resolve().parent / "fixtures" / "fixture_manifest.json"
_SHA256: Final[re.Pattern[str]] = re.compile(r"^[0-9a-f]{64}$")
MANIFEST_VERSION: Final = "cardioassist.demo_fixture_manifest/v1"


class ManifestError(RuntimeError):
    """The fixture allowlist is missing, malformed or inconsistent."""


@dataclass(frozen=True)
class FixtureEntry:
    sha256: str
    filename: str
    template_id: str
    document_kind: str
    media_type: str
    byte_size: int
    page_count: int
    pixel_width: int | None
    pixel_height: int | None


@dataclass(frozen=True)
class FixtureManifest:
    entries: Mapping[str, FixtureEntry]
    manifest_sha256: str

    def lookup(self, sha256: str) -> FixtureEntry | None:
        return self.entries.get(sha256)


def _validate_entry(raw: object) -> FixtureEntry:
    if not isinstance(raw, dict):
        raise ManifestError("Fixture entry is not an object.")
    sha = raw.get("sha256")
    if not isinstance(sha, str) or not _SHA256.match(sha):
        raise ManifestError("Fixture entry has an invalid sha256.")
    template = raw.get("template_id")
    if template not in C.FIXTURE_TEMPLATES:
        raise ManifestError("Fixture entry has an unknown template_id.")
    kind = raw.get("document_kind")
    if kind != C.TEMPLATE_TO_KIND[template]:
        raise ManifestError("Fixture document_kind does not match its template.")
    media = raw.get("media_type")
    if media not in C.ALLOWED_MEDIA_TYPES:
        raise ManifestError("Fixture entry has an unsupported media_type.")
    byte_size = raw.get("byte_size")
    if not isinstance(byte_size, int) or not (0 < byte_size <= C.FILE_CAP_BYTES):
        raise ManifestError("Fixture byte_size is out of bounds.")
    page_count = raw.get("page_count")
    if not isinstance(page_count, int) or not (1 <= page_count <= C.MAX_PDF_PAGES):
        raise ManifestError("Fixture page_count is out of bounds.")
    width = raw.get("pixel_width")
    height = raw.get("pixel_height")
    for value in (width, height):
        if value is not None and (not isinstance(value, int) or value > C.MAX_PIXEL_SIDE):
            raise ManifestError("Fixture pixel dimension is out of bounds.")
    filename = raw.get("filename")
    if not isinstance(filename, str) or "/" in filename or "\\" in filename or filename in (".", ".."):
        raise ManifestError("Fixture filename is not a safe basename.")
    return FixtureEntry(
        sha256=sha, filename=filename, template_id=template, document_kind=kind,
        media_type=media, byte_size=byte_size, page_count=page_count,
        pixel_width=width, pixel_height=height,
    )


def load_manifest(path: Path = MANIFEST_PATH) -> FixtureManifest:
    """Load and strictly validate the server-owned allowlist; fail closed."""
    try:
        raw_bytes = path.read_bytes()
    except OSError as error:
        raise ManifestError("Fixture manifest is unavailable.") from error
    manifest_sha256 = hashlib.sha256(raw_bytes).hexdigest()
    try:
        document = json.loads(raw_bytes.decode("utf-8"))
    except (ValueError, UnicodeError) as error:
        raise ManifestError("Fixture manifest is not valid UTF-8 JSON.") from error
    if not isinstance(document, dict) or document.get("manifest_version") != MANIFEST_VERSION:
        raise ManifestError("Fixture manifest version is unsupported.")
    files = document.get("files")
    if not isinstance(files, list) or not files:
        raise ManifestError("Fixture manifest has no files.")
    entries: dict[str, FixtureEntry] = {}
    for raw in files:
        entry = _validate_entry(raw)
        if entry.sha256 in entries:
            raise ManifestError("Fixture manifest contains a duplicate sha256.")
        entries[entry.sha256] = entry
    return FixtureManifest(entries=entries, manifest_sha256=manifest_sha256)


def sha256_of(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()
