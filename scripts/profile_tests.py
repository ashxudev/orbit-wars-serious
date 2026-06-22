"""Profile unittest modules one at a time and report the slowest modules."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from ow_eval.local_tests import discover_test_modules, run_test_modules


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Profile unittest modules with per-module timings.",
    )
    parser.add_argument("--tests-dir", default="tests", help="Test directory.")
    parser.add_argument("--pattern", default="test_*.py", help="Test file glob.")
    parser.add_argument("--top", type=int, default=20, help="Number of slow modules to print.")
    parser.add_argument(
        "--timeout-per-module",
        type=float,
        help="Optional timeout in seconds for each module.",
    )
    parser.add_argument(
        "--json-output",
        help="Optional path for a JSON timing report.",
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
        workers=1,
        timeout_seconds=args.timeout_per_module,
    )
    print(summary.summary_text)
    for index, result in enumerate(summary.slowest(args.top), start=1):
        status = "PASS" if result.passed else "FAIL"
        print(f"{index:>2}. {result.duration_seconds:>8.3f}s {status} {result.module}")
    for result in summary.failed_results:
        print(f"\nFAILED {result.module}", file=sys.stderr)
        _print_tail(result.stderr or result.stdout, stream=sys.stderr)
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
