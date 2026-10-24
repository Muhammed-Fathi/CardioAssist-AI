"""Frozen, bounded configuration for the UCI-412 internal research benchmark.

The committed plan is a *registered proposal*. It authorizes nothing. A real run
requires the separate M3a local internal-research authorization whose manifest
binds the exact plan hash, the feature-dictionary hash, and the proposal hash.

Every value that influences splitting, selection, metrics, or model complexity is
read from the plan and re-checked against in-code invariants. CLI options cannot
override them.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
import json
from pathlib import Path
from typing import Any, Final

from research.uci412.feature_schema import (
    DICTIONARY_PATH,
    DICTIONARY_SCHEMA_ID,
    DICTIONARY_SCHEMA_VERSION,
    PRIMARY_PANEL_COLUMNS,
    PRIMARY_PANEL_ID,
    PRIMARY_PANEL_VERSION,
    FeatureDictionary,
    DEFAULT_DICTIONARY,
)
from research.uci412.source_spec import (
    DATASET_ID,
    EXPECTED_NEGATIVE_COUNT,
    EXPECTED_POSITIVE_COUNT,
    EXPECTED_ROW_COUNT,
    NUMERIC_BINARY_SOURCE_COLUMNS,
    NUMERIC_BINARY_SOURCE_ENCODING_ID,
    NUMERIC_BINARY_SOURCE_SEMANTICS,
    NUMERIC_BINARY_SEMANTICS_EVIDENCE_CITATION_IDS,
    NUMERIC_BINARY_SEMANTICS_EVIDENCE_STATUS,
    SOURCE_COLUMNS,
    SOURCE_FILENAME,
    SOURCE_ID,
    SOURCE_PROFILE_ID,
    SOURCE_RELATIVE_PATH,
    TARGET_COLUMN,
    TARGET_NEGATIVE_TOKENS,
    TARGET_POSITIVE_TOKENS,
    TEXT_CATEGORICAL_SOURCE_COLUMNS,
)

PACKAGE_ROOT: Final[Path] = Path(__file__).resolve().parent
REPOSITORY_ROOT: Final[Path] = PACKAGE_ROOT.parents[1]
PLAN_PATH: Final[Path] = PACKAGE_ROOT / "uci412_cad_research_plan.v0.1.json"
PROPOSAL_RELATIVE_PATH: Final[Path] = Path(
    "docs/research/gate-pt/08_m3a_uci412_source_specific_benchmark_SPECIFICATION.md"
)
AUTHORIZATION_TEMPLATE_PATH: Final[Path] = (
    PACKAGE_ROOT / "internal_research_authorization.template.json"
)

EXPERIMENT_ID: Final[str] = "CAI-UCI412-CAD-BENCHMARK-V0.1"
REPORT_BANNER: Final[str] = "INTERNAL_EXPLORATORY_NOT_SUPERVISOR_APPROVED"
PROTOCOL_STATUS: Final[str] = "PROPOSED_NOT_FROZEN_NOT_SUPERVISOR_APPROVED"

M3A_AUTHORIZATION_COMMENT: Final[str] = "AUTHORIZE-M3A-UCI412-INTERNAL-RESEARCH"
M3A_AUTHORIZATION_STATUS: Final[str] = "AUTHORIZED_FOR_LOCAL_INTERNAL_RESEARCH"
M3A_AUTHORIZING_MAINTAINER: Final[str] = "Muhammed Fathi"
M3A_SIGNATURE_SEMANTICS: Final[str] = "HUMAN_ATTESTATION_FIELDS_NOT_A_CRYPTOGRAPHIC_SIGNATURE"
#: Amendment A-1: the only registered numeric-binary source encoding. Binding the
#: id (rather than restating the mapping) keeps one source of truth in
#: ``source_spec.py`` and makes a silent mapping change impossible.
M3A_PROTOCOL_AMENDMENT_ID: Final[str] = "M3A-AMENDMENT-A1"
SOURCE_ENCODING_REGISTER_ID: Final[str] = NUMERIC_BINARY_SOURCE_ENCODING_ID

M3A_LOCAL_SIGNATURE_ATTESTATION: Final[str] = (
    "I have reviewed and authorize this exact hash-bound local UCI-412 internal research "
    "benchmark. I understand Gate PT P-3 remains CLOSED, that no supervisor approval is "
    "claimed, and that no clinical use, external validation, or publication claim is made."
)

ALLOWED_MODEL_FAMILIES: Final[tuple[str, ...]] = (
    "prevalence_dummy",
    "l2_logistic_regression",
    "constrained_random_forest",
)
RESERVED_MODEL_FAMILIES: Final[tuple[str, ...]] = ("gradient_boosting_reserved",)

ALLOWED_OPERATIONS: Final[tuple[str, ...]] = (
    "read_only_source_loading",
    "internal_model_fitting",
    "internal_nested_cv",
    "internal_model_family_comparison",
    "internal_negative_control",
    "internal_aggregate_metrics_report",
)
FORBIDDEN_OPERATIONS: Final[tuple[str, ...]] = (
    "remote_patient_data_upload",
    "model_serving",
    "clinical_decision",
    "external_validation_claim",
    "multi_cohort_pooling",
    "uci411_row_reuse",
    "unapproved_dataset_ingestion",
    "patient_level_git_commit",
    "shap_or_lime_patient_explanations",
    "artifact_packaging_for_serving",
)

OUTPUT_ROOT_RELATIVE_PATH: Final[str] = "data/uci412-experiments"
PROTECTED_MANIFEST_ROOT: Final[str] = "data/manifests"


@dataclass(frozen=True, slots=True)
class Uci412Config:
    """Validated projection of the committed UCI-412 research plan."""

    experiment_id: str
    protocol_status: str
    report_banner: str
    dataset_id: str
    source_id: str
    source_relative_path: str
    expected_row_count: int
    expected_class_counts: tuple[tuple[int, int], ...]
    source_columns: tuple[str, ...]
    target_column: str
    negative_source_tokens: tuple[str, ...]
    positive_source_tokens: tuple[str, ...]
    panel_id: str
    panel_version: str
    dictionary_schema_id: str
    dictionary_schema_version: str
    feature_names: tuple[str, ...]
    numeric_features: tuple[str, ...]
    categorical_features: tuple[str, ...]
    category_codes: tuple[tuple[str, tuple[int, ...]], ...]
    numeric_binary_source_features: tuple[str, ...]
    source_encoding_register_id: str
    protocol_amendment_id: str
    outer_folds: int
    inner_folds: int
    outer_repeat_seeds: tuple[int, ...]
    auc_equivalence_tolerance: float
    logistic_c_values: tuple[float, ...]
    logistic_max_iter: int
    rf_n_estimators: int
    rf_max_depths: tuple[int, ...]
    rf_min_samples_leaf: tuple[int, ...]
    rf_max_features: str
    threshold: float
    negative_control_seeds: tuple[int, ...]
    negative_control_outer_repeats: int
    leakage_alarm_threshold: float
    leakage_warning_threshold: float
    bootstrap_resamples: int
    calibration_bins: int
    inner_seed_offset: int
    inner_fold_multiplier: int
    model_seed_offset: int
    model_fold_multiplier: int
    logistic_seed_offset: int
    forest_seed_offset: int
    bootstrap_seed_offset: int

    @property
    def expected_counts(self) -> dict[int, int]:
        return dict(self.expected_class_counts)

    @property
    def category_code_map(self) -> dict[str, tuple[int, ...]]:
        return dict(self.category_codes)

    def model_configuration(self) -> dict[str, Any]:
        return {
            "prevalence_dummy": {"strategy": "prior", "uses_predictors": False},
            "l2_logistic_regression": {
                "solver": "liblinear",
                "penalty": "l2",
                "C": list(self.logistic_c_values),
                "max_iter": self.logistic_max_iter,
                "class_weight": None,
                "numeric_pipeline": ["median_imputer", "standard_scaler"],
                "categorical_pipeline": [
                    "training_fold_most_frequent_imputer",
                    "fixed_registered_vocabulary_one_hot_drop_first",
                ],
            },
            "constrained_random_forest": {
                "n_estimators": self.rf_n_estimators,
                "max_depth": list(self.rf_max_depths),
                "min_samples_leaf": list(self.rf_min_samples_leaf),
                "max_features": self.rf_max_features,
                "class_weight": None,
                "numeric_pipeline": ["median_imputer"],
                "categorical_pipeline": [
                    "training_fold_most_frequent_imputer",
                    "fixed_registered_vocabulary_one_hot_drop_first",
                ],
            },
        }

    def as_report_dict(self) -> dict[str, Any]:
        return {
            "experiment_id": self.experiment_id,
            "protocol_status": self.protocol_status,
            "report_banner": self.report_banner,
            "dataset": {
                "dataset_id": self.dataset_id,
                "source_id": self.source_id,
                "source_relative_path": self.source_relative_path,
                "expected_row_count": self.expected_row_count,
                "expected_class_counts": {str(k): v for k, v in self.expected_class_counts},
                "independent_cohort": False,
                "uci_411_is_same_participants": True,
            },
            "outcome": {
                "target_column": self.target_column,
                "mapping": {
                    **{token: 1 for token in self.positive_source_tokens},
                    **{token: 0 for token in self.negative_source_tokens},
                },
                "interpretation": "CURRENT_ANGIOGRAPHY_REFERENCED_CAD_PRESENCE_NOT_FUTURE_EVENT_RISK",
            },
            "feature_dictionary": {
                "schema_id": self.dictionary_schema_id,
                "schema_version": self.dictionary_schema_version,
                "panel_id": self.panel_id,
                "panel_version": self.panel_version,
                "predictors": list(self.feature_names),
                "numeric_predictors": list(self.numeric_features),
                "categorical_source_codes": {
                    key: list(values) for key, values in self.category_codes
                },
            },
            "source_value_encoding": {
                "protocol_amendment_id": self.protocol_amendment_id,
                "register_id": self.source_encoding_register_id,
                "numeric_binary_source_columns": list(self.numeric_binary_source_features),
                "numeric_binary_semantics": {
                    str(code): meaning for code, meaning in NUMERIC_BINARY_SOURCE_SEMANTICS
                },
                "numeric_binary_semantics_status": NUMERIC_BINARY_SEMANTICS_EVIDENCE_STATUS,
                "numeric_binary_semantics_evidence_citation_ids": list(
                    NUMERIC_BINARY_SEMANTICS_EVIDENCE_CITATION_IDS
                ),
                "numeric_binary_semantics_human_acceptance_required": True,
                "text_categorical_source_columns": list(TEXT_CATEGORICAL_SOURCE_COLUMNS),
                "global_automatic_coercion": "FORBIDDEN",
                "numeric_binary_model_codes_unchanged": [0, 1],
                "encoded_parameter_count": DEFAULT_DICTIONARY.encoded_parameter_count(),
            },
            "model_configuration": self.model_configuration(),
            "cv": {
                "outer_folds": self.outer_folds,
                "inner_folds": self.inner_folds,
                "outer_repeat_seeds": list(self.outer_repeat_seeds),
                "stratified": True,
                "selection_metric": "roc_auc",
                "auc_equivalence_tolerance": self.auc_equivalence_tolerance,
                "simplicity_preference": "l2_logistic_regression_within_tolerance",
                "threshold": self.threshold,
                "threshold_rule": "positive_if_probability_greater_than_or_equal_to_0_5",
                "seed_derivation": {
                    "inner_cv_seed": (
                        "outer_repeat_seed + 211 + 1013 * outer_fold_number_1_based"
                    ),
                    "model_seed": (
                        "outer_repeat_seed + 200003 + 131 * outer_fold_number_1_based "
                        "+ model_family_offset"
                    ),
                    "family_offsets": {
                        "l2_logistic_regression": self.logistic_seed_offset,
                        "constrained_random_forest": self.forest_seed_offset,
                    },
                    "bootstrap_seed": "outer_repeat_seed + 500009",
                },
            },
            "preprocessing": {
                "numeric_imputation": "training_fold_median",
                "numeric_scaling_for_logistic_regression": "training_fold_standard",
                "categorical_imputation": "training_fold_most_frequent",
                "categorical_encoding": "fixed_registered_vocabulary_reference_one_hot",
                "all_transforms_fitted_inside_inner_cv_pipeline": True,
                "global_transformation_before_cv": False,
            },
            "uncertainty": {
                "method": "participant_level_percentile_bootstrap_within_each_repeat",
                "resamples": self.bootstrap_resamples,
                "interpretation": (
                    "Conditional on the fitted fold models; it does not represent refitting variability, "
                    "a future-patient confidence interval, or independent external validation."
                ),
            },
            "negative_control": {
                "method": "permute_source_labels_before_nested_cv",
                "shuffle_seeds": list(self.negative_control_seeds),
                "outer_repeats_per_shuffle": self.negative_control_outer_repeats,
                "interpretation": "smoke_test_only_not_a_formal_permutation_p_value",
                "leakage_alarm_threshold_auroc": self.leakage_alarm_threshold,
            },
        }


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(f"Registered UCI-412 research plan violates a safety invariant: {message}")


def _positive_int(value: Any, name: str) -> int:
    _require(type(value) is int and value > 0, f"{name} must be a positive integer")
    return int(value)


def load_registered_config(plan_path: Path = PLAN_PATH) -> Uci412Config:
    """Load and validate the single registered UCI-412 plan."""
    try:
        plan = json.loads(Path(plan_path).read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001 - never echo plan contents
        raise ValueError("Unable to read the registered UCI-412 research plan.") from exc
    _require(isinstance(plan, dict), "plan root must be an object")
    _require(plan.get("protocol_id") == EXPERIMENT_ID, "protocol id")
    _require(plan.get("protocol_status") == PROTOCOL_STATUS, "protocol status")
    _require(plan.get("report_banner") == REPORT_BANNER, "report banner")

    dataset = plan.get("dataset")
    _require(isinstance(dataset, dict), "dataset settings")
    _require(dataset.get("id") == DATASET_ID and dataset.get("source") == SOURCE_ID, "source scope")
    _require(dataset.get("relative_file") == SOURCE_RELATIVE_PATH, "exact permitted source path")
    _require(dataset.get("filename") == SOURCE_FILENAME, "exact permitted source filename")
    _require(dataset.get("source_profile_id") == SOURCE_PROFILE_ID, "source profile id")
    _require(tuple(dataset.get("source_columns", ())) == SOURCE_COLUMNS, "exact 56-column order")
    _require(dataset.get("target_column") == TARGET_COLUMN, "target column")
    _require(dataset.get("target_mapping") == {"Cad": 1, "Normal": 0}, "reviewed target mapping")
    _require(dataset.get("expected_row_count") == EXPECTED_ROW_COUNT, "audited row count")
    _require(
        dataset.get("expected_class_counts") == {
            "0": EXPECTED_NEGATIVE_COUNT,
            "1": EXPECTED_POSITIVE_COUNT,
        },
        "audited class counts",
    )
    _require(dataset.get("independent_cohort") is False, "source must not be labelled an independent cohort")
    _require(dataset.get("uci_411_is_same_participants") is True, "UCI-411 identity rule")

    revision = plan.get("protocol_revision")
    _require(isinstance(revision, dict), "protocol revision block")
    _require(revision.get("revision_id") == M3A_PROTOCOL_AMENDMENT_ID, "protocol revision id")
    _require(
        revision.get("change_class") == "SOURCE_VALUE_ENCODING_CORRECTION_ONLY",
        "protocol revision change class",
    )
    _require(revision.get("gate_pt_p3_status") == "CLOSED", "protocol revision must keep P-3 closed")
    _require(
        revision.get("previous_authorization_status")
        == "NOT_SUFFICIENT_FOR_THESE_BYTES_A_NEW_HUMAN_DECISION_AND_MANIFEST_ARE_REQUIRED",
        "protocol revision must state that the previous authorization is not sufficient",
    )

    source_encoding = plan.get("source_encoding")
    _require(isinstance(source_encoding, dict), "source encoding block")
    _require(source_encoding.get("register_id") == SOURCE_ENCODING_REGISTER_ID, "source encoding id")
    _require(
        tuple(source_encoding.get("numeric_binary_source_columns", ()))
        == NUMERIC_BINARY_SOURCE_COLUMNS,
        "numeric-binary source column allowlist",
    )
    _require(
        tuple(source_encoding.get("text_categorical_source_columns", ()))
        == TEXT_CATEGORICAL_SOURCE_COLUMNS,
        "text-categorical source column allowlist",
    )
    _require(
        source_encoding.get("numeric_binary_source_semantics")
        == {str(code): meaning for code, meaning in NUMERIC_BINARY_SOURCE_SEMANTICS},
        "numeric-binary source semantics",
    )
    _require(
        source_encoding.get("numeric_binary_semantics_status")
        == NUMERIC_BINARY_SEMANTICS_EVIDENCE_STATUS,
        "the provisional status of the 0/1 direction must be stated",
    )
    semantics_evidence = source_encoding.get("numeric_binary_semantics_evidence")
    _require(isinstance(semantics_evidence, dict), "the semantics evidence block must be present")
    _require(
        semantics_evidence.get("direction") == "TAO_2025_RCM_TABLE1"
        and semantics_evidence.get("representation") == "HUMAN_LOCAL_READ_ONLY_AUDIT_2026_10_24",
        "the semantics evidence must name the peer-reviewed direction source and the human audit",
    )
    _require(
        "10.31083/RCM26204" in str(semantics_evidence.get("direction_reference", "")),
        "the semantics evidence must cite the peer-reviewed direction source",
    )
    _require(
        semantics_evidence.get("official_dataset_owner_codebook")
        == "NOT_AVAILABLE_NOT_INDEPENDENTLY_VERIFIED",
        "the absence of an official dataset-owner codebook must be stated",
    )
    _require(
        semantics_evidence.get("explicit_human_acceptance_required") is True,
        "explicit human acceptance of the provisional direction must remain required",
    )
    _require(
        tuple(source_encoding.get("accepted_numeric_values", ())) == (0, 1),
        "accepted numeric source values must be exactly 0 and 1",
    )
    _require(
        source_encoding.get("global_automatic_coercion") == "FORBIDDEN",
        "global automatic conversion must be forbidden",
    )
    _require(source_encoding.get("affected_predictor_count") == 6, "six affected predictors")
    _require(source_encoding.get("unaffected_predictor_count") == 10, "ten unaffected predictors")
    _require(
        source_encoding.get("encoded_parameter_count_unchanged") is True,
        "the encoding correction may not change the encoded parameter count",
    )
    _require(
        source_encoding.get("verification_status")
        == "HUMAN_SHA256_VERIFIED_LOCAL_READ_ONLY_AUDIT_2026-10-24",
        "source encoding must be human-audit verified",
    )

    dictionary_block = plan.get("feature_dictionary")
    _require(isinstance(dictionary_block, dict), "feature dictionary settings")
    _require(dictionary_block.get("schema_id") == DICTIONARY_SCHEMA_ID, "dictionary schema id")
    _require(dictionary_block.get("schema_version") == DICTIONARY_SCHEMA_VERSION, "dictionary version")
    _require(dictionary_block.get("panel_id") == PRIMARY_PANEL_ID, "only the primary panel is executable")
    _require(dictionary_block.get("panel_version") == PRIMARY_PANEL_VERSION, "panel version")

    dictionary: FeatureDictionary = DEFAULT_DICTIONARY
    feature_names = dictionary.executable_columns()
    _require(feature_names == PRIMARY_PANEL_COLUMNS, "feature allowlist")
    numeric_features = dictionary.numeric_columns()
    categorical_features = dictionary.categorical_columns()
    category_codes = dictionary.category_codes()

    cv = plan.get("cv")
    _require(isinstance(cv, dict), "CV settings")
    _require(cv.get("outer_folds") == 5 and cv.get("inner_folds") == 5, "nested stratified 5-fold CV")
    _require(cv.get("outer_repeat_seeds") == [20261024, 20261025, 20261026, 20261027], "outer seeds")
    _require(cv.get("stratified") is True, "stratification")
    _require(cv.get("primary_inner_selection_metric") == "roc_auc", "inner selection metric")
    _require(cv.get("primary_outer_assessment_metric") == "roc_auc", "outer assessment metric")
    _require(cv.get("simplicity_preference") == "l2_logistic_regression", "simplicity rule")
    _require(cv.get("inner_auc_equivalence_tolerance") == 0.01, "selection tolerance")
    seeds = cv.get("seed_derivation")
    _require(isinstance(seeds, dict), "seed derivation block")
    _require(
        seeds.get("inner_cv_seed") == "outer_repeat_seed + 211 + 1013 * outer_fold_number_1_based",
        "inner seed derivation",
    )
    _require(
        seeds.get("model_seed")
        == "outer_repeat_seed + 200003 + 131 * outer_fold_number_1_based + model_family_offset",
        "model seed derivation",
    )
    _require(
        seeds.get("model_family_offsets")
        == {"l2_logistic_regression": 17, "constrained_random_forest": 29},
        "family seed offsets",
    )
    _require(seeds.get("bootstrap_seed") == "outer_repeat_seed + 500009", "bootstrap seed derivation")

    models = plan.get("models")
    _require(isinstance(models, dict) and tuple(models) == ALLOWED_MODEL_FAMILIES, "model family allowlist")
    _require(models["prevalence_dummy"] == {"strategy": "prior"}, "prevalence dummy")
    lr = models["l2_logistic_regression"]
    _require(
        lr == {
            "solver": "liblinear",
            "penalty": "l2",
            "C": [0.1, 1, 10],
            "max_iter": 2000,
            "class_weight": None,
        },
        "bounded L2 logistic grid",
    )
    rf = models["constrained_random_forest"]
    _require(
        rf == {
            "n_estimators": 200,
            "max_depth": [3, 5],
            "min_samples_leaf": [5, 10],
            "max_features": "sqrt",
            "class_weight": None,
        },
        "bounded constrained forest grid",
    )
    reserved = plan.get("reserved_not_implemented")
    _require(
        isinstance(reserved, dict) and tuple(reserved) == RESERVED_MODEL_FAMILIES,
        "reserved extension point must not be an active family",
    )
    _require(
        reserved["gradient_boosting_reserved"].get("status")
        == "RESERVED_EXTENSION_POINT_NOT_IMPLEMENTED",
        "reserved family status",
    )

    preprocessing = plan.get("preprocessing")
    _require(isinstance(preprocessing, dict), "preprocessing settings")
    _require(preprocessing.get("numeric_imputation") == "training_fold_median", "numeric imputation")
    _require(preprocessing.get("numeric_scaling_for_lr") == "training_fold_standard", "LR scaling")
    _require(
        preprocessing.get("categorical") == "fixed_registered_vocabulary_reference_one_hot",
        "categorical encoding",
    )
    _require(
        preprocessing.get("categorical_missing_imputation") == "training_fold_most_frequent",
        "categorical missing handling",
    )
    _require(preprocessing.get("learn_transforms_inside_inner_cv") is True, "fold-local preprocessing")
    _require(preprocessing.get("global_transformation_before_cv") == "FORBIDDEN", "no global transform")
    _require(
        preprocessing.get("missing_reason_columns") == "FORBIDDEN_NOT_RECORDED_IN_UCI412",
        "no fabricated missingness reasons",
    )
    _require(
        preprocessing.get("fake_synthetic_flag_for_real_data") == "FORBIDDEN",
        "no synthetic-to-real bypass",
    )

    metrics = plan.get("metrics")
    _require(isinstance(metrics, dict), "metric settings")
    _require(metrics.get("primary") == "roc_auc", "primary metric")
    _require(metrics.get("decision_threshold_exploratory_only") == 0.5, "fixed exploratory threshold")
    _require(metrics.get("threshold_tuning") == "FORBIDDEN", "no threshold tuning")
    _require(
        metrics.get("naive_ci_treating_repeated_oof_rows_as_independent") == "FORBIDDEN",
        "repeated-CV dependence rule",
    )
    uncertainty = metrics.get("uncertainty")
    _require(isinstance(uncertainty, dict), "uncertainty block")
    _require(
        uncertainty.get("method") == "PARTICIPANT_LEVEL_PERCENTILE_BOOTSTRAP_WITHIN_EACH_REPEAT",
        "bootstrap method",
    )
    _require(uncertainty.get("pooled_repeat_inference") == "FORBIDDEN", "no pooled repeat inference")

    negative = plan.get("negative_control")
    _require(isinstance(negative, dict), "negative control settings")
    _require(negative.get("shuffle_seeds") == [20262004, 20262005, 20262006], "shuffle seeds")
    _require(negative.get("outer_repeats_per_shuffle") == 1, "one repeat per shuffle")
    _require(
        negative.get("interpretation") == "SMOKE_TEST_NOT_FORMAL_PERMUTATION_P_VALUE",
        "negative-control interpretation",
    )
    _require(negative.get("leakage_alarm_threshold_auroc") == 0.9, "leakage alarm threshold")
    _require(negative.get("leakage_warning_threshold_auroc") == 0.7, "leakage warning threshold")

    execution = plan.get("execution")
    _require(isinstance(execution, dict), "execution settings")
    _require(execution.get("environment") == "MAINTAINER_LOCAL_WINDOWS_CPU_ONLY", "Windows-local execution")
    _require(
        execution.get("authorized_only_after_m3a_human_authorization_and_signed_local_manifest") is True,
        "separate local authorization gate",
    )
    _require(execution.get("local_output_root") == OUTPUT_ROOT_RELATIVE_PATH, "protected output root")
    _require(execution.get("patient_level_git_upload") is False, "no patient-level upload")
    _require(execution.get("external_validation_or_clinical_claims") is False, "no clinical claim")
    _require(execution.get("artifact_saved") is False, "no reusable model artifact")

    offsets = seeds["model_family_offsets"]
    config = Uci412Config(
        experiment_id=EXPERIMENT_ID,
        protocol_status=PROTOCOL_STATUS,
        report_banner=REPORT_BANNER,
        dataset_id=DATASET_ID,
        source_id=SOURCE_ID,
        source_relative_path=SOURCE_RELATIVE_PATH,
        expected_row_count=EXPECTED_ROW_COUNT,
        expected_class_counts=((0, EXPECTED_NEGATIVE_COUNT), (1, EXPECTED_POSITIVE_COUNT)),
        source_columns=SOURCE_COLUMNS,
        target_column=TARGET_COLUMN,
        negative_source_tokens=TARGET_NEGATIVE_TOKENS,
        positive_source_tokens=TARGET_POSITIVE_TOKENS,
        panel_id=PRIMARY_PANEL_ID,
        panel_version=PRIMARY_PANEL_VERSION,
        dictionary_schema_id=DICTIONARY_SCHEMA_ID,
        dictionary_schema_version=DICTIONARY_SCHEMA_VERSION,
        feature_names=feature_names,
        numeric_features=numeric_features,
        categorical_features=categorical_features,
        category_codes=tuple((name, tuple(category_codes[name])) for name in categorical_features),
        numeric_binary_source_features=dictionary.numeric_binary_source_columns(),
        source_encoding_register_id=SOURCE_ENCODING_REGISTER_ID,
        protocol_amendment_id=M3A_PROTOCOL_AMENDMENT_ID,
        outer_folds=_positive_int(cv["outer_folds"], "outer_folds"),
        inner_folds=_positive_int(cv["inner_folds"], "inner_folds"),
        outer_repeat_seeds=tuple(cv["outer_repeat_seeds"]),
        auc_equivalence_tolerance=float(cv["inner_auc_equivalence_tolerance"]),
        logistic_c_values=tuple(float(value) for value in models["l2_logistic_regression"]["C"]),
        logistic_max_iter=_positive_int(models["l2_logistic_regression"]["max_iter"], "max_iter"),
        rf_n_estimators=_positive_int(
            models["constrained_random_forest"]["n_estimators"], "n_estimators"
        ),
        rf_max_depths=tuple(int(value) for value in models["constrained_random_forest"]["max_depth"]),
        rf_min_samples_leaf=tuple(
            int(value) for value in models["constrained_random_forest"]["min_samples_leaf"]
        ),
        rf_max_features=str(models["constrained_random_forest"]["max_features"]),
        threshold=float(metrics["decision_threshold_exploratory_only"]),
        negative_control_seeds=tuple(negative["shuffle_seeds"]),
        negative_control_outer_repeats=_positive_int(
            negative["outer_repeats_per_shuffle"], "negative-control repeats"
        ),
        leakage_alarm_threshold=float(negative["leakage_alarm_threshold_auroc"]),
        leakage_warning_threshold=float(negative["leakage_warning_threshold_auroc"]),
        bootstrap_resamples=_positive_int(uncertainty["resamples"], "bootstrap resamples"),
        calibration_bins=5,
        inner_seed_offset=211,
        inner_fold_multiplier=1013,
        model_seed_offset=200003,
        model_fold_multiplier=131,
        logistic_seed_offset=int(offsets["l2_logistic_regression"]),
        forest_seed_offset=int(offsets["constrained_random_forest"]),
        bootstrap_seed_offset=500009,
    )
    _require(
        set(config.numeric_features).isdisjoint(config.categorical_features)
        and set(config.numeric_features) | set(config.categorical_features) == set(config.feature_names)
        and tuple(name for name in config.feature_names if name in config.numeric_features)
        == config.numeric_features,
        "feature order and types",
    )
    _require(
        config.numeric_binary_source_features == NUMERIC_BINARY_SOURCE_COLUMNS,
        "numeric-binary source columns must be the reviewed six, in source order",
    )
    _require(
        set(config.numeric_binary_source_features) <= set(config.categorical_features),
        "numeric-binary source columns must stay categorical (binary) model inputs",
    )
    _require(
        dict(config.category_code_map)["DM"] == (0, 1)
        and dict(config.category_code_map)["Typical Chest Pain"] == (0, 1),
        "numeric-binary source columns must encode to exactly 0/1",
    )
    return config


DEFAULT_CONFIG: Final[Uci412Config] = load_registered_config()
PLAN_SHA256_BINDING_NOTE: Final[str] = (
    "The plan file hash is bound into the local M3a authorization manifest; editing the plan "
    "without a new authorization invalidates every existing local manifest."
)
DICTIONARY_PATH_REFERENCE: Final[Path] = DICTIONARY_PATH


SMOKE_TEST_PROFILE: Final[Uci412Config] = replace(
    DEFAULT_CONFIG,
    # Reduced fit budget for the synthetic dry-run and the software tests only.
    # It preserves the registered panel, seeds scheme, preprocessing contract,
    # metric set, and negative-control wiring, but runs fewer repeats, folds,
    # trees and bootstrap resamples. The real-run entry point refuses any
    # configuration other than DEFAULT_CONFIG.
    outer_folds=3,
    inner_folds=3,
    outer_repeat_seeds=(DEFAULT_CONFIG.outer_repeat_seeds[0],),
    rf_n_estimators=40,
    rf_max_depths=(DEFAULT_CONFIG.rf_max_depths[0],),
    bootstrap_resamples=100,
    negative_control_seeds=(DEFAULT_CONFIG.negative_control_seeds[0],),
)
