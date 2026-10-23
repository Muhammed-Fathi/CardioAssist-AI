"""Versioned, bounded configuration for the D-047 local experiment runner.

The JSON plan is a registered proposal, not an authorization token. Real-data
execution separately requires a completed local D-047 manifest and the D-046
read-only provenance chain.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any

from research.audit.registry import UCI_45_CONVENTIONAL_14_COLUMNS

PACKAGE_ROOT = Path(__file__).resolve().parent
REPOSITORY_ROOT = PACKAGE_ROOT.parents[1]
PLAN_PATH = PACKAGE_ROOT / "cleveland_d047_exploratory_plan.v0.1.json"
PROTOCOL_RELATIVE_PATH = Path(
    "docs/research/gate-pt/02_d047_internal_exploratory_cleveland_PROTOCOL_PROPOSED.md"
)
AUTHORIZATION_TEMPLATE_PATH = PACKAGE_ROOT / "internal_exploratory_authorization.template.json"

D047_AUTHORIZATION_COMMENT = "AUTHORIZE-D047-INTERNAL-CLEVELAND"
D047_AUTHORIZING_PR_NUMBER = 31
D047_AUTHORIZING_MAINTAINER = "Muhammed Fathi"
D047_AUTHORIZING_MERGED_AT_UTC = "2026-10-22T23:06:35+00:00"
D047_AUTHORIZING_MERGE_SHA = "434e49a37e6e60b8b91498dde0f9d02dc1af18de"
D047_REPORT_BANNER = "INTERNAL_EXPLORATORY_NOT_SUPERVISOR_APPROVED"
D047_AUTHORIZATION_STATUS = "AUTHORIZED_FOR_LOCAL_INTERNAL_EXPLORATORY_CLEVELAND"
D047_LOCAL_SIGNATURE_ATTESTATION = (
    "I have reviewed and authorize this exact hash-bound local D-047 internal "
    "exploratory experiment. I understand Gate PT P-3 remains CLOSED."
)

ALLOWED_MODEL_FAMILIES = (
    "prevalence_dummy",
    "l2_logistic_regression",
    "constrained_random_forest",
)
ALLOWED_OPERATIONS = (
    "read_only_source_loading",
    "internal_model_fitting",
    "internal_nested_cv",
    "internal_model_family_comparison",
    "internal_negative_control",
    "internal_aggregate_metrics_report",
)
FORBIDDEN_OPERATIONS = (
    "remote_patient_data_upload",
    "model_serving",
    "clinical_decision",
    "external_validation_claim",
    "multi_cohort_pooling",
    "unapproved_dataset_ingestion",
    "patient_level_git_commit",
)
PROHIBITED_PREDICTORS = frozenset({
    "num", "ca", "thal", "Cath", "LAD", "LCX", "RCA",
    "lmt", "ladprox", "laddist", "diag", "cxmain", "ramus", "om1", "om2",
    "rcaprox", "rcadist", "cmo", "cday", "cyr",
    "id", "ccf", "name", "site", "patient_id", "patient_ref", "mrn",
    "wearable_heart_rate", "heart_rate_bpm", "steps", "wearable_ecg",
    "monitoring_observation",
})


@dataclass(frozen=True, slots=True)
class ExperimentConfig:
    """Validated in-code projection of the committed D-047 plan."""

    experiment_id: str
    report_banner: str
    source_relative_path: str
    expected_row_count: int
    expected_binary_target_counts: tuple[tuple[int, int], ...]
    source_columns: tuple[str, ...]
    target_column: str
    negative_source_labels: tuple[int, ...]
    positive_source_labels: tuple[int, ...]
    feature_names: tuple[str, ...]
    numeric_features: tuple[str, ...]
    categorical_features: tuple[str, ...]
    categorical_source_code_order: tuple[tuple[str, tuple[int, ...]], ...]
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
    inner_seed_offset: int
    inner_fold_multiplier: int
    model_seed_offset: int
    model_fold_multiplier: int
    logistic_seed_offset: int
    forest_seed_offset: int
    calibration_bins: int

    @property
    def expected_class_counts(self) -> dict[int, int]:
        return dict(self.expected_binary_target_counts)

    @property
    def category_codes(self) -> dict[str, tuple[int, ...]]:
        return dict(self.categorical_source_code_order)

    def model_configuration(self) -> dict[str, Any]:
        """Return the exact registered model and preprocessing configuration."""
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
                    "fixed_vocabulary_one_hot_drop_first",
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
                    "fixed_vocabulary_one_hot_drop_first",
                ],
            },
        }

    def as_report_dict(self) -> dict[str, Any]:
        """A JSON-friendly record of frozen CV, target and feature settings."""
        return {
            "experiment_id": self.experiment_id,
            "report_banner": self.report_banner,
            "source_relative_path": self.source_relative_path,
            "expected_row_count": self.expected_row_count,
            "expected_binary_target_counts": {
                str(k): v for k, v in self.expected_binary_target_counts
            },
            "source_columns": list(self.source_columns),
            "target_mapping": {
                "source_zero_to_binary_zero": list(self.negative_source_labels),
                "source_one_through_four_to_binary_one": list(self.positive_source_labels),
                "binary_labels": {"0": "num=0", "1": "num=1,2,3,4"},
            },
            "predictors": list(self.feature_names),
            "numeric_predictors": list(self.numeric_features),
            "categorical_source_code_order": {
                key: list(values) for key, values in self.categorical_source_code_order
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
                        "outer_repeat_seed + 97 + 1009 * outer_fold_number_1_based"
                    ),
                    "model_seed": (
                        "outer_repeat_seed + 100003 + 101 * outer_fold_number_1_based "
                        "+ family_offset"
                    ),
                    "family_offsets": {
                        "l2_logistic_regression": self.logistic_seed_offset,
                        "constrained_random_forest": self.forest_seed_offset,
                    },
                },
            },
            "preprocessing": {
                "numeric_imputation": "training_fold_median",
                "numeric_scaling_for_logistic_regression": "training_fold_standard",
                "categorical_imputation": "training_fold_most_frequent",
                "categorical_encoding": "fixed_source_vocabulary_reference_one_hot",
                "missing_token": "? -> NaN; no synthetic missing-reason labels",
                "all_transforms_fitted_inside_inner_cv_pipeline": True,
            },
            "negative_control": {
                "method": "permute_binary_source_labels_before_nested_cv",
                "shuffle_seeds": list(self.negative_control_seeds),
                "outer_repeats_per_shuffle": self.negative_control_outer_repeats,
                "interpretation": "smoke_test_only_not_a_formal_permutation_p_value",
            },
        }


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(f"Registered D-047 experiment plan violates a safety invariant: {message}")


def _as_positive_int(value: Any, name: str) -> int:
    _require(type(value) is int and value > 0, f"{name} must be a positive integer")
    return value


def load_registered_config(plan_path: Path = PLAN_PATH) -> ExperimentConfig:
    """Load and validate the single registered plan; callers cannot supply grids."""
    try:
        plan = json.loads(plan_path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise ValueError("Unable to read the registered D-047 experiment plan.") from exc
    _require(isinstance(plan, dict), "plan root must be an object")
    _require(plan.get("protocol_id") == "CAI-T1-D047-CLEVELAND-EXPLORATORY-V0.1", "protocol ID")
    _require(plan.get("report_banner") == D047_REPORT_BANNER, "report banner")

    dataset = plan.get("dataset")
    _require(isinstance(dataset, dict), "dataset settings")
    source_columns = tuple(dataset.get("processed_source_columns", ()))
    _require(source_columns == UCI_45_CONVENTIONAL_14_COLUMNS, "exact UCI-45 14-column order")
    _require(dataset.get("id") == "DA-A2" and dataset.get("source") == "UCI-45", "source scope")
    _require(
        dataset.get("relative_file") == "data/raw/uci-45/processed.cleveland.data",
        "exact permitted source path",
    )
    target_column = dataset.get("original_target_column")
    _require(target_column == "num" and source_columns[-1] == target_column, "target column position")
    _require(dataset.get("negative_source_label") == [0], "negative source target mapping")
    _require(dataset.get("positive_source_labels") == [1, 2, 3, 4], "positive source target mapping")
    _require(
        dataset.get("primary_predictors") == ["age", "sex", "cp", "trestbps", "restecg"],
        "five-field predictor allowlist",
    )
    feature_names = tuple(dataset["primary_predictors"])
    _require(
        not ({"num", "ca", "thal", "Cath", "LAD", "LCX", "RCA", "site", "patient_id"}
             & set(feature_names)),
        "target leakage, angiography, identifier and site predictors are prohibited",
    )
    prohibited = set(dataset.get("prohibited_predictors", ()))
    _require(prohibited == PROHIBITED_PREDICTORS, "complete leakage/angiography/identifier/wearable registry")
    _require(not (prohibited & set(feature_names)), "prohibited predictors are not in the feature allowlist")
    _require(
        dataset.get("numeric_predictors") == ["age", "trestbps"],
        "numeric predictor types",
    )
    numeric_features = tuple(dataset["numeric_predictors"])
    categorical_features = tuple(name for name in feature_names if name not in numeric_features)
    raw_category_order = dataset.get("categorical_source_code_order")
    _require(isinstance(raw_category_order, dict), "categorical source-code registry")
    expected_category_order = {
        "sex": (0, 1),
        "cp": (1, 2, 3, 4),
        "restecg": (0, 1, 2),
    }
    category_order: list[tuple[str, tuple[int, ...]]] = []
    for field in categorical_features:
        observed = raw_category_order.get(field)
        _require(isinstance(observed, list), f"fixed vocabulary for {field}")
        codes = tuple(observed)
        _require(codes == expected_category_order[field], f"fixed ordered vocabulary for {field}")
        category_order.append((field, codes))
    _require(
        set(raw_category_order) == set(categorical_features),
        "no undeclared categorical fields",
    )

    expected_binary_counts_raw = dataset.get("expected_binary_target_counts")
    _require(
        expected_binary_counts_raw == {"0": 164, "1": 139},
        "audited binary target counts (aggregate only)",
    )
    expected_binary_counts = ((0, 164), (1, 139))

    cv = plan.get("cv")
    _require(isinstance(cv, dict), "CV settings")
    _require(cv.get("outer_folds") == 5 and cv.get("inner_folds") == 5, "nested stratified 5-fold CV")
    _require(cv.get("outer_repeat_seeds") == [20261023, 20261024, 20261025, 20261026], "outer seeds")
    _require(cv.get("stratified") is True, "stratification")
    _require(cv.get("primary_inner_selection_metric") == "roc_auc", "inner selection metric")
    _require(cv.get("primary_outer_assessment_metric") == "roc_auc", "outer assessment metric")
    _require(cv.get("simplicity_preference") == "l2_logistic_regression", "simplicity rule")
    _require(cv.get("inner_auc_equivalence_tolerance") == 0.01, "selection tolerance")
    seed_config = cv.get("seed_derivation")
    _require(isinstance(seed_config, dict), "frozen seed derivation")
    _require(
        seed_config.get("inner_cv_seed") == "outer_repeat_seed + 97 + 1009 * outer_fold_number_1_based",
        "inner seed derivation",
    )
    _require(
        seed_config.get("model_seed") == (
            "outer_repeat_seed + 100003 + 101 * outer_fold_number_1_based + model_family_offset"
        ),
        "estimator seed derivation",
    )
    model_offsets = seed_config.get("model_family_offsets")
    _require(
        model_offsets == {"l2_logistic_regression": 11, "constrained_random_forest": 23},
        "estimator family seed offsets",
    )
    _require(
        seed_config.get("label_shuffle_outer_seed") == "the corresponding label_shuffle_seed",
        "negative-control split seed derivation",
    )

    models = plan.get("models")
    _require(isinstance(models, dict) and tuple(models) == ALLOWED_MODEL_FAMILIES, "only the allowlisted model families")
    _require(models["prevalence_dummy"] == {"strategy": "prior"}, "prevalence dummy")
    lr = models["l2_logistic_regression"]
    _require(
        lr == {
            "solver": "liblinear", "penalty": "l2", "C": [0.1, 1, 10],
            "max_iter": 2000, "class_weight": None,
        },
        "bounded L2 logistic-regression grid",
    )
    rf = models["constrained_random_forest"]
    _require(
        rf == {
            "n_estimators": 200, "max_depth": [3, 5], "min_samples_leaf": [5, 10],
            "max_features": "sqrt", "class_weight": None,
        },
        "bounded constrained random-forest grid",
    )

    preprocessing = plan.get("preprocessing")
    _require(isinstance(preprocessing, dict), "preprocessing settings")
    _require(preprocessing.get("numeric_imputation") == "training_fold_median", "numeric imputation")
    _require(preprocessing.get("numeric_scaling_for_lr") == "training_fold_standard", "LR scaling")
    _require(preprocessing.get("categorical") == "source_vocab_reference_one_hot", "categorical encoding")
    _require(
        preprocessing.get("categorical_missing_imputation") == "training_fold_most_frequent",
        "categorical missing-value handling",
    )
    _require(preprocessing.get("learn_transforms_inside_inner_cv") is True, "fold-local preprocessing")
    _require(
        preprocessing.get("missing_reason_columns") == "FORBIDDEN_NOT_RECORDED_IN_UCI45",
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
    _require(
        metrics.get("naive_ci_treating_4_repeated_oof_rows_as_independent") == "FORBIDDEN",
        "repeated-CV dependence warning",
    )
    _require(
        metrics.get("calibration_diagnostics") == [
            "calibration_in_the_large_intercept", "calibration_slope_and_intercept",
            "five_bin_quantile_reliability_curve_when_estimable",
        ],
        "calibration diagnostic set",
    )

    negative_control = plan.get("negative_control")
    _require(isinstance(negative_control, dict), "negative-control settings")
    _require(
        negative_control.get("method") == "permute_source_labels_on_exploratory_local_run",
        "label-shuffle negative control",
    )
    _require(
        negative_control.get("shuffle_seeds") == [20262001, 20262002, 20262003],
        "negative-control seeds",
    )
    _require(negative_control.get("outer_repeats_per_shuffle") == 1, "one repeat per shuffle")
    _require(
        negative_control.get("interpretation") == "SMOKE_TEST_NOT_FORMAL_PERMUTATION_P_VALUE",
        "negative-control interpretation",
    )

    execution = plan.get("execution")
    _require(isinstance(execution, dict), "execution settings")
    _require(execution.get("environment") == "MAINTAINER_LOCAL_WINDOWS_CPU_ONLY", "Windows-local execution")
    _require(
        execution.get("authorized_only_after_d047_human_comment_merge_and_signed_local_manifest") is True,
        "separate local authorization gate",
    )
    _require(execution.get("local_output_root") == "data/experiments", "protected local output root")
    _require(execution.get("patient_level_git_upload") is False, "no remote patient-level output")
    _require(execution.get("external_validation_or_clinical_claims") is False, "no clinical/external claim")

    model_settings = models
    config = ExperimentConfig(
        experiment_id=plan["protocol_id"],
        report_banner=plan["report_banner"],
        source_relative_path=dataset["relative_file"],
        expected_row_count=_as_positive_int(dataset["expected_row_count"], "expected_row_count"),
        expected_binary_target_counts=expected_binary_counts,
        source_columns=source_columns,
        target_column=target_column,
        negative_source_labels=(0,),
        positive_source_labels=(1, 2, 3, 4),
        feature_names=feature_names,
        numeric_features=numeric_features,
        categorical_features=categorical_features,
        categorical_source_code_order=tuple(category_order),
        outer_folds=_as_positive_int(cv["outer_folds"], "outer_folds"),
        inner_folds=_as_positive_int(cv["inner_folds"], "inner_folds"),
        outer_repeat_seeds=tuple(cv["outer_repeat_seeds"]),
        auc_equivalence_tolerance=float(cv["inner_auc_equivalence_tolerance"]),
        logistic_c_values=tuple(model_settings["l2_logistic_regression"]["C"]),
        logistic_max_iter=_as_positive_int(model_settings["l2_logistic_regression"]["max_iter"], "logistic max_iter"),
        rf_n_estimators=_as_positive_int(model_settings["constrained_random_forest"]["n_estimators"], "rf n_estimators"),
        rf_max_depths=tuple(model_settings["constrained_random_forest"]["max_depth"]),
        rf_min_samples_leaf=tuple(model_settings["constrained_random_forest"]["min_samples_leaf"]),
        rf_max_features=model_settings["constrained_random_forest"]["max_features"],
        threshold=float(metrics["decision_threshold_exploratory_only"]),
        negative_control_seeds=tuple(negative_control["shuffle_seeds"]),
        negative_control_outer_repeats=_as_positive_int(
            negative_control["outer_repeats_per_shuffle"], "negative-control repeats"
        ),
        inner_seed_offset=97,
        inner_fold_multiplier=1009,
        model_seed_offset=100003,
        model_fold_multiplier=101,
        logistic_seed_offset=model_offsets["l2_logistic_regression"],
        forest_seed_offset=model_offsets["constrained_random_forest"],
        calibration_bins=5,
    )
    _require(
        set(config.numeric_features).isdisjoint(config.categorical_features)
        and set(config.numeric_features) | set(config.categorical_features) == set(config.feature_names)
        and tuple(name for name in config.feature_names if name in config.numeric_features)
        == config.numeric_features,
        "feature order and types",
    )
    return config


DEFAULT_CONFIG = load_registered_config()
