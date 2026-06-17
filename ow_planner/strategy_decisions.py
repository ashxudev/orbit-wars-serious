"""Planner decision bundle composition boundary.

Strategy Modes Cycle 1 joins already-computed planner artifacts by mission
candidate identity. It does not generate, evaluate, score, respond, commit,
rank, prune, select, convert actions, or run simulator rollouts.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from .candidates import MissionCandidate
from .commitment import CandidateCommitmentOptions
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
    "planner_decision_bundles",
)
