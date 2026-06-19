"""Single-match official environment smoke runner.

This module runs one ``MatchConfig`` through the local official
``kaggle_environments`` Orbit Wars environment, extracts deterministic metrics
from safe replay payloads, and optionally writes artifacts. It avoids importing
``kaggle_environments`` until ``run_official_match`` is called.
"""

from __future__ import annotations

import io
from collections.abc import Mapping, Sequence
from contextlib import redirect_stderr, redirect_stdout
from dataclasses import replace
from typing import Any

from .agent_loading import KaggleAgent, load_agent_callable
from .artifacts import (
    EvaluationArtifactConfig,
    artifact_paths_for_config,
    write_match_result_artifact,
    write_replay_artifact,
)
from .contracts import (
    AgentSpec,
    EvaluationStatus,
    MatchConfig,
    MatchResult,
)
from .metrics import extract_match_metrics


class AgentExecutionError(RuntimeError):
    """Raised when a loaded agent fails during official environment execution."""


def run_official_match(
    config: MatchConfig,
    artifacts: EvaluationArtifactConfig | None = None,
) -> MatchResult:
    """Run exactly one local official Orbit Wars match for ``config``."""

    try:
        agents = _agents_for_config(config)
    except Exception as exc:
        result = _match_result(config, EvaluationStatus.IMPORT_ERROR, exc)
        return _finalize_match_result(
            result=result,
            artifacts=artifacts,
            env=None,
            replay_allowed=False,
        )

    env: Any | None = None
    try:
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            from kaggle_environments import make

            env = make(
                "orbit_wars",
                configuration=_official_environment_configuration(config),
                debug=True,
            )
            env.reset(config.player_count.value)
            env.run(list(agents))
    except AgentExecutionError as exc:
        result = _match_result(config, EvaluationStatus.AGENT_ERROR, exc)
        return _finalize_match_result(
            result=result,
            artifacts=artifacts,
            env=env,
            replay_allowed=True,
        )
    except Exception as exc:
        result = _match_result(config, EvaluationStatus.ENV_ERROR, exc)
        return _finalize_match_result(
            result=result,
            artifacts=artifacts,
            env=env,
            replay_allowed=True,
        )

    return _finalize_match_result(
        result=MatchResult(config=config, status=EvaluationStatus.COMPLETED),
        artifacts=artifacts,
        env=env,
        replay_allowed=True,
    )


def _agents_for_config(config: MatchConfig) -> tuple[KaggleAgent, ...]:
    seats: list[KaggleAgent | None] = [None] * config.player_count.value
    seats[config.controlled_seat] = _wrapped_agent(config.candidate_agent)

    opponent_iter = iter(config.opponent_agents)
    for seat_index in range(config.player_count.value):
        if seat_index == config.controlled_seat:
            continue
        seats[seat_index] = _wrapped_agent(next(opponent_iter).agent)

    return tuple(agent for agent in seats if agent is not None)


def _official_environment_configuration(config: MatchConfig) -> dict[str, int]:
    configuration = {"seed": config.seed}
    metadata = dict(config.metadata)
    episode_steps = metadata.get("episode_steps")
    if episode_steps is not None:
        configuration["episodeSteps"] = _positive_int_from_metadata(
            episode_steps,
            "episode_steps",
        )
    return configuration


def _positive_int_from_metadata(value: str, name: str) -> int:
    try:
        parsed = int(value)
    except ValueError as exc:
        raise ValueError(f"{name} must be a positive integer") from exc
    if parsed <= 0:
        raise ValueError(f"{name} must be a positive integer")
    return parsed


def _wrapped_agent(agent_spec: AgentSpec) -> KaggleAgent:
    agent = load_agent_callable(agent_spec)

    def wrapped_agent(observation: Any, configuration: Any = None) -> list[list[int | float]]:
        try:
            return agent(observation, configuration)
        except Exception as exc:
            raise AgentExecutionError(
                f"{agent_spec.name}: {_error_text(exc)}",
            ) from exc

    return wrapped_agent


def _match_result(
    config: MatchConfig,
    status: EvaluationStatus,
    exc: Exception,
) -> MatchResult:
    return MatchResult(
        config=config,
        status=status,
        error_text=_error_text(exc),
    )


def _error_text(exc: Exception) -> str:
    return f"{type(exc).__name__}: {exc}"


def _finalize_match_result(
    *,
    result: MatchResult,
    artifacts: EvaluationArtifactConfig | None,
    env: Any | None,
    replay_allowed: bool,
) -> MatchResult:
    replay_payload = (
        _safe_replay_payload(env)
        if replay_allowed and env is not None
        else None
    )

    try:
        result = _result_with_metrics(result, replay_payload)
    except Exception as exc:
        return MatchResult(
            config=result.config,
            status=EvaluationStatus.UNKNOWN_ERROR,
            error_text=_error_text(exc),
        )

    if artifacts is None:
        return result

    try:
        return _write_requested_artifacts(
            result=result,
            artifact_config=artifacts,
            replay_payload=replay_payload,
        )
    except Exception as exc:
        return MatchResult(
            config=result.config,
            status=EvaluationStatus.UNKNOWN_ERROR,
            error_text=_error_text(exc),
        )


def _write_requested_artifacts(
    *,
    result: MatchResult,
    artifact_config: EvaluationArtifactConfig,
    replay_payload: Mapping[str, object] | Sequence[object] | None,
) -> MatchResult:
    replay_path, artifact_path = artifact_paths_for_config(result.config, artifact_config)

    written_replay_path: str | None = None
    if artifact_config.write_replay and replay_payload is not None:
        written_replay_path = str(write_replay_artifact(replay_payload, replay_path))

    final_result = replace(
        result,
        replay_path=written_replay_path,
        artifact_path=str(artifact_path) if artifact_config.write_result else None,
    )
    if artifact_config.write_result:
        write_match_result_artifact(final_result, artifact_path)
    return final_result


def _result_with_metrics(
    result: MatchResult,
    replay_payload: Mapping[str, object] | Sequence[object] | None,
) -> MatchResult:
    if not isinstance(replay_payload, Mapping):
        return result
    return replace(
        result,
        metrics=extract_match_metrics(
            replay_payload,
            result.config.controlled_seat,
        ),
    )


def _safe_replay_payload(env: Any) -> Mapping[str, object] | Sequence[object] | None:
    try:
        payload = env.toJSON()
    except Exception:
        return None
    if isinstance(payload, (str, bytes)):
        return None
    if not isinstance(payload, (Mapping, Sequence)):
        return None
    return payload


__all__ = ("run_official_match",)
