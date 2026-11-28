"""Resource limits and the confidence/conflict gate (real engines + parser)."""

from __future__ import annotations

import io

import pytest

from backend.app.term1_c2_documents import constants as C
from backend.app.term1_c2_documents.admission import AdmissionError, validate_structure
from backend.app.term1_c2_documents.extraction_types import OcrLine
from backend.app.term1_c2_documents.template_parser import _parse_resting_field


def _line(text, confidence):
    return OcrLine(page_number=1, text=text, confidence=confidence, bbox=(0, 0, 100, 20))


def test_low_confidence_raster_field_is_withheld():
    # A raster field below the 0.75 threshold is LOW_CONFIDENCE, never auto-typed.
    field = _parse_resting_field("age", (_line("Age: 54 years", 0.50),), raster=True)
    assert field.parse_status == C.PARSE_LOW_CONFIDENCE
    assert field.typed_value is None
    assert field.confidence == 0.50
    assert field.field_provenance == C.PROV_OCR_UNCONFIRMED


def test_high_confidence_raster_field_is_parsed():
    field = _parse_resting_field("age", (_line("Age: 54 years", 0.92),), raster=True)
    assert field.parse_status == C.PARSE_PARSED
    assert field.typed_value == 54
    assert field.unit == "years"


def test_text_layer_has_no_confidence_gate():
    # Deterministic text-layer extraction carries no confidence; it parses.
    field = _parse_resting_field("age", (_line("Age: 54 years", None),), raster=False)
    assert field.parse_status == C.PARSE_PARSED
    assert field.typed_value == 54


def test_conflicting_values_flag_review():
    lines = (_line("Age: 54 years", 0.95), _line("Age: 61 years", 0.95))
    field = _parse_resting_field("age", lines, raster=True)
    assert field.parse_status == C.PARSE_CONFLICT
    assert field.conflict_flag is True
    assert field.typed_value is None


def test_wrong_unit_in_ocr_text_is_invalid():
    field = _parse_resting_field("trestbps", (_line("Resting Systolic BP (trestbps): 130 kPa", 0.95),),
                                 raster=True)
    assert field.parse_status == C.PARSE_INVALID
    assert field.typed_value is None


def test_oversized_image_dimensions_rejected():
    from PIL import Image

    img = Image.new("RGB", (C.MAX_PIXEL_SIDE + 1, 50), (255, 255, 255))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    with pytest.raises(AdmissionError) as exc:
        validate_structure(buf.getvalue(), C.MEDIA_PNG)
    assert exc.value.code == "invalid_document_content"


def _multipage_pdf(page_count: int) -> bytes:
    # Build a well-formed PDF with the requested page count.
    objs = []
    kids = " ".join(f"{3 + i} 0 R" for i in range(page_count))
    objs.append(b"<< /Type /Catalog /Pages 2 0 R >>")
    objs.append(f"<< /Type /Pages /Kids [{kids}] /Count {page_count} >>".encode())
    for i in range(page_count):
        objs.append(
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Contents {3 + page_count + i} 0 R >>".encode()
        )
    for i in range(page_count):
        stream = b"BT /F1 12 Tf 72 720 Td (Demo) Tj ET"
        objs.append(b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream")
    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for i, obj in enumerate(objs, start=1):
        offsets.append(len(out))
        out += f"{i} 0 obj\n".encode() + obj + b"\nendobj\n"
    xref_pos = len(out)
    out += f"xref\n0 {len(objs) + 1}\n".encode() + b"0000000000 65535 f \n"
    for off in offsets:
        out += f"{off:010d} 00000 n \n".encode()
    out += (f"trailer\n<< /Size {len(objs) + 1} /Root 1 0 R >>\nstartxref\n{xref_pos}\n%%EOF\n").encode()
    return bytes(out)


def test_pdf_within_page_limit_accepted():
    info = validate_structure(_multipage_pdf(C.MAX_PDF_PAGES), C.MEDIA_PDF)
    assert info.page_count == C.MAX_PDF_PAGES


def test_pdf_over_page_limit_rejected():
    with pytest.raises(AdmissionError) as exc:
        validate_structure(_multipage_pdf(C.MAX_PDF_PAGES + 1), C.MEDIA_PDF)
    assert exc.value.code == "invalid_document_content"
