"""Genuine local OCR engine — worker-side only (OCR dependencies).

This module is imported **only** by the isolated OCR worker process running in
``.venv-ocr-worker`` under a separate unprivileged OS account. The backend never
imports it in production; it reaches the worker over loopback IPC. It performs
real extraction, never hardcoded autofill:

* text-layer PDFs  -> ``pdfminer.six`` deterministic per-page text extraction;
* scanned PDFs     -> ``pypdfium2`` bounded rasterization (200 DPI) + Tesseract;
* PNG / JPEG       -> ``Pillow`` bounded decode + Tesseract.

All resource limits from the accepted design are enforced here, and the
corrections round (T2-R4) tightens the ordering:

* raster dimensions are checked BEFORE rendering a PDF page (from the page
  media box at the target DPI) and BEFORE decoding an image (from the header,
  prior to ``Image.load()``), so an oversized document is rejected without ever
  allocating the decoded raster;
* extracted text over the 1 MiB aggregate cap is REJECTED, never silently
  truncated;
* text-layer PDF lines carry their real per-page provenance (page 1..N), not a
  constant page 1;
* a monotonic total deadline and per-page subprocess timeout bound processing.

No cloud service, paid API, credit or quota is used. If the native Tesseract
binary is unavailable the engine raises :class:`OcrUnavailableError` so the
caller can report ``NOT_RUN`` / ``FAILED`` rather than fabricating a result.
"""

from __future__ import annotations

import io
import math
import time
from dataclasses import dataclass

import pdfminer
import pypdfium2 as pdfium
import pytesseract
from pdfminer.high_level import extract_text as _pdfminer_extract_text
from PIL import Image

from . import constants as C
from .extraction_types import (
    ExtractionDeadlineError,
    ExtractionLimitError,
    OcrLine,
    OcrUnavailableError,
    RawExtraction,
)

# Pillow decompression-bomb guard (defence in depth alongside explicit checks).
Image.MAX_IMAGE_PIXELS = C.MAX_PIXELS


@dataclass(frozen=True)
class OcrEngineConfig:
    tesseract_cmd: str = "tesseract"
    tessdata_dir: str | None = None
    lang: str = "eng"
    dpi: int = C.RASTER_DPI
    page_timeout: float = C.OCR_PAGE_TIMEOUT_SECONDS
    total_timeout: float = C.OCR_TOTAL_TIMEOUT_SECONDS
    text_cap: int = C.EXTRACTED_TEXT_CAP_BYTES
    max_pages: int = C.MAX_PDF_PAGES
    max_pixel_side: int = C.MAX_PIXEL_SIDE
    max_decoded_raster_bytes: int = C.MAX_DECODED_RASTER_BYTES

    def tesseract_config(self) -> str:
        # --psm 6: assume a uniform block of text (the fixed-template layout).
        cfg = "--psm 6"
        if self.tessdata_dir:
            cfg += f' --tessdata-dir "{self.tessdata_dir}"'
        return cfg


def _check_tesseract(config: OcrEngineConfig) -> str:
    pytesseract.pytesseract.tesseract_cmd = config.tesseract_cmd
    try:
        version = pytesseract.get_tesseract_version()
    except Exception as error:  # noqa: BLE001 - normalize to a typed failure
        raise OcrUnavailableError(
            "Native Tesseract binary is unavailable or not executable."
        ) from error
    return str(version)


def _guard_pixels(width: int, height: int, config: OcrEngineConfig) -> None:
    if width > config.max_pixel_side or height > config.max_pixel_side:
        raise ExtractionLimitError("Image exceeds the maximum pixel side.")
    if width * height > C.MAX_PIXELS:
        raise ExtractionLimitError("Image exceeds the maximum pixel count.")
    # RGB decoded raster memory bound.
    if width * height * 3 > config.max_decoded_raster_bytes:
        raise ExtractionLimitError("Decoded raster exceeds the memory bound.")


def _reject_text_overflow(text: str, cap: int) -> str:
    """Return the text unchanged, or REJECT it if over the aggregate cap.

    T2-R4: over-cap extracted text is a hard rejection, never a silent
    truncation that would misrepresent the document or its digest.
    """
    if len(text.encode("utf-8")) > cap:
        raise ExtractionLimitError("Extracted text exceeds the aggregate cap.")
    return text


def _ocr_image(img: "Image.Image", page_number: int, config: OcrEngineConfig,
               deadline: float) -> tuple[str, list[OcrLine]]:
    if time.monotonic() >= deadline:
        raise ExtractionDeadlineError("OCR total deadline exceeded.")
    _guard_pixels(img.width, img.height, config)
    if img.mode != "RGB":
        img = img.convert("RGB")
    remaining = max(0.1, deadline - time.monotonic())
    timeout = min(config.page_timeout, remaining)
    try:
        data = pytesseract.image_to_data(
            img, lang=config.lang, config=config.tesseract_config(),
            output_type=pytesseract.Output.DICT, timeout=timeout,
        )
    except RuntimeError as error:
        # pytesseract raises RuntimeError on subprocess timeout (it kills the
        # Tesseract child process), so an expired page never runs unbounded.
        raise ExtractionDeadlineError("OCR page deadline exceeded.") from error
    lines = _group_lines(data, page_number)
    text = "\n".join(line.text for line in lines)
    return text, lines


def _group_lines(data: dict, page_number: int) -> list[OcrLine]:
    """Group Tesseract word boxes into lines with mean confidence in [0, 1]."""
    buckets: dict[tuple[int, int, int], list[int]] = {}
    n = len(data["text"])
    for i in range(n):
        word = (data["text"][i] or "").strip()
        if not word:
            continue
        key = (data["block_num"][i], data["par_num"][i], data["line_num"][i])
        buckets.setdefault(key, []).append(i)
    lines: list[OcrLine] = []
    for key in sorted(buckets):
        idxs = buckets[key]
        words = [data["text"][i].strip() for i in idxs]
        confs = [float(data["conf"][i]) for i in idxs if float(data["conf"][i]) >= 0]
        confidence = (sum(confs) / len(confs) / 100.0) if confs else None
        left = min(data["left"][i] for i in idxs)
        top = min(data["top"][i] for i in idxs)
        right = max(data["left"][i] + data["width"][i] for i in idxs)
        bottom = max(data["top"][i] + data["height"][i] for i in idxs)
        lines.append(
            OcrLine(
                page_number=page_number,
                text=" ".join(words),
                confidence=confidence,
                bbox=(left, top, right, bottom),
            )
        )
    return lines


def _pdf_page_text(data: bytes, page_index: int) -> str:
    try:
        text = _pdfminer_extract_text(
            io.BytesIO(data), page_numbers=[page_index], maxpages=1,
        )
    except Exception:  # noqa: BLE001 - malformed PDF text layer -> fall back to raster
        return ""
    return text or ""


def _looks_like_text_layer(text: str) -> bool:
    stripped = "".join(ch for ch in text if ch.isalpha())
    return len(stripped) >= 24


def _extract_pdf(data: bytes, config: OcrEngineConfig, deadline: float) -> RawExtraction:
    pdf = pdfium.PdfDocument(io.BytesIO(data))
    try:
        page_count = len(pdf)
        if page_count < 1:
            raise ExtractionLimitError("PDF has no pages.")
        if page_count > config.max_pages:
            raise ExtractionLimitError("PDF exceeds the maximum page count.")

        # Per-page text extraction preserves real page provenance (T2-R4).
        page_texts: list[str] = []
        for index in range(page_count):
            if time.monotonic() >= deadline:
                raise ExtractionDeadlineError("OCR total deadline exceeded.")
            page_texts.append(_pdf_page_text(data, index))
        aggregate = "\n".join(page_texts)

        if _looks_like_text_layer(aggregate):
            lines: list[OcrLine] = []
            for index, text in enumerate(page_texts):
                for ln in text.splitlines():
                    if ln.strip():
                        lines.append(OcrLine(page_number=index + 1, text=ln, confidence=None))
            full_text = _reject_text_overflow(aggregate, config.text_cap)
            return RawExtraction(
                mode=C.MODE_PDF_TEXT, engine_name="pdfminer",
                engine_version=pdfminer.__version__, page_count=page_count,
                pixel_width=None, pixel_height=None, full_text=full_text, lines=tuple(lines),
            )

        # Scanned PDF: rasterize each page and run genuine Tesseract OCR.
        version = _check_tesseract(config)
        all_lines: list[OcrLine] = []
        pieces: list[str] = []
        width = height = None
        scale = config.dpi / 72.0
        for index in range(page_count):
            if time.monotonic() >= deadline:
                raise ExtractionDeadlineError("OCR total deadline exceeded.")
            page = pdf[index]
            # T2-R4: guard the rendered pixel size BEFORE rendering/decoding.
            point_width, point_height = page.get_size()
            render_w = int(math.ceil(point_width * scale))
            render_h = int(math.ceil(point_height * scale))
            _guard_pixels(render_w, render_h, config)
            bitmap = page.render(scale=scale)
            img = bitmap.to_pil()
            _guard_pixels(img.width, img.height, config)  # actual size, defence in depth
            width, height = img.size
            page_text, lines = _ocr_image(img, index + 1, config, deadline)
            pieces.append(page_text)
            all_lines.extend(lines)
            _reject_text_overflow("\n".join(pieces), config.text_cap)
        full_text = _reject_text_overflow("\n".join(pieces), config.text_cap)
        return RawExtraction(
            mode=C.MODE_RASTER_OCR, engine_name="tesseract", engine_version=version,
            page_count=page_count, pixel_width=width, pixel_height=height,
            full_text=full_text, lines=tuple(all_lines),
        )
    finally:
        pdf.close()


def _extract_image(data: bytes, media_type: str, config: OcrEngineConfig,
                   deadline: float) -> RawExtraction:
    version = _check_tesseract(config)
    try:
        img = Image.open(io.BytesIO(data))
        # T2-R4: Image.open parses the header only; guard the declared pixel
        # dimensions BEFORE load() allocates the decoded raster.
        _guard_pixels(img.width, img.height, config)
        img.load()
    except ExtractionLimitError:
        raise
    except Exception as error:  # noqa: BLE001
        raise ExtractionLimitError("Malformed or unsupported raster image.") from error
    _guard_pixels(img.width, img.height, config)
    text, lines = _ocr_image(img, 1, config, deadline)
    text = _reject_text_overflow(text, config.text_cap)
    return RawExtraction(
        mode=C.MODE_RASTER_OCR, engine_name="tesseract", engine_version=version,
        page_count=1, pixel_width=img.width, pixel_height=img.height,
        full_text=text, lines=tuple(lines),
    )


def extract(data: bytes, media_type: str, config: OcrEngineConfig | None = None) -> RawExtraction:
    """Extract raw text + lines from an admitted document, genuinely and bounded."""
    config = config or OcrEngineConfig()
    deadline = time.monotonic() + config.total_timeout
    if media_type == C.MEDIA_PDF:
        return _extract_pdf(data, config, deadline)
    if media_type in (C.MEDIA_PNG, C.MEDIA_JPEG):
        return _extract_image(data, media_type, config, deadline)
    raise ExtractionLimitError("Unsupported media type for extraction.")
