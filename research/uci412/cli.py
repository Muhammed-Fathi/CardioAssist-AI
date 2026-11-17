"""Command-line entry point for the guarded UCI-412 research benchmark."""
from __future__ import annotations

import argparse
import json
import sys
from typing import Sequence

from research.uci412.config import (
    DEFAULT_CONFIG,
    M3A_PROTOCOL_AMENDMENT_ID,
    PROPOSAL_RELATIVE_PATH,
    REPOSITORY_ROOT,
)
from research.uci412.errors import Uci412Error
from research.uci412.feature_schema import describe_panels
from research.uci412.runner import run_authorized_local_experiment, run_synthetic_dry_run
from research.uci412.safety import run_preflight
from research.uci412.sample_size import planning_summary
from research.uci412.readiness import assess_readiness

CONFIRMATION_PHRASE = "RUN M3A UCI412 LOCALLY"


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m research.uci412",
        description=(
            "UCI-412 source-specific CAD research benchmark. The dry-run is synthetic-only and safe "
            "anywhere; preflight/run are Windows-local and require a separate human authorization."
        ),
    )
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser(
        "describe",
        help="print the registered panels, exclusions, sample-size planning status, and blockers",
    )
    commands.add_parser(
        "dry-run",
        help="exercise the registered pipeline on generated in-memory synthetic rows only",
    )
    commands.add_parser(
        "preflight",
        help="check local authorization/provenance/storage without opening workbook rows",
    )
    commands.add_parser("readiness", help="evidence-only AI-8R review; never grants authorization")
    commands.add_parser("run", help="prompt a human, then run the authorized local benchmark")
    return parser


def _confirm_real_local_run() -> None:
    if not sys.stdin.isatty():
        raise SystemExit(
            "FAIL CLOSED: real-data execution requires an interactive local Windows console."
        )
    print("UCI-412 internal research benchmark. Gate PT P-3 remains CLOSED.")
    print("This will open the protected workbook and fit only the registered nested-CV models.")
    print("No patient-care use, external validation, cloud, CI, or remote upload is permitted.")
    try:
        answer = input(f"Type exactly '{CONFIRMATION_PHRASE}' to continue: ")
    except EOFError:
        raise SystemExit("FAIL CLOSED: interactive confirmation was not received.") from None
    if answer != CONFIRMATION_PHRASE:
        raise SystemExit("FAIL CLOSED: human confirmation did not match; no rows were parsed.")


def _describe() -> dict[str, object]:
    specification = describe_panels()
    specification["sample_size_planning"] = planning_summary()
    specification["authorization"] = {
        "proposal_document": PROPOSAL_RELATIVE_PATH.as_posix(),
        "authorization_comment_required": "AUTHORIZE-M3A-UCI412-INTERNAL-RESEARCH",
        "current_status": "PROPOSED_NOT_AUTHORIZED_LOCALLY",
        "local_manifest_required": "data/manifests/uci412_internal_research_authorization.local.json",
    }
    specification["protocol_amendment"] = {
        "amendment_id": M3A_PROTOCOL_AMENDMENT_ID,
        "document": "docs/research/gate-pt/10_m3a_uci412_source_encoding_AMENDMENT_A1.md",
        "change_class": "SOURCE_VALUE_ENCODING_CORRECTION_ONLY",
        "evidence_addendum_id": "M3A-AMENDMENT-A1-E1",
        "direction_evidence": "TAO_2025_RCM_TABLE1 (doi:10.31083/RCM26204, Table 1)",
        "direction_official_codebook_confirmed": False,
        "previous_authorization_reusable": False,
    }
    specification["blockers_before_first_real_run"] = [
        "Human maintainer ratification comment on the amendment PR plus its human-approved merge.",
        "A NEW locally signed, hash-bound M3a authorization manifest binding the amended proposal, plan, "
        "feature dictionary (schema 1.1.0), panel (1.1.0), amendment id and source hash. The pre-amendment "
        "manifest cannot be reused.",
        "Completed D-046 DA-A1 provenance and license chain for the exact workbook bytes.",
        "Human acceptance of residual item S-9: the six numeric 0/1 columns are read as "
        "0 = absent/false and 1 = present/true. The direction is stated by peer-reviewed secondary "
        "literature (Tao et al. 2025, doi:10.31083/RCM26204, Table 1), but no official dataset-owner "
        "codebook confirms it.",
        "Human review of the exact workbook header spellings and category tokens for the 43 non-admitted "
        "columns (the 12 admitted categorical predictors were verified by the 2026-10-24 human audit).",
        "Human acceptance that the R²-dependent sample-size criteria remain NOT ASSESSED.",
    ]
    return specification


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "describe":
            print(json.dumps(_describe(), indent=2, sort_keys=True))
            return 0
        if args.command == "dry-run":
            result = run_synthetic_dry_run()
            print(json.dumps(result, indent=2, sort_keys=True))
            return 0
        if args.command == "readiness":
            result = assess_readiness(repo_root=REPOSITORY_ROOT)
            print(json.dumps(result, indent=2, sort_keys=True))
            # Readiness is an evidence-only diagnostic, never a green light to run.
            # Exit 2 even for a future reviewed panel + successful local preflight:
            # authorization and actual execution remain separate human actions.
            return 2
        if args.command == "preflight":
            preflight = run_preflight(repo_root=REPOSITORY_ROOT, config=DEFAULT_CONFIG)
            print(
                json.dumps(
                    {
                        "status": "PREFLIGHT_PASS",
                        "experiment_id": DEFAULT_CONFIG.experiment_id,
                        "report_banner_required_on_real_output": DEFAULT_CONFIG.report_banner,
                        "source_sha256_and_byte_size_verified": True,
                        "source_rows_parsed": False,
                        "model_fitting_started": False,
                        "code_commit_sha": preflight.current_git_commit,
                        "authorization_comment_exact": preflight.authorization[
                            "authorization_comment_exact"
                        ],
                        "output_root": "data/uci412-experiments",
                    },
                    indent=2,
                    sort_keys=True,
                )
            )
            return 0
        if args.command == "run":
            _confirm_real_local_run()
            result = run_authorized_local_experiment(
                repo_root=REPOSITORY_ROOT, config=DEFAULT_CONFIG
            )
            print(json.dumps(result, indent=2, sort_keys=True))
            return 0
        raise RuntimeError("Unknown UCI-412 command.")
    except Uci412Error as exc:
        print(f"FAIL CLOSED: {exc}", file=sys.stderr)
        return 2
    except SystemExit as exc:
        print(str(exc), file=sys.stderr)
        return 2
    except Exception as exc:  # noqa: BLE001 - never echo library diagnostics or paths
        print(
            f"FAIL CLOSED: {type(exc).__name__}; no clinical or external-validation claim is produced.",
            file=sys.stderr,
        )
        return 2
