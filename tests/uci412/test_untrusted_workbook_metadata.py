"""Adversarial tests: untrusted workbook metadata must never leak.

A workbook's worksheet names and column headers are author-controlled text. A
real file could carry a participant name, a record number, a local path, or any
other string in those positions. These tests inject one unmistakable synthetic
secret into each such position and prove it cannot reach a user-visible error
message, a dataset audit object, or the aggregate report.

Every fixture here is generated in memory or written to an isolated temporary
directory under the registered synthetic file name. No real UCI-412 byte, row,
or patient-level value is read, written, or asserted on.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from research.audit.xlsx_reader import SheetData, write_synthetic_xlsx
from research.uci412 import cli
from research.uci412.adapter import (
    WORKSHEET_IDENTIFIER,
    load_authorized_dataset,
    parse_workbook,
    sha256_bytes,
    sheet_from_rows,
    validate_workbook_structure,
)
from research.uci412.config import DEFAULT_CONFIG
from research.uci412.errors import SourceFormatError
from research.uci412.reporting import (
    REPORT_TYPE,
    StorageProtectionError,
    validate_aggregate_report,
)
from research.uci412.source_spec import SOURCE_FILENAME
from tests.uci412.conftest import synthetic_rows

SECRET = "ZZQC-SYNTHETIC-PARTICIPANT-SECRET-7F3A9C"


def _workbook():
    headers, rows = synthetic_rows()
    return headers, tuple(tuple(row) for row in rows)


def _minimal_report(audit: object) -> dict[str, object]:
    """Smallest mapping that passes every aggregate-report invariant."""
    return {
        "report_banner": DEFAULT_CONFIG.report_banner,
        "report_type": REPORT_TYPE,
        "formal_supervisor_approval": False,
        "independent_external_validation_performed": False,
        "clinical_or_patient_care_use_authorized": False,
        "model_artifact_saved": False,
        "cohort": {"aggregate_source_audit": audit},
    }


def _assert_secret_absent(text: str) -> None:
    assert SECRET not in text, "untrusted workbook metadata escaped into a user-visible surface"


def test_unexpected_header_secret_is_never_echoed() -> None:
    headers, rows = _workbook()
    poisoned = (f"{SECRET} Echo Score",) + headers[1:]
    workbook = sheet_from_rows(poisoned, rows)

    with pytest.raises(SourceFormatError) as excinfo:
        validate_workbook_structure(workbook)

    # The registered identifier that went missing is still named, because it is a
    # static reviewed string rather than workbook content.
    message = str(excinfo.value)
    _assert_secret_absent(message)
    _assert_secret_absent(repr(excinfo.value))
    assert "Age" in message
    assert "1 unregistered or prohibited column(s) at header position(s) [1]" in message


def test_accepted_workbook_headers_stay_out_of_default_reprs() -> None:
    """Even an accepted header string must not appear in a repr/log surface."""
    headers, rows = _workbook()
    # A worksheet name is the only place a secret can survive validation, so it is
    # used here to prove the accepted objects still do not print it.
    parsed = validate_workbook_structure(
        sheet_from_rows(headers, rows, sheet_name=f"{SECRET} Worksheet")
    )
    dataset = parse_workbook(parsed)

    for surface in (repr(parsed), repr(dataset), repr(dataset.audit)):
        _assert_secret_absent(surface)
    assert "array" not in repr(dataset).lower()


def test_missing_registered_columns_are_named_but_untrusted_ones_are_not() -> None:
    headers, rows = _workbook()
    poisoned = tuple(
        f"{SECRET} Weight" if name == "Weight" else name for name in headers
    )
    workbook = sheet_from_rows(poisoned, rows)

    with pytest.raises(SourceFormatError) as excinfo:
        validate_workbook_structure(workbook)

    message = str(excinfo.value)
    _assert_secret_absent(message)
    assert "1 registered column(s) missing: ['Weight']" in message
    assert "workbook-supplied column names are withheld" in message


def test_unexpected_header_positions_are_capped() -> None:
    headers, rows = _workbook()
    poisoned = headers[:-1] + tuple(f"{SECRET}-{index}" for index in range(30))
    workbook = sheet_from_rows(poisoned, rows)

    with pytest.raises(SourceFormatError) as excinfo:
        validate_workbook_structure(workbook)

    message = str(excinfo.value)
    _assert_secret_absent(message)
    assert "30 unregistered or prohibited column(s)" in message
    assert "(+20 more)" in message
    assert len(message) < 1_000


def test_worksheet_name_secret_is_not_in_audit_or_dataset_repr() -> None:
    headers, rows = _workbook()
    workbook = sheet_from_rows(headers, rows, sheet_name=f"{SECRET} Worksheet")

    parsed = validate_workbook_structure(workbook)
    dataset = parse_workbook(parsed)

    _assert_secret_absent(repr(parsed))
    _assert_secret_absent(repr(dataset.audit))
    assert dataset.audit["data_worksheet_identifier"] == WORKSHEET_IDENTIFIER
    assert dataset.audit["data_worksheet_ordinal"] == 1
    assert dataset.audit["workbook_supplied_sheet_and_header_names_withheld"] is True
    validate_aggregate_report(_minimal_report(dict(dataset.audit)))


def test_extra_blank_sheet_with_secret_name_is_tolerated_without_leaking() -> None:
    headers, rows = _workbook()
    extras = (SheetData(name=f"{SECRET} Notes", headers=("Note",), rows=()),)
    workbook = sheet_from_rows(headers, rows, other_sheets=extras)

    dataset = parse_workbook(validate_workbook_structure(workbook))

    assert dataset.audit["other_sheet_count"] == 1
    _assert_secret_absent(repr(dataset.audit))
    _assert_secret_absent(repr(dataset))


def test_two_data_sheets_error_reports_counts_only() -> None:
    headers, rows = _workbook()
    extras = (
        SheetData(name=f"{SECRET} Secondary", headers=("Note",), rows=(("x",),)),
    )
    workbook = sheet_from_rows(headers, rows, other_sheets=extras)

    with pytest.raises(SourceFormatError) as excinfo:
        validate_workbook_structure(workbook)

    message = str(excinfo.value)
    _assert_secret_absent(message)
    assert "found 2" in message
    assert "worksheet names are withheld" in message


def test_reader_level_failure_with_secret_sheet_name_is_wrapped_safely(
    tmp_path: Path,
) -> None:
    """A malformed workbook must not leak its sheet name through the reader error."""
    source = tmp_path / SOURCE_FILENAME
    write_synthetic_xlsx(
        source,
        [(f"{SECRET} Broken", ("Age", ""), (("1", "x"),))],
    )
    digest = sha256_bytes(source.read_bytes())

    with pytest.raises(SourceFormatError) as excinfo:
        load_authorized_dataset(source, expected_sha256=digest)

    message = str(excinfo.value)
    _assert_secret_absent(message)
    assert "could not be parsed" in message


def test_rejected_workbook_keeps_secret_out_of_cli_stderr(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    source = tmp_path / SOURCE_FILENAME
    headers, rows = _workbook()
    write_synthetic_xlsx(
        source,
        [
            (
                f"{SECRET} Worksheet",
                (f"{SECRET} Echo",) + tuple(headers[1:]),
                [list(row) for row in rows],
            )
        ],
    )
    digest = sha256_bytes(source.read_bytes())
    with pytest.raises(SourceFormatError) as excinfo:
        load_authorized_dataset(source, expected_sha256=digest)

    def _raise_after_confirmation(**_: object) -> None:
        raise excinfo.value

    monkeypatch.setattr(cli, "_confirm_real_local_run", lambda: None)
    monkeypatch.setattr(cli, "run_authorized_local_experiment", _raise_after_confirmation)

    exit_code = cli.main(["run"])
    captured = capsys.readouterr()

    assert exit_code == 2
    assert "FAIL CLOSED" in captured.err
    _assert_secret_absent(captured.err)
    _assert_secret_absent(captured.out)


@pytest.mark.parametrize(
    "raw_key",
    ["sheet_name", "worksheet_name", "data_sheet_name", "header_names", "unexpected_columns"],
)
def test_report_validator_rejects_reintroduced_workbook_metadata(raw_key: str) -> None:
    report = _minimal_report({raw_key: SECRET})

    with pytest.raises(StorageProtectionError) as excinfo:
        validate_aggregate_report(report)

    _assert_secret_absent(str(excinfo.value))
    assert "untrusted workbook metadata" in str(excinfo.value)


def test_static_worksheet_identifier_is_the_only_permitted_label() -> None:
    headers, rows = _workbook()
    dataset = parse_workbook(
        validate_workbook_structure(
            sheet_from_rows(headers, rows, sheet_name=f"{SECRET} Sheet")
        )
    )

    labels = [
        value
        for key, value in dataset.audit.items()
        if "worksheet" in key or "sheet" in key
    ]
    assert WORKSHEET_IDENTIFIER in labels
    assert all(SECRET not in str(label) for label in labels)
