"""RH-04.7/.8: assemble *existing* synthetic evidence and a real one-shot rehearsal.

No patient records, input-feature values, artifact loading options, real study,
new predictor, or HTTP endpoint. This module never claims clinical validation.
The public document is an aggregate manifest, not the protected ledger itself.

    python -m research.report_assembly --ledger /private/new-ledger.json --output /private/new-report.json
    python -m research.report_assembly --validate /private/new-report.json
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
from typing import Any, Mapping

from ai.ai10_synthetic_transport import (
    EVIDENCE as LOCKED_EVIDENCE,
    SyntheticLockedSitePlan,
    _sha as locked_digest,
    run_ai10_synthetic_locked_site,
    validate_fake_identities,
)
from ai.errors import CohortGovernanceError
from ai.filesystem_security import (
    ensure_private_directory,
    is_reparse_or_symlink,
    relative_posix_if_within_directory,
    write_new_private_file,
)
from ai.report_comparison import read_report, report_bytes
from ai.research_evidence import PACK_VERSION, build_evidence_pack
from ai.research_facade import canonical_response_digest
from ai.training import ExternalEvaluationLedger
from research.intake import offline_demo_card_mapping as cards
from research.intake import offline_fixture_pack as fixtures

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = "cardioassist.rh04.synthetic_research_report/v1"
STATUS_ORDER = ("SYNTHETIC_RESULT", "ABSTAIN", "UNAVAILABLE", "ERROR")
SHA256 = re.compile(r"^[0-9a-f]{64}$")
SHA1 = re.compile(r"^[0-9a-f]{40}$")
BLOCKED = tuple(sorted(set(fixtures.inputs()) - fixtures.ACTIVE))
NO_GO = "NOT_PERFORMED_NOT_ELIGIBLE_IN_CURRENT_RESEARCH_SCOPE"
LIMITATIONS = (
    "All output is fabricated and offline; no patient or Hungary record was read.",
    "Ledger refusal is software evidence, not independent-person/site validation.",
    "Checksums provide integrity comparison, not signatures or medical approval.",
    "Numeric ML outputs may vary across OS; structural/security/status rules are exact.",
    "No clinical probability, external AUROC, medical advice or serving provider.",
)
DEPENDENCY_NAMES = frozenset({
    "numpy", "scipy", "scikit-learn", "joblib", "threadpoolctl",
    "openpyxl", "et-xmlfile",
})
ENVIRONMENT_FIELDS = frozenset({
    "os", "architecture", "python", "implementation", "numeric_libraries",
})


def _sha_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _shape(obj: Any) -> Any:
    """Schema shape only: never include submitted or predicted values."""
    if isinstance(obj, Mapping):
        return {key: _shape(value) for key, value in sorted(obj.items())}
    if isinstance(obj, list):
        return [_shape(value) for value in obj]
    if obj is None:
        return "null"
    if type(obj) is bool:
        return "bool"
    if type(obj) in (float, int):
        return "number"
    if isinstance(obj, str):
        return "string"
    raise ValueError("Unsupported fixture structure.")


def _case_manifest() -> tuple[list[dict[str, Any]], dict[str, str]]:
    """Bind all reviewed case projections, without any values or identities."""
    data = json.loads(fixtures.PACK.read_text(encoding="utf-8"))
    if (
        data["bindings"] != fixtures.bindings()
        or data["requests"] != fixtures.inputs()
        or canonical_response_digest(data) != fixtures.PACK_SHA256
        or cards.validate() != 29
    ):
        raise ValueError("Stale fixture pack or approved consumer mapping.")
    card_doc = cards.load_mapping()
    card_cases = card_doc["offline_case_cards"]
    cases = data["cases"]
    if len(cases) != 29 or len(card_cases) != 29:
        raise ValueError("Incomplete reviewed fixture inventory.")
    output: list[dict[str, Any]] = []
    for case, card in zip(cases, card_cases):
        expected = case["expected"]
        status = expected["status"]
        if (
            status not in STATUS_ORDER
            or card["case_id"] != case["id"]
            or card["status"] != status
            or card["expected_projection_sha256"] != canonical_response_digest(expected)
        ):
            raise ValueError("Invalid fixture status/card projection binding.")
        outcomes = expected["outcomes"]
        if status != "SYNTHETIC_RESULT" and any(
            outcome["score"] is not None for outcome in outcomes
        ):
            raise ValueError("A refused fixture carried a research score.")
        output.append({
            "case_id": case["id"],
            "route_id": case["route"],
            "status": status,
            "outcome_statuses": [o["status"] for o in outcomes],
            "expected_projection_sha256": canonical_response_digest(expected),
            "structural_sha256": canonical_response_digest(_shape(expected)),
            "score_allowed": status == "SYNTHETIC_RESULT",
        })
    if set(c["status"] for c in output) != set(STATUS_ORDER):
        raise ValueError("Four original facade statuses not covered.")
    return output, {
        "fixture_canonical_sha256": fixtures.PACK_SHA256,
        "fixture_bytes_sha256": _sha_file(fixtures.PACK),
        "demo_card_bytes_sha256": _sha_file(cards.MAPPING_PATH),
        "crosswalk_sha256": data["bindings"]["crosswalk_sha256"],
        "registry_sha256": data["bindings"]["registry_sha256"],
        "response_schema": data["bindings"]["response_schema"],
        "demo_card_schema": cards.SCHEMA_VERSION,
    }


def _rehearse_ledger(ledger_path: Path) -> dict[str, Any]:
    """Real generated fabricated-site run + existing protected-ledger refusals."""
    plan = SyntheticLockedSitePlan()
    report = run_ai10_synthetic_locked_site(
        ledger_path=ledger_path, plan=plan, expected_plan_sha256=plan.sha256
    )
    if (
        report["status"] != "SYNTHETIC_LOCKED_SITE_EXERCISE_COMPLETE"
        or report["evidence_class"] != LOCKED_EVIDENCE
        or report["sha256"] != locked_digest(
            {k: v for k, v in report.items() if k != "sha256"}
        )
        or report["real_external_validation_performed"] is not False
        or report["real_hungary_accessed"] is not False
        or report["ledger_status"] != "COMPLETED"
    ):
        raise ValueError("Synthetic ledger run did not complete with a valid digest.")

    ledger = ExternalEvaluationLedger(ledger_path)
    entries = ledger.list_entries()
    if (
        len(entries) != 1
        or entries[0]["status"] != "COMPLETED"
        or not SHA256.fullmatch(str(entries[0].get("result_summary_sha256", "")))
    ):
        raise ValueError("Protected one-shot completion receipt unavailable.")
    entry = entries[0]
    try:
        ledger.reserve_evaluation(**{
            k: entry[k] for k in (
                "protocol_id", "model_id", "model_version", "external_cohort_id",
                "external_dataset_id", "preprocessor_sha256", "calibrator_sha256",
                "cohort_fingerprint_sha256",
            )
        })
    except CohortGovernanceError as exc:
        replay_refusal = exc.code
    else:
        raise ValueError("Duplicate ledger consumption was not rejected.")
    if replay_refusal != "one_shot_external_evaluation_already_consumed":
        raise ValueError("Unexpected ledger replay decision.")

    try:
        run_ai10_synthetic_locked_site(
            ledger_path=ledger_path, plan=plan, expected_plan_sha256="0" * 64
        )
    except CohortGovernanceError as exc:
        plan_refusal = exc.code
    else:
        raise ValueError("Mismatched research plan was not rejected.")
    if plan_refusal != "ai10_plan_digest_mismatch":
        raise ValueError("Unexpected research-plan rejection.")
    try:
        validate_fake_identities(["ai10_fake_dev_a"], ["ai10_fake_dev_a"])
    except CohortGovernanceError as exc:
        overlap_refusal = exc.code
    else:
        raise ValueError("Overlap was not rejected.")
    if overlap_refusal != "ai10_overlapping_fixture_id":
        raise ValueError("Unexpected overlap rejection.")
    insufficient = run_ai10_synthetic_locked_site(
        ledger_path=ledger_path, plan=SyntheticLockedSitePlan(n_external=8)
    )
    if (
        insufficient["status"] != "INSUFFICIENT_EVIDENCE"
        or insufficient["ledger_slot_consumed"] is not False
        or insufficient["sha256"] != locked_digest({
            k: v for k, v in insufficient.items() if k != "sha256"
        })
        or len(ledger.list_entries()) != 1
    ):
        raise ValueError("Insufficient sample case consumed a ledger slot.")
    return {
        "schema_version": report["schema_version"],
        "evidence_class": report["evidence_class"],
        "status": report["status"],
        "run_report_sha256": report["sha256"],
        "plan_sha256": report["plan_sha256"],
        "panel_sha256": report["panel_sha256"],
        "target_id": report["target_id"],
        "protected_ledger_status": entry["status"],
        "protected_ledger_result_summary_sha256": entry["result_summary_sha256"],
        "ledger_entries": 1,
        "replay_refusal": replay_refusal,
        "plan_refusal": plan_refusal,
        "overlap_refusal": overlap_refusal,
        "insufficient_status": insufficient["status"],
        "insufficient_ledger_slot_consumed": False,
        "real_external_validation_performed": False,
    }


def assemble(*, ledger_path: Path, with_lime: bool = False) -> dict[str, Any]:
    """Produce an evidence manifest only after the actual synthetic runs pass."""
    cases, sources = _case_manifest()
    # Existing executable 29-case pack is the authority; no new prediction path.
    if fixtures.validate(json.loads(fixtures.PACK.read_text(encoding="utf-8"))) != 29:
        raise ValueError("Actual 29-case facade replay incomplete.")
    evidence = build_evidence_pack(with_lime=with_lime)
    if (
        evidence["schema_version"] != PACK_VERSION
        or evidence["evidence_status"] != "SYNTHETIC_E2E_COMPLETE"
        or evidence["report"]["summary"]["stages_succeeded"] != 8
        or canonical_response_digest({
            k: v for k, v in evidence.items() if k != "pack_sha256"
        }) != evidence["pack_sha256"]
    ):
        raise ValueError("Existing AI-12.1 evidence is incomplete.")
    ledger = _rehearse_ledger(ledger_path)
    doc = {
        "schema_version": SCHEMA,
        "status": "SYNTHETIC_REPORT_ASSEMBLY_COMPLETE",
        "evidence_grade": "SYNTHETIC_ENGINEERING_ONLY_NOT_CLINICAL",
        "source_commit": evidence["reproducibility"]["source"]["git_commit"],
        "environment": evidence["reproducibility"]["environment"],
        "dependencies": evidence["reproducibility"]["dependencies"],
        "source_bindings": sources,
        "ai12_evidence": {
            "schema_version": evidence["schema_version"],
            "pack_sha256": evidence["pack_sha256"],
            "demo_deterministic_sha256": evidence["report"]["deterministic_sha256"],
            "stages_passed": 8,
        },
        "facade": {
            "cases_validated_by_actual_replay": 29,
            "statuses": list(STATUS_ORDER),
            "routes": sorted(fixtures.inputs()),
            "blocked_routes": list(BLOCKED),
            "cases": cases,
        },
        "ai10_ledger": ledger,
        "mock_backend": "MOCK_SYNTHETIC_SEPARATE_STATIC_CONTRACT_ONLY",
        "real_studies": {"AI-9.2": NO_GO, "AI-10.2": NO_GO},
        "limitations": list(LIMITATIONS),
    }
    doc["report_sha256"] = canonical_response_digest(doc)
    validate(doc)
    return doc


def _git_sha() -> str:
    value = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True, capture_output=True,
        check=True, timeout=10
    ).stdout.strip()
    if not SHA1.fullmatch(value):
        raise ValueError("Source revision invalid.")
    return value


def validate(doc: Mapping[str, Any]) -> None:
    """Strict consumer validation; checksum != authenticated evidence of a run."""
    keys = {
        "schema_version", "status", "evidence_grade", "source_commit",
        "environment", "dependencies", "source_bindings", "ai12_evidence",
        "facade", "ai10_ledger", "mock_backend", "real_studies",
        "limitations", "report_sha256",
    }
    if type(doc) is not dict or set(doc) != keys:
        raise ValueError("Unknown report structure.")
    if doc["schema_version"] != SCHEMA or doc["status"] != "SYNTHETIC_REPORT_ASSEMBLY_COMPLETE":
        raise ValueError("Wrong synthetic schema/status.")
    if doc["evidence_grade"] != "SYNTHETIC_ENGINEERING_ONLY_NOT_CLINICAL":
        raise ValueError("Unsupported evidence grade.")
    if doc["source_commit"] != _git_sha():
        raise ValueError("Stale report source SHA.")
    if doc["report_sha256"] != canonical_response_digest({
        k: v for k, v in doc.items() if k != "report_sha256"
    }):
        raise ValueError("Report integrity mismatch.")
    cases, bindings = _case_manifest()
    facade = doc["facade"]
    if (
        type(facade) is not dict
        or set(facade) != {
            "cases_validated_by_actual_replay", "statuses", "routes",
            "blocked_routes", "cases",
        }
        or facade["cases_validated_by_actual_replay"] != 29
        or facade["statuses"] != list(STATUS_ORDER)
        or facade["routes"] != sorted(fixtures.inputs())
        or facade["blocked_routes"] != list(BLOCKED)
        or facade["cases"] != cases
        or doc["source_bindings"] != bindings
    ):
        raise ValueError("Offline source or case binding drift.")
    ai12 = doc["ai12_evidence"]
    if (
        type(ai12) is not dict
        or set(ai12) != {
            "schema_version", "pack_sha256", "demo_deterministic_sha256", "stages_passed"
        }
        or ai12["schema_version"] != PACK_VERSION
        or ai12["stages_passed"] != 8
        or not all(SHA256.fullmatch(str(ai12[k])) for k in (
            "pack_sha256", "demo_deterministic_sha256"
        ))
    ):
        raise ValueError("AI-12.1 evidence binding invalid.")
    locked = doc["ai10_ledger"]
    if (
        type(locked) is not dict
        or set(locked) != {
            "schema_version", "evidence_class", "status", "run_report_sha256",
            "plan_sha256", "panel_sha256", "target_id", "protected_ledger_status",
            "protected_ledger_result_summary_sha256", "ledger_entries",
            "replay_refusal", "plan_refusal", "overlap_refusal",
            "insufficient_status", "insufficient_ledger_slot_consumed",
            "real_external_validation_performed",
        }
        or locked["schema_version"] != "cardioassist.ai.synthetic_locked_site/v1"
        or locked["evidence_class"] != LOCKED_EVIDENCE
        or locked["status"] != "SYNTHETIC_LOCKED_SITE_EXERCISE_COMPLETE"
        or locked["plan_sha256"] != SyntheticLockedSitePlan().sha256
        or locked["target_id"] != SyntheticLockedSitePlan().target_id
        or locked["panel_sha256"] != SyntheticLockedSitePlan().panel_sha256
        or locked["protected_ledger_status"] != "COMPLETED"
        or locked["ledger_entries"] != 1
        or locked["replay_refusal"] != "one_shot_external_evaluation_already_consumed"
        or locked["plan_refusal"] != "ai10_plan_digest_mismatch"
        or locked["overlap_refusal"] != "ai10_overlapping_fixture_id"
        or locked["insufficient_status"] != "INSUFFICIENT_EVIDENCE"
        or locked["insufficient_ledger_slot_consumed"] is not False
        or locked["real_external_validation_performed"] is not False
        or not all(SHA256.fullmatch(str(locked[k])) for k in (
            "run_report_sha256", "panel_sha256",
            "protected_ledger_result_summary_sha256",
        ))
    ):
        raise ValueError("Locked synthetic ledger proof invalid.")
    if (
        doc["mock_backend"] != "MOCK_SYNTHETIC_SEPARATE_STATIC_CONTRACT_ONLY"
        or doc["real_studies"] != {"AI-9.2": NO_GO, "AI-10.2": NO_GO}
        or doc["limitations"] != list(LIMITATIONS)
        or type(doc["environment"]) is not dict
        or set(doc["environment"]) != ENVIRONMENT_FIELDS
        or doc["environment"].get("os") not in ("Linux", "Windows", "Darwin")
        or not all(
            isinstance(doc["environment"].get(k), str)
            and re.fullmatch(r"[a-zA-Z0-9_. +()-]{1,80}", doc["environment"][k])
            for k in ("os", "python", "architecture", "implementation")
        )
        or type(doc["environment"].get("numeric_libraries")) is not list
        or len(doc["environment"]["numeric_libraries"]) > 32
        or any(
            type(lib) is not dict
            or set(lib) != {"internal_api", "version", "architecture", "num_threads"}
            or type(lib["num_threads"]) is not int
            or lib["num_threads"] < 1
            or not isinstance(lib["internal_api"], str)
            or not all(
                lib[k] is None or (
                    isinstance(lib[k], str)
                    and re.fullmatch(r"[a-zA-Z0-9_. +()-]{1,80}", lib[k])
                ) for k in ("architecture", "version")
            )
            for lib in doc["environment"]["numeric_libraries"]
        )
        or type(doc["dependencies"]) is not dict
        or set(doc["dependencies"]) != DEPENDENCY_NAMES
        or not all(
            isinstance(v, str) and re.fullmatch(r"[a-zA-Z0-9_.+!-]{1,80}", v)
            for v in doc["dependencies"].values()
        )
    ):
        raise ValueError("Unsafe or incomplete report semantics.")
    wire = report_bytes(dict(doc)).decode("ascii")
    if any(s in wire.lower() for s in (
        "patient_ref", "record_ref", "signing_key", "private_key",
        "bundle_dir", "trusted_local_root", "external_cohort_id",
        "medical_advice", "local_path",
    )):
        raise ValueError("Disallowed input, path or authorization material.")


def _fresh_external_path(path: Path, purpose: str) -> Path:
    raw = path.expanduser()
    if is_reparse_or_symlink(raw) or is_reparse_or_symlink(raw.parent):
        raise ValueError("Links and reparse points are not permitted.")
    candidate = raw.resolve(strict=False)
    if (
        candidate.suffix.lower() != ".json"
        or relative_posix_if_within_directory(candidate, ROOT) is not None
        or candidate.exists()
        or is_reparse_or_symlink(candidate.parent)
    ):
        raise ValueError("A new external JSON file is required.")
    return candidate


def _strict_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON key.")
        result[key] = value
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ledger", type=Path, help="Fresh private synthetic ledger outside checkout")
    parser.add_argument("--output", type=Path, help="Fresh private JSON report outside checkout")
    parser.add_argument("--validate", type=Path, help="Validate an existing JSON report without executing")
    parser.add_argument("--with-lime", action="store_true", help="Run the optional synthetic LIME")
    args = parser.parse_args(argv)
    try:
        if args.validate is not None:
            if args.ledger is not None or args.output is not None or args.with_lime:
                raise ValueError("Validation takes only an existing JSON file.")
            wire = read_report(args.validate)
            doc = json.loads(wire, object_pairs_hook=_strict_object,
                             parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))
            validate(doc)
            print(json.dumps({"status": "VALID_SYNTHETIC_REPORT",
                              "report_sha256": doc["report_sha256"]}, sort_keys=True))
            return 0
        if args.ledger is None:
            raise ValueError("Fresh synthetic ledger is mandatory.")
        ledger = _fresh_external_path(args.ledger, "ledger")
        output = _fresh_external_path(args.output, "output") if args.output else None
        if output is not None and ledger == output:
            raise ValueError("Ledger/report path collision.")
        doc = assemble(ledger_path=ledger, with_lime=args.with_lime)
        wire = report_bytes(doc)
        if output is not None:
            ensure_private_directory(output.parent)
            write_new_private_file(output, wire)
            print(json.dumps({"status": doc["status"], "report_sha256": doc["report_sha256"]},
                             sort_keys=True))
        else:
            sys.stdout.buffer.write(wire)
        return 0
    except Exception:
        # No user-submitted paths, exceptions, identifiers or values in refusal.
        print('{"status":"FAIL_CLOSED","code":"rh04_report_refused"}', file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
