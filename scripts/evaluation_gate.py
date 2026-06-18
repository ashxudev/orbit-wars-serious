"""Run the canonical quick local evaluation regression gate."""

from __future__ import annotations

import sys
from collections.abc import Sequence
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from ow_eval import run_regression_gate


def main(argv: Sequence[str] | None = None) -> int:
    """Run the quick gate and return a process exit code."""

    _ = argv
    result = run_regression_gate()
    print(result.summary_text)
    for failure in result.failures:
        print(f"{failure.code}: {failure.message}")
    return 0 if result.passed else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
