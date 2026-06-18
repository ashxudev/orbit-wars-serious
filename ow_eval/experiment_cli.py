"""CLI workflow for one local evaluation experiment manifest.

Evaluation Harness Cycle 16 composes existing manifest execution, promotion
gate evaluation, and report writing into one explicit local workflow. It does
not run matches at import time or write reports unless a report path is given.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from .experiment_manifest import ExperimentManifest
from .experiment_report import (
    ExperimentReport,
    build_experiment_report,
    write_experiment_report,
)
from .experiment_runner import (
    ExperimentRunConfig,
    ExperimentRunResult,
    run_experiment_manifest,
)
from .promotion_gate import PromotionGateDecision, evaluate_promotion_gate


@dataclass(frozen=True, slots=True)
class ExperimentCliResult:
    """Deterministic outcome from running one local experiment workflow."""

    manifest_path: str
    report_path: str | None = None
    run_result: ExperimentRunResult | None = None
    promotion_decision: PromotionGateDecision | None = None
    experiment_report: ExperimentReport | None = None
    exit_code: int = 2
    summary_text: str = ""
    error_text: str | None = None

    def __post_init__(self) -> None:
        _validate_nonempty_string(self.manifest_path, "manifest_path")
        if self.report_path is not None:
            _validate_nonempty_string(self.report_path, "report_path")
        if self.run_result is not None and not isinstance(
            self.run_result,
            ExperimentRunResult,
        ):
            raise ValueError("run_result must be an ExperimentRunResult")
        if self.promotion_decision is not None and not isinstance(
            self.promotion_decision,
            PromotionGateDecision,
        ):
            raise ValueError("promotion_decision must be a PromotionGateDecision")
        if self.experiment_report is not None and not isinstance(
            self.experiment_report,
            ExperimentReport,
        ):
            raise ValueError("experiment_report must be an ExperimentReport")
        if isinstance(self.exit_code, bool) or not isinstance(self.exit_code, int):
            raise ValueError("exit_code must be an integer")
        _validate_nonempty_string(self.summary_text, "summary_text")
        if self.error_text is not None:
            _validate_nonempty_string(self.error_text, "error_text")

    def to_dict(self) -> dict[str, object]:
        """Return a deterministic JSON-safe dictionary."""

        return {
            "manifest_path": self.manifest_path,
            "report_path": self.report_path,
            "run_result": (
                self.run_result.to_dict()
                if self.run_result is not None
                else None
            ),
            "promotion_decision": (
                self.promotion_decision.to_dict()
                if self.promotion_decision is not None
                else None
            ),
            "experiment_report": (
                self.experiment_report.to_dict()
                if self.experiment_report is not None
                else None
            ),
            "exit_code": self.exit_code,
            "summary_text": self.summary_text,
            "error_text": self.error_text,
        }


def run_evaluation_experiment(
    manifest_path: str | Path,
    *,
    report_path: str | Path | None = None,
    config: ExperimentRunConfig | None = None,
) -> ExperimentCliResult:
    """Run one manifest through local evaluation, gate, and optional report."""

    manifest_path_text = str(manifest_path)
    report_path_text = str(report_path) if report_path is not None else None
    try:
        manifest = _read_manifest(manifest_path)
        run_result = run_experiment_manifest(manifest, config)
        decision = evaluate_promotion_gate(run_result)
        report = build_experiment_report(run_result, decision)
        written_report_path = report_path_text
        if report_path is not None:
            written_report_path = str(write_experiment_report(report, report_path))
        exit_code = 0 if decision.passed else 1
        return ExperimentCliResult(
            manifest_path=manifest_path_text,
            report_path=written_report_path,
            run_result=run_result,
            promotion_decision=decision,
            experiment_report=report,
            exit_code=exit_code,
            summary_text=_summary_text(
                manifest=manifest,
                decision=decision,
                exit_code=exit_code,
                report_path=written_report_path,
            ),
        )
    except Exception as exc:  # noqa: BLE001 - CLI boundary returns structured errors.
        error_text = f"{type(exc).__name__}: {exc}"
        return ExperimentCliResult(
            manifest_path=manifest_path_text,
            report_path=report_path_text,
            exit_code=2,
            summary_text=(
                "experiment_workflow=ERROR "
                f"manifest={manifest_path_text} exit_code=2"
            ),
            error_text=error_text,
        )


def main(argv: Sequence[str] | None = None) -> int:
    """Run the experiment workflow from command-line arguments."""

    parser = argparse.ArgumentParser(
        description="Run one local evaluation experiment manifest.",
    )
    parser.add_argument("manifest", help="Path to an experiment manifest JSON file.")
    parser.add_argument(
        "--report-output",
        help="Optional path for deterministic experiment report JSON.",
    )
    args = parser.parse_args(argv)

    result = run_evaluation_experiment(
        args.manifest,
        report_path=args.report_output,
    )
    print(result.summary_text)
    if result.promotion_decision is not None:
        for failure in result.promotion_decision.failures:
            print(f"{failure.code}: {failure.message}")
    if result.error_text is not None:
        print(result.error_text, file=sys.stderr)
    return result.exit_code


def _read_manifest(path: str | Path) -> ExperimentManifest:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, Mapping):
        raise ValueError("manifest JSON must be an object")
    return ExperimentManifest.from_dict(payload)


def _summary_text(
    *,
    manifest: ExperimentManifest,
    decision: PromotionGateDecision,
    exit_code: int,
    report_path: str | None,
) -> str:
    status = "PASS" if decision.passed else "FAIL"
    report_text = report_path if report_path is not None else "none"
    return (
        f"experiment_workflow={status} manifest={manifest.name} "
        f"promotion_passed={str(decision.passed).lower()} "
        f"exit_code={exit_code} report_path={report_text}"
    )


def _validate_nonempty_string(value: object, name: str) -> None:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{name} must be a non-empty string")


__all__ = (
    "ExperimentCliResult",
    "main",
    "run_evaluation_experiment",
)
