"""Run unittest modules in parallel subprocesses."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from ow_eval.local_tests import (
    default_worker_count,
    discover_test_modules,
    run_test_modules,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run unittest modules in parallel subprocesses.",
    )
    parser.add_argument("--tests-dir", default="tests", help="Test directory.")
    parser.add_argument("--pattern", default="test_*.py", help="Test file glob.")
    parser.add_argument(
        "--workers",
        type=int,
        default=default_worker_count(),
        help="Parallel worker count.",
    )
    parser.add_argument(
        "--timeout-per-module",
        type=float,
        help="Optional timeout in seconds for each module.",
    )
    parser.add_argument(
        "--top-slowest",
        type=int,
        default=10,
        help="Number of slowest modules to print.",
    )
    parser.add_argument(
        "--json-output",
        help="Optional path for a JSON test report.",
    )
    parser.add_argument(
        "--include-output",
        action="store_true",
        help="Include captured stdout/stderr in JSON output.",
    )
    args = parser.parse_args(argv)

    modules = discover_test_modules(
        args.tests_dir,
        pattern=args.pattern,
        repo_root=REPO_ROOT,
    )
    summary = run_test_modules(
        modules,
        repo_root=REPO_ROOT,
        workers=args.workers,
        timeout_seconds=args.timeout_per_module,
    )
    print(summary.summary_text)
    if summary.failed_results:
        print("Failed modules:", file=sys.stderr)
        for result in summary.failed_results:
            print(f"- {result.module} returncode={result.returncode}", file=sys.stderr)
            _print_tail(result.stderr or result.stdout, stream=sys.stderr)
    print("Slowest modules:")
    for index, result in enumerate(summary.slowest(args.top_slowest), start=1):
        status = "PASS" if result.passed else "FAIL"
        print(f"{index:>2}. {result.duration_seconds:>8.3f}s {status} {result.module}")
    if args.json_output:
        output_path = Path(args.json_output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            json.dumps(
                summary.to_dict(include_output=args.include_output),
                sort_keys=True,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
    return summary.exit_code


def _print_tail(text: str, *, stream) -> None:  # noqa: ANN001 - stdout/stderr stream.
    if not text:
        return
    print(text[-4000:].rstrip(), file=stream)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
