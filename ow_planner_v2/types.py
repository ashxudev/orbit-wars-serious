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


class TrajectoryPhase(str, Enum):
    """Coarse V2 trajectory phase labels."""

    OPENING = "opening"
    EARLY_BASE = "early_base"
    MIDGAME = "midgame"
    TERMINAL = "terminal"


class TrajectoryObjective(str, Enum):
    """Measurable V2 trajectory objectives."""

    SECURE_SECOND_SOURCE = "secure_second_source"
    PRESERVE_PRIMARY_SOURCE = "preserve_primary_source"
    CAPTURE_NEAREST_PRODUCTIVE_NEUTRAL = "capture_nearest_productive_neutral"
    DELAY_ENEMY_DENIAL_UNTIL_BASE_SECURED = "delay_enemy_denial_until_base_secured"
    HOLD_RECENT_CAPTURE = "hold_recent_capture"
    DENY_AFTER_STABILIZING = "deny_after_stabilizing"


@dataclass(frozen=True, slots=True)
class PlannerV2Config:
    """Configuration for bounded Planner V2 mission/search execution."""

    max_missions: int | None = 32
    max_surface_candidates: int | None = 12
    max_action_sets: int | None = 16
    max_missions_per_action_set: int = 2
    horizons: tuple[int, ...] = (10, 25, 50)
    endgame_horizon: int = 100
    minimum_plan_score: float = -100.0
    enable_trajectory_second_source: bool = True

    def __post_init__(self) -> None:
        _validate_optional_nonnegative_int(self.max_missions, "max_missions")
        _validate_optional_nonnegative_int(
            self.max_surface_candidates,
            "max_surface_candidates",
        )
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
        if not isinstance(self.enable_trajectory_second_source, bool):
            raise ValueError("enable_trajectory_second_source must be boolean")


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
class TrajectoryDiagnosis:
    """V2 trajectory facts for early strategic-collapse diagnosis."""

    turn: int | None
    phase: TrajectoryPhase
    player_id: int | None
    owned_planet_count: int
    owned_production: int
    owned_ships: int
    owned_fleet_ships: int
    best_neutral_production_available: int
    nearest_productive_neutral_ids: tuple[int, ...] = ()
    nearest_productive_neutral_distances: tuple[float, ...] = ()
    second_source_secured: bool = False
    single_source_fragile: bool = False
    source_drain_risk: bool = False
    expansion_deficit: int = 0
    production_gap_to_leader: int = 0
    recommended_objectives: tuple[TrajectoryObjective, ...] = ()
    labels: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, object]:
        return {
            "best_neutral_production_available": self.best_neutral_production_available,
            "expansion_deficit": self.expansion_deficit,
            "labels": list(self.labels),
            "nearest_productive_neutral_distances": [
                round(value, 6)
                for value in self.nearest_productive_neutral_distances
            ],
            "nearest_productive_neutral_ids": list(self.nearest_productive_neutral_ids),
            "owned_fleet_ships": self.owned_fleet_ships,
            "owned_planet_count": self.owned_planet_count,
            "owned_production": self.owned_production,
            "owned_ships": self.owned_ships,
            "phase": self.phase.value,
            "player_id": self.player_id,
            "production_gap_to_leader": self.production_gap_to_leader,
            "recommended_objectives": [
                objective.value for objective in self.recommended_objectives
            ],
            "second_source_secured": self.second_source_secured,
            "single_source_fragile": self.single_source_fragile,
            "source_drain_risk": self.source_drain_risk,
            "turn": self.turn,
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
class ActionSetPruneRecord:
    """One V2 action-set plan or possible combination excluded before scoring."""

    reason: str
    plan: ActionSetPlan | None = None
    mission_ids: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, object]:
        return {
            "mission_ids": list(self.mission_ids),
            "plan": None if self.plan is None else self.plan.to_dict(),
            "reason": self.reason,
        }


@dataclass(frozen=True, slots=True)
class ActionSetCoverageReport:
    """Minimal funnel coverage for action-set construction."""

    single_action_sets: tuple[ActionSetPlan, ...]
    kept_action_sets: tuple[ActionSetPlan, ...]
    pruned_action_sets: tuple[ActionSetPruneRecord, ...] = ()

    def to_dict(self) -> dict[str, object]:
        return {
            "kept_action_sets": [
                action_set.to_dict()
                for action_set in self.kept_action_sets
            ],
            "pruned_action_sets": [
                record.to_dict()
                for record in self.pruned_action_sets
            ],
            "single_action_sets": [
                action_set.to_dict()
                for action_set in self.single_action_sets
            ],
        }


@dataclass(frozen=True, slots=True)
class ScenarioOutcome:
    """One simulated action-set outcome compared with an idle baseline."""

    horizon: int
    valid: bool
    score: float
    own_production_delta: int = 0
    own_planet_delta: int = 0
    own_planet_count: int = 0
    own_ship_delta: int = 0
    own_production: int = 0
    opponent_production_delta: int = 0
    idle_own_planet_count: int = 0
    idle_own_production: int = 0
    target_owned_by_player_count: int = 0
    target_planet_ids: tuple[int, ...] = ()
    source_planet_lost_ids: tuple[int, ...] = ()
    source_planet_lost_production: int = 0
    source_counterattack_lost_ids: tuple[int, ...] = ()
    source_counterattack_lost_production: int = 0
    target_hold_failure_ids: tuple[int, ...] = ()
    target_hold_failure_production: int = 0
    vulnerable_planet_lost_ids: tuple[int, ...] = ()
    vulnerable_planet_lost_production: int = 0
    eliminated: bool = False
    notes: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, object]:
        return {
            "eliminated": self.eliminated,
            "horizon": self.horizon,
            "notes": list(self.notes),
            "opponent_production_delta": self.opponent_production_delta,
            "own_planet_delta": self.own_planet_delta,
            "own_planet_count": self.own_planet_count,
            "idle_own_planet_count": self.idle_own_planet_count,
            "idle_own_production": self.idle_own_production,
            "own_production_delta": self.own_production_delta,
            "own_production": self.own_production,
            "own_ship_delta": self.own_ship_delta,
            "score": self.score,
            "source_counterattack_lost_ids": list(
                self.source_counterattack_lost_ids
            ),
            "source_counterattack_lost_production": (
                self.source_counterattack_lost_production
            ),
            "source_planet_lost_ids": list(self.source_planet_lost_ids),
            "source_planet_lost_production": self.source_planet_lost_production,
            "target_hold_failure_ids": list(self.target_hold_failure_ids),
            "target_hold_failure_production": self.target_hold_failure_production,
            "target_owned_by_player_count": self.target_owned_by_player_count,
            "target_planet_ids": list(self.target_planet_ids),
            "valid": self.valid,
            "vulnerable_planet_lost_ids": list(self.vulnerable_planet_lost_ids),
            "vulnerable_planet_lost_production": (
                self.vulnerable_planet_lost_production
            ),
        }


@dataclass(frozen=True, slots=True)
class ScenarioEvaluation:
    """Scenario outcomes for one action-set plan."""

    plan_id: str
    outcomes: tuple[ScenarioOutcome, ...]
    valid: bool
    notes: tuple[str, ...] = ()

    @property
    def has_elimination(self) -> bool:
        return any(outcome.eliminated for outcome in self.outcomes if outcome.valid)

    @property
    def has_source_loss(self) -> bool:
        return any(outcome.source_planet_lost_ids for outcome in self.outcomes if outcome.valid)

    @property
    def has_source_counterattack_loss(self) -> bool:
        return any(
            outcome.source_counterattack_lost_ids
            for outcome in self.outcomes
            if outcome.valid
        )

    @property
    def has_target_hold_failure(self) -> bool:
        return any(
            outcome.target_hold_failure_ids
            for outcome in self.outcomes
            if outcome.valid
        )

    @property
    def has_vulnerable_loss(self) -> bool:
        return any(outcome.vulnerable_planet_lost_ids for outcome in self.outcomes if outcome.valid)

    def to_dict(self) -> dict[str, object]:
        return {
            "notes": list(self.notes),
            "outcomes": [outcome.to_dict() for outcome in self.outcomes],
            "plan_id": self.plan_id,
            "valid": self.valid,
        }


@dataclass(frozen=True, slots=True)
class EvaluatedPlan:
    """Planner V2 scored action-set plan."""

    plan: ActionSetPlan
    score: float
    score_components: tuple[tuple[str, float], ...] = ()
    horizon_scores: tuple[tuple[int, float], ...] = ()
    selected_horizon: int | None = None
    scenario_evaluation: ScenarioEvaluation | None = None
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
            "scenario_evaluation": (
                None
                if self.scenario_evaluation is None
                else self.scenario_evaluation.to_dict()
            ),
        }


@dataclass(frozen=True, slots=True)
class FallbackRankRecord:
    """Final-selection ordering evidence for one evaluated V2 plan."""

    plan_id: str
    rank: int
    score: float
    selected: bool = False

    def to_dict(self) -> dict[str, object]:
        return {
            "plan_id": self.plan_id,
            "rank": self.rank,
            "score": self.score,
            "selected": self.selected,
        }


@dataclass(frozen=True, slots=True)
class PlannerV2FunnelDiagnostics:
    """Minimal V2 planner-funnel diagnostics for search diagnosis."""

    action_set_report: ActionSetCoverageReport
    fallback_ranks: tuple[FallbackRankRecord, ...] = ()

    def to_dict(self) -> dict[str, object]:
        return {
            "action_set_report": self.action_set_report.to_dict(),
            "fallback_ranks": [
                record.to_dict()
                for record in self.fallback_ranks
            ],
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
    funnel_diagnostics: PlannerV2FunnelDiagnostics | None = None
    trajectory_diagnosis: TrajectoryDiagnosis | None = None

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
            "funnel_diagnostics": (
                None
                if self.funnel_diagnostics is None
                else self.funnel_diagnostics.to_dict()
            ),
            "no_action_reason": self.no_action_reason,
            "notes": list(self.notes),
            "selected_plan": None if self.selected_plan is None else self.selected_plan.to_dict(),
            "trajectory_diagnosis": (
                None
                if self.trajectory_diagnosis is None
                else self.trajectory_diagnosis.to_dict()
            ),
        }


def _validate_optional_nonnegative_int(value: object, name: str) -> None:
    if value is None:
        return
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{name} must be None or an integer >= 0")


__all__ = (
    "ActionSetPlan",
    "ActionSetCoverageReport",
    "ActionSetPruneRecord",
    "BoardDiagnosis",
    "EvaluatedPlan",
    "FallbackRankRecord",
    "MissionFamily",
    "MissionPlan",
    "PlannerV2Config",
    "PlannerV2Mode",
    "PlannerV2FunnelDiagnostics",
    "PlannerV2Result",
    "ScenarioEvaluation",
    "ScenarioOutcome",
    "TrajectoryDiagnosis",
    "TrajectoryObjective",
    "TrajectoryPhase",
)
