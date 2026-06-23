"""Typed public contracts for the Planner V2 mission/search boundary."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from ow_planner import (
    CommitmentOption,
    LaunchCandidate,
    MissionCandidate,
    MissionEvaluation,
    MissionType,
)


class PlannerV2Mode(str, Enum):
    """Planner V2 board modes."""

    TWO_PLAYER = "two_player"
    FOUR_PLAYER = "four_player"
    ENDGAME = "endgame"
    UNKNOWN = "unknown"


class MissionFamily(str, Enum):
    """Planner V2 mission families generated from board diagnosis."""

    SAFE_EXPAND = "safe_expand"
    URGENT_DEFEND = "urgent_defend"
    RECAPTURE = "recapture"
    HOLD_CAPTURE = "hold_capture"
    ENEMY_PRODUCTION_DENIAL = "enemy_production_denial"
    LEADER_PRESSURE = "leader_pressure"
    RANK_SWING = "rank_swing"
    MULTI_SOURCE_CAPTURE = "multi_source_capture"
    FUNNEL_FOR_DOWNSTREAM_ATTACK = "funnel_for_downstream_attack"
    LATE_LIQUIDATION = "late_liquidation"


@dataclass(frozen=True, slots=True)
class PlannerV2Config:
    """Configuration for bounded Planner V2 mission/search execution."""

    max_missions: int | None = 32
    max_action_sets: int | None = 16
    max_missions_per_action_set: int = 2
    horizons: tuple[int, ...] = (10, 25, 50)
    endgame_horizon: int = 100
    minimum_plan_score: float = -100.0

    def __post_init__(self) -> None:
        _validate_optional_nonnegative_int(self.max_missions, "max_missions")
        _validate_optional_nonnegative_int(self.max_action_sets, "max_action_sets")
        if (
            isinstance(self.max_missions_per_action_set, bool)
            or not isinstance(self.max_missions_per_action_set, int)
            or self.max_missions_per_action_set < 1
        ):
            raise ValueError("max_missions_per_action_set must be an integer >= 1")
        if not isinstance(self.horizons, tuple) or not self.horizons:
            raise ValueError("horizons must be a non-empty tuple")
        for index, horizon in enumerate(self.horizons):
            if isinstance(horizon, bool) or not isinstance(horizon, int) or horizon < 0:
                raise ValueError(f"horizons[{index}] must be an integer >= 0")
        if (
            isinstance(self.endgame_horizon, bool)
            or not isinstance(self.endgame_horizon, int)
            or self.endgame_horizon < 0
        ):
            raise ValueError("endgame_horizon must be an integer >= 0")
        if isinstance(self.minimum_plan_score, bool) or not isinstance(
            self.minimum_plan_score,
            (int, float),
        ):
            raise ValueError("minimum_plan_score must be numeric")


@dataclass(frozen=True, slots=True)
class BoardDiagnosis:
    """Central board diagnosis used by Planner V2 policies."""

    mode: PlannerV2Mode
    player_id: int | None
    active_player_ids: tuple[int, ...]
    opponent_player_ids: tuple[int, ...]
    owned_planet_count: int
    owned_production: int
    owned_planet_ships: int
    owned_fleet_ships: int
    opponent_production: int
    opponent_planet_ships: int
    neutral_production: int
    pressure_magnitude: int = 0
    source_drain_risk_planet_ids: tuple[int, ...] = ()
    vulnerable_owned_planet_ids: tuple[int, ...] = ()
    high_value_target_ids: tuple[int, ...] = ()
    rank_labels: tuple[str, ...] = ()
    pressure_labels: tuple[str, ...] = ()
    transfer_labels: tuple[str, ...] = ()
    denial_labels: tuple[str, ...] = ()
    plateau_labels: tuple[str, ...] = ()
    labels: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, object]:
        return {
            "active_player_ids": list(self.active_player_ids),
            "denial_labels": list(self.denial_labels),
            "high_value_target_ids": list(self.high_value_target_ids),
            "labels": list(self.labels),
            "mode": self.mode.value,
            "neutral_production": self.neutral_production,
            "opponent_planet_ships": self.opponent_planet_ships,
            "opponent_player_ids": list(self.opponent_player_ids),
            "opponent_production": self.opponent_production,
            "owned_fleet_ships": self.owned_fleet_ships,
            "owned_planet_count": self.owned_planet_count,
            "owned_planet_ships": self.owned_planet_ships,
            "owned_production": self.owned_production,
            "plateau_labels": list(self.plateau_labels),
            "player_id": self.player_id,
            "pressure_magnitude": self.pressure_magnitude,
            "pressure_labels": list(self.pressure_labels),
            "rank_labels": list(self.rank_labels),
            "source_drain_risk_planet_ids": list(self.source_drain_risk_planet_ids),
            "transfer_labels": list(self.transfer_labels),
            "vulnerable_owned_planet_ids": list(self.vulnerable_owned_planet_ids),
        }


@dataclass(frozen=True, slots=True)
class MissionPlan:
    """One Planner V2 mission surface, optionally backed by a V1 candidate."""

    mission_id: str
    family: MissionFamily
    mission_type: MissionType | None = None
    candidate: MissionCandidate | None = None
    evaluation: MissionEvaluation | None = None
    target_planet_id: int | None = None
    source_planet_ids: tuple[int, ...] = ()
    priority: float = 0.0
    labels: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, object]:
        return {
            "family": self.family.value,
            "labels": list(self.labels),
            "mission_id": self.mission_id,
            "mission_type": None if self.mission_type is None else self.mission_type.value,
            "priority": self.priority,
            "source_planet_ids": list(self.source_planet_ids),
            "target_planet_id": self.target_planet_id,
        }


@dataclass(frozen=True, slots=True)
class ActionSetPlan:
    """One V2 action-set plan assembled from one or more missions."""

    plan_id: str
    missions: tuple[MissionPlan, ...]
    launches: tuple[LaunchCandidate, ...]
    commitment_option: CommitmentOption | None = None
    labels: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, object]:
        return {
            "labels": list(self.labels),
            "launches": [
                {
                    "angle": launch.angle,
                    "player_id": launch.player_id,
                    "ships": launch.ships,
                    "source_planet_id": launch.source_planet_id,
                }
                for launch in self.launches
            ],
            "missions": [mission.to_dict() for mission in self.missions],
            "plan_id": self.plan_id,
        }


@dataclass(frozen=True, slots=True)
class EvaluatedPlan:
    """Planner V2 scored action-set plan."""

    plan: ActionSetPlan
    score: float
    score_components: tuple[tuple[str, float], ...] = ()
    horizon_scores: tuple[tuple[int, float], ...] = ()
    selected_horizon: int | None = None
    labels: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, object]:
        return {
            "labels": list(self.labels),
            "plan": self.plan.to_dict(),
            "score": self.score,
            "score_components": [
                {"name": name, "value": value}
                for name, value in self.score_components
            ],
            "horizon_scores": [
                {"horizon": horizon, "score": score}
                for horizon, score in self.horizon_scores
            ],
            "selected_horizon": self.selected_horizon,
        }


@dataclass(frozen=True, slots=True)
class PlannerV2Result:
    """Planner V2 result and diagnostics."""

    actions: tuple[LaunchCandidate, ...]
    diagnosis: BoardDiagnosis
    missions: tuple[MissionPlan, ...]
    action_sets: tuple[ActionSetPlan, ...]
    evaluated_plans: tuple[EvaluatedPlan, ...]
    selected_plan: EvaluatedPlan | None
    no_action_reason: str | None = None
    notes: tuple[str, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict[str, object]:
        return {
            "action_sets": [plan.to_dict() for plan in self.action_sets],
            "actions": [
                {
                    "angle": launch.angle,
                    "player_id": launch.player_id,
                    "ships": launch.ships,
                    "source_planet_id": launch.source_planet_id,
                }
                for launch in self.actions
            ],
            "diagnosis": self.diagnosis.to_dict(),
            "evaluated_plans": [plan.to_dict() for plan in self.evaluated_plans],
            "missions": [mission.to_dict() for mission in self.missions],
            "no_action_reason": self.no_action_reason,
            "notes": list(self.notes),
            "selected_plan": None if self.selected_plan is None else self.selected_plan.to_dict(),
        }


def _validate_optional_nonnegative_int(value: object, name: str) -> None:
    if value is None:
        return
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{name} must be None or an integer >= 0")


__all__ = (
    "ActionSetPlan",
    "BoardDiagnosis",
    "EvaluatedPlan",
    "MissionFamily",
    "MissionPlan",
    "PlannerV2Config",
    "PlannerV2Mode",
    "PlannerV2Result",
)
