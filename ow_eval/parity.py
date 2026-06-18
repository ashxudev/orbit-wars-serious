"""Generated-submission parity checks for local official matches.

Evaluation Harness Cycle 7 compares the modular runtime agent with a generated
or caller-provided single-file submission through the existing sequential batch
runner. It does not add scoreboards, gates, triage reports, or live submission
automation.
"""

from __future__ import annotations

import tempfile
from collections.abc import Mapping
from contextlib import contextmanager
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Iterator

from scripts.build_submission import write_submission

from .artifacts import EvaluationArtifactConfig
from .batch_runner import (
    EvaluationBatchConfig,
    EvaluationBatchResult,
    run_evaluation_batch,
)
from .contracts import AgentSourceKind, AgentSpec, MatchConfig, MatchResult


METRIC_FIELDS = (
    "final_rank",
    "final_score",
    "final_planets",
    "final_ships",
    "final_production",
    "turns_survived",
    "error_count",
    "invalid_action_count",
    "timeout_count",
)


@dataclass(frozen=True, slots=True)
class SubmissionParityConfig:
    """Config for one modular-vs-submission parity check."""

    matches: tuple[MatchConfig, ...]
    modular_agent: AgentSpec | None = None
    submission_path: str | Path | None = None
    artifacts: EvaluationArtifactConfig | None = None
    artifact_prefix: str | None = "parity"

    def __post_init__(self) -> None:
        if not isinstance(self.matches, tuple):
            raise ValueError("matches must be a tuple")
        for match in self.matches:
            if not isinstance(match, MatchConfig):
                raise ValueError("matches entries must be MatchConfig objects")
        if self.modular_agent is not None and not isinstance(
            self.modular_agent,
            AgentSpec,
        ):
            raise ValueError("modular_agent must be an AgentSpec")
        if self.submission_path is not None and not isinstance(
            self.submission_path,
            (str, Path),
        ):
            raise ValueError("submission_path must be a path")
        if self.artifacts is not None and not isinstance(
            self.artifacts,
            EvaluationArtifactConfig,
        ):
            raise ValueError("artifacts must be an EvaluationArtifactConfig")
        if self.artifact_prefix is not None and not isinstance(
            self.artifact_prefix,
            str,
        ):
            raise ValueError("artifact_prefix must be a string")
        if self.artifact_prefix == "":
            raise ValueError("artifact_prefix must be non-empty when provided")


@dataclass(frozen=True, slots=True)
class SubmissionParityComparison:
    """Pairwise parity comparison for one match index."""

    index: int
    modular_result: MatchResult
    submission_result: MatchResult
    status_matches: bool
    metrics_match: bool
    matched: bool
    mismatch_reasons: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class SubmissionParityResult:
    """Result of comparing modular and submission batches."""

    comparisons: tuple[SubmissionParityComparison, ...]
    modular_batch: EvaluationBatchResult
    submission_batch: EvaluationBatchResult
    passed: bool
    mismatch_count: int


def submission_agent_spec(
    path: str | Path,
    name: str = "bundled-submission",
) -> AgentSpec:
    """Return an ``AgentSpec`` for a generated or standalone submission file."""

    return AgentSpec(
        name=name,
        source_kind=AgentSourceKind.SUBMISSION_FILE,
        file_path=str(Path(path)),
    )


def run_submission_parity_check(
    config: SubmissionParityConfig,
) -> SubmissionParityResult:
    """Run modular and submission batches and compare deterministic metrics."""

    if config.submission_path is None:
        with tempfile.TemporaryDirectory(prefix="ow-eval-parity-") as tmp:
            submission_path = write_submission(Path(tmp) / "orbit_wars_submission.py")
            return _run_submission_parity_with_path(config, submission_path)

    return _run_submission_parity_with_path(config, Path(config.submission_path))


def _run_submission_parity_with_path(
    config: SubmissionParityConfig,
    submission_path: Path,
) -> SubmissionParityResult:
    modular_agent = config.modular_agent or _default_modular_agent_spec()
    submission_agent = submission_agent_spec(submission_path)
    modular_matches = _matches_with_candidate(
        config.matches,
        modular_agent,
        suffix="modular",
    )
    submission_matches = _matches_with_candidate(
        config.matches,
        submission_agent,
        suffix="submission",
    )

    with _bounded_runtime_agent_for_parity():
        modular_batch = run_evaluation_batch(
            EvaluationBatchConfig(
                matches=modular_matches,
                artifacts=config.artifacts,
                artifact_prefix=_batch_artifact_prefix(config, "modular"),
            )
        )
        submission_batch = run_evaluation_batch(
            EvaluationBatchConfig(
                matches=submission_matches,
                artifacts=config.artifacts,
                artifact_prefix=_batch_artifact_prefix(config, "submission"),
            )
        )

    comparisons = tuple(
        _compare_results(index, modular_result, submission_result)
        for index, (modular_result, submission_result) in enumerate(
            zip(modular_batch.results, submission_batch.results)
        )
    )
    mismatch_count = sum(1 for comparison in comparisons if not comparison.matched)
    return SubmissionParityResult(
        comparisons=comparisons,
        modular_batch=modular_batch,
        submission_batch=submission_batch,
        passed=mismatch_count == 0,
        mismatch_count=mismatch_count,
    )


def _default_modular_agent_spec() -> AgentSpec:
    return AgentSpec(
        name="modular-runtime",
        source_kind=AgentSourceKind.MODULAR_AGENT,
        module_path="agents.orbit_wars_agent",
    )


def _matches_with_candidate(
    matches: tuple[MatchConfig, ...],
    candidate_agent: AgentSpec,
    *,
    suffix: str,
) -> tuple[MatchConfig, ...]:
    return tuple(
        replace(
            match,
            candidate_agent=candidate_agent,
            label=f"{_base_label(match, index)}-{suffix}",
        )
        for index, match in enumerate(matches)
    )


def _base_label(match: MatchConfig, index: int) -> str:
    if match.label is not None:
        return match.label
    return f"match-{index:04d}"


def _batch_artifact_prefix(
    config: SubmissionParityConfig,
    side: str,
) -> str | None:
    if config.artifacts is None:
        return None
    prefix = config.artifact_prefix
    if prefix is None:
        prefix = config.artifacts.prefix
    if prefix is None:
        prefix = "parity"
    return f"{prefix}-{side}"


def _compare_results(
    index: int,
    modular_result: MatchResult,
    submission_result: MatchResult,
) -> SubmissionParityComparison:
    reasons: list[str] = []
    status_matches = modular_result.status is submission_result.status
    if not status_matches:
        reasons.append("status differs")

    metric_reasons = []
    for field in METRIC_FIELDS:
        if getattr(modular_result.metrics, field) != getattr(
            submission_result.metrics,
            field,
        ):
            metric_reasons.append(f"{field} differs")

    reasons.extend(metric_reasons)
    metrics_match = not metric_reasons
    matched = status_matches and metrics_match
    return SubmissionParityComparison(
        index=index,
        modular_result=modular_result,
        submission_result=submission_result,
        status_matches=status_matches,
        metrics_match=metrics_match,
        matched=matched,
        mismatch_reasons=tuple(reasons),
    )


@contextmanager
def _bounded_runtime_agent_for_parity() -> Iterator[None]:
    from . import official_runner

    original_loader = official_runner.load_agent_callable

    def bounded_loader(agent_spec: AgentSpec) -> Any:
        agent = original_loader(agent_spec)

        def bounded_agent(
            observation: object,
            configuration: object | None = None,
        ) -> Any:
            bounded_observation = observation
            if isinstance(observation, Mapping):
                bounded_observation = dict(observation)
                bounded_observation["remainingOverageTime"] = 0.0
            return agent(bounded_observation, configuration)

        return bounded_agent

    official_runner.load_agent_callable = bounded_loader
    try:
        yield
    finally:
        official_runner.load_agent_callable = original_loader


__all__ = (
    "METRIC_FIELDS",
    "SubmissionParityComparison",
    "SubmissionParityConfig",
    "SubmissionParityResult",
    "run_submission_parity_check",
    "submission_agent_spec",
)
