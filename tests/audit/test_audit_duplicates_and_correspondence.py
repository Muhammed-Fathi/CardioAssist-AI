"""Tests for duplicate/near-duplicate detection, independence discipline, UCI-411/412 correspondence, and Statlog overlap."""
from __future__ import annotations

from pathlib import Path

from research.audit.duplicates import (
    compute_cross_cohort_duplicates,
    evaluate_uci_411_412_correspondence,
    investigate_statlog_cleveland_overlap,
)
from research.audit.registry import EVIDENCE_REQUIRES_APPROVAL, EVIDENCE_VERIFIED
from research.audit.synthetic_fixtures import (
    build_synthetic_uci_412_rows,
    get_uci_412_headers,
    materialize_synthetic_audit_suite,
)
from research.audit.validators import (
    audit_uci_45_processed_file,
    audit_uci_145_statlog_file,
    audit_uci_412_or_411_workbook,
)
from research.audit.xlsx_reader import write_synthetic_xlsx


def test_within_and_cross_cohort_duplicate_and_near_duplicate_detection(tmp_path: Path) -> None:
    suite = materialize_synthetic_audit_suite(tmp_path, authorize_all=True)
    clev_parsed = audit_uci_45_processed_file(tmp_path / "data/raw/uci-45/processed.cleveland.data")
    hung_parsed = audit_uci_45_processed_file(tmp_path / "data/raw/uci-45/processed.hungarian.data")

    clev_dups = clev_parsed["report"]["within_dataset_duplicates"]
    # Synthetic Cleveland has 1 exact duplicate pair (rows 0 and 1) and 2 near-duplicate pairs (row 2 vs rows 0 and 1)
    assert clev_dups["observed_exact_full_row_duplicate_groups"] == 1
    assert clev_dups["observed_exact_full_row_pairs"] == 1
    assert clev_dups["observed_near_duplicate_candidate_pairs"] == 2

    cross = compute_cross_cohort_duplicates(
        {
            "DA-A2:cleveland": clev_parsed["normalized_rows"],
            "DA-A2:hungarian": hung_parsed["normalized_rows"],
        }
    )
    pair_summary = cross["pairwise_cross_cohort_summary"][0]
    assert pair_summary["cohort_a"] == "DA-A2:cleveland"
    assert pair_summary["cohort_b"] == "DA-A2:hungarian"
    # Hungarian row 0 shares the 11 clinical predictors with Cleveland rows 0 & 1
    assert pair_summary["observed_exact_11_predictor_no_ca_thal_distinct_profiles"] == 1
    assert pair_summary["observed_exact_11_predictor_rows_in_a"] == 2
    assert pair_summary["observed_exact_11_predictor_rows_in_b"] == 1


def test_zero_duplicates_never_permits_proven_independence_claim() -> None:
    cohort_a = [
        {"age": 42, "sex": 0, "cp": 1, "trestbps": 110, "chol": 180, "fbs": 0, "restecg": 0, "thalach": 170, "exang": 0, "oldpeak": 0.0, "slope": 1, "ca": 0, "thal": 3, "num": 0}
    ]
    cohort_b = [
        {"age": 71, "sex": 1, "cp": 4, "trestbps": 165, "chol": 310, "fbs": 1, "restecg": 2, "thalach": 105, "exang": 1, "oldpeak": 3.2, "slope": 3, "ca": 3, "thal": 7, "num": 3}
    ]
    cross = compute_cross_cohort_duplicates({"cohort_a": cohort_a, "cohort_b": cohort_b})
    pair = cross["pairwise_cross_cohort_summary"][0]
    assert pair["observed_exact_13_predictor_distinct_profiles"] == 0
    assert pair["observed_near_duplicate_candidate_cross_pairs"] == 0

    indep = cross["independence_and_overlap_distinction"]
    assert indep["proven_independence_claim_permitted"] is False
    assert "NEVER claim proven patient independence" in indep["scientific_rule"]


def test_uci_411_412_same_cohort_provenance_and_row_correspondence(tmp_path: Path) -> None:
    suite = materialize_synthetic_audit_suite(tmp_path, authorize_all=True)
    p_412 = audit_uci_412_or_411_workbook(
        tmp_path / "data/raw/uci-412/Z-Alizadeh sani dataset.xlsx",
        dataset_id="DA-A1",
    )
    p_411 = audit_uci_412_or_411_workbook(
        tmp_path / "data/raw/uci-411/extention of Z-Alizadeh sani dataset.xlsx",
        dataset_id="DA-B1",
    )

    # 1. When DA-B1 is NOT authorized, provenance is still VERIFIED but row correspondence is REQUIRES APPROVAL
    unauth = evaluate_uci_411_412_correspondence(p_412, None, da_b1_authorized=False)
    assert unauth["same_cohort_provenance_status"] == EVIDENCE_VERIFIED
    assert unauth["never_independent_cohort"] is True
    assert unauth["row_correspondence_evaluated"] is False
    assert unauth["row_correspondence_evidence_status"] == EVIDENCE_REQUIRES_APPROVAL

    # 2. When both DA-A1 and DA-B1 are authorized, 1-to-1 row correspondence is evaluated
    auth_corr = evaluate_uci_411_412_correspondence(p_412, p_411, da_b1_authorized=True)
    assert auth_corr["row_correspondence_evaluated"] is True
    assert auth_corr["row_correspondence_evidence_status"] == EVIDENCE_VERIFIED
    assert auth_corr["exact_1_to_1_positional_alignment"] is True
    assert auth_corr["positional_exact_match_count"] == 6
    assert auth_corr["unordered_exact_match_count"] == 6
    assert auth_corr["columns_only_in_uci_411"] == ["LAD", "LCX", "RCA"]
    assert auth_corr["uci_411_artery_to_cath_consistent_rows"] == 6
    assert auth_corr["uci_411_artery_to_cath_inconsistent_rows"] == 0

    # 3. If UCI-411 rows are reordered relative to UCI-412, positional alignment is False while unordered is 6
    h_411 = get_uci_412_headers(include_bbb=True, include_arteries=True)
    reordered_rows = list(reversed(build_synthetic_uci_412_rows(h_411, include_arteries=True)))
    reordered_path = tmp_path / "extention of Z-Alizadeh sani dataset.xlsx"
    write_synthetic_xlsx(reordered_path, [("Sheet1", h_411, reordered_rows)])
    p_411_reordered = audit_uci_412_or_411_workbook(reordered_path, dataset_id="DA-B1")
    reordered_corr = evaluate_uci_411_412_correspondence(p_412, p_411_reordered, da_b1_authorized=True)
    assert reordered_corr["exact_1_to_1_positional_alignment"] is False
    assert reordered_corr["unordered_exact_match_count"] == 6


def test_uci_145_statlog_overlap_is_gated_on_da_b2_approval(tmp_path: Path) -> None:
    suite = materialize_synthetic_audit_suite(tmp_path, authorize_all=True)
    clev_parsed = audit_uci_45_processed_file(tmp_path / "data/raw/uci-45/processed.cleveland.data")
    stat_parsed = audit_uci_145_statlog_file(tmp_path / "data/raw/uci-145/heart.dat")

    # 1. When DA-B2 is NOT approved, overlap investigation is blocked and marked REQUIRES APPROVAL
    blocked = investigate_statlog_cleveland_overlap(
        clev_parsed["normalized_rows"],
        stat_parsed["normalized_rows"],
        da_b2_authorized=False,
    )
    assert blocked["da_b2_authorized"] is False
    assert blocked["investigation_status"] == "BLOCKED_PENDING_DA_B2_AUTHORIZATION"
    assert blocked["evidence_status"] == EVIDENCE_REQUIRES_APPROVAL
    assert blocked["never_training_or_external_validation_by_audit_grant"] is True

    # 2. When DA-B2 IS approved, overlap investigation runs and reports exact/near matches
    approved = investigate_statlog_cleveland_overlap(
        clev_parsed["normalized_rows"],
        stat_parsed["normalized_rows"],
        da_b2_authorized=True,
    )
    assert approved["da_b2_authorized"] is True
    assert approved["investigation_status"] == "EXECUTED_READ_ONLY"
    assert approved["evidence_status"] == EVIDENCE_VERIFIED
    assert approved["exact_13_predictor_plus_binary_target_statlog_rows"] == 2
    assert approved["exact_13_predictor_statlog_rows"] == 2
    assert approved["near_duplicate_cross_pairs"] >= 1
    assert approved["never_training_or_external_validation_by_audit_grant"] is True
