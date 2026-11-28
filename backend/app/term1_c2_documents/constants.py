"""Closed vocabularies, frozen limits and panel field rules for Track 2.

Every enum here is closed: the migration ``20261128_08`` CHECK constraints, the
DOC request/response schemas and the service code all use these exact values.
Adding a value is a contract change requiring review, not a code tweak.

Vocabulary reconciliation (mandatory reviewer clarification #7229164710 item 2):
the accepted API spec (Revision 3 §3.1) and the accepted schema spec (§4) used
two different spellings for document kind and extraction status. This
implementation **adopts the persisted schema vocabulary consistently** in both
the database and the HTTP projection, as the clarification explicitly permits.
The mapping from the older API spelling is recorded in
``docs/term1/TERM1_C2_TRACK2_DOCUMENTS_OCR_IMPLEMENTATION_20261128.md``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final, Mapping

# --- contract identity --------------------------------------------------------
CONTRACT_VERSION: Final = "v1"
SOURCE_CONTRACT_VERSION: Final = "term1.c2.intake/v1"
DOCUMENT_SCHEMA_VERSION: Final = "term1.c2.document/v1"
EXTRACTION_SCHEMA_VERSION: Final = "term1.c2.extraction/v1"

# --- panel binding (reuse da_a2_resting_v1; literals from ai/panels.py) --------
PANEL_ID: Final = "da_a2_resting_v1"
PANEL_VERSION: Final = "1.0.0"
PANEL_CONTRACT_SHA256: Final = (
    "c18ad4cd2cf08f6fefb2e340573760da7000bc1d8eb4ad38783b873c018e57b8"
)
# Exact ordered five eligible Cleveland resting fields. No other field may ever
# enter a model input from this workstream.
PANEL_FIELD_ORDER: Final[tuple[str, ...]] = ("age", "sex", "cp", "trestbps", "restecg")
MANDATORY_FIELDS: Final[frozenset[str]] = frozenset({"age", "sex", "cp"})
OPTIONAL_FIELDS: Final[frozenset[str]] = frozenset({"trestbps", "restecg"})

# Missingness vocabulary (research/intake/synthetic_stage_validator.py).
MISSING_REASONS: Final[frozenset[str]] = frozenset(
    {"not_measured", "not_available_at_time", "unknown", "not_provided"}
)
# ED-DA-A2-01: a measured trestbps of 0 is unavailable, not a valid measurement.
# Categorical zero (sex=0, restecg=0) remains valid data.
ZERO_IS_UNAVAILABLE_FIELDS: Final[frozenset[str]] = frozenset({"trestbps"})


@dataclass(frozen=True)
class PanelFieldRule:
    """Strict typed-value rule for one eligible resting field."""

    name: str
    role: str  # "numeric" | "categorical"
    unit: str | None
    codes: tuple[int, ...]
    strictly_positive: bool
    # Human-readable source category labels used by the anchored template.
    code_labels: Mapping[int, str]


PANEL_FIELD_RULES: Final[Mapping[str, PanelFieldRule]] = {
    "age": PanelFieldRule("age", "numeric", "years", (), True, {}),
    "sex": PanelFieldRule(
        "sex", "categorical", None, (0, 1), False, {0: "Female", 1: "Male"}
    ),
    "cp": PanelFieldRule(
        "cp",
        "categorical",
        None,
        (1, 2, 3, 4),
        False,
        {
            1: "Typical Angina",
            2: "Atypical Angina",
            3: "Non-Anginal Pain",
            4: "Asymptomatic",
        },
    ),
    "trestbps": PanelFieldRule("trestbps", "numeric", "mmHg", (), True, {}),
    "restecg": PanelFieldRule(
        "restecg",
        "categorical",
        None,
        (0, 1, 2),
        False,
        {
            0: "Normal",
            1: "ST-T Abnormality",
            2: "Left Ventricular Hypertrophy",
        },
    ),
}

# --- document kind (persisted schema vocabulary, spec §4.1) -------------------
DOC_KIND_RESTING: Final = "RESTING_CARDIAC_DEMO_REPORT"
DOC_KIND_LABS: Final = "UNRELATED_LAB_DEMO_REPORT"
DOCUMENT_KINDS: Final[tuple[str, ...]] = (DOC_KIND_RESTING, DOC_KIND_LABS)

# --- fixture templates (server-owned allowlist identities) --------------------
TEMPLATE_RESTING: Final = "CAI-DEMO-RESTING-CARDIAC-REPORT-V1"
TEMPLATE_LABS: Final = "CAI-DEMO-UNRELATED-LABS-V1"
TEMPLATE_VERSION: Final = "1"
FIXTURE_TEMPLATES: Final[tuple[str, ...]] = (TEMPLATE_RESTING, TEMPLATE_LABS)
TEMPLATE_TO_KIND: Final[Mapping[str, str]] = {
    TEMPLATE_RESTING: DOC_KIND_RESTING,
    TEMPLATE_LABS: DOC_KIND_LABS,
}

# --- media types (verified by magic bytes, never by extension/header alone) ---
MEDIA_PDF: Final = "application/pdf"
MEDIA_PNG: Final = "image/png"
MEDIA_JPEG: Final = "image/jpeg"
ALLOWED_MEDIA_TYPES: Final[tuple[str, ...]] = (MEDIA_PDF, MEDIA_PNG, MEDIA_JPEG)

# --- upload lifecycle (spec §4.1) ---------------------------------------------
UPLOAD_PENDING_SCAN: Final = "PENDING_SCAN"
UPLOAD_STORED: Final = "STORED"
UPLOAD_FAILED: Final = "UPLOAD_FAILED"
UPLOAD_SUPERSEDED: Final = "SUPERSEDED"
UPLOAD_STATUSES: Final[tuple[str, ...]] = (
    UPLOAD_PENDING_SCAN,
    UPLOAD_STORED,
    UPLOAD_FAILED,
    UPLOAD_SUPERSEDED,
)
# Quota counts every non-reclaimed row, including pending/failed/superseded.
QUOTA_COUNTED_STATUSES: Final[tuple[str, ...]] = (
    UPLOAD_PENDING_SCAN,
    UPLOAD_STORED,
    UPLOAD_SUPERSEDED,
    UPLOAD_FAILED,
)

# --- extraction mode / status (persisted schema vocabulary, spec §4.2) --------
MODE_PDF_TEXT: Final = "PDF_TEXT"
MODE_RASTER_OCR: Final = "RASTER_OCR"
MODE_FAILED: Final = "FAILED"
EXTRACTION_MODES: Final[tuple[str, ...]] = (MODE_PDF_TEXT, MODE_RASTER_OCR, MODE_FAILED)

STATUS_EXTRACTED_DRAFT: Final = "EXTRACTED_DRAFT"
STATUS_NEEDS_MANUAL_REVIEW: Final = "NEEDS_MANUAL_REVIEW"
STATUS_UNSUPPORTED_TEMPLATE: Final = "UNSUPPORTED_TEMPLATE"
STATUS_CONFIRMED: Final = "CONFIRMED_BY_PATIENT"
STATUS_FAILED: Final = "FAILED"
EXTRACTION_STATUSES: Final[tuple[str, ...]] = (
    STATUS_EXTRACTED_DRAFT,
    STATUS_NEEDS_MANUAL_REVIEW,
    STATUS_UNSUPPORTED_TEMPLATE,
    STATUS_CONFIRMED,
    STATUS_FAILED,
)

# --- per-field parse status (spec §4.2) ---------------------------------------
PARSE_PARSED: Final = "PARSED"
PARSE_LOW_CONFIDENCE: Final = "LOW_CONFIDENCE"
PARSE_CONFLICT: Final = "CONFLICT_REVIEW_REQUIRED"
PARSE_INVALID: Final = "INVALID_VALUE"
PARSE_MISSING: Final = "MISSING"
PARSE_UNRELATED: Final = "UNRELATED_IGNORED"
PARSE_STATUSES: Final[tuple[str, ...]] = (
    PARSE_PARSED,
    PARSE_LOW_CONFIDENCE,
    PARSE_CONFLICT,
    PARSE_INVALID,
    PARSE_MISSING,
    PARSE_UNRELATED,
)

# --- field provenance (spec §4.2) ---------------------------------------------
PROV_OCR_UNCONFIRMED: Final = "OCR_EXTRACTED_UNCONFIRMED"
PROV_OCR_CONFIRMED: Final = "OCR_EXTRACTED_PATIENT_CONFIRMED"
PROV_PATIENT_FROM_DRAFT: Final = "PATIENT_ENTERED_FROM_OCR_DRAFT"
PROV_UNRELATED: Final = "UNRELATED_NON_MODEL_FIELD"
FIELD_PROVENANCES: Final[tuple[str, ...]] = (
    PROV_OCR_UNCONFIRMED,
    PROV_OCR_CONFIRMED,
    PROV_PATIENT_FROM_DRAFT,
    PROV_UNRELATED,
)

# --- assessment attachment role (spec §4.4) -----------------------------------
ROLE_SUPPORTING: Final = "SUPPORTING_REPORT"
ROLE_OCR_SOURCE: Final = "OCR_SOURCE_REPORT"
ROLE_UNRELATED_LAB: Final = "UNRELATED_LAB_ATTACHMENT"
ATTACHMENT_ROLES: Final[tuple[str, ...]] = (
    ROLE_SUPPORTING,
    ROLE_OCR_SOURCE,
    ROLE_UNRELATED_LAB,
)

# --- extraction event types (spec §4.3; DOCTOR_ACKNOWLEDGED is C3-only) --------
EVENT_UPLOADED: Final = "UPLOADED"
EVENT_EXTRACTED: Final = "EXTRACTED"
EVENT_EXTRACTION_FAILED: Final = "EXTRACTION_FAILED"
EVENT_PATIENT_EDITED: Final = "PATIENT_EDITED"
EVENT_PATIENT_CONFIRMED: Final = "PATIENT_CONFIRMED"
EVENT_EDITED_AND_CONFIRMED: Final = "EDITED_AND_CONFIRMED"
EVENT_DOCTOR_ACKNOWLEDGED: Final = "DOCTOR_ACKNOWLEDGED"  # C3 boundary; never emitted in C2
EXTRACTION_EVENT_TYPES: Final[tuple[str, ...]] = (
    EVENT_UPLOADED,
    EVENT_EXTRACTED,
    EVENT_EXTRACTION_FAILED,
    EVENT_PATIENT_EDITED,
    EVENT_PATIENT_CONFIRMED,
    EVENT_EDITED_AND_CONFIRMED,
)

# --- workflow audit additive vocabulary (Track 2-owned; no constants.py edit) --
# These extend the C1 workflow_audit_event vocabulary additively. The C1 table
# has no DB CHECK on event_type/subject_type (only outcome), so Track 2 writes
# these via its own audit helper without modifying backend/app/term1/constants.py.
AUDIT_EVENT_DOCUMENT_UPLOADED: Final = "DOCUMENT_UPLOADED"
AUDIT_EVENT_DOCUMENT_UPLOAD_FAILED: Final = "DOCUMENT_UPLOAD_FAILED"
AUDIT_EVENT_DOCUMENT_EXTRACTED: Final = "DOCUMENT_EXTRACTED"
AUDIT_EVENT_DOCUMENT_EXTRACTION_FAILED: Final = "DOCUMENT_EXTRACTION_FAILED"
AUDIT_EVENT_DOCUMENT_CONFIRMED: Final = "DOCUMENT_CONFIRMED"
AUDIT_EVENT_DOCUMENT_INTEGRITY_MISMATCH: Final = "DOCUMENT_INTEGRITY_MISMATCH"
AUDIT_EVENT_DOCUMENT_RECOVERED: Final = "DOCUMENT_RECOVERED"
AUDIT_SUBJECT_MEDICAL_DOCUMENT: Final = "medical_document"
AUDIT_SUBJECT_DOCUMENT_EXTRACTION: Final = "document_extraction"

# --- frozen admission / resource limits (owner sign-off checklist) ------------
RAW_MULTIPART_CAP_BYTES: Final = 6 * 1024 * 1024          # 6 MiB pre-parser body cap
FILE_CAP_BYTES: Final = 5 * 1024 * 1024                  # 5 MiB per file
MAX_PDF_PAGES: Final = 3
MAX_PIXEL_SIDE: Final = 4096
MAX_PIXELS: Final = 4096 * 4096                          # 16,777,216
MAX_DECODED_RASTER_BYTES: Final = 64 * 1024 * 1024       # 64 MiB decoded raster
EXTRACTED_TEXT_CAP_BYTES: Final = 1 * 1024 * 1024        # 1 MiB aggregate text
OCR_PAGE_TIMEOUT_SECONDS: Final = 10.0
OCR_TOTAL_TIMEOUT_SECONDS: Final = 30.0
RASTER_DPI: Final = 200
LOW_CONFIDENCE_THRESHOLD: Final = 0.75

MAX_FORM_FIELDS: Final = 4
MAX_FILE_PARTS: Final = 1
MAX_METADATA_FIELD_BYTES: Final = 64 * 1024              # 64 KiB non-file fields
MAX_ATTACHMENTS_PER_ASSESSMENT: Final = 5

QUOTA_MAX_DOCUMENTS: Final = 20
QUOTA_MAX_BYTES: Final = 50 * 1024 * 1024                # 50 MiB per patient

PDF_MAX_OBJECTS: Final = 5000
PDF_MAX_DECOMPRESSED_BYTES: Final = 32 * 1024 * 1024     # 32 MiB decompressed streams

# Recovery: a PENDING_SCAN row older than this is eligible for crash recovery.
PENDING_SCAN_RECOVERY_AGE_SECONDS: Final = 60

# --- DOC operation identities (exact method + path template) ------------------
OP_DOC1_UPLOAD: Final = "POST /v1/me/documents"
OP_DOC2_LIST: Final = "GET /v1/me/documents"
OP_DOC3_READ: Final = "GET /v1/me/documents/{document_id}"
OP_DOC4_CONTENT: Final = "GET /v1/me/documents/{document_id}/content"
OP_DOC5_EXTRACT: Final = "POST /v1/me/documents/{document_id}/extract"
OP_DOC6_EXTRACTION: Final = "GET /v1/me/documents/{document_id}/extraction"
OP_DOC7_CONFIRM: Final = "POST /v1/me/documents/{document_id}/confirm"

# --- OCR worker IPC -----------------------------------------------------------
OCR_IPC_PATH: Final = "/internal/ocr/v1/extract"
OCR_IPC_RESPONSE_CAP_BYTES: Final = 1 * 1024 * 1024      # 1 MiB OCR response cap
OCR_WORKER_ID: Final = "ocr-worker-v1"

# --- fabricated demo watermark (must be visibly present on every fixture) -----
DEMO_WATERMARK: Final = "SYNTHETIC DEMO REPORT - NOT A REAL PATIENT RECORD"
