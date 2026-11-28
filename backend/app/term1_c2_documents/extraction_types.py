"""Stdlib-only shared types for the extraction pipeline.

These types are shared between the OCR engine (worker-side, OCR dependencies)
and the anchored template parser (pure stdlib, importable by the backend without
any OCR library). Keeping them dependency-free lets the backend test the parser
and confirmation logic in ``backend/requirements.txt``'s minimal environment.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass


@dataclass(frozen=True)
class OcrLine:
    """One recognized text line with optional engine confidence."""

    page_number: int
    text: str
    # Mean Tesseract word confidence in [0, 1]; None for deterministic text-layer
    # extraction (pdfminer.six exposes no confidence).
    confidence: float | None = None
    bbox: tuple[int, int, int, int] | None = None


@dataclass(frozen=True)
class RawExtraction:
    """Raw engine output, preserved separately from any corrected value."""

    mode: str  # PDF_TEXT | RASTER_OCR | FAILED
    engine_name: str
    engine_version: str
    page_count: int
    pixel_width: int | None
    pixel_height: int | None
    full_text: str
    lines: tuple[OcrLine, ...] = ()
    failure_reason: str | None = None

    @property
    def raw_text_sha256(self) -> str:
        return hashlib.sha256(self.full_text.encode("utf-8")).hexdigest()

    @property
    def extracted_text_bytes(self) -> int:
        return len(self.full_text.encode("utf-8"))


@dataclass(frozen=True)
class ParsedField:
    """One anchored field result. ``typed_value`` is None unless PARSED."""

    field_name: str
    raw_text: str | None
    typed_value: int | float | None
    unit: str | None
    confidence: float | None
    parse_status: str
    conflict_flag: bool
    field_provenance: str
    page_number: int
    region: tuple[int, int, int, int] | None = None
    missing_reason: str | None = None


@dataclass(frozen=True)
class ParsedTemplate:
    """Full parse result for one document."""

    template_id: str | None
    template_matched: bool
    fields: tuple[ParsedField, ...]
    # Aggregate extraction status derived from the field results.
    extraction_status: str
    conflict_flag: bool


class OcrUnavailableError(RuntimeError):
    """Raised when the native Tesseract binary or tessdata is unavailable."""


class ExtractionDeadlineError(RuntimeError):
    """Raised when the bounded worker deadline is exceeded."""


class ExtractionLimitError(RuntimeError):
    """Raised when a page/pixel/text/resource limit is exceeded."""
