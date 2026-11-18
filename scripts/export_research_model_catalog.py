"""Export the read-only AI-11.2 research model catalog. No model is loaded."""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


class _Parser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        self.exit(2, "catalog_invalid_arguments\n")


def main(argv: list[str] | None = None) -> int:
    parser = _Parser(description=__doc__)
    parser.add_argument("--format", choices=("json",), default="json")
    parser.add_argument("--output", type=Path, help="NEW file outside repository; no overwrite")
    args = parser.parse_args(argv)

    # Import only after validating the command, and never from backend/app.
    from ai.research_catalog import catalog_json_bytes

    payload = catalog_json_bytes()
    if args.output is None:
        sys.stdout.buffer.write(payload)
        return 0

    # A catalog is metadata. Output inside the checkout would dirty the repo
    # and potentially replace a source file; forbid it altogether.
    target = args.output.resolve()
    if target == ROOT or ROOT in target.parents or not target.parent.is_dir():
        print("catalog_invalid_output_location", file=sys.stderr)
        return 2

    created = False
    try:
        fd = os.open(str(target), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        created = True
        with os.fdopen(fd, "wb") as out:
            out.write(payload)
            out.flush()
            os.fsync(out.fileno())
        return 0
    except OSError:
        if created:
            try:
                target.unlink()
            except OSError:
                pass
        print("catalog_export_failed", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
