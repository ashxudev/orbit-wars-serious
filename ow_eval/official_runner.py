"""Single-match official environment smoke runner.

Evaluation Harness Cycle 1 runs one ``MatchConfig`` through the local official
``kaggle_environments`` Orbit Wars environment. This module avoids importing
``kaggle_environments`` until ``run_official_match`` is called.
"""

from __future__ import annotations

import importlib
import io
from collections.abc import Callable
from contextlib import redirect_stderr, redirect_stdout
from typing import Any

from .contracts import (
    AgentSourceKind,
    AgentSpec,
    EvaluationStatus,
    MatchConfig,
    MatchResult,
    OpponentSpec,
)


KaggleAgent = Callable[[Any, Any], list[list[int | float]]]


class AgentExecutionError(RuntimeError):
    """Raised when a loaded agent fails during official environment execution."""


def run_official_match(config: MatchConfig) -> MatchResult:
    """Run exactly one local official Orbit Wars match for ``config``."""

    try:
        agents = _agents_for_config(config)
    except Exception as exc:
        return _match_result(config, EvaluationStatus.IMPORT_ERROR, exc)

    try:
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            from kaggle_environments import make

            env = make("orbit_wars", configuration={"seed": config.seed}, debug=True)
            env.reset(config.player_count.value)
            env.run(list(agents))
    except AgentExecutionError as exc:
        return _match_result(config, EvaluationStatus.AGENT_ERROR, exc)
    except Exception as exc:
        return _match_result(config, EvaluationStatus.ENV_ERROR, exc)

    return MatchResult(config=config, status=EvaluationStatus.COMPLETED)


def _agents_for_config(config: MatchConfig) -> tuple[KaggleAgent, ...]:
    seats: list[KaggleAgent | None] = [None] * config.player_count.value
    seats[config.controlled_seat] = _candidate_agent(config.candidate_agent)

    opponent_iter = iter(config.opponent_agents)
    for seat_index in range(config.player_count.value):
        if seat_index == config.controlled_seat:
            continue
        seats[seat_index] = _opponent_agent(next(opponent_iter))

    return tuple(agent for agent in seats if agent is not None)


def _candidate_agent(agent_spec: AgentSpec) -> KaggleAgent:
    if agent_spec.source_kind is not AgentSourceKind.MODULAR_AGENT:
        raise ValueError(
            "candidate agent source kind must be modular_agent",
        )
    return _wrap_agent(agent_spec, _modular_agent_callable(agent_spec))


def _opponent_agent(opponent_spec: OpponentSpec) -> KaggleAgent:
    if opponent_spec.agent.source_kind is not AgentSourceKind.BUILTIN_BASELINE:
        raise ValueError(
            "opponent agent source kind must be builtin_baseline",
        )
    return _noop_baseline_agent


def _modular_agent_callable(agent_spec: AgentSpec) -> KaggleAgent:
    if agent_spec.module_path is None:
        raise ValueError("module_path is required for modular agent")

    module = importlib.import_module(agent_spec.module_path)
    candidate = getattr(module, agent_spec.callable_name)
    if not callable(candidate):
        raise ValueError(f"{agent_spec.callable_name} is not callable")
    return candidate


def _wrap_agent(agent_spec: AgentSpec, agent: KaggleAgent) -> KaggleAgent:
    def wrapped_agent(observation: Any, configuration: Any = None) -> list[list[int | float]]:
        try:
            return agent(observation, configuration)
        except Exception as exc:
            raise AgentExecutionError(
                f"{agent_spec.name}: {_error_text(exc)}",
            ) from exc

    return wrapped_agent


def _noop_baseline_agent(
    observation: Any,
    configuration: Any = None,
) -> list[list[int | float]]:
    _ = observation, configuration
    return []


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


__all__ = ("run_official_match",)
