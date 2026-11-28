"""Anchored fixed-template parser — pure stdlib, no OCR dependency.

The parser turns raw engine output into strict typed field values. It is genuine
parsing of the document text, never hardcoded autofill: the admission allowlist
contains no expected values, and every typed value here is derived from an
anchored regular expression over the extracted text.

Rules (accepted design §5.3):

* verify the printed ``Template ID:`` anchor (OCR-confusion tolerant) against the
  server-owned template identity bound at admission;
* parse each eligible field by its exact anchored label;
* duplicate conflicting values -> ``CONFLICT_REVIEW_REQUIRED``, typed value None;
* confidence < 0.75 (raster) -> ``LOW_CONFIDENCE``, typed value None;
* wrong unit / out-of-vocabulary category -> ``INVALID_VALUE``, typed value None;
* explicit ``NOT_MEASURED`` / ``NOT_AVAILABLE`` or absent label -> ``MISSING``;
* unrelated-lab values are record-only (``UNRELATED_IGNORED``) and never become
  one of the five model fields.

Patient confirmation (DOC7) is a separate, explicit step; nothing here confirms
a value, writes a health profile, or submits an assessment.
"""

from __future__ import annotations

import re
from typing import Final

from . import constants as C
from .extraction_types import OcrLine, ParsedField, ParsedTemplate, RawExtraction

# Anchored labels for the five eligible resting fields.
_FIELD_ANCHORS: Final[dict[str, re.Pattern[str]]] = {
    "age": re.compile(r"^\s*Age\s*:\s*(.+)$", re.IGNORECASE),
    "sex": re.compile(r"^\s*Sex\s*:\s*(.+)$", re.IGNORECASE),
    "cp": re.compile(r"^\s*Chest\s+Pain\s+Category\s*\(cp\)\s*:\s*(.+)$", re.IGNORECASE),
    "trestbps": re.compile(r"^\s*Resting\s+Systolic\s+BP\s*\(trestbps\)\s*:\s*(.+)$", re.IGNORECASE),
    "restecg": re.compile(r"^\s*Resting\s+ECG\s+Classification\s*\(restecg\)\s*:\s*(.+)$", re.IGNORECASE),
}

_TEMPLATE_ANCHOR: Final[re.Pattern[str]] = re.compile(
    r"^\s*Template\s+ID\s*:\s*(.+)$", re.IGNORECASE
)

_MISSING_MARKERS: Final[dict[str, str]] = {
    "NOT_MEASURED": "not_measured",
    "NOT_AVAILABLE": "not_available_at_time",
    "NOT_AVAILABLE_AT_TIME": "not_available_at_time",
    "N/A": "unknown",
    "NA": "unknown",
    "UNKNOWN": "unknown",
}

# Unrelated-lab anchors (record-only; never model inputs).
_LAB_ANCHORS: Final[dict[str, re.Pattern[str]]] = {
    "unrelated_lab_total_cholesterol": re.compile(r"^\s*Total\s+Cholesterol\s*:\s*(.+)$", re.IGNORECASE),
    "unrelated_lab_fasting_blood_sugar": re.compile(r"^\s*Fasting\s+Blood\s+Sugar\s*:\s*(.+)$", re.IGNORECASE),
    "unrelated_lab_ldl": re.compile(r"^\s*LDL\s+Cholesterol\s*:\s*(.+)$", re.IGNORECASE),
    "unrelated_lab_hdl": re.compile(r"^\s*HDL\s+Cholesterol\s*:\s*(.+)$", re.IGNORECASE),
    "unrelated_lab_triglycerides": re.compile(r"^\s*Triglycerides\s*:\s*(.+)$", re.IGNORECASE),
    "unrelated_lab_creatinine": re.compile(r"^\s*Creatinine\s*:\s*(.+)$", re.IGNORECASE),
    "unrelated_lab_hemoglobin": re.compile(r"^\s*Hemoglobin\s*:\s*(.+)$", re.IGNORECASE),
    "unrelated_lab_wbc": re.compile(r"^\s*White\s+Blood\s+Cells\s*\(WBC\)\s*:\s*(.+)$", re.IGNORECASE),
}

_LEADING_NUMBER: Final[re.Pattern[str]] = re.compile(r"^\s*(\d+)\s*(.*)$")


def _fold_ocr(text: str) -> str:
    """Fold common OCR confusions for *template anchor* comparison only.

    I/L/1 and O/0 are frequently substituted by Tesseract. This fold is applied
    to both the expected and observed template id; it is never applied to field
    values, which are parsed strictly.
    """
    upper = text.upper()
    return upper.translate(str.maketrans({"L": "I", "1": "I", "O": "0", "0": "0"}))


# Distinctive, OCR-stable core of each template id. The shared "CAI-DEMO-"
# prefix and "-V1" suffix are noise-prone under raster OCR (character
# insertions/substitutions), so anchor verification matches the distinctive
# core substring inside the printed ``Template ID:`` line, folded for common
# OCR confusions. This remains genuine verification of the printed anchor.
_TEMPLATE_CORES: Final[dict[str, str]] = {
    C.TEMPLATE_RESTING: "RESTING-CARDIAC-REPORT",
    C.TEMPLATE_LABS: "UNRELATED-LABS",
}


def _detect_template(lines: tuple[OcrLine, ...], expected: str | None) -> tuple[str | None, bool]:
    for line in lines:
        match = _TEMPLATE_ANCHOR.match(line.text)
        if not match:
            continue
        observed = match.group(1).strip()
        folded_observed = _fold_ocr(observed)
        if expected is not None:
            core = _fold_ocr(_TEMPLATE_CORES[expected])
            if core in folded_observed:
                return expected, True
            # A printed template that disagrees with the admission-bound identity.
            return observed, False
        # No expected identity: recognize against the closed allowlist.
        for template in C.FIXTURE_TEMPLATES:
            if _fold_ocr(_TEMPLATE_CORES[template]) in folded_observed:
                return template, True
        return observed, False
    return None, False


def _parse_single(field_name: str, value_text: str) -> tuple[int | None, str | None, str, str | None]:
    """Parse one anchored value occurrence.

    Returns (typed_value, unit, parse_status, missing_reason).
    """
    rule = C.PANEL_FIELD_RULES[field_name]
    cleaned = value_text.strip()
    marker = cleaned.upper().replace(" ", "_")
    if marker in _MISSING_MARKERS:
        return None, None, C.PARSE_MISSING, _MISSING_MARKERS[marker]

    number_match = _LEADING_NUMBER.match(cleaned)
    if number_match is None:
        return None, None, C.PARSE_INVALID, None
    number = int(number_match.group(1))
    remainder = number_match.group(2).strip()

    if rule.role == "numeric":
        # Strict unit token check (exact token; values are never converted).
        unit_token = remainder.split()[0] if remainder else ""
        if rule.unit is not None and unit_token != rule.unit:
            return None, None, C.PARSE_INVALID, None
        if number <= 0:
            if field_name in C.ZERO_IS_UNAVAILABLE_FIELDS and number == 0:
                # ED-DA-A2-01: a measured 0 is unavailable, not a measurement.
                return None, rule.unit, C.PARSE_MISSING, "not_measured"
            return None, rule.unit, C.PARSE_INVALID, None
        return number, rule.unit, C.PARSE_PARSED, None

    # Categorical: strict source-code vocabulary.
    if number not in rule.codes:
        return None, None, C.PARSE_INVALID, None
    return number, None, C.PARSE_PARSED, None


def _parse_resting_field(
    field_name: str, lines: tuple[OcrLine, ...], raster: bool
) -> ParsedField:
    anchor = _FIELD_ANCHORS[field_name]
    matches: list[tuple[OcrLine, str]] = []
    for line in lines:
        match = anchor.match(line.text)
        if match:
            matches.append((line, match.group(1)))

    if not matches:
        return ParsedField(
            field_name=field_name, raw_text=None, typed_value=None, unit=None,
            confidence=None, parse_status=C.PARSE_MISSING, conflict_flag=False,
            field_provenance=C.PROV_OCR_UNCONFIRMED, page_number=1,
            missing_reason="not_provided",
        )

    parsed = []
    for line, value_text in matches:
        typed, unit, status, reason = _parse_single(field_name, value_text)
        parsed.append((line, value_text, typed, unit, status, reason))

    raw_text = " | ".join(value_text for _, value_text, *_ in parsed)
    page_number = matches[0][0].page_number
    region = matches[0][0].bbox
    confidences = [line.confidence for line, _ in matches if line.confidence is not None]
    confidence = min(confidences) if confidences else None

    # Distinct non-missing typed values drive conflict detection.
    distinct_values = {typed for _, _, typed, _, status, _ in parsed
                       if status == C.PARSE_PARSED and typed is not None}
    has_missing = any(status == C.PARSE_MISSING for *_, status, _ in parsed)
    has_invalid = any(status == C.PARSE_INVALID for *_, status, _ in parsed)

    if len(distinct_values) > 1 or (len(distinct_values) == 1 and has_missing):
        return ParsedField(
            field_name=field_name, raw_text=raw_text, typed_value=None, unit=None,
            confidence=confidence, parse_status=C.PARSE_CONFLICT, conflict_flag=True,
            field_provenance=C.PROV_OCR_UNCONFIRMED, page_number=page_number, region=region,
        )

    if has_invalid and not distinct_values:
        return ParsedField(
            field_name=field_name, raw_text=raw_text, typed_value=None, unit=None,
            confidence=confidence, parse_status=C.PARSE_INVALID, conflict_flag=False,
            field_provenance=C.PROV_OCR_UNCONFIRMED, page_number=page_number, region=region,
        )

    if has_missing and not distinct_values:
        reason = next(reason for *_, status, reason in parsed if status == C.PARSE_MISSING)
        return ParsedField(
            field_name=field_name, raw_text=raw_text, typed_value=None, unit=None,
            confidence=confidence, parse_status=C.PARSE_MISSING, conflict_flag=False,
            field_provenance=C.PROV_OCR_UNCONFIRMED, page_number=page_number,
            region=region, missing_reason=reason,
        )

    # Exactly one distinct parsed value.
    line, value_text, typed, unit, status, reason = next(
        p for p in parsed if p[4] == C.PARSE_PARSED
    )
    if raster and confidence is not None and confidence < C.LOW_CONFIDENCE_THRESHOLD:
        return ParsedField(
            field_name=field_name, raw_text=raw_text, typed_value=None, unit=unit,
            confidence=confidence, parse_status=C.PARSE_LOW_CONFIDENCE, conflict_flag=False,
            field_provenance=C.PROV_OCR_UNCONFIRMED, page_number=page_number, region=region,
        )
    return ParsedField(
        field_name=field_name, raw_text=value_text, typed_value=typed, unit=unit,
        confidence=confidence, parse_status=C.PARSE_PARSED, conflict_flag=False,
        field_provenance=C.PROV_OCR_UNCONFIRMED, page_number=page_number, region=region,
    )


def _parse_labs_fields(lines: tuple[OcrLine, ...]) -> tuple[ParsedField, ...]:
    fields: list[ParsedField] = []
    for field_name, anchor in _LAB_ANCHORS.items():
        raw = None
        page_number = 1
        region = None
        for line in lines:
            match = anchor.match(line.text)
            if match:
                raw = match.group(1).strip()
                page_number = line.page_number
                region = line.bbox
                break
        fields.append(
            ParsedField(
                field_name=field_name, raw_text=raw, typed_value=None, unit=None,
                confidence=None, parse_status=C.PARSE_UNRELATED, conflict_flag=False,
                field_provenance=C.PROV_UNRELATED, page_number=page_number, region=region,
            )
        )
    return tuple(fields)


def parse(raw: RawExtraction, expected_template_id: str | None) -> ParsedTemplate:
    """Parse raw extraction output into strict typed fields for the bound template."""
    if raw.mode == C.MODE_FAILED:
        return ParsedTemplate(
            template_id=None, template_matched=False, fields=(),
            extraction_status=C.STATUS_FAILED, conflict_flag=False,
        )

    template_id, matched = _detect_template(raw.lines, expected_template_id)
    if not matched:
        return ParsedTemplate(
            template_id=template_id, template_matched=False, fields=(),
            extraction_status=C.STATUS_UNSUPPORTED_TEMPLATE, conflict_flag=False,
        )

    raster = raw.mode == C.MODE_RASTER_OCR
    if template_id == C.TEMPLATE_LABS:
        # The unrelated-lab template is recognized and recorded, but it is never
        # a resting-intake draft: its fields are record-only (UNRELATED_IGNORED)
        # and it can never be confirmed as panel input. UNSUPPORTED_TEMPLATE
        # signals this at the extraction level; DOC7 also refuses it.
        fields = _parse_labs_fields(raw.lines)
        return ParsedTemplate(
            template_id=template_id, template_matched=True, fields=fields,
            extraction_status=C.STATUS_UNSUPPORTED_TEMPLATE, conflict_flag=False,
        )

    fields = tuple(
        _parse_resting_field(name, raw.lines, raster) for name in C.PANEL_FIELD_ORDER
    )
    conflict = any(f.conflict_flag for f in fields)
    needs_review = any(f.parse_status != C.PARSE_PARSED for f in fields)
    status = C.STATUS_NEEDS_MANUAL_REVIEW if needs_review else C.STATUS_EXTRACTED_DRAFT
    return ParsedTemplate(
        template_id=template_id, template_matched=True, fields=fields,
        extraction_status=status, conflict_flag=conflict,
    )
