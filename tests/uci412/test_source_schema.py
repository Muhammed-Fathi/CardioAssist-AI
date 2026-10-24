"""Versioned source schema, feature dictionary, and registered-plan invariants."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from research.uci412.config import (
    AUTHORIZATION_TEMPLATE_PATH,
    DEFAULT_CONFIG,
    PLAN_PATH,
    load_registered_config,
)
from research.uci412.errors import SchemaError
from research.uci412.feature_schema import (
    ADMISSION_STATUSES,
    DICTIONARY_PATH,
    EXECUTABLE_PANELS,
    PRIMARY_PANEL_COLUMNS,
    PRIMARY_PANEL_ID,
    REGISTERED_PANELS,
    FeatureDictionary,
    describe_panels,
    load_feature_dictionary,
)
from research.uci412.sample_size import planning_summary
from research.uci412.source_spec import (
    ECHO_COLUMNS,
    EXPECTED_NEGATIVE_COUNT,
    EXPECTED_POSITIVE_COUNT,
    EXPECTED_ROW_COUNT,
    PROHIBITED_PREDICTORS,
    SOURCE_COLUMNS,
    SOURCE_FILENAME,
    TARGET_COLUMN,
    column_group,
)


def _dictionary_payload() -> dict:
    return json.loads(DICTIONARY_PATH.read_text(encoding="utf-8"))


def test_exact_registered_source_profile() -> None:
    assert EXPECTED_ROW_COUNT == 303
    assert EXPECTED_POSITIVE_COUNT == 216
    assert EXPECTED_NEGATIVE_COUNT == 87
    assert EXPECTED_POSITIVE_COUNT + EXPECTED_NEGATIVE_COUNT == EXPECTED_ROW_COUNT
    assert SOURCE_FILENAME == "Z-Alizadeh sani dataset.xlsx"
    assert len(SOURCE_COLUMNS) == 56
    assert SOURCE_COLUMNS[-1] == TARGET_COLUMN == "Cath"
    assert len(set(SOURCE_COLUMNS)) == 56
    assert not {"LAD", "LCX", "RCA"} & set(SOURCE_COLUMNS)


def test_column_groups_match_the_audited_structure() -> None:
    groups = [column_group(column) for column in SOURCE_COLUMNS[:-1]]
    assert groups.count("demographic") == 17
    assert groups.count("symptom_and_examination") == 14
    assert groups.count("ecg") == 7
    assert groups.count("laboratory_and_echocardiography") == 17
    assert column_group(TARGET_COLUMN) == "target_label"


def test_dictionary_covers_each_source_column_exactly_once() -> None:
    dictionary = load_feature_dictionary()
    assert tuple(dictionary.features) == SOURCE_COLUMNS
    assert sorted(spec.position for spec in dictionary.features.values()) == list(range(1, 57))
    assert dictionary.schema_version


def test_primary_panel_is_an_explicit_ordered_exclusion_reviewed_allowlist() -> None:
    dictionary = load_feature_dictionary()
    assert PRIMARY_PANEL_COLUMNS == (
        "Age",
        "Sex",
        "BMI",
        "DM",
        "HTN",
        "Current Smoker",
        "EX-Smoker",
        "FH",
        "DLP",
        "BP",
        "PR",
        "Typical Chest Pain",
        "Atypical",
        "Nonanginal",
        "Exertional CP",
        "Dyspnea",
    )
    assert dictionary.panel(PRIMARY_PANEL_ID).columns == PRIMARY_PANEL_COLUMNS
    assert not set(PRIMARY_PANEL_COLUMNS) & PROHIBITED_PREDICTORS
    assert TARGET_COLUMN not in PRIMARY_PANEL_COLUMNS


def test_ecg_laboratory_and_echo_features_are_not_in_the_basic_panel() -> None:
    dictionary = load_feature_dictionary()
    for spec in dictionary.features.values():
        if spec.column in ECHO_COLUMNS:
            # Echocardiography timing relative to angiography is source-unverified:
            # these columns stay unregistered for any panel and cannot be modelled.
            assert spec.panels == ()
            assert spec.admission == "EXCLUDED_ECHO_TIMING_UNVERIFIED"
            assert spec.exclusion_reason
        if spec.column in {"Q Wave", "St Elevation", "St Depression", "Tinversion", "LVH"}:
            assert "uci412_basic_clinical_v1" not in spec.panels
    assert dictionary.panel("uci412_basic_clinical_v1").executable is True


def test_every_excluded_feature_records_why_it_is_excluded() -> None:
    dictionary = load_feature_dictionary()
    for spec in dictionary.features.values():
        assert spec.admission in ADMISSION_STATUSES
        if not spec.panels:
            assert spec.exclusion_reason, spec.column
        if spec.admission == "ADMITTED_PRIMARY_PANEL":
            if spec.is_numeric:
                assert spec.unit
                assert spec.plausible_range is not None
            else:
                assert spec.vocabulary
            assert spec.availability_at_decision_time
            assert spec.leakage_risk
            assert spec.evidence
            assert spec.uncertainty


def test_dictionary_edit_cannot_add_an_unreviewed_predictor(tmp_path: Path) -> None:
    payload = _dictionary_payload()
    payload["panels"][0]["columns"].append("Q Wave")
    payload["features"]["Q Wave"]["panels"].append("uci412_basic_clinical_v1")
    tampered = tmp_path / "dictionary.json"
    tampered.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(SchemaError):
        load_feature_dictionary(tampered)


def test_dictionary_edit_cannot_reorder_or_drop_a_feature(tmp_path: Path) -> None:
    payload = _dictionary_payload()
    del payload["features"]["Age"]
    tampered = tmp_path / "dictionary.json"
    tampered.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(SchemaError):
        load_feature_dictionary(tampered)


def test_dictionary_rejects_a_prohibited_angiography_column(tmp_path: Path) -> None:
    payload = _dictionary_payload()
    payload["features"]["LAD"] = dict(payload["features"]["Cath"], column="LAD")
    tampered = tmp_path / "dictionary.json"
    tampered.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(SchemaError):
        load_feature_dictionary(tampered)


def test_dictionary_type_is_stable() -> None:
    assert isinstance(load_feature_dictionary(), FeatureDictionary)


def test_registered_plan_matches_the_frozen_config() -> None:
    config = load_registered_config()
    assert config == DEFAULT_CONFIG
    assert config.expected_counts == {0: 87, 1: 216}
    assert config.feature_names == PRIMARY_PANEL_COLUMNS
    assert config.outer_folds == 5
    assert config.inner_folds == 5
    assert config.outer_repeat_seeds == (20261024, 20261025, 20261026, 20261027)
    assert config.threshold == 0.5
    assert config.logistic_c_values == (0.1, 1.0, 10.0)
    assert config.rf_max_depths == (3, 5)
    assert config.rf_min_samples_leaf == (5, 10)
    assert config.negative_control_seeds == (20262004, 20262005, 20262006)
    assert config.bootstrap_resamples >= 200


def _mutated_plan(tmp_path: Path, mutate) -> Path:
    plan = json.loads(PLAN_PATH.read_text(encoding="utf-8"))
    mutate(plan)
    target = tmp_path / "plan.json"
    target.write_text(json.dumps(plan), encoding="utf-8")
    return target


@pytest.mark.parametrize(
    "mutate",
    [
        lambda plan: plan["cv"].update(outer_folds=4),
        lambda plan: plan["metrics"].update(decision_threshold_exploratory_only=0.4),
        lambda plan: plan["cv"].update(inner_folds=10),
        lambda plan: plan["models"].update(extra_model={"C": [1000]}),
        lambda plan: plan["dataset"].update(relative_file="data/raw/uci-45/cleveland.xlsx"),
        lambda plan: plan["dataset"].update(target_mapping={"CAD": 1, "Normal": 0}),
        lambda plan: plan["dataset"].update(source_columns=plan["dataset"]["source_columns"][:-1]),
        lambda plan: plan["dataset"].update(expected_class_counts={"0": 0, "1": 303}),
        lambda plan: plan["execution"].update(artifact_saved=True),
    ],
)
def test_tampered_plan_is_rejected(tmp_path: Path, mutate) -> None:
    tampered = _mutated_plan(tmp_path, mutate)
    with pytest.raises(ValueError):
        load_registered_config(tampered)


def test_unknown_model_family_cannot_be_added_through_the_plan(tmp_path: Path) -> None:
    tampered = _mutated_plan(
        tmp_path, lambda plan: plan["models"].update(gradient_boosting_reserved_eager={"n_estimators": 400})
    )
    with pytest.raises(ValueError):
        load_registered_config(tampered)


def test_config_cannot_be_mutated_at_runtime() -> None:
    with pytest.raises(Exception):
        DEFAULT_CONFIG.outer_folds = 2  # type: ignore[misc]


def test_authorization_template_present_and_non_authorizing() -> None:
    template = json.loads(AUTHORIZATION_TEMPLATE_PATH.read_text(encoding="utf-8"))
    assert template["authorization_status"] != "AUTHORIZED_FOR_LOCAL_INTERNAL_RESEARCH"
    assert template["supervisor_signoff_claimed"] is False
    assert template["gate_pt_status"] == "CLOSED_REQUIRES_SUPERVISOR_SIGNOFF_P3"
    assert "REPLACE" in template["maintainer_approval_comment_exact"]
    assert template["dataset_id"] == "DA-A1"
    assert template["panel_schema_id"] == PRIMARY_PANEL_ID


def test_executable_panel_and_parameter_count_are_frozen() -> None:
    dictionary = load_feature_dictionary()
    assert EXECUTABLE_PANELS == (PRIMARY_PANEL_ID,)
    assert dictionary.encoded_parameter_count() == 16
    assert len(dictionary.numeric_columns()) == 4
    assert len(dictionary.categorical_columns()) == 12


def test_blocked_panels_cannot_execute_and_state_their_blockers() -> None:
    dictionary = load_feature_dictionary()
    for panel_id in REGISTERED_PANELS:
        panel = dictionary.panel(panel_id)
        if panel_id == PRIMARY_PANEL_ID:
            assert panel.executable is True
        else:
            assert panel.executable is False
            assert panel.status == "REGISTERED_BLOCKED"
            assert panel.blockers


def test_resting_ecg_columns_exist_only_in_the_blocked_ecg_panel() -> None:
    dictionary = load_feature_dictionary()
    for column in ("Q Wave", "St Elevation", "St Depression", "Tinversion", "LVH", "Poor R Progression", "BBB"):
        spec = dictionary.feature(column)
        assert spec.panels == ("uci412_basic_plus_resting_ecg_v1",)
        assert dictionary.panel("uci412_basic_plus_resting_ecg_v1").executable is False


def test_review_description_is_patient_free_and_lists_blockers() -> None:
    description = describe_panels()
    payload = json.dumps(description)
    assert description["executable_parameter_count"] == 16
    assert description["feature_dictionary"]["executable_panel"]["panel_id"] == PRIMARY_PANEL_ID
    assert "uci412_basic_plus_laboratory_v1" in payload
    assert "value" not in description["feature_dictionary"]["executable_panel"]


def test_sample_size_planning_is_r2_independent_and_not_an_adequacy_claim() -> None:
    summary = planning_summary()
    assert summary["participants"] == 303
    assert summary["events"] == 216
    assert summary["outcome_proportion_required_n"] == 315
    assert summary["outcome_proportion_criterion_met"] is False
    assert summary["clinical_adequacy_claimed"] is False
    assert summary["uses_observed_model_performance"] is False
