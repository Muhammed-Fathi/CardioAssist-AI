"""File admission gates.

The backend performs the stdlib-only gates (size, magic bytes, exact SHA-256
allowlist, declared-identity consistency) so it never needs an OCR library.
The deeper structural validation (semantic PDF inspection, bounded raster
decode) runs in the isolated OCR worker via :func:`validate_structure`, which
imports its OCR dependencies lazily.

Nothing here trusts a filename, a Content-Type header or watermark text: the
media type comes from magic bytes and the template/kind come from the
server-owned SHA allowlist.
"""

from __future__ import annotations

from dataclasses import dataclass

from . import constants as C
from .fixture_manifest import FixtureManifest, sha256_of

_PNG_MAGIC = b"\x89PNG\r\n\x1a\n"
_JPEG_SOI = b"\xff\xd8"
_JPEG_EOI = b"\xff\xd9"


class AdmissionError(RuntimeError):
    """Admission failure carrying a closed API error code."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class AdmissionResult:
    content_sha256: str
    media_type: str
    template_id: str
    document_kind: str
    byte_size: int


@dataclass(frozen=True)
class StructureInfo:
    page_count: int
    pixel_width: int | None
    pixel_height: int | None


def detect_media_type(data: bytes) -> str | None:
    """Identify the media type from magic bytes only."""
    if data[:1024].find(b"%PDF-") >= 0:
        return C.MEDIA_PDF
    if data[:8] == _PNG_MAGIC:
        return C.MEDIA_PNG
    if data[:2] == _JPEG_SOI and data[-2:] == _JPEG_EOI:
        return C.MEDIA_JPEG
    return None


def admit_bytes(
    data: bytes,
    *,
    declared_template_id: str,
    declared_document_kind: str,
    manifest: FixtureManifest,
) -> AdmissionResult:
    """Stdlib-only admission gates; raises :class:`AdmissionError` on refusal.

    The media type is derived from magic bytes (server-owned), never from a
    client header or filename. The client-declared template/kind must agree with
    the server-owned SHA allowlist entry.
    """
    if len(data) == 0:
        raise AdmissionError("invalid_document_content")
    if len(data) > C.FILE_CAP_BYTES:
        raise AdmissionError("payload_too_large")

    media_type = detect_media_type(data)
    if media_type is None:
        raise AdmissionError("unsupported_media_type")

    digest = sha256_of(data)
    entry = manifest.lookup(digest)
    if entry is None:
        # Unlisted file: never trust watermark text or filename.
        raise AdmissionError("invalid_document_content")

    if media_type != entry.media_type:
        raise AdmissionError("invalid_document_content")
    if declared_template_id != entry.template_id:
        raise AdmissionError("invalid_document_content")
    if declared_document_kind != entry.document_kind:
        raise AdmissionError("invalid_document_content")
    if len(data) != entry.byte_size:
        raise AdmissionError("invalid_document_content")

    return AdmissionResult(
        content_sha256=digest, media_type=media_type, template_id=entry.template_id,
        document_kind=entry.document_kind, byte_size=len(data),
    )


def validate_structure(data: bytes, media_type: str) -> StructureInfo:
    """Worker-side bounded structural validation (lazy OCR imports).

    Raises :class:`AdmissionError` (``active_pdf_content_rejected`` /
    ``invalid_document_content``) on any violation.
    """
    if media_type == C.MEDIA_PDF:
        from .pdf_inspection import PdfRejectedError, inspect_pdf

        try:
            info = inspect_pdf(data)
        except PdfRejectedError as error:
            raise AdmissionError(error.code) from error
        return StructureInfo(
            page_count=info.page_count, pixel_width=None, pixel_height=None
        )

    if media_type in (C.MEDIA_PNG, C.MEDIA_JPEG):
        import io

        from PIL import Image

        Image.MAX_IMAGE_PIXELS = C.MAX_PIXELS
        try:
            img = Image.open(io.BytesIO(data))
            img.load()
        except Exception as error:  # noqa: BLE001
            raise AdmissionError("invalid_document_content") from error
        expected_format = "PNG" if media_type == C.MEDIA_PNG else "JPEG"
        if img.format != expected_format:
            raise AdmissionError("invalid_document_content")
        width, height = img.size
        if width > C.MAX_PIXEL_SIDE or height > C.MAX_PIXEL_SIDE:
            raise AdmissionError("invalid_document_content")
        if width * height > C.MAX_PIXELS:
            raise AdmissionError("invalid_document_content")
        if width * height * 3 > C.MAX_DECODED_RASTER_BYTES:
            raise AdmissionError("invalid_document_content")
        return StructureInfo(page_count=1, pixel_width=width, pixel_height=height)

    raise AdmissionError("unsupported_media_type")
