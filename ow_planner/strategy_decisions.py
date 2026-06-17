"""Planner decision bundle and selection-result boundaries.

Strategy Modes Cycle 1 joins already-computed planner artifacts by mission
candidate identity. Cycle 2 adds structural strategy-selection result
contracts. It does not generate, evaluate, score, respond, commit, rank, prune,
select, convert actions, or run simulator rollouts.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Sequence

from .candidates import MissionCandidate
from .commitment import CandidateCommitmentOptions, CommitmentOption
from .evaluation import MissionEvaluation
from .response import MissionResponseEvaluation
from .strategy_modes import StrategyModeFacts


@dataclass(frozen=True, slots=True)
class PlannerDecisionBundle:
    """Structural bundle of existing planner artifacts for one candidate."""

    candidate: MissionCandidate
    strategy_mode_facts: StrategyModeFacts | None = None
    evaluation: MissionEvaluation | None = None
    response_evaluation: MissionResponseEvaluation | None = None
    commitment_options: CandidateCommitmentOptions | None = None
    notes: tuple[str, ...] = ()


class StrategySelectionStatus(str, Enum):
    """Lifecycle status for future strategy-selection results."""

    UNSELECTED = "unselected"
    SELECTED = "selected"
    NO_ACTION = "no_action"
    REJECTED = "rejected"


@dataclass(frozen=True, slots=True)
class StrategySelectionResult:
    """Structural result object for future strategy-selection policies."""

    status: StrategySelectionStatus = StrategySelectionStatus.UNSELECTED
    strategy_mode_facts: StrategyModeFacts | None = None
    selected_bundle: PlannerDecisionBundle | None = None
    selected_commitment_option: CommitmentOption | None = None
    notes: tuple[str, ...] = ()


def planner_decision_bundles(
    candidates: Sequence[MissionCandidate],
    *,
    strategy_mode_facts: StrategyModeFacts | None = None,
    evaluations: Sequence[MissionEvaluation] = (),
    response_evaluations: Sequence[MissionResponseEvaluation] = (),
    commitment_options: Sequence[CandidateCommitmentOptions] = (),
) -> tuple[PlannerDecisionBundle, ...]:
    """Return candidate-ordered bundles of existing planner artifacts.

    Artifacts are matched by mission candidate object identity. Duplicate
    artifacts for the same candidate identity use the first artifact supplied.
    """

    evaluations_by_candidate = _first_evaluations_by_candidate(evaluations)
    responses_by_candidate = _first_responses_by_candidate(response_evaluations)
    commitments_by_candidate = _first_commitments_by_candidate(commitment_options)

    bundles: list[PlannerDecisionBundle] = []
    for candidate in candidates:
        candidate_key = id(candidate)
        evaluation = evaluations_by_candidate.get(candidate_key)
        response_evaluation = responses_by_candidate.get(candidate_key)
        candidate_commitment_options = commitments_by_candidate.get(candidate_key)
        notes = []
        if evaluation is None:
            notes.append("missing evaluation")
        if response_evaluation is None:
            notes.append("missing response evaluation")
        if candidate_commitment_options is None:
            notes.append("missing commitment options")
        bundles.append(
            PlannerDecisionBundle(
                candidate=candidate,
                strategy_mode_facts=strategy_mode_facts,
                evaluation=evaluation,
                response_evaluation=response_evaluation,
                commitment_options=candidate_commitment_options,
                notes=tuple(notes),
            )
        )
    return tuple(bundles)


def selected_strategy_result(
    bundle: PlannerDecisionBundle,
    commitment_option: CommitmentOption,
    notes: Sequence[str] = (),
) -> StrategySelectionResult:
    """Return a structural selected result without judging quality."""

    return StrategySelectionResult(
        status=StrategySelectionStatus.SELECTED,
        strategy_mode_facts=bundle.strategy_mode_facts,
        selected_bundle=bundle,
        selected_commitment_option=commitment_option,
        notes=tuple(notes),
    )


def no_action_strategy_result(
    strategy_mode_facts: StrategyModeFacts | None = None,
    notes: Sequence[str] = ("no action",),
) -> StrategySelectionResult:
    """Return a structural no-action fallback result."""

    return StrategySelectionResult(
        status=StrategySelectionStatus.NO_ACTION,
        strategy_mode_facts=strategy_mode_facts,
        notes=tuple(notes),
    )


def rejected_strategy_result(
    strategy_mode_facts: StrategyModeFacts | None = None,
    notes: Sequence[str] = (),
) -> StrategySelectionResult:
    """Return a structural rejected/undecided result."""

    return StrategySelectionResult(
        status=StrategySelectionStatus.REJECTED,
        strategy_mode_facts=strategy_mode_facts,
        notes=tuple(notes),
    )


def _first_evaluations_by_candidate(
    evaluations: Sequence[MissionEvaluation],
) -> dict[int, MissionEvaluation]:
    evaluations_by_candidate: dict[int, MissionEvaluation] = {}
    for evaluation in evaluations:
        candidate_key = id(evaluation.candidate)
        if candidate_key not in evaluations_by_candidate:
            evaluations_by_candidate[candidate_key] = evaluation
    return evaluations_by_candidate


def _first_responses_by_candidate(
    response_evaluations: Sequence[MissionResponseEvaluation],
) -> dict[int, MissionResponseEvaluation]:
    responses_by_candidate: dict[int, MissionResponseEvaluation] = {}
    for response_evaluation in response_evaluations:
        candidate_key = id(response_evaluation.evaluation.candidate)
        if candidate_key not in responses_by_candidate:
            responses_by_candidate[candidate_key] = response_evaluation
    return responses_by_candidate


def _first_commitments_by_candidate(
    commitment_options: Sequence[CandidateCommitmentOptions],
) -> dict[int, CandidateCommitmentOptions]:
    commitments_by_candidate: dict[int, CandidateCommitmentOptions] = {}
    for candidate_commitment_options in commitment_options:
        candidate_key = id(candidate_commitment_options.candidate)
        if candidate_key not in commitments_by_candidate:
            commitments_by_candidate[candidate_key] = candidate_commitment_options
    return commitments_by_candidate


__all__ = (
    "PlannerDecisionBundle",
    "StrategySelectionResult",
    "StrategySelectionStatus",
    "no_action_strategy_result",
    "planner_decision_bundles",
    "rejected_strategy_result",
    "selected_strategy_result",
)
