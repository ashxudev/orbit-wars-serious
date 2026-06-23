"""Typed contracts for future local Orbit Wars evaluation runs.

Evaluation Harness Cycle 0 defines stable immutable shapes only. It does not
import Kaggle environments, launch matches, capture replays, or write result
artifacts.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Mapping


class AgentSourceKind(str, Enum):
    """Where an evaluation harness should load an agent from."""

    MODULAR_AGENT = "modular_agent"
    SUBMISSION_FILE = "submission_file"
    PYTHON_FILE = "python_file"
    BUILTIN_BASELINE = "builtin_baseline"


class PlayerCount(int, Enum):
    """Supported local match player counts."""

    TWO_PLAYER = 2
    FOUR_PLAYER = 4


class EvaluationStatus(str, Enum):
    """Lifecycle status for future local evaluation results."""

    NOT_RUN = "not_run"
    COMPLETED = "completed"
    IMPORT_ERROR = "import_error"
    ENV_ERROR = "env_error"
    AGENT_ERROR = "agent_error"
    TIMEOUT = "timeout"
    INVALID_ACTION = "invalid_action"
    UNKNOWN_ERROR = "unknown_error"


@dataclass(frozen=True, slots=True)
class AgentSpec:
    """Declarative source descriptor for one evaluated agent."""

    name: str
    source_kind: AgentSourceKind
    module_path: str | None = None
    file_path: str | None = None
    callable_name: str = "agent"
    metadata: tuple[tuple[str, str], ...] = ()

    def __post_init__(self) -> None:
        _validate_nonempty_string(self.name, "name")
        _validate_nonempty_string(self.callable_name, "callable_name")
        _validate_metadata(self.metadata)

    def to_dict(self) -> dict[str, object]:
        """Return a deterministic plain dictionary representation."""

        return {
            "name": self.name,
            "source_kind": self.source_kind.value,
            "module_path": self.module_path,
            "file_path": self.file_path,
            "callable_name": self.callable_name,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, object]) -> AgentSpec:
        """Create an ``AgentSpec`` from a deterministic dictionary."""

        return cls(
            name=_string_or_raise(data.get("name"), "name"),
            source_kind=AgentSourceKind(data.get("source_kind")),
            module_path=_optional_string(data.get("module_path"), "module_path"),
            file_path=_optional_string(data.get("file_path"), "file_path"),
            callable_name=_string_or_default(
                data.get("callable_name"),
                "callable_name",
                "agent",
            ),
            metadata=_metadata_from_mapping(data.get("metadata")),
        )


@dataclass(frozen=True, slots=True)
class OpponentSpec:
    """Thin wrapper around an opponent agent descriptor."""

    agent: AgentSpec

    @property
    def name(self) -> str:
        return self.agent.name

    def to_dict(self) -> dict[str, object]:
        """Return a deterministic plain dictionary representation."""

        return {"agent": self.agent.to_dict()}

    @classmethod
    def from_dict(cls, data: Mapping[str, object]) -> OpponentSpec:
        """Create an ``OpponentSpec`` from a deterministic dictionary."""

        agent_data = data.get("agent")
        if not isinstance(agent_data, Mapping):
            raise ValueError("agent must be a mapping")
        return cls(agent=AgentSpec.from_dict(agent_data))


@dataclass(frozen=True, slots=True)
class MatchConfig:
    """Declarative config for one future local match run."""

    seed: int
    player_count: PlayerCount
    controlled_seat: int
    candidate_agent: AgentSpec
    opponent_agents: tuple[OpponentSpec, ...] = ()
    label: str | None = None
    metadata: tuple[tuple[str, str], ...] = ()

    def __post_init__(self) -> None:
        if isinstance(self.seed, bool) or not isinstance(self.seed, int):
            raise ValueError("seed must be an integer")
        if isinstance(self.controlled_seat, bool) or not isinstance(
            self.controlled_seat,
            int,
        ):
            raise ValueError("controlled_seat must be an integer")
        if self.controlled_seat < 0 or self.controlled_seat >= self.player_count.value:
            raise ValueError("controlled_seat must be within player count")
        expected_opponents = self.player_count.value - 1
        if len(self.opponent_agents) != expected_opponents:
            raise ValueError("opponent_agents must match player count")
        if self.label is not None:
            _validate_nonempty_string(self.label, "label")
        _validate_metadata(self.metadata)

    def to_dict(self) -> dict[str, object]:
        """Return a deterministic plain dictionary representation."""

        return {
            "seed": self.seed,
            "player_count": self.player_count.value,
            "controlled_seat": self.controlled_seat,
            "candidate_agent": self.candidate_agent.to_dict(),
            "opponent_agents": [
                opponent.to_dict()
                for opponent in self.opponent_agents
            ],
            "label": self.label,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, object]) -> MatchConfig:
        """Create a ``MatchConfig`` from a deterministic dictionary."""

        candidate_data = data.get("candidate_agent")
        if not isinstance(candidate_data, Mapping):
            raise ValueError("candidate_agent must be a mapping")
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
            candidate_agent=AgentSpec.from_dict(candidate_data),
            opponent_agents=tuple(opponents),
            label=_optional_string(data.get("label"), "label"),
            metadata=_metadata_from_mapping(data.get("metadata")),
        )


@dataclass(frozen=True, slots=True)
class MatchMetrics:
    """Summary metrics extracted from one local official match replay."""

    final_rank: int | None = None
    final_score: float | None = None
    final_planets: int | None = None
    final_ships: int | None = None
    final_production: int | None = None
    turns_survived: int | None = None
    no_action_count: int | None = None
    error_count: int | None = None
    invalid_action_count: int | None = None
    timeout_count: int | None = None
    action_count_after_t20: int | None = None
    no_action_with_owned_production_count: int | None = None
    enemy_target_action_count: int | None = None
    own_transfer_action_count: int | None = None
    neutral_target_action_count: int | None = None
    production_collapse: bool | None = None
    defense_coverage_count: int | None = None
    four_player_rank_pressure_count: int | None = None
    early_elimination: bool | None = None

    def to_dict(self) -> dict[str, object]:
        """Return a deterministic plain dictionary representation."""

        return {
            "final_rank": self.final_rank,
            "final_score": self.final_score,
            "final_planets": self.final_planets,
            "final_ships": self.final_ships,
            "final_production": self.final_production,
            "turns_survived": self.turns_survived,
            "no_action_count": self.no_action_count,
            "error_count": self.error_count,
            "invalid_action_count": self.invalid_action_count,
            "timeout_count": self.timeout_count,
            "action_count_after_t20": self.action_count_after_t20,
            "no_action_with_owned_production_count": (
                self.no_action_with_owned_production_count
            ),
            "enemy_target_action_count": self.enemy_target_action_count,
            "own_transfer_action_count": self.own_transfer_action_count,
            "neutral_target_action_count": self.neutral_target_action_count,
            "production_collapse": self.production_collapse,
            "defense_coverage_count": self.defense_coverage_count,
            "four_player_rank_pressure_count": self.four_player_rank_pressure_count,
            "early_elimination": self.early_elimination,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, object]) -> MatchMetrics:
        """Create ``MatchMetrics`` from a deterministic dictionary."""

        return cls(
            final_rank=_optional_int(data.get("final_rank"), "final_rank"),
            final_score=_optional_float(data.get("final_score"), "final_score"),
            final_planets=_optional_int(data.get("final_planets"), "final_planets"),
            final_ships=_optional_int(data.get("final_ships"), "final_ships"),
            final_production=_optional_int(
                data.get("final_production"),
                "final_production",
            ),
            turns_survived=_optional_int(
                data.get("turns_survived"),
                "turns_survived",
            ),
            no_action_count=_optional_int(
                data.get("no_action_count"),
                "no_action_count",
            ),
            error_count=_optional_int(data.get("error_count"), "error_count"),
            invalid_action_count=_optional_int(
                data.get("invalid_action_count"),
                "invalid_action_count",
            ),
            timeout_count=_optional_int(data.get("timeout_count"), "timeout_count"),
            action_count_after_t20=_optional_int(
                data.get("action_count_after_t20"),
                "action_count_after_t20",
            ),
            no_action_with_owned_production_count=_optional_int(
                data.get("no_action_with_owned_production_count"),
                "no_action_with_owned_production_count",
            ),
            enemy_target_action_count=_optional_int(
                data.get("enemy_target_action_count"),
                "enemy_target_action_count",
            ),
            own_transfer_action_count=_optional_int(
                data.get("own_transfer_action_count"),
                "own_transfer_action_count",
            ),
            neutral_target_action_count=_optional_int(
                data.get("neutral_target_action_count"),
                "neutral_target_action_count",
            ),
            production_collapse=_optional_bool(
                data.get("production_collapse"),
                "production_collapse",
            ),
            defense_coverage_count=_optional_int(
                data.get("defense_coverage_count"),
                "defense_coverage_count",
            ),
            four_player_rank_pressure_count=_optional_int(
                data.get("four_player_rank_pressure_count"),
                "four_player_rank_pressure_count",
            ),
            early_elimination=_optional_bool(
                data.get("early_elimination"),
                "early_elimination",
            ),
        )


@dataclass(frozen=True, slots=True)
class MatchResult:
    """Result contract for one future local match run."""

    config: MatchConfig
    status: EvaluationStatus = EvaluationStatus.NOT_RUN
    metrics: MatchMetrics = MatchMetrics()
    error_text: str | None = None
    replay_path: str | None = None
    artifact_path: str | None = None
    metadata: tuple[tuple[str, str], ...] = ()

    def __post_init__(self) -> None:
        if self.error_text is not None:
            _validate_nonempty_string(self.error_text, "error_text")
        if self.replay_path is not None:
            _validate_nonempty_string(self.replay_path, "replay_path")
        if self.artifact_path is not None:
            _validate_nonempty_string(self.artifact_path, "artifact_path")
        _validate_metadata(self.metadata)

    def to_dict(self) -> dict[str, object]:
        """Return a deterministic plain dictionary representation."""

        return {
            "config": self.config.to_dict(),
            "status": self.status.value,
            "metrics": self.metrics.to_dict(),
            "error_text": self.error_text,
            "replay_path": self.replay_path,
            "artifact_path": self.artifact_path,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, object]) -> MatchResult:
        """Create a ``MatchResult`` from a deterministic dictionary."""

        config_data = data.get("config")
        if not isinstance(config_data, Mapping):
            raise ValueError("config must be a mapping")
        metrics_data = data.get("metrics", {})
        if not isinstance(metrics_data, Mapping):
            raise ValueError("metrics must be a mapping")
        return cls(
            config=MatchConfig.from_dict(config_data),
            status=EvaluationStatus(data.get("status", EvaluationStatus.NOT_RUN)),
            metrics=MatchMetrics.from_dict(metrics_data),
            error_text=_optional_string(data.get("error_text"), "error_text"),
            replay_path=_optional_string(data.get("replay_path"), "replay_path"),
            artifact_path=_optional_string(data.get("artifact_path"), "artifact_path"),
            metadata=_metadata_from_mapping(data.get("metadata")),
        )


def _validate_nonempty_string(value: object, name: str) -> None:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{name} must be a non-empty string")


def _validate_metadata(metadata: tuple[tuple[str, str], ...]) -> None:
    if not isinstance(metadata, tuple):
        raise ValueError("metadata must be a tuple")
    for item in metadata:
        if not isinstance(item, tuple) or len(item) != 2:
            raise ValueError("metadata entries must be key/value tuples")
        _validate_nonempty_string(item[0], "metadata key")
        if not isinstance(item[1], str):
            raise ValueError("metadata values must be strings")


def _metadata_from_mapping(value: object) -> tuple[tuple[str, str], ...]:
    if value is None:
        return ()
    if not isinstance(value, Mapping):
        raise ValueError("metadata must be a mapping")
    return tuple(sorted((str(key), str(item)) for key, item in value.items()))


def _string_or_raise(value: object, name: str) -> str:
    _validate_nonempty_string(value, name)
    return value


def _optional_string(value: object, name: str) -> str | None:
    if value is None:
        return None
    _validate_nonempty_string(value, name)
    return value


def _string_or_default(value: object, name: str, default: str) -> str:
    if value is None:
        return default
    return _string_or_raise(value, name)


def _int_or_raise(value: object, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{name} must be an integer")
    return value


def _optional_int(value: object, name: str) -> int | None:
    if value is None:
        return None
    return _int_or_raise(value, name)


def _optional_bool(value: object, name: str) -> bool | None:
    if value is None:
        return None
    if not isinstance(value, bool):
        raise ValueError(f"{name} must be a boolean or None")
    return value


def _optional_float(value: object, name: str) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (float, int)):
        raise ValueError(f"{name} must be a number")
    return float(value)


__all__ = (
    "AgentSourceKind",
    "AgentSpec",
    "EvaluationStatus",
    "MatchConfig",
    "MatchMetrics",
    "MatchResult",
    "OpponentSpec",
    "PlayerCount",
)
