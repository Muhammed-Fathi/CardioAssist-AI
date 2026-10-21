"""Exact/near duplicate screening, UCI-411/412 row correspondence, and UCI-145/Cleveland overlap audit."""
from __future__ import annotations

from collections import Counter
from typing import Any, Sequence

from research.audit.registry import (
    EVIDENCE_REQUIRES_APPROVAL,
    EVIDENCE_UNVERIFIED,
    EVIDENCE_VERIFIED,
    UCI_45_CONVENTIONAL_14_COLUMNS,
)

SHARED_13_PREDICTOR_COLUMNS: tuple[str, ...] = UCI_45_CONVENTIONAL_14_COLUMNS[:13]
SHARED_11_PREDICTOR_NO_CA_THAL: tuple[str, ...] = (
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
)

CONTINUOUS_TOLERANCES: dict[str, float] = {
    "age": 1.0,
    "trestbps": 2.0,
    "chol": 5.0,
    "thalach": 2.0,
    "oldpeak": 0.1,
}


def _canonicalize_scalar(val: Any) -> str:
    if val is None:
        return "<MISSING>"
    if isinstance(val, bool):
        return "1" if val else "0"
    if isinstance(val, (int, float)):
        if float(val).is_integer():
            return str(int(round(float(val))))
        return f"{float(val):.4f}"
    s = str(val).strip()
    if s in ("?", "-9", "-9.0", ""):
        return "<MISSING>"
    try:
        f = float(s)
        if f.is_integer():
            return str(int(round(f)))
        return f"{f:.4f}"
    except ValueError:
        return s.lower()


def _to_float_or_none(val: Any) -> float | None:
    if val is None:
        return None
    if isinstance(val, (int, float)) and not isinstance(val, bool):
        return float(val)
    s = str(val).strip()
    if s in ("?", "-9", "-9.0", ""):
        return None
    try:
        return float(s)
    except ValueError:
        return None


def _rows_are_near_duplicate_11_features(row_a: dict[str, Any], row_b: dict[str, Any]) -> bool:
    """Check documented near-duplicate rule on the 11 non-leakage conventional clinical predictors.

    Two records are near-duplicates (when not already exact duplicates on the 11 features) if:
    - They have identical non-missing categorical predictors (sex, cp, fbs, restecg, exang, slope), AND
    - All 5 continuous predictors (age, trestbps, chol, thalach, oldpeak) are non-missing and within
      documented tolerances (|Δage|<=1, |Δtrestbps|<=2, |Δchol|<=5, |Δthalach|<=2, |Δoldpeak|<=0.1),
      OR they match exactly on >=10 of the 11 predictors with matching sex and cp.
    """
    sig_a = tuple(_canonicalize_scalar(row_a.get(col)) for col in SHARED_11_PREDICTOR_NO_CA_THAL)
    sig_b = tuple(_canonicalize_scalar(row_b.get(col)) for col in SHARED_11_PREDICTOR_NO_CA_THAL)
    if sig_a == sig_b:
        return False  # Already an exact match on the 11 features

    # Anchor rule: sex and cp must be non-missing and identical
    if sig_a[1] == "<MISSING>" or sig_a[2] == "<MISSING>":
        return False
    if sig_a[1] != sig_b[1] or sig_a[2] != sig_b[2]:
        return False

    # Rule A: Hamming distance == 1 across the 11 features (10 of 11 identical and non-missing)
    matching_non_missing = sum(
        1 for a_val, b_val in zip(sig_a, sig_b) if a_val == b_val and a_val != "<MISSING>"
    )
    if matching_non_missing >= 10:
        return True

    # Rule B: All categoricals match and continuous fields are within tolerance
    categorical_cols = ("sex", "cp", "fbs", "restecg", "exang", "slope")
    for c_col in categorical_cols:
        ca = _canonicalize_scalar(row_a.get(c_col))
        cb = _canonicalize_scalar(row_b.get(c_col))
        if ca == "<MISSING>" or ca != cb:
            return False

    for cont_col, tol in CONTINUOUS_TOLERANCES.items():
        fa = _to_float_or_none(row_a.get(cont_col))
        fb = _to_float_or_none(row_b.get(cont_col))
        if fa is None or fb is None:
            return False
        if abs(fa - fb) > tol + 1e-9:
            return False

    return True


def compute_within_dataset_duplicates(
    dataset_label: str,
    rows: Sequence[dict[str, Any]],
    predictor_columns: Sequence[str],
    target_column: str,
    *,
    has_11_shared_clinical: bool = False,
) -> dict[str, Any]:
    """Compute exact and near duplicate counts within a single cohort without emitting any row values."""
    full_cols = tuple(predictor_columns) + (target_column,)
    full_counter: Counter[tuple[str, ...]] = Counter()
    pred_counter: Counter[tuple[str, ...]] = Counter()

    for r in rows:
        full_sig = tuple(_canonicalize_scalar(r.get(c)) for c in full_cols)
        pred_sig = tuple(_canonicalize_scalar(r.get(c)) for c in predictor_columns)
        full_counter[full_sig] += 1
        pred_counter[pred_sig] += 1

    exact_full_duplicate_groups = sum(1 for c in full_counter.values() if c > 1)
    exact_full_excess_rows = sum(c - 1 for c in full_counter.values() if c > 1)
    exact_full_pair_count = sum(c * (c - 1) // 2 for c in full_counter.values() if c > 1)

    exact_pred_duplicate_groups = sum(1 for c in pred_counter.values() if c > 1)
    exact_pred_excess_rows = sum(c - 1 for c in pred_counter.values() if c > 1)
    exact_pred_pair_count = sum(c * (c - 1) // 2 for c in pred_counter.values() if c > 1)

    near_dup_pair_count = 0
    if has_11_shared_clinical and len(rows) <= 2000:
        for i in range(len(rows)):
            for j in range(i + 1, len(rows)):
                if _rows_are_near_duplicate_11_features(rows[i], rows[j]):
                    near_dup_pair_count += 1
    else:
        # Generic single-column-difference near-duplicate check on predictor_columns
        pred_sigs = [tuple(_canonicalize_scalar(r.get(c)) for c in predictor_columns) for r in rows]
        if len(pred_sigs) <= 2000 and len(predictor_columns) >= 5:
            for i in range(len(pred_sigs)):
                for j in range(i + 1, len(pred_sigs)):
                    if pred_sigs[i] == pred_sigs[j]:
                        continue
                    diffs = sum(1 for a, b in zip(pred_sigs[i], pred_sigs[j]) if a != b)
                    if diffs == 1:
                        near_dup_pair_count += 1

    return {
        "dataset_label": dataset_label,
        "total_rows_screened": len(rows),
        "observed_exact_full_row_duplicate_groups": exact_full_duplicate_groups,
        "observed_exact_full_row_excess_records": exact_full_excess_rows,
        "observed_exact_full_row_pairs": exact_full_pair_count,
        "observed_exact_predictor_duplicate_groups": exact_pred_duplicate_groups,
        "observed_exact_predictor_excess_records": exact_pred_excess_rows,
        "observed_exact_predictor_pairs": exact_pred_pair_count,
        "observed_near_duplicate_candidate_pairs": near_dup_pair_count,
        "evidence_status": EVIDENCE_VERIFIED,
    }


def compute_cross_cohort_duplicates(
    cohort_rows_map: dict[str, Sequence[dict[str, Any]]],
) -> dict[str, Any]:
    """Screen exact and near duplicates across authorized 14-column cohorts (Audit Functions 5 & 6)."""
    cohort_names = sorted(cohort_rows_map.keys())
    pairwise_results: list[dict[str, Any]] = []

    for i in range(len(cohort_names)):
        for j in range(i + 1, len(cohort_names)):
            c_a = cohort_names[i]
            c_b = cohort_names[j]
            rows_a = cohort_rows_map[c_a]
            rows_b = cohort_rows_map[c_b]

            sigs_13_a = Counter(
                tuple(_canonicalize_scalar(r.get(c)) for c in SHARED_13_PREDICTOR_COLUMNS) for r in rows_a
            )
            sigs_13_b = Counter(
                tuple(_canonicalize_scalar(r.get(c)) for c in SHARED_13_PREDICTOR_COLUMNS) for r in rows_b
            )
            shared_13_keys = set(sigs_13_a.keys()) & set(sigs_13_b.keys())
            exact_13_matched_rows_in_a = sum(sigs_13_a[k] for k in shared_13_keys)
            exact_13_matched_rows_in_b = sum(sigs_13_b[k] for k in shared_13_keys)

            sigs_11_a = Counter(
                tuple(_canonicalize_scalar(r.get(c)) for c in SHARED_11_PREDICTOR_NO_CA_THAL) for r in rows_a
            )
            sigs_11_b = Counter(
                tuple(_canonicalize_scalar(r.get(c)) for c in SHARED_11_PREDICTOR_NO_CA_THAL) for r in rows_b
            )
            shared_11_keys = set(sigs_11_a.keys()) & set(sigs_11_b.keys())
            exact_11_matched_rows_in_a = sum(sigs_11_a[k] for k in shared_11_keys)
            exact_11_matched_rows_in_b = sum(sigs_11_b[k] for k in shared_11_keys)

            near_cross_pairs = 0
            if len(rows_a) * len(rows_b) <= 500_000:
                for ra in rows_a:
                    for rb in rows_b:
                        if _rows_are_near_duplicate_11_features(ra, rb):
                            near_cross_pairs += 1

            pairwise_results.append(
                {
                    "cohort_a": c_a,
                    "cohort_b": c_b,
                    "rows_a": len(rows_a),
                    "rows_b": len(rows_b),
                    "observed_exact_13_predictor_distinct_profiles": len(shared_13_keys),
                    "observed_exact_13_predictor_rows_in_a": exact_13_matched_rows_in_a,
                    "observed_exact_13_predictor_rows_in_b": exact_13_matched_rows_in_b,
                    "observed_exact_11_predictor_no_ca_thal_distinct_profiles": len(shared_11_keys),
                    "observed_exact_11_predictor_rows_in_a": exact_11_matched_rows_in_a,
                    "observed_exact_11_predictor_rows_in_b": exact_11_matched_rows_in_b,
                    "observed_near_duplicate_candidate_cross_pairs": near_cross_pairs,
                    "evidence_status": EVIDENCE_VERIFIED,
                }
            )

    return {
        "methods_documented": {
            "exact_full_row": "Canonicalized exact match across all predictor columns and the target column.",
            "exact_13_predictor_profile": "Canonicalized exact match across the 13 conventional UCI-45 predictors (age..thal).",
            "exact_11_predictor_no_ca_thal_profile": "Canonicalized exact match across the 11 pre-angiography/stress predictors (excluding ca and thal).",
            "near_duplicate_tolerance_rule": (
                "Identical sex and cp, plus either (a) >=10 of 11 non-missing shared predictors identical "
                "(Hamming distance 1) or (b) all 6 categorical predictors identical and all 5 continuous predictors "
                "within documented tolerances (|Δage|<=1, |Δtrestbps|<=2, |Δchol|<=5, |Δthalach|<=2, |Δoldpeak|<=0.1)."
            ),
        },
        "pairwise_cross_cohort_summary": pairwise_results,
        "independence_and_overlap_distinction": {
            "observed_duplicates_vs_suspected_overlap": (
                "Observed exact/near duplicate counts measure feature-vector collisions in de-identified tabular "
                "records. Suspected patient overlap (such as UCI-145 Statlog vs UCI-45 Cleveland recirculation, or "
                "UCI-411 vs UCI-412 same-cohort extension) is a provenance and study-design property."
            ),
            "proven_independence_claim_permitted": False,
            "scientific_rule": (
                "NEVER claim proven patient independence from identifier-free tabular data, even when observed "
                "exact or near duplicate counts are zero. Conversely, near-duplicate collisions on coarse clinical "
                "variables are candidate overlaps requiring Gate PT resolution rules, not re-identification."
            ),
            "evidence_status": EVIDENCE_VERIFIED,
        },
    }


def evaluate_uci_411_412_correspondence(
    uci_412_parsed: dict[str, Any] | None,
    uci_411_parsed: dict[str, Any] | None,
    *,
    da_b1_authorized: bool,
) -> dict[str, Any]:
    """Audit Function 7: Confirm UCI-411/412 same-cohort provenance and evaluate row correspondence if both authorized."""
    base_provenance = {
        "register_id": "L-04",
        "same_cohort_provenance_status": EVIDENCE_VERIFIED,
        "same_cohort_provenance_basis": (
            "Both official UCI pages (id 412 DOI 10.24432/C5Q31T and id 411 DOI 10.24432/C5461K) list the same "
            "creators, 303 instances, and CAD definition, and UCI-411 explicitly describes itself as an extension "
            "of the Z-Alizadeh Sani dataset with LAD, LCX, and RCA stenosis columns added."
        ),
        "never_independent_cohort": True,
        "never_training_or_external_validation_for_uci_412": True,
        "sample_size_summation_prohibited": True,
    }

    if not da_b1_authorized or uci_412_parsed is None or uci_411_parsed is None:
        return {
            **base_provenance,
            "da_b1_authorized": da_b1_authorized,
            "row_correspondence_evaluated": False,
            "row_correspondence_evidence_status": (
                EVIDENCE_REQUIRES_APPROVAL if not da_b1_authorized else EVIDENCE_UNVERIFIED
            ),
            "note": (
                "Same-cohort provenance is VERIFIED from official UCI metadata. Row-level 1-to-1 correspondence "
                "requires both DA-A1 (UCI-412) and DA-B1 (UCI-411) to be authorized and present locally."
            ),
        }

    rows_412: Sequence[dict[str, Any]] = uci_412_parsed["normalized_rows"]
    rows_411: Sequence[dict[str, Any]] = uci_411_parsed["normalized_rows"]
    cols_412 = set(uci_412_parsed.get("all_canonical_columns", uci_412_parsed["normalized_columns"]))
    cols_411 = set(uci_411_parsed.get("all_canonical_columns", uci_411_parsed["normalized_columns"]))

    shared_cols = sorted(cols_412 & cols_411)
    only_in_411 = sorted(cols_411 - cols_412)
    only_in_412 = sorted(cols_412 - cols_411)

    sigs_412 = [tuple(_canonicalize_scalar(r.get(c)) for c in shared_cols) for r in rows_412]
    sigs_411 = [tuple(_canonicalize_scalar(r.get(c)) for c in shared_cols) for r in rows_411]

    min_len = min(len(sigs_412), len(sigs_411))
    positional_matches = sum(1 for idx in range(min_len) if sigs_412[idx] == sigs_411[idx])

    counter_412 = Counter(sigs_412)
    counter_411 = Counter(sigs_411)
    unordered_matches = sum(min(counter_412[k], counter_411[k]) for k in (set(counter_412) & set(counter_411)))

    exact_1_to_1_positional = (
        len(rows_412) == len(rows_411) and positional_matches == len(rows_412) and len(rows_412) > 0
    )

    return {
        **base_provenance,
        "da_b1_authorized": True,
        "row_correspondence_evaluated": True,
        "uci_412_row_count": len(rows_412),
        "uci_411_row_count": len(rows_411),
        "shared_columns_count": len(shared_cols),
        "columns_only_in_uci_411": only_in_411,
        "columns_only_in_uci_412": only_in_412,
        "positional_exact_match_count": positional_matches,
        "unordered_exact_match_count": unordered_matches,
        "exact_1_to_1_positional_alignment": exact_1_to_1_positional,
        "uci_411_artery_to_cath_consistent_rows": uci_411_parsed.get("artery_to_cath_consistent_rows", 0),
        "uci_411_artery_to_cath_inconsistent_rows": uci_411_parsed.get("artery_to_cath_inconsistent_rows", 0),
        "row_correspondence_evidence_status": EVIDENCE_VERIFIED,
    }


def investigate_statlog_cleveland_overlap(
    cleveland_rows: Sequence[dict[str, Any]] | None,
    statlog_rows: Sequence[dict[str, Any]] | None,
    *,
    da_b2_authorized: bool,
) -> dict[str, Any]:
    """Audit Function 8: Investigate UCI-145 Statlog vs UCI-45 Cleveland overlap ONLY if DA-B2 is approved."""
    base_policy = {
        "register_id": "L-05",
        "never_training_or_external_validation_by_audit_grant": True,
        "prohibited_roles": ["training_cohort", "external_validation_cohort", "pooled_sample_size_addition"],
    }

    if not da_b2_authorized:
        return {
            **base_policy,
            "da_b2_authorized": False,
            "investigation_status": "BLOCKED_PENDING_DA_B2_AUTHORIZATION",
            "evidence_status": EVIDENCE_REQUIRES_APPROVAL,
            "note": (
                "DA-B2 (UCI-145 Statlog) access is NOT approved. Overlap investigation was not executed, and "
                "UCI-145 remains excluded as a suspect-duplicate recirculation of Cleveland."
            ),
        }

    if cleveland_rows is None or statlog_rows is None:
        return {
            **base_policy,
            "da_b2_authorized": True,
            "investigation_status": "AWAITING_LOCAL_FILES",
            "evidence_status": EVIDENCE_UNVERIFIED,
        }

    clev_13_with_target = Counter(
        tuple(_canonicalize_scalar(r.get(c)) for c in SHARED_13_PREDICTOR_COLUMNS)
        + (str(r.get("binary_target")),)
        for r in cleveland_rows
    )
    stat_13_with_target = Counter(
        tuple(_canonicalize_scalar(r.get(c)) for c in SHARED_13_PREDICTOR_COLUMNS)
        + (str(r.get("binary_target")),)
        for r in statlog_rows
    )
    shared_13_t = set(clev_13_with_target) & set(stat_13_with_target)
    matched_statlog_13_t = sum(stat_13_with_target[k] for k in shared_13_t)
    matched_cleveland_13_t = sum(clev_13_with_target[k] for k in shared_13_t)

    clev_13 = Counter(
        tuple(_canonicalize_scalar(r.get(c)) for c in SHARED_13_PREDICTOR_COLUMNS) for r in cleveland_rows
    )
    stat_13 = Counter(
        tuple(_canonicalize_scalar(r.get(c)) for c in SHARED_13_PREDICTOR_COLUMNS) for r in statlog_rows
    )
    shared_13 = set(clev_13) & set(stat_13)
    matched_statlog_13 = sum(stat_13[k] for k in shared_13)

    clev_11 = Counter(
        tuple(_canonicalize_scalar(r.get(c)) for c in SHARED_11_PREDICTOR_NO_CA_THAL) for r in cleveland_rows
    )
    stat_11 = Counter(
        tuple(_canonicalize_scalar(r.get(c)) for c in SHARED_11_PREDICTOR_NO_CA_THAL) for r in statlog_rows
    )
    shared_11 = set(clev_11) & set(stat_11)
    matched_statlog_11 = sum(stat_11[k] for k in shared_11)

    near_pairs = 0
    for sr in statlog_rows:
        for cr in cleveland_rows:
            if _rows_are_near_duplicate_11_features(sr, cr):
                near_pairs += 1

    statlog_total = len(statlog_rows)
    overlap_fraction = round(matched_statlog_13 / statlog_total, 4) if statlog_total > 0 else 0.0

    return {
        **base_policy,
        "da_b2_authorized": True,
        "investigation_status": "EXECUTED_READ_ONLY",
        "cleveland_row_count": len(cleveland_rows),
        "statlog_row_count": statlog_total,
        "exact_13_predictor_plus_binary_target_statlog_rows": matched_statlog_13_t,
        "exact_13_predictor_plus_binary_target_cleveland_rows": matched_cleveland_13_t,
        "exact_13_predictor_statlog_rows": matched_statlog_13,
        "exact_11_predictor_no_ca_thal_statlog_rows": matched_statlog_11,
        "near_duplicate_cross_pairs": near_pairs,
        "statlog_exact_13_predictor_overlap_fraction": overlap_fraction,
        "evidence_status": EVIDENCE_VERIFIED,
    }
