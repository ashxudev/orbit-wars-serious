"""Single-match official environment smoke runner.

This module runs one ``MatchConfig`` through the local official
``kaggle_environments`` Orbit Wars environment, extracts deterministic metrics
from safe replay payloads, and optionally writes artifacts. It avoids importing
``kaggle_environments`` until ``run_official_match`` is called.
"""

from __future__ import annotations

import io
from collections.abc import Mapping, Sequence
from contextlib import nullcontext, redirect_stderr, redirect_stdout
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
        candidate_diagnostics: list[tuple[tuple[str, str], ...]] = []
        agents = _agents_for_config(config, candidate_diagnostics)
    except Exception as exc:
        result = _match_result(config, EvaluationStatus.IMPORT_ERROR, exc)
        return _finalize_match_result(
            result=result,
            artifacts=artifacts,
            env=None,
            replay_allowed=False,
            candidate_diagnostics=(),
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
            candidate_diagnostics=tuple(candidate_diagnostics),
        )
    except Exception as exc:
        result = _match_result(config, EvaluationStatus.ENV_ERROR, exc)
        return _finalize_match_result(
            result=result,
            artifacts=artifacts,
            env=env,
            replay_allowed=True,
            candidate_diagnostics=tuple(candidate_diagnostics),
        )

    return _finalize_match_result(
        result=MatchResult(config=config, status=EvaluationStatus.COMPLETED),
        artifacts=artifacts,
        env=env,
        replay_allowed=True,
        candidate_diagnostics=tuple(candidate_diagnostics),
    )


def _agents_for_config(
    config: MatchConfig,
    candidate_diagnostics: list[tuple[tuple[str, str], ...]],
) -> tuple[KaggleAgent, ...]:
    seats: list[KaggleAgent | None] = [None] * config.player_count.value
    seats[config.controlled_seat] = _wrapped_agent(
        config.candidate_agent,
        diagnostics=candidate_diagnostics,
    )

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


def _wrapped_agent(
    agent_spec: AgentSpec,
    diagnostics: list[tuple[tuple[str, str], ...]] | None = None,
) -> KaggleAgent:
    agent = load_agent_callable(agent_spec)

    def wrapped_agent(observation: Any, configuration: Any = None) -> list[list[int | float]]:
        try:
            actions = agent(observation, configuration)
            if diagnostics is not None:
                diagnostics.append(_runtime_diagnostics_for_agent(agent, actions))
            return actions
        except Exception as exc:
            raise AgentExecutionError(
                f"{agent_spec.name}: {_error_text(exc)}",
            ) from exc

    return wrapped_agent


def _runtime_diagnostics_for_agent(
    agent: KaggleAgent,
    actions: list[list[int | float]],
) -> tuple[tuple[str, str], ...]:
    getter = _runtime_diagnostic_getter(agent)
    isolation_context = _agent_isolation_context(agent)
    context = isolation_context() if isolation_context is not None else nullcontext()
    with context:
        metadata = getter() if getter is not None else ()
    if metadata:
        return metadata
    return (
        ("runtime_diagnostic_status", "unknown"),
        ("runtime_diagnostic_no_action_reason", "runtime_diagnostic_unavailable"),
        ("runtime_diagnostic_action_count", str(len(actions))),
    )


def _runtime_diagnostic_getter(agent: KaggleAgent) -> Any | None:
    for wrapped_agent in _closed_over_callables(agent):
        getter = _runtime_diagnostic_getter(wrapped_agent)
        if getter is not None:
            return getter
    agent_globals = getattr(agent, "__globals__", None)
    if not isinstance(agent_globals, Mapping):
        return None
    safe_actions = agent_globals.get("safe_actions_for_observation")
    safe_action_globals = getattr(safe_actions, "__globals__", None)
    if not isinstance(safe_action_globals, Mapping):
        return None
    getter = safe_action_globals.get("last_runtime_diagnostic_metadata")
    return getter if callable(getter) else None


def _agent_isolation_context(agent: KaggleAgent) -> Any | None:
    context = getattr(agent, "isolated_modules", None)
    if callable(context):
        return context
    for wrapped_agent in _closed_over_callables(agent):
        context = _agent_isolation_context(wrapped_agent)
        if context is not None:
            return context
    return None


def _closed_over_callables(agent: KaggleAgent) -> tuple[KaggleAgent, ...]:
    closure = getattr(agent, "__closure__", None)
    if not closure:
        return ()
    callables = []
    for cell in closure:
        try:
            value = cell.cell_contents
        except ValueError:
            continue
        if callable(value):
            callables.append(value)
    return tuple(callables)


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
    candidate_diagnostics: tuple[tuple[tuple[str, str], ...], ...],
) -> MatchResult:
    replay_payload = (
        _safe_replay_payload(env)
        if replay_allowed and env is not None
        else None
    )

    try:
        result = _result_with_metrics(result, replay_payload)
        result = _result_with_runtime_diagnostics(result, candidate_diagnostics)
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


def _result_with_runtime_diagnostics(
    result: MatchResult,
    diagnostics: tuple[tuple[tuple[str, str], ...], ...],
) -> MatchResult:
    metadata = _runtime_diagnostic_summary(diagnostics)
    if not metadata:
        return result
    return replace(
        result,
        metadata=tuple(sorted((*result.metadata, *metadata))),
    )


def _runtime_diagnostic_summary(
    diagnostics: tuple[tuple[tuple[str, str], ...], ...],
) -> tuple[tuple[str, str], ...]:
    if not diagnostics:
        return ()
    records = tuple(dict(record) for record in diagnostics)
    action_counts = tuple(
        _metadata_int(record.get("runtime_diagnostic_action_count"))
        for record in records
    )
    no_action_records = tuple(
        record
        for record, action_count in zip(records, action_counts)
        if action_count == 0
    )
    reason_counts = _reason_counts(no_action_records)
    metadata = [
        ("runtime_diagnostic_turn_count", str(len(records))),
        (
            "runtime_diagnostic_action_turn_count",
            str(sum(1 for count in action_counts if count > 0)),
        ),
        ("runtime_diagnostic_no_action_turn_count", str(len(no_action_records))),
    ]
    if reason_counts:
        metadata.extend(
            (
                (
                    "runtime_diagnostic_no_action_reasons",
                    ",".join(
                        f"{reason}:{count}"
                        for reason, count in reason_counts
                    ),
                ),
                (
                    "runtime_diagnostic_primary_no_action_reason",
                    reason_counts[0][0],
                ),
                (
                    "runtime_diagnostic_last_no_action_reason",
                    no_action_records[-1].get(
                        "runtime_diagnostic_no_action_reason",
                        "unknown",
                    ),
                ),
            )
        )
    last_record = records[-1]
    for key in (
        "runtime_diagnostic_status",
        "runtime_diagnostic_selection_status",
        "runtime_diagnostic_selection_notes",
        "runtime_diagnostic_selected_commitment_type",
        "runtime_diagnostic_selected_commitment_status",
        "runtime_diagnostic_candidate_count",
        "runtime_diagnostic_evaluation_count",
        "runtime_diagnostic_validated_commitment_count",
        "runtime_diagnostic_action_count",
    ):
        if key in last_record:
            metadata.append((f"{key}_last", last_record[key]))
    return tuple(metadata)


def _reason_counts(
    records: tuple[dict[str, str], ...],
) -> tuple[tuple[str, int], ...]:
    counts: dict[str, int] = {}
    order: list[str] = []
    for record in records:
        reason = record.get("runtime_diagnostic_no_action_reason", "unknown")
        if reason not in counts:
            counts[reason] = 0
            order.append(reason)
        counts[reason] += 1
    ordered = sorted(
        ((reason, counts[reason], index) for index, reason in enumerate(order)),
        key=lambda item: (-item[1], item[2]),
    )
    return tuple((reason, count) for reason, count, _index in ordered)


def _metadata_int(value: str | None) -> int:
    if value is None:
        return 0
    try:
        return int(value)
    except ValueError:
        return 0


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
