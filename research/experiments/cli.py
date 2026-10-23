"""Command-line entry point for the guarded D-047 local runner."""
from __future__ import annotations

import argparse
import json
import sys
from typing import Sequence

from research.experiments.config import DEFAULT_CONFIG, REPOSITORY_ROOT
from research.experiments.errors import ExperimentRunnerError, RuntimeGuardError
from research.experiments.runner import run_authorized_local_experiment, run_synthetic_dry_run
from research.experiments.safety import run_preflight


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m research.experiments",
        description=(
            "D-047 guarded local CAD experiment runner. Synthetic dry-run is safe anywhere; "
            "real source parsing/fitting is Windows-local and separately authorized."
        ),
    )
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("dry-run", help="run the registered pipeline on generated in-memory synthetic fixtures only")
    commands.add_parser("preflight", help="check local authorization/provenance/storage without parsing source rows")
    commands.add_parser("run", help="prompt a human, then run the authorized local experiment")
    return parser


def _confirm_real_local_run() -> None:
    if not sys.stdin.isatty():
        raise RuntimeGuardError("Real-data execution requires an interactive local Windows console.")
    print("D-047 local-only exploratory run. Gate PT P-3 remains CLOSED.")
    print("This will parse the protected Cleveland source and fit only the registered nested-CV models.")
    print("No patient-care use, external validation, cloud, CI, or remote upload is permitted.")
    phrase = "RUN D047 CLEVELAND LOCALLY"
    try:
        answer = input(f"Type exactly '{phrase}' to continue: ")
    except EOFError as exc:
        raise RuntimeGuardError("Interactive confirmation was not received; no source rows were parsed.") from exc
    if answer != phrase:
        raise RuntimeGuardError("Human confirmation did not match; no source rows were parsed.")


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "dry-run":
            result = run_synthetic_dry_run(config=DEFAULT_CONFIG)
            print(json.dumps(result, indent=2, sort_keys=True))
            return 0
        if args.command == "preflight":
            preflight = run_preflight(repo_root=REPOSITORY_ROOT, config=DEFAULT_CONFIG)
            print(json.dumps({
                "status": "PREFLIGHT_PASS",
                "experiment_id": DEFAULT_CONFIG.experiment_id,
                "report_banner_required_on_real_output": DEFAULT_CONFIG.report_banner,
                "source_sha256_and_byte_size_verified": True,
                "source_rows_parsed": False,
                "model_fitting_started": False,
                "source_relative_path": DEFAULT_CONFIG.source_relative_path,
                "code_commit_sha": preflight.current_git_commit,
                "output_root": "data/experiments",
            }, indent=2, sort_keys=True))
            return 0
        if args.command == "run":
            _confirm_real_local_run()
            result = run_authorized_local_experiment(
                repo_root=REPOSITORY_ROOT,
                config=DEFAULT_CONFIG,
            )
            print(json.dumps(result, indent=2, sort_keys=True))
            return 0
        raise RuntimeError("Unknown experiment command.")
    except ExperimentRunnerError as exc:
        print(f"FAIL CLOSED: {exc}", file=sys.stderr)
        return 2
    except Exception as exc:
        # Avoid echoing arbitrary library exceptions that might include local
        # file contents, absolute paths, or diagnostic values.
        print(
            f"FAIL CLOSED: {type(exc).__name__}; no clinical or external-validation claim is produced.",
            file=sys.stderr,
        )
        return 2
