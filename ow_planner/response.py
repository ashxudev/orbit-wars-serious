"""Planner opponent-response model contracts.

Opponent Response Model Cycle 0 defines immutable response-evaluation
containers and a structural public API. It does not model reinforcement, races,
counterattacks, third-party effects, scoring, ranking, pruning, or selection.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Sequence

from ow_sim.state import GameState

from .evaluation import MissionEvaluation


class ResponseEvaluationStatus(str, Enum):
    """Status for opponent-response evaluation lifecycle."""

    UNEVALUATED = "unevaluated"
    EVALUATED = "evaluated"
    INCOMPLETE = "incomplete"


@dataclass(frozen=True, slots=True)
class ResponseConfig:
    """Configuration boundary for future opponent-response modeling."""

    response_window_ticks: int = 0

    def __post_init__(self) -> None:
        if (
            isinstance(self.response_window_ticks, bool)
            or not isinstance(self.response_window_ticks, int)
            or self.response_window_ticks < 0
        ):
            raise ValueError("response_window_ticks must be an integer >= 0")


@dataclass(frozen=True, slots=True)
class MissionResponseFacts:
    """Deterministic response facts for one mission evaluation."""

    response_labels: tuple[str, ...] = ()
    notes: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class MissionResponseEvaluation:
    """Structural opponent-response wrapper for one mission evaluation."""

    evaluation: MissionEvaluation
    status: ResponseEvaluationStatus = ResponseEvaluationStatus.UNEVALUATED
    facts: MissionResponseFacts = field(default_factory=MissionResponseFacts)
    note: str | None = None


def evaluate_responses(
    state: GameState,
    evaluations: Sequence[MissionEvaluation],
    config: ResponseConfig | None = None,
) -> tuple[MissionResponseEvaluation, ...]:
    """Return structural opponent-response evaluations in input order."""

    del state
    ResponseConfig() if config is None else config
    if not evaluations:
        return ()

    response_evaluations: list[MissionResponseEvaluation] = []
    for evaluation in evaluations:
        if evaluation.facts is None:
            response_evaluations.append(
                MissionResponseEvaluation(
                    evaluation=evaluation,
                    status=ResponseEvaluationStatus.INCOMPLETE,
                    facts=MissionResponseFacts(
                        notes=("mission facts are missing",),
                    ),
                    note="mission facts are missing",
                )
            )
            continue
        response_evaluations.append(
            MissionResponseEvaluation(
                evaluation=evaluation,
                status=ResponseEvaluationStatus.EVALUATED,
            )
        )
    return tuple(response_evaluations)


__all__ = (
    "MissionResponseEvaluation",
    "MissionResponseFacts",
    "ResponseConfig",
    "ResponseEvaluationStatus",
    "evaluate_responses",
)
