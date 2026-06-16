"""Run the simulator validation test suite."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def main() -> int:
    repo_root = Path(__file__).resolve().parents[1]
    command = [sys.executable, "-m", "unittest", "discover", "-s", "tests"]
    return subprocess.run(command, cwd=repo_root, check=False).returncode


if __name__ == "__main__":
    raise SystemExit(main())
