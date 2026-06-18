"""Deterministic experiment manifests for local evaluation runs.

Evaluation Harness Cycle 12 defines reusable manifest and promotion-threshold
contracts, plus ordered expansion into ``MatchConfig`` objects. It does not run
matches, enforce promotion decisions, or import Kaggle environments.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass, field
from numbers import Real

from .contracts import AgentSpec, MatchConfig, OpponentSpec, PlayerCount


@dataclass(frozen=True, slots=True)
class PromotionThresholds:
    """Declarative thresholds for later promotion-gate cycles."""

    min_win_rate: float | None = None
    max_error_rate: float | None = None
    max_mean_rank: float | None = None
    min_completed_count: int | None = None

    def __post_init__(self) -> None:
        _validate_optional_rate(self.min_win_rate, "min_win_rate")
        _validate_optional_rate(self.max_error_rate, "max_error_rate")
        _validate_optional_nonnegative_number(self.max_mean_rank, "max_mean_rank")
        _validate_optional_nonnegative_int(
            self.min_completed_count,
            "min_completed_count",
        )

    def to_dict(self) -> dict[str, object]:
        """Return a deterministic JSON-safe dictionary."""

        return {
            "min_win_rate": self.min_win_rate,
            "max_error_rate": self.max_error_rate,
            "max_mean_rank": self.max_mean_rank,
            "min_completed_count": self.min_completed_count,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, object]) -> PromotionThresholds:
        """Create ``PromotionThresholds`` from a plain dictionary."""

        if not isinstance(data, Mapping):
            raise ValueError("promotion_thresholds must be a mapping")
        return cls(
            min_win_rate=_optional_float(data.get("min_win_rate"), "min_win_rate"),
            max_error_rate=_optional_float(
                data.get("max_error_rate"),
                "max_error_rate",
            ),
            max_mean_rank=_optional_float(data.get("max_mean_rank"), "max_mean_rank"),
            min_completed_count=_optional_int(
                data.get("min_completed_count"),
                "min_completed_count",
            ),
        )


@dataclass(frozen=True, slots=True)
class ExperimentScenario:
    """One fixed local evaluation scenario in an experiment manifest."""

    seed: int
    player_count: PlayerCount
    controlled_seat: int
    opponent_agents: tuple[OpponentSpec, ...]
    label: str | None = None
    metadata: tuple[tuple[str, str], ...] = ()

    def __post_init__(self) -> None:
        _validate_int(self.seed, "seed")
        if not isinstance(self.player_count, PlayerCount):
            raise ValueError("player_count must be a PlayerCount")
        _validate_int(self.controlled_seat, "controlled_seat")
        if not isinstance(self.opponent_agents, tuple):
            raise ValueError("opponent_agents must be a tuple")
        for opponent in self.opponent_agents:
            if not isinstance(opponent, OpponentSpec):
                raise ValueError("opponent_agents entries must be OpponentSpec")
        if self.label is not None:
            _validate_nonempty_string(self.label, "label")
        _validate_metadata(self.metadata)

    def to_dict(self) -> dict[str, object]:
        """Return a deterministic JSON-safe dictionary."""

        return {
            "seed": self.seed,
            "player_count": self.player_count.value,
            "controlled_seat": self.controlled_seat,
            "opponent_agents": [
                opponent.to_dict()
                for opponent in self.opponent_agents
            ],
            "label": self.label,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, object]) -> ExperimentScenario:
        """Create ``ExperimentScenario`` from a plain dictionary."""

        if not isinstance(data, Mapping):
            raise ValueError("scenario must be a mapping")
        opponents_data = data.get("opponent_agents", ())
        if not isinstance(opponents_data, (list, tuple)):
            raise ValueError("opponent_agents must be a sequence")
        opponents = []
        for index, opponent in enumerate(opponents_data):
            if not isinstance(opponent, Mapping):
                raise ValueError(f"opponent_agents[{index}] must be a mapping")
            opponents.append(OpponentSpec.from_dict(opponent))
        return cls(
            seed=_int_or_raise(data.get("seed"), "seed"),
            player_count=PlayerCount(data.get("player_count")),
            controlled_seat=_int_or_raise(
                data.get("controlled_seat"),
                "controlled_seat",
            ),
            opponent_agents=tuple(opponents),
            label=_optional_string(data.get("label"), "label"),
            metadata=_metadata_from_mapping(data.get("metadata")),
        )


@dataclass(frozen=True, slots=True)
class ExperimentManifest:
    """Reusable deterministic local evaluation experiment manifest."""

    name: str
    candidate_agent: AgentSpec
    scenarios: tuple[ExperimentScenario, ...]
    description: str | None = None
    version: str | None = None
    metadata: tuple[tuple[str, str], ...] = ()
    promotion_thresholds: PromotionThresholds = field(
        default_factory=lambda: PromotionThresholds()
    )

    def __post_init__(self) -> None:
        _validate_nonempty_string(self.name, "name")
        if not isinstance(self.candidate_agent, AgentSpec):
            raise ValueError("candidate_agent must be an AgentSpec")
        if not isinstance(self.scenarios, tuple):
            raise ValueError("scenarios must be a tuple")
        for scenario in self.scenarios:
            if not isinstance(scenario, ExperimentScenario):
                raise ValueError("scenarios entries must be ExperimentScenario")
        if self.description is not None:
            _validate_nonempty_string(self.description, "description")
        if self.version is not None:
            _validate_nonempty_string(self.version, "version")
        _validate_metadata(self.metadata)
        if not isinstance(self.promotion_thresholds, PromotionThresholds):
            raise ValueError("promotion_thresholds must be PromotionThresholds")

    def to_dict(self) -> dict[str, object]:
        """Return a deterministic JSON-safe dictionary."""

        return {
            "name": self.name,
            "candidate_agent": self.candidate_agent.to_dict(),
            "scenarios": [
                scenario.to_dict()
                for scenario in self.scenarios
            ],
            "description": self.description,
            "version": self.version,
            "metadata": dict(self.metadata),
            "promotion_thresholds": self.promotion_thresholds.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, object]) -> ExperimentManifest:
        """Create ``ExperimentManifest`` from a plain dictionary."""

        if not isinstance(data, Mapping):
            raise ValueError("manifest must be a mapping")
        candidate_data = data.get("candidate_agent")
        if not isinstance(candidate_data, Mapping):
            raise ValueError("candidate_agent must be a mapping")
        scenarios_data = data.get("scenarios", ())
        if not isinstance(scenarios_data, (list, tuple)):
            raise ValueError("scenarios must be a sequence")
        scenarios = []
        for index, scenario in enumerate(scenarios_data):
            if not isinstance(scenario, Mapping):
                raise ValueError(f"scenarios[{index}] must be a mapping")
            scenarios.append(ExperimentScenario.from_dict(scenario))
        thresholds_data = data.get("promotion_thresholds", {})
        if not isinstance(thresholds_data, Mapping):
            raise ValueError("promotion_thresholds must be a mapping")
        return cls(
            name=_string_or_raise(data.get("name"), "name"),
            candidate_agent=AgentSpec.from_dict(candidate_data),
            scenarios=tuple(scenarios),
            description=_optional_string(data.get("description"), "description"),
            version=_optional_string(data.get("version"), "version"),
            metadata=_metadata_from_mapping(data.get("metadata")),
            promotion_thresholds=PromotionThresholds.from_dict(thresholds_data),
        )


def manifest_to_match_configs(
    manifest: ExperimentManifest,
) -> tuple[MatchConfig, ...]:
    """Expand ``manifest`` scenarios into ordered ``MatchConfig`` objects."""

    if not isinstance(manifest, ExperimentManifest):
        raise ValueError("manifest must be an ExperimentManifest")
    return tuple(
        MatchConfig(
            seed=scenario.seed,
            player_count=scenario.player_count,
            controlled_seat=scenario.controlled_seat,
            candidate_agent=manifest.candidate_agent,
            opponent_agents=scenario.opponent_agents,
            label=scenario.label,
            metadata=scenario.metadata,
        )
        for scenario in manifest.scenarios
    )


def _validate_nonempty_string(value: object, name: str) -> None:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{name} must be a non-empty string")


def _validate_int(value: object, name: str) -> None:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{name} must be an integer")


def _int_or_raise(value: object, name: str) -> int:
    _validate_int(value, name)
    return value


def _optional_int(value: object, name: str) -> int | None:
    if value is None:
        return None
    return _int_or_raise(value, name)


def _optional_float(value: object, name: str) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, Real):
        raise ValueError(f"{name} must be a number")
    numeric_value = float(value)
    if not math.isfinite(numeric_value):
        raise ValueError(f"{name} must be finite")
    return numeric_value


def _optional_string(value: object, name: str) -> str | None:
    if value is None:
        return None
    return _string_or_raise(value, name)


def _string_or_raise(value: object, name: str) -> str:
    _validate_nonempty_string(value, name)
    return value


def _metadata_from_mapping(value: object) -> tuple[tuple[str, str], ...]:
    if value is None:
        return ()
    if not isinstance(value, Mapping):
        raise ValueError("metadata must be a mapping")
    return tuple(sorted((str(key), str(item)) for key, item in value.items()))


def _validate_metadata(metadata: tuple[tuple[str, str], ...]) -> None:
    if not isinstance(metadata, tuple):
        raise ValueError("metadata must be a tuple")
    for item in metadata:
        if not isinstance(item, tuple) or len(item) != 2:
            raise ValueError("metadata entries must be key/value tuples")
        _validate_nonempty_string(item[0], "metadata key")
        if not isinstance(item[1], str):
            raise ValueError("metadata values must be strings")


def _validate_optional_nonnegative_int(value: int | None, name: str) -> None:
    if value is None:
        return
    _validate_int(value, name)
    if value < 0:
        raise ValueError(f"{name} must be non-negative")


def _validate_optional_nonnegative_number(value: float | None, name: str) -> None:
    if value is None:
        return
    if isinstance(value, bool) or not isinstance(value, Real):
        raise ValueError(f"{name} must be a non-negative number")
    if not math.isfinite(float(value)) or float(value) < 0.0:
        raise ValueError(f"{name} must be a non-negative number")


def _validate_optional_rate(value: float | None, name: str) -> None:
    _validate_optional_nonnegative_number(value, name)
    if value is not None and float(value) > 1.0:
        raise ValueError(f"{name} must be between 0.0 and 1.0")


__all__ = (
    "ExperimentManifest",
    "ExperimentScenario",
    "PromotionThresholds",
    "manifest_to_match_configs",
)
