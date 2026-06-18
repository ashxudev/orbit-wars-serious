"""Sequential local evaluation batch runner.

Evaluation Harness Cycle 6 composes ordered ``MatchConfig`` objects through the
existing single-match runner. It does not add parallelism, scoreboards,
regression gates, retries, or live submission behavior.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass, replace

from .artifacts import EvaluationArtifactConfig
from .contracts import EvaluationStatus, MatchConfig, MatchResult
from .official_runner import run_official_match


@dataclass(frozen=True, slots=True)
class EvaluationBatchConfig:
    """Config for one deterministic sequential evaluation batch."""

    matches: tuple[MatchConfig, ...]
    artifacts: EvaluationArtifactConfig | None = None
    artifact_prefix: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.matches, tuple):
            raise ValueError("matches must be a tuple")
        for match in self.matches:
            if not isinstance(match, MatchConfig):
                raise ValueError("matches entries must be MatchConfig objects")
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
class EvaluationBatchSummary:
    """In-memory summary for one deterministic evaluation batch."""

    total_matches: int = 0
    completed_count: int = 0
    error_count: int = 0
    status_counts: tuple[tuple[str, int], ...] = ()
    mean_final_rank: float | None = None
    mean_final_score: float | None = None
    mean_turns_survived: float | None = None


@dataclass(frozen=True, slots=True)
class EvaluationBatchResult:
    """Ordered batch results plus deterministic aggregate summary."""

    results: tuple[MatchResult, ...] = ()
    summary: EvaluationBatchSummary = EvaluationBatchSummary()


def run_evaluation_batch(config: EvaluationBatchConfig) -> EvaluationBatchResult:
    """Run ``config.matches`` sequentially and return ordered results."""

    results = []
    for index, match_config in enumerate(config.matches):
        try:
            result = run_official_match(
                match_config,
                artifacts=_artifacts_for_match(config, index),
            )
        except Exception as exc:
            result = MatchResult(
                config=match_config,
                status=EvaluationStatus.UNKNOWN_ERROR,
                error_text=_error_text(exc),
            )
        results.append(result)

    result_tuple = tuple(results)
    return EvaluationBatchResult(
        results=result_tuple,
        summary=summarize_match_results(result_tuple),
    )


def summarize_match_results(results: Sequence[MatchResult]) -> EvaluationBatchSummary:
    """Return a deterministic summary for ``results``."""

    result_tuple = tuple(results)
    status_counts = _status_counts(result_tuple)
    completed_count = sum(
        1
        for result in result_tuple
        if result.status is EvaluationStatus.COMPLETED
    )
    return EvaluationBatchSummary(
        total_matches=len(result_tuple),
        completed_count=completed_count,
        error_count=len(result_tuple) - completed_count,
        status_counts=status_counts,
        mean_final_rank=_mean(
            result.metrics.final_rank
            for result in result_tuple
        ),
        mean_final_score=_mean(
            result.metrics.final_score
            for result in result_tuple
        ),
        mean_turns_survived=_mean(
            result.metrics.turns_survived
            for result in result_tuple
        ),
    )


def _artifacts_for_match(
    config: EvaluationBatchConfig,
    index: int,
) -> EvaluationArtifactConfig | None:
    if config.artifacts is None:
        return None

    base_prefix = (
        config.artifact_prefix
        if config.artifact_prefix is not None
        else config.artifacts.prefix
    )
    if base_prefix is None:
        base_prefix = "batch"

    return replace(
        config.artifacts,
        prefix=f"{base_prefix}-match-{index:04d}",
    )


def _status_counts(results: tuple[MatchResult, ...]) -> tuple[tuple[str, int], ...]:
    counts = {
        status: 0
        for status in EvaluationStatus
    }
    for result in results:
        counts[result.status] += 1
    return tuple(
        (status.value, count)
        for status, count in counts.items()
        if count > 0
    )


def _mean(values: Iterable[int | float | None]) -> float | None:
    numeric_values = tuple(
        float(value)
        for value in values
        if value is not None and not isinstance(value, bool)
    )
    if not numeric_values:
        return None
    return sum(numeric_values) / len(numeric_values)


def _error_text(exc: Exception) -> str:
    return f"{type(exc).__name__}: {exc}"


__all__ = (
    "EvaluationBatchConfig",
    "EvaluationBatchResult",
    "EvaluationBatchSummary",
    "run_evaluation_batch",
    "summarize_match_results",
)
