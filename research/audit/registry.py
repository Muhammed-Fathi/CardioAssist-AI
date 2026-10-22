"""Canonical dataset specifications, feature groups, leakage register, and harmonization metadata."""
from __future__ import annotations

from typing import Any

# Required evidence labels per Gate DA package and M2a specification
EVIDENCE_VERIFIED = "VERIFIED"
EVIDENCE_SOURCE_REPORTED = "SOURCE-REPORTED"
EVIDENCE_UNVERIFIED = "UNVERIFIED"
EVIDENCE_REQUIRES_APPROVAL = "REQUIRES APPROVAL"

VALID_EVIDENCE_LABELS = frozenset(
    {
        EVIDENCE_VERIFIED,
        EVIDENCE_SOURCE_REPORTED,
        EVIDENCE_UNVERIFIED,
        EVIDENCE_REQUIRES_APPROVAL,
    }
)

# Official UCI host and dataset endpoints (mirrors/Kaggle strictly forbidden)
OFFICIAL_UCI_HOST = "archive.ics.uci.edu"

# Global and per-dataset authorization status constants (D-046)
GLOBAL_AUTHORIZED_WORKFLOW_STATUS = "AUTHORIZED_FOR_LOCAL_READ_ONLY_AUDIT"
DATASET_AUTHORIZED_STATUS = "AUTHORIZED_FOR_READ_ONLY_AUDIT"
PENDING_HUMAN_ACCEPTANCE_STATUS = "PENDING_HUMAN_ACCEPTANCE"

# Provenance timestamp and origin-verification constants
UNKNOWN_DOWNLOAD_TIMESTAMP = "UNKNOWN_PENDING_HUMAN_VERIFICATION"
LOCAL_INTEGRITY_VERIFIED_STATUS = "VERIFIED"
SOURCE_ORIGIN_HUMAN_ATTESTED_STATUS = "HUMAN_ATTESTED_NOT_INDEPENDENTLY_PROVEN_BY_LOCAL_HASH"

# Explicit documented allowlist of harmless non-dataset archive metadata files
# known to accompany official UCI ZIP archives. Any ZIP entry not in
# (authorized_files | optional_documentation_files | harmless_metadata_allowlist)
# causes inspect_zip_archive() to fail closed with STOP_REQUIRES_REVIEW.
UCI_ARCHIVE_HARMLESS_METADATA_ALLOWLIST: dict[str, frozenset[str]] = {
    "DA-A1": frozenset(),
    "DA-A2": frozenset({"Index", "WARNING", "bak"}),
    "DA-B1": frozenset(),
    "DA-B2": frozenset(),
}

# Exact DA-A2 UCI-45 archive members that are documented in the locally inspected
# 2026-10-22 official ZIP inventory but are NOT authorized dataset inputs.
# These names are RECOGNIZED ONLY FOR REVIEW, NEVER extracted. Their presence
# triggers the same human-reviewed selective-extraction approval as new.data.
# A nested entry under costs/ not EXACTLY listed here remains prohibited.
UCI_45_REVIEW_ONLY_HISTORICAL_MEMBERS: frozenset[str] = frozenset({
    "ask-detrano",
    "cleve.mod",
    "costs/",
    "costs/Index",
    "costs/heart-disease.README",
    "costs/heart-disease.cost",
    "costs/heart-disease.delay",
    "costs/heart-disease.expense",
    "costs/heart-disease.group",
})


FORBIDDEN_SOURCE_HOSTS_SUBSTRINGS = (
    "kaggle.com",
    "github.com",
    "githubusercontent.com",
    "zenodo.org",
    "huggingface.co",
    "figshare.com",
    "openml.org",
    "datahub.io",
)

# UCI-45 conventional 14 columns in exact order (processed.*.data)
UCI_45_CONVENTIONAL_14_COLUMNS: tuple[str, ...] = (
    "age",
    "sex",
    "cp",
    "trestbps",
    "chol",
    "fbs",
    "restecg",
    "thalach",
    "exang",
    "oldpeak",
    "slope",
    "ca",
    "thal",
    "num",
)

# UCI-145 Statlog 14 columns (13 predictors matching Cleveland + class 1/2)
UCI_145_STATLOG_14_COLUMNS: tuple[str, ...] = (
    "age",
    "sex",
    "cp",
    "trestbps",
    "chol",
    "fbs",
    "restecg",
    "thalach",
    "exang",
    "oldpeak",
    "slope",
    "ca",
    "thal",
    "class",
)

# 1-based positions of the 14 conventional attributes inside the 76-attribute raw UCI-45 record
UCI_45_RAW_TO_CONVENTIONAL_1BASED: dict[str, int] = {
    "age": 3,
    "sex": 4,
    "cp": 9,
    "trestbps": 10,
    "chol": 12,
    "fbs": 16,
    "restecg": 19,
    "thalach": 32,
    "exang": 38,
    "oldpeak": 40,
    "slope": 41,
    "ca": 44,
    "thal": 51,
    "num": 58,
}

# Full 76-attribute UCI-45 dictionary (1-based index -> canonical attribute name from heart-disease.names)
UCI_45_RAW_76_ATTRIBUTES: tuple[str, ...] = (
    "id",        # 1
    "ccf",       # 2
    "age",       # 3
    "sex",       # 4
    "painloc",   # 5
    "painexer",  # 6
    "relrest",   # 7
    "pncaden",   # 8
    "cp",        # 9
    "trestbps",  # 10
    "htn",       # 11
    "chol",      # 12
    "smoke",     # 13
    "cigs",      # 14
    "years",     # 15
    "fbs",       # 16
    "dm",        # 17
    "famhist",   # 18
    "restecg",   # 19
    "ekgmo",     # 20
    "ekgday",    # 21
    "ekgyr",     # 22
    "dig",       # 23
    "prop",      # 24
    "nitr",      # 25
    "pro",       # 26
    "diuretic",  # 27
    "proto",     # 28
    "thaldur",   # 29
    "thaltime",  # 30
    "met",       # 31
    "thalach",   # 32
    "thalrest",  # 33
    "tpeakbps",  # 34
    "tpeakbpd",  # 35
    "dummy",     # 36
    "trestbpd",  # 37
    "exang",     # 38
    "xhypo",     # 39
    "oldpeak",   # 40
    "slope",     # 41
    "rldv5",     # 42
    "rldv5e",    # 43
    "ca",        # 44
    "restckm",   # 45
    "exerckm",   # 46
    "restef",    # 47
    "restwm",    # 48
    "exeref",    # 49
    "exerwm",    # 50
    "thal",      # 51
    "thalsev",   # 52
    "thalpul",   # 53
    "earlobe",   # 54
    "cmo",       # 55
    "cday",      # 56
    "cyr",       # 57
    "num",       # 58
    "lmt",       # 59
    "ladprox",   # 60
    "laddist",   # 61
    "diag",      # 62
    "cxmain",    # 63
    "ramus",     # 64
    "om1",       # 65
    "om2",       # 66
    "rcaprox",   # 67
    "rcadist",   # 68
    "lvx1",      # 69
    "lvx2",      # 70
    "lvx3",      # 71
    "lvx4",      # 72
    "lvf",       # 73
    "cathef",    # 74
    "junk",      # 75
    "name",      # 76
)

# Per-vessel angiography label-component attributes (L-02)
UCI_45_PER_VESSEL_ATTRIBUTES: tuple[str, ...] = (
    "lmt",
    "ladprox",
    "laddist",
    "diag",
    "cxmain",
    "ramus",
    "om1",
    "om2",
    "rcaprox",
    "rcadist",
)

UCI_45_CATH_DATE_ATTRIBUTES: tuple[str, ...] = ("cmo", "cday", "cyr")
UCI_45_IDENTIFIER_ATTRIBUTES: tuple[str, ...] = ("id", "ccf", "name")

# DA-A2 file role mapping (exact as defined in PR #10 / document 04 §1.1)
UCI_45_FILE_ROLES: dict[str, dict[str, Any]] = {
    "processed.cleveland.data": {
        "cohort": "cleveland",
        "format": "processed_14_col",
        "expected_columns": 14,
        "documented_rows": 303,
        "intended_role": "PRIMARY_CONVENTIONAL_CLEVELAND_DEVELOPMENT_BENCHMARK",
        "notes": "13 conventional predictors + num; still contains ca (L-01 excluded) and thal (L-06 pending review).",
        "evidence_status": EVIDENCE_VERIFIED,
    },
    "cleveland.data": {
        "cohort": "cleveland",
        "format": "raw_76_attr",
        "expected_columns": 76,
        "documented_rows": 303,
        "intended_role": "CLEVELAND_RAW_DICTIONARY_IDENTIFIER_LABEL_COMPONENT_AUDIT",
        "notes": "76-attribute raw file (59.2 KB as listed at UCI); used for dictionary, -9.0 missing code, L-02 vessel fields, and raw<->processed correspondence.",
        "evidence_status": EVIDENCE_VERIFIED,
    },
    "processed.hungarian.data": {
        "cohort": "hungarian",
        "format": "processed_14_col",
        "expected_columns": 14,
        "documented_rows": 294,
        "intended_role": "CANDIDATE_HUNGARY_STRATEGY_B_EXTERNAL_EVALUATION_AFTER_FORMAT_AUDIT",
        "notes": "14 columns; format, missing symbols, and num coding (0/1 vs 0-4) must be verified at audit.",
        "evidence_status": EVIDENCE_VERIFIED,
    },
    "hungarian.data": {
        "cohort": "hungarian",
        "format": "raw_76_attr",
        "expected_columns": 76,
        "documented_rows": 294,
        "intended_role": "HUNGARY_RAW_DICTIONARY_MISSINGNESS_CORRESPONDENCE_AUDIT",
        "notes": "76-attribute raw file (60.7 KB as listed at UCI).",
        "evidence_status": EVIDENCE_VERIFIED,
    },
    "processed.switzerland.data": {
        "cohort": "switzerland",
        "format": "processed_14_col",
        "expected_columns": 14,
        "documented_rows": 123,
        "intended_role": "CANDIDATE_SWITZERLAND_STRATEGY_B_CONDITIONAL_ON_COMPLETENESS",
        "notes": "14 columns; subject to pre-registered completeness rules (DQ-SCI-6).",
        "evidence_status": EVIDENCE_VERIFIED,
    },
    "switzerland.data": {
        "cohort": "switzerland",
        "format": "raw_76_attr",
        "expected_columns": 76,
        "documented_rows": 123,
        "intended_role": "SWITZERLAND_RAW_MISSINGNESS_AND_CORRESPONDENCE_AUDIT",
        "notes": "76-attribute raw file (24.1 KB as listed at UCI).",
        "evidence_status": EVIDENCE_VERIFIED,
    },
    "processed.va.data": {
        "cohort": "va",
        "format": "processed_14_col",
        "expected_columns": 14,
        "documented_rows": 200,
        "intended_role": "CANDIDATE_VA_LONG_BEACH_STRATEGY_B_CONDITIONAL_ON_COMPLETENESS",
        "notes": "Exact filename is processed.va.data (NOT processed.long-beach-va.data).",
        "evidence_status": EVIDENCE_VERIFIED,
    },
    "long-beach-va.data": {
        "cohort": "va",
        "format": "raw_76_attr",
        "expected_columns": 76,
        "documented_rows": 200,
        "intended_role": "VA_LONG_BEACH_RAW_MISSINGNESS_AND_CORRESPONDENCE_AUDIT",
        "notes": "76-attribute raw file (39 KB as listed at UCI).",
        "evidence_status": EVIDENCE_VERIFIED,
    },
    "heart-disease.names": {
        "cohort": "documentation",
        "format": "documentation_text",
        "expected_columns": 0,
        "documented_rows": 0,
        "intended_role": "OFFICIAL_UCI_45_DICTIONARY_AND_ATTRIBUTION_DOCUMENTATION",
        "notes": "Official UCI documentation (no patient rows); defines 76 attributes and missing code -9.0.",
        "evidence_status": EVIDENCE_VERIFIED,
    },
}

UCI_45_UNAPPROVED_FILES: frozenset[str] = frozenset(
    {
        "new.data",
        "reprocessed.hungarian.data",
        "processed.long-beach-va.data",
        "cleve.mod",
        "ask-detrano",
        "costs",
    }
)

# UCI-45 processed categorical domain expectations (for invalid-coding detection)
UCI_45_PROCESSED_DOMAIN_RULES: dict[str, set[float]] = {
    "sex": {0.0, 1.0},
    "cp": {1.0, 2.0, 3.0, 4.0},
    "fbs": {0.0, 1.0},
    "restecg": {0.0, 1.0, 2.0},
    "exang": {0.0, 1.0},
    "slope": {1.0, 2.0, 3.0},
    "ca": {0.0, 1.0, 2.0, 3.0},
    "thal": {3.0, 6.0, 7.0},
    "num": {0.0, 1.0, 2.0, 3.0, 4.0},
}

# UCI-412 / UCI-411 4-group feature structure (group names VERIFIED at UCI;
# individual column list is SOURCE-REPORTED until the local Windows audit verifies the .xlsx file)
UCI_412_FEATURE_GROUPS: dict[str, tuple[str, ...]] = {
    "demographic": (
        "Age",
        "Weight",
        "Length",
        "Sex",
        "BMI",
        "DM",
        "HTN",
        "Current Smoker",
        "EX-Smoker",
        "FH",
        "Obesity",
        "CRF",
        "CVA",
        "Airway disease",
        "Thyroid Disease",
        "CHF",
        "DLP",
    ),
    "symptom_and_examination": (
        "BP",
        "PR",
        "Edema",
        "Weak Peripheral Pulse",
        "Lung rales",
        "Systolic Murmur",
        "Diastolic Murmur",
        "Typical Chest Pain",
        "Dyspnea",
        "Function Class",
        "Atypical",
        "Nonanginal",
        "Exertional CP",
        "LowTH Ang",
    ),
    "ecg": (
        "Q Wave",
        "St Elevation",
        "St Depression",
        "Tinversion",
        "LVH",
        "Poor R Progression",
        "BBB",  # Present in 55-predictor / 56-column workbook layout; reconciles 54 vs 55/56 count
    ),
    "laboratory_and_echocardiography": (
        "FBS",
        "CR",
        "TG",
        "LDL",
        "HDL",
        "BUN",
        "ESR",
        "HB",
        "K",
        "Na",
        "WBC",
        "Lymph",
        "Neut",
        "PLT",
        "EF-TTE",
        "Region RWMA",
        "VHD",
    ),
}

UCI_412_ECHO_FEATURES: frozenset[str] = frozenset({"EF-TTE", "Region RWMA", "VHD"})
UCI_412_LAB_FEATURES: frozenset[str] = frozenset(
    {"FBS", "CR", "TG", "LDL", "HDL", "BUN", "ESR", "HB", "K", "Na", "WBC", "Lymph", "Neut", "PLT"}
)

UCI_412_TARGET_COLUMN = "Cath"
UCI_412_ALLOWED_TARGETS: frozenset[str] = frozenset({"CAD", "Normal"})

UCI_411_ARTERY_LEAKAGE_COLUMNS: tuple[str, ...] = ("LAD", "LCX", "RCA")
UCI_411_ALLOWED_ARTERY_VALUES: frozenset[str] = frozenset({"Normal", "Stenotic", "CAD", "0", "1"})


def normalize_column_key(name: str) -> str:
    """Normalize a column header for lookup while preserving exact original names in reports."""
    return " ".join(name.strip().lower().replace("_", " ").replace("-", " ").split())


UCI_412_CANONICAL_BY_NORMALIZED: dict[str, tuple[str, str]] = {}
for _group_name, _cols in UCI_412_FEATURE_GROUPS.items():
    for _col in _cols:
        UCI_412_CANONICAL_BY_NORMALIZED[normalize_column_key(_col)] = (_col, _group_name)


# Audit Function 9: Feature Availability & Leakage Review Table
FEATURE_AVAILABILITY_AND_LEAKAGE_TABLE: tuple[dict[str, Any], ...] = (
    {
        "register_id": "L-01",
        "dataset_scope": "UCI-45 (raw & processed) / UCI-145 Statlog",
        "feature_or_group": "ca (number of major vessels [0-3] colored by fluoroscopy)",
        "category": "angiography_fluoroscopy_derived",
        "pre_angiography_availability": "NO_OBTAINED_BY_LABEL_PROCEDURE",
        "ruling": "EXCLUDED_LEAKAGE_BLOCKER",
        "evidence_status": EVIDENCE_VERIFIED,
        "notes": "Obtained during fluoroscopy/angiography that defines the CAD label. Excluded from primary pre-angiography T1 models (Phase 0 §F-1).",
    },
    {
        "register_id": "L-02",
        "dataset_scope": "UCI-45 (raw 76-attribute files)",
        "feature_or_group": "Per-vessel stenosis fields (#59-#68: lmt, ladprox, laddist, diag, cxmain, ramus, om1, om2, rcaprox, rcadist) & cath dates (#55-#57: cmo, cday, cyr)",
        "category": "angiography_label_components",
        "pre_angiography_availability": "NO_DEFINES_LABEL",
        "ruling": "EXCLUDED_LEAKAGE_BLOCKER",
        "evidence_status": EVIDENCE_VERIFIED,
        "notes": "Direct components and procedure dates of the angiographic outcome num. Never predictors in any T1 model.",
    },
    {
        "register_id": "L-02/L-12",
        "dataset_scope": "UCI-45 (raw 76-attribute files)",
        "feature_or_group": "Identifiers (#1 id, #2 ccf, #76 name) and dummy/junk slots (#36 dummy, #75 junk)",
        "category": "identifiers_and_provenance",
        "pre_angiography_availability": "NOT_CLINICAL_FEATURES",
        "ruling": "EXCLUDED_IDENTIFIER_PROHIBITED",
        "evidence_status": EVIDENCE_VERIFIED,
        "notes": "name is dummy-replaced at source; identifiers and administrative slots are never predictors and re-identification is prohibited.",
    },
    {
        "register_id": "L-03",
        "dataset_scope": "UCI-411 (DA-B1 audit-only) & UCI-412 (DA-A1)",
        "feature_or_group": "LAD, LCX, RCA, and Cath (as predictor)",
        "category": "artery_stenosis_label_definitions",
        "pre_angiography_availability": "NO_DEFINES_CATH_LABEL",
        "ruling": "EXCLUDED_LEAKAGE_BLOCKER",
        "evidence_status": EVIDENCE_VERIFIED,
        "notes": "Official UCI-411 guidance states CAD happens when at least one of LAD/LCX/RCA is stenotic and only one of LAD/LCX/RCA/Cath may be kept per task. Never T1 predictors; T2 per-artery target remains UNAPPROVED (REQUIRES APPROVAL, P-1).",
    },
    {
        "register_id": "L-06",
        "dataset_scope": "UCI-45 (raw & processed) / UCI-145 Statlog",
        "feature_or_group": "thal (thallium scintigraphy defect coding 3=normal, 6=fixed, 7=reversible — NOT thalassemia)",
        "category": "stress_imaging",
        "pre_angiography_availability": "CONDITIONAL_POST_SCINTIGRAPHY_ONLY",
        "ruling": "PENDING_AVAILABILITY_EXCLUDED_BY_DEFAULT",
        "evidence_status": EVIDENCE_REQUIRES_APPROVAL,
        "notes": "Coding (3/6/7) is VERIFIED from official UCI page; admissibility depends on the frozen prediction moment at Gate PT and clinician review (P-3/P-4). Excluded from primary model until ruled.",
    },
    {
        "register_id": "L-07",
        "dataset_scope": "UCI-45 (raw & processed) / UCI-145 Statlog",
        "feature_or_group": "Exercise-test block (thalach, exang, oldpeak, slope + raw #23-#50 exercise/medication fields)",
        "category": "exercise_stress_test",
        "pre_angiography_availability": "CONDITIONAL_POST_EXERCISE_TEST_ONLY",
        "ruling": "REQUIRES_GATE_PT_PREDICTION_MOMENT_FREEZE",
        "evidence_status": EVIDENCE_REQUIRES_APPROVAL,
        "notes": "Knowable only after an exercise test. oldpeak unit is UNVERIFIED on the official UCI page (Q2 / DQ-SCI-4). Gate PT must freeze the prediction moment and admit/exclude the entire block accordingly.",
    },
    {
        "register_id": "L-08-ECHO",
        "dataset_scope": "UCI-412 (DA-A1) / UCI-411 (DA-B1)",
        "feature_or_group": "UCI-412 Echocardiography features (EF-TTE, Region RWMA, VHD)",
        "category": "echocardiography",
        "pre_angiography_availability": "TIMING_UNVERIFIED_RELATIVE_TO_ANGIOGRAPHY",
        "ruling": "AUDIT_CRITICAL_DEFAULT_EXCLUDED_UNTIL_RULED",
        "evidence_status": EVIDENCE_UNVERIFIED,
        "notes": "Group existence VERIFIED on official UCI-412 page; individual feature timing relative to angiography decision is UNVERIFIED and requires Gate DA dictionary audit + clinician/Gate PT ruling (REQUIRES APPROVAL).",
    },
    {
        "register_id": "L-08-LAB",
        "dataset_scope": "UCI-412 (DA-A1) / UCI-411 (DA-B1)",
        "feature_or_group": "UCI-412 Laboratory features (FBS, CR, TG, LDL, HDL, BUN, ESR, HB, K, Na, WBC, Lymph, Neut, PLT)",
        "category": "laboratory_panel",
        "pre_angiography_availability": "TIMING_AND_UNITS_PENDING_DICTIONARY_AUDIT",
        "ruling": "REQUIRES_DICTIONARY_AND_GATE_PT_RULING",
        "evidence_status": EVIDENCE_UNVERIFIED,
        "notes": "Units, ranges, and pre-angiography collection timing must be verified from the acquired workbook/documentation at Gate DA and frozen at Gate PT (REQUIRES APPROVAL). Track-B lab values additionally require the 6-condition checklist in docs/blueprint/05 §2.1.",
    },
    {
        "register_id": "L-08-CLIN",
        "dataset_scope": "UCI-412 (DA-A1) / UCI-411 (DA-B1)",
        "feature_or_group": "UCI-412 Demographic, Symptom & Examination, and Resting ECG features",
        "category": "routine_clinical_and_resting_ecg",
        "pre_angiography_availability": "PLAUSIBLY_PRE_ANGIOGRAPHY_SUBJECT_TO_AUDIT",
        "ruling": "CANDIDATE_PRIMARY_PREDICTORS_PENDING_GATE_PT",
        "evidence_status": EVIDENCE_SOURCE_REPORTED,
        "notes": "Group structure VERIFIED at UCI; exact per-column coding and absence of post-diagnosis treatment leakage remain UNVERIFIED until local audit and Gate PT sign-off (REQUIRES APPROVAL).",
    },
)


# Audit Function 10: Target Harmonization & 50% Boundary Specification (H-01 .. H-07)
TARGET_HARMONIZATION_SPEC: dict[str, Any] = {
    "issue_id": "H-01",
    "title": "UCI-45 (>50%) versus UCI-412 (>=50%) Stenosis Threshold Wording and Unresolved 50% Boundary",
    "uci_45_wording": {
        "source": "UCI Heart Disease (id 45, DOI 10.24432/C52P4X)",
        "label_column": "num",
        "verbatim_rule": "Value 0: < 50% diameter narrowing; Value 1 (1..4 in distributed coding): > 50% diameter narrowing (in any major vessel).",
        "inequality_operator": "> 50% (strictly greater than 50%)",
        "wording_evidence_status": EVIDENCE_VERIFIED,
    },
    "uci_412_wording": {
        "source": "UCI Z-Alizadeh Sani (id 412, DOI 10.24432/C5Q31T)",
        "label_column": "Cath",
        "verbatim_rule": "If diameter narrowing >= 50%, patient is categorized as CAD; otherwise Normal.",
        "inequality_operator": ">= 50% (greater than or equal to 50%)",
        "wording_evidence_status": EVIDENCE_VERIFIED,
    },
    "boundary_50_percent_status": {
        "reconciliation_status": "UNRESOLVED_BOUNDARY_COMPATIBILITY",
        "evidence_status": EVIDENCE_UNVERIFIED,
        "gate_pt_ruling_status": EVIDENCE_REQUIRES_APPROVAL,
        "explanation": (
            "The threshold wording difference (>50% in UCI-45 vs >=50% in UCI-412) is VERIFIED from the official UCI "
            "landing pages. However, whether any patient record in either distributed dataset sits at exactly 50% "
            "diameter narrowing, and how such a boundary case was coded in practice, is UNVERIFIED. Processed UCI-45 "
            "files and UCI-412 carry discrete class codes rather than continuous percentage stenosis measurements. "
            "No reconciliation evidence may be invented or inferred. Until data-level or primary-source evidence and "
            "an explicit Gate PT ruling (REQUIRES APPROVAL) close H-01, cross-dataset evaluations between UCI-45 and "
            "UCI-412 must be described strictly as evaluation across related labels whose 50% boundary compatibility "
            "is unresolved, and Strategy C pooling across them remains prohibited."
        ),
    },
    "related_harmonization_rules": (
        {
            "id": "H-02",
            "summary": "UCI-45 num 1..4 supports binary presence (0 vs 1..4) only; ordinal/severity modelling is UNAPPROVED.",
            "evidence_status": EVIDENCE_VERIFIED,
            "ruling_status": EVIDENCE_REQUIRES_APPROVAL,
        },
        {
            "id": "H-03",
            "summary": "Self-report (BRFSS/NHANES T3), incident events (Framingham T4), ECG statements (PTB-XL T5), and generic CVD (CVD-70K) must never be pooled with angiographic T1.",
            "evidence_status": EVIDENCE_VERIFIED,
            "ruling_status": EVIDENCE_VERIFIED,
        },
        {
            "id": "H-04",
            "summary": "Per-file coding, delimiter, missing symbol (-9.0 vs ?), and feature-count discrepancies (UCI-412 54/55/56) must be verified per file at audit, never assumed.",
            "evidence_status": EVIDENCE_VERIFIED,
            "ruling_status": EVIDENCE_UNVERIFIED,
        },
        {
            "id": "H-05",
            "summary": "Angiography-referred cohorts are case-enriched (~71% CAD in UCI-412 as SOURCE-REPORTED); scores are benchmark-cohort scores, never population or personal risk probabilities.",
            "evidence_status": EVIDENCE_SOURCE_REPORTED,
            "ruling_status": EVIDENCE_VERIFIED,
        },
    ),
}
