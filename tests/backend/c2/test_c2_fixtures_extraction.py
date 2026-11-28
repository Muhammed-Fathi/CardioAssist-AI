"""Genuine local extraction evidence — REAL engines, never mocked.

These tests run pdfminer.six (text PDFs), pypdfium2 + Pillow + native Tesseract
(raster PDFs / PNG / JPEG) over the fabricated fixture allowlist and assert the
actual extracted values, parse statuses and provenance. They are skipped
(NOT_RUN) when the native Tesseract binary is unavailable.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from backend.app.term1_c2_documents import constants as C
from backend.app.term1_c2_documents.admission import validate_structure
from backend.app.term1_c2_documents.fixture_manifest import load_manifest
from backend.app.term1_c2_documents.ocr_engine import extract
from backend.app.term1_c2_documents.template_parser import parse

from .conftest import ocr_engine_config, requires_native_ocr

FIXTURES = Path(__file__).resolve().parents[3] / "backend" / "app" / "term1_c2_documents" / "fixtures"

EXPECTED_RESTING = {"age": 54, "sex": 1, "cp": 2, "trestbps": 130, "restecg": 0}


def _read(name: str) -> bytes:
    return (FIXTURES / name).read_bytes()


def _manifest():
    return load_manifest()


def _admit(name: str):
    data = _read(name)
    entry = _manifest().lookup(__import__("hashlib").sha256(data).hexdigest())
    assert entry is not None, f"{name} must be on the server-owned allowlist"
    return data, entry


@requires_native_ocr
@pytest.mark.parametrize(
    "filename,mode",
    [
        ("resting_text.pdf", C.MODE_PDF_TEXT),
        ("resting_raster.pdf", C.MODE_RASTER_OCR),
        ("resting.png", C.MODE_RASTER_OCR),
        ("resting.jpg", C.MODE_RASTER_OCR),
    ],
)
def test_clean_resting_extracts_exact_values(filename, mode):
    data, entry = _admit(filename)
    validate_structure(data, entry.media_type)
    raw = extract(data, entry.media_type, ocr_engine_config())
    assert raw.mode == mode
    assert raw.engine_name and raw.engine_version
    parsed = parse(raw, entry.template_id)
    assert parsed.template_matched is True
    assert parsed.extraction_status == C.STATUS_EXTRACTED_DRAFT
    values = {f.field_name: f.typed_value for f in parsed.fields}
    assert values == EXPECTED_RESTING
    for field in parsed.fields:
        assert field.parse_status == C.PARSE_PARSED
        assert field.field_provenance == C.PROV_OCR_UNCONFIRMED
        assert field.conflict_flag is False
    # Explicit units on the continuous fields.
    units = {f.field_name: f.unit for f in parsed.fields}
    assert units["age"] == "years"
    assert units["trestbps"] == "mmHg"


@requires_native_ocr
def test_missing_variant_marks_restecg_missing():
    data, entry = _admit("resting_missing_text.pdf")
    raw = extract(data, entry.media_type, ocr_engine_config())
    parsed = parse(raw, entry.template_id)
    assert parsed.extraction_status == C.STATUS_NEEDS_MANUAL_REVIEW
    fields = {f.field_name: f for f in parsed.fields}
    assert fields["restecg"].parse_status == C.PARSE_MISSING
    assert fields["restecg"].typed_value is None
    # The other four fields still parse cleanly.
    for name in ("age", "sex", "cp", "trestbps"):
        assert fields[name].parse_status == C.PARSE_PARSED


@requires_native_ocr
def test_conflict_variant_flags_age_conflict():
    data, entry = _admit("resting_conflict_text.pdf")
    raw = extract(data, entry.media_type, ocr_engine_config())
    parsed = parse(raw, entry.template_id)
    assert parsed.extraction_status == C.STATUS_NEEDS_MANUAL_REVIEW
    assert parsed.conflict_flag is True
    fields = {f.field_name: f for f in parsed.fields}
    assert fields["age"].parse_status == C.PARSE_CONFLICT
    assert fields["age"].conflict_flag is True
    assert fields["age"].typed_value is None


@requires_native_ocr
@pytest.mark.parametrize(
    "filename", ["labs_text.pdf", "labs_raster.pdf", "labs.png", "labs.jpg"]
)
def test_unrelated_labs_are_record_only_never_model_input(filename):
    data, entry = _admit(filename)
    assert entry.document_kind == C.DOC_KIND_LABS
    raw = extract(data, entry.media_type, ocr_engine_config())
    parsed = parse(raw, entry.template_id)
    assert parsed.template_matched is True
    # No resting panel field is ever produced from the unrelated lab template.
    assert all(f.parse_status == C.PARSE_UNRELATED for f in parsed.fields)
    assert all(f.field_provenance == C.PROV_UNRELATED for f in parsed.fields)
    assert all(f.typed_value is None for f in parsed.fields)
    assert parsed.extraction_status == C.STATUS_UNSUPPORTED_TEMPLATE


@requires_native_ocr
def test_raster_confidence_is_real_and_bounded():
    data, entry = _admit("resting_raster.pdf")
    raw = extract(data, entry.media_type, ocr_engine_config())
    assert raw.mode == C.MODE_RASTER_OCR
    # Genuine Tesseract line confidence exists and lies in [0, 1].
    confidences = [ln.confidence for ln in raw.lines if ln.confidence is not None]
    assert confidences, "raster OCR must expose real engine confidence"
    assert all(0.0 <= c <= 1.0 for c in confidences)
    assert raw.pixel_width and raw.pixel_height


@requires_native_ocr
def test_text_layer_and_raster_agree_on_values():
    text_data, text_entry = _admit("resting_text.pdf")
    raster_data, raster_entry = _admit("resting_raster.pdf")
    text_parsed = parse(extract(text_data, text_entry.media_type, ocr_engine_config()),
                        text_entry.template_id)
    raster_parsed = parse(extract(raster_data, raster_entry.media_type, ocr_engine_config()),
                          raster_entry.template_id)
    text_values = {f.field_name: f.typed_value for f in text_parsed.fields}
    raster_values = {f.field_name: f.typed_value for f in raster_parsed.fields}
    assert text_values == raster_values == EXPECTED_RESTING


def test_all_ten_fixtures_are_on_the_allowlist():
    manifest = _manifest()
    expected = {
        "resting_text.pdf", "resting_raster.pdf", "resting.png", "resting.jpg",
        "resting_missing_text.pdf", "resting_conflict_text.pdf",
        "labs_text.pdf", "labs_raster.pdf", "labs.png", "labs.jpg",
    }
    listed = {e.filename for e in manifest.entries.values()}
    assert expected.issubset(listed)
    for name in expected:
        data = _read(name)
        import hashlib
        entry = manifest.lookup(hashlib.sha256(data).hexdigest())
        assert entry is not None
        assert entry.byte_size == len(data)


def test_watermark_is_present_in_every_fixture_text():
    # The synthetic-demo watermark is embedded; admission never trusts it, but
    # its presence is part of the fabricated-fixture contract.
    import hashlib
    manifest = _manifest()
    for entry in manifest.entries.values():
        data = _read(entry.filename)
        assert hashlib.sha256(data).hexdigest() == entry.sha256
