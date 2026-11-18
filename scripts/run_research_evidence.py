"""One-command clean-checkout demo (no environment activation or global install)."""

from pathlib import Path
import os
import subprocess
import sys
from tempfile import TemporaryDirectory
import venv


if __name__ == "__main__":
    if sys.version_info[:2] not in ((3, 11), (3, 12)):
        sys.exit("Use Python 3.11 or 3.12 with venv and pip available.")
    root = Path(__file__).resolve().parents[1]
    with TemporaryDirectory(prefix="cardioassist-ai121-venv-") as tmp:
        venv.EnvBuilder(with_pip=True).create(tmp)
        python = str(Path(tmp) / ("Scripts/python.exe" if os.name == "nt" else "bin/python"))
        subprocess.run(
            [
                python,
                "-m",
                "pip",
                "--disable-pip-version-check",
                "install",
                "-q",
                "-r",
                "research/uci412/requirements.txt",
            ],
            cwd=root,
            stdout=sys.stderr,
            check=True,
        )
        subprocess.run([python, "-m", "pip", "check"], stdout=sys.stderr, check=True)
        sys.exit(
            subprocess.call(
                [python, "-W", "error", "-m", "ai.research_evidence", *sys.argv[1:]], cwd=root
            )
        )
