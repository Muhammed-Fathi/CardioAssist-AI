"""AI-9.1: generate a fixed matched synthetic clinical-vs-labs comparison.

No dataset input, patient record, model bundle, real-labs route or HTTP provider.
Only generates in-process fabricated records on CPU.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


class _Parser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        self.exit(2, '{"status":"FAIL_CLOSED","code":"invalid_arguments"}\n')


def main(argv: list[str] | None = None) -> int:
    parser = _Parser(description=__doc__)
    parser.add_argument("--format", choices=("json",), default="json")
    parser.add_argument("--output", type=Path, help="new external JSON path only; never overwrite")
    args = parser.parse_args(argv)

    target = None
    if args.output is not None:
        try:
            target = args.output.resolve(strict=False)
            if (
                target == ROOT or ROOT in target.parents
                or target.suffix.lower() != ".json"
                or not target.parent.is_dir()
                or target.exists()
            ):
                print('{"status":"FAIL_CLOSED","code":"invalid_output"}', file=sys.stderr)
                return 2
        except (OSError, ValueError):
            print('{"status":"FAIL_CLOSED","code":"invalid_output"}', file=sys.stderr)
            return 2

    from ai.ai9_paired_synthetic import run_ai9_synthetic_comparison

    try:
        report = run_ai9_synthetic_comparison()
        payload = (json.dumps(report, sort_keys=True, indent=2,
                              allow_nan=False, ensure_ascii=True) + "\n").encode("utf-8")
    except Exception:
        # Do not echo input paths or stack traces in the research CLI.
        print('{"status":"FAIL_CLOSED","code":"synthetic_comparison_failed"}', file=sys.stderr)
        return 1
    if target is None:
        sys.stdout.buffer.write(payload)
        return 0
    created = False
    try:
        fd = os.open(str(target), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        created = True
        with os.fdopen(fd, "wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
    except OSError:
        if created:
            try:
                target.unlink()
            except OSError:
                pass
        print('{"status":"FAIL_CLOSED","code":"output_write_failed"}', file=sys.stderr)
        return 1
    print(json.dumps({
        "status": report["status"],
        "evidence_class": report["evidence_class"],
        "n_matched": report["cohort"]["n_matched"],
        "sha256": report["sha256"],
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
