"""Command-line surface: safe commands anywhere, guarded commands fail closed here."""
from __future__ import annotations

import json

import pytest

from research.uci412 import cli


def test_describe_is_read_only_and_lists_blockers(capsys) -> None:
    assert cli.main(["describe"]) == 0
    output = json.loads(capsys.readouterr().out)
    assert output["authorization"]["current_status"] == "PROPOSED_NOT_AUTHORIZED_LOCALLY"
    assert output["authorization"]["local_manifest_required"].endswith(
        "uci412_internal_research_authorization.local.json"
    )
    assert output["executable_parameter_count"] == 16
    assert output["blockers_before_first_real_run"]
    assert output["sample_size_planning"]["clinical_adequacy_claimed"] is False


def test_dry_run_is_synthetic_only(capsys) -> None:
    assert cli.main(["dry-run"]) == 0
    output = json.loads(capsys.readouterr().out)
    assert output["status"] == "PASS"
    assert output["synthetic_scope"] == "SYNTHETIC_SOFTWARE_FIXTURE_NOT_UCI_DATA"
    assert output["real_data_path_opened"] is False
    assert output["report_or_prediction_files_written"] is False
    assert output["metrics_generated_for_medical_or_benchmark_use"] is False
    assert output["fit_profile"]["real_run_requires_default_config"] is True


def test_preflight_fails_closed_off_windows(capsys) -> None:
    assert cli.main(["preflight"]) == 2
    captured = capsys.readouterr()
    assert "FAIL CLOSED" in captured.err
    assert "Windows-local only" in captured.err


def test_run_requires_an_interactive_console(capsys) -> None:
    assert cli.main(["run"]) == 2
    captured = capsys.readouterr()
    assert "FAIL CLOSED" in captured.err


def test_confirmation_phrase_is_exact() -> None:
    assert cli.CONFIRMATION_PHRASE == "RUN M3A UCI412 LOCALLY"


def test_missing_command_exits_with_usage_error() -> None:
    with pytest.raises(SystemExit) as excinfo:
        cli.main([])
    assert excinfo.value.code == 2
