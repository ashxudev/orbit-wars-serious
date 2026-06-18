"""Single-match official environment smoke runner.

Evaluation Harness Cycle 1 runs one ``MatchConfig`` through the local official
``kaggle_environments`` Orbit Wars environment. This module avoids importing
``kaggle_environments`` until ``run_official_match`` is called.
"""

from __future__ import annotations

import io
from contextlib import redirect_stderr, redirect_stdout
from typing import Any

from .agent_loading import KaggleAgent, load_agent_callable
from .contracts import (
    AgentSpec,
    EvaluationStatus,
    MatchConfig,
    MatchResult,
)


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
    seats[config.controlled_seat] = _wrapped_agent(config.candidate_agent)

    opponent_iter = iter(config.opponent_agents)
    for seat_index in range(config.player_count.value):
        if seat_index == config.controlled_seat:
            continue
        seats[seat_index] = _wrapped_agent(next(opponent_iter).agent)

    return tuple(agent for agent in seats if agent is not None)


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


__all__ = ("run_official_match",)
