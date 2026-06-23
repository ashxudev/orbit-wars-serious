"""Build the fallback source-guard reserve candidate as one Python file."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Iterable
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from agents.fallback_source_guard import build_source


def write_submission(output_path: Path) -> Path:
    """Write the deterministic standalone candidate and return its path."""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(build_source(), encoding="utf-8")
    return output_path


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Build fallback source-guard standalone Orbit Wars agent.",
    )
    parser.add_argument(
        "--output",
        required=True,
        type=Path,
        help="Path to write the generated Python file.",
    )
    args = parser.parse_args(tuple(argv) if argv is not None else None)
    write_submission(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
