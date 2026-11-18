"""AI-10.1: synthetic locked-site rehearsal CLI, never real Hungary evaluation."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from ai.errors import AiPipelineError
from ai.ai10_synthetic_transport import (
    SyntheticLockedSitePlan,
    run_ai10_synthetic_locked_site,
)
from ai.filesystem_security import (
    ensure_private_directory,
    is_reparse_or_symlink,
    relative_posix_if_within_directory,
    write_new_private_file,
)

ROOT = Path(__file__).resolve().parents[1]


def _check_external_new_path(path: Path, *, purpose: str) -> Path:
    candidate = path.expanduser().resolve(strict=False)
    if relative_posix_if_within_directory(candidate, ROOT) is not None:
        raise ValueError(f"{purpose} must be outside the Git checkout.")
    if candidate.exists() or is_reparse_or_symlink(candidate):
        raise ValueError(f"{purpose} must be a fresh ordinary file, not an existing file or link.")
    if is_reparse_or_symlink(candidate.parent):
        raise ValueError(f"{purpose} parent cannot be a symlink or Windows junction.")
    return candidate


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Single-shot fabricated site evaluation: no real patient/site data."
    )
    parser.add_argument("--ledger", required=True, type=Path,
                        help="New protected one-shot ledger outside the Git checkout")
    parser.add_argument("--output", type=Path,
                        help="Optional NEW aggregate JSON file outside the Git checkout")
    parser.add_argument("--seed", type=int, default=20261118)
    parser.add_argument("--n-development", type=int, default=96)
    parser.add_argument("--n-external", type=int, default=48)
    args = parser.parse_args(argv)

    try:
        ledger = _check_external_new_path(args.ledger, purpose="Ledger")
        output = (
            _check_external_new_path(args.output, purpose="Report")
            if args.output is not None else None
        )
        if output is not None and output == ledger:
            raise ValueError("Report and ledger cannot be the same path.")
        plan = SyntheticLockedSitePlan(
            seed=args.seed,
            n_development=args.n_development,
            n_external=args.n_external,
        )
        report = run_ai10_synthetic_locked_site(
            ledger_path=ledger, plan=plan,
            expected_plan_sha256=plan.sha256,
        )
        raw = json.dumps(
            report, indent=2, sort_keys=True, ensure_ascii=True, allow_nan=False
        ) + "\n"
        if output is not None:
            ensure_private_directory(output.parent)
            write_new_private_file(output, raw.encode("utf-8"))
            print(json.dumps({
                "status": report["status"],
                "evidence_class": report["evidence_class"],
                "report_sha256": report["sha256"],
            }, sort_keys=True))
        else:
            print(raw, end="")
        return 0
    except (AiPipelineError, ValueError, OSError) as exc:
        # No private path or caller record values are echoed.
        print(f"AI-10.1 refused: {type(exc).__name__}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
