"""Reusable agent loading for local evaluation harness runs.

Evaluation Harness Cycle 2 centralizes loading for all current
``AgentSourceKind`` values without importing ``kaggle_environments``.
"""

from __future__ import annotations

import hashlib
import importlib
import importlib.util
from collections.abc import Callable
from pathlib import Path
from typing import Any

from .baselines import load_builtin_baseline
from .contracts import AgentSourceKind, AgentSpec


KaggleAgent = Callable[[Any, Any], list[list[int | float]]]


def load_agent_callable(agent_spec: AgentSpec) -> KaggleAgent:
    """Load a Kaggle-compatible agent callable from ``agent_spec``."""

    if agent_spec.source_kind is AgentSourceKind.MODULAR_AGENT:
        return _load_modular_agent(agent_spec)
    if agent_spec.source_kind is AgentSourceKind.BUILTIN_BASELINE:
        return load_builtin_baseline(agent_spec)
    if agent_spec.source_kind in (
        AgentSourceKind.PYTHON_FILE,
        AgentSourceKind.SUBMISSION_FILE,
    ):
        return _load_file_agent(agent_spec)
    raise ValueError(f"unsupported agent source kind: {agent_spec.source_kind.value}")


def _load_modular_agent(agent_spec: AgentSpec) -> KaggleAgent:
    if agent_spec.module_path is None:
        raise ValueError("module_path is required for modular_agent")

    module = importlib.import_module(agent_spec.module_path)
    return _callable_from_module(module, agent_spec.callable_name)


def _load_file_agent(agent_spec: AgentSpec) -> KaggleAgent:
    source_kind = agent_spec.source_kind.value
    if agent_spec.file_path is None:
        raise ValueError(f"file_path is required for {source_kind}")

    path = Path(agent_spec.file_path)
    if not path.is_file():
        raise ValueError(f"{source_kind} file not found: {agent_spec.file_path}")

    module_name = _module_name_for_file(path, source_kind)
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise ValueError(f"could not load {source_kind} file: {agent_spec.file_path}")

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return _callable_from_module(module, agent_spec.callable_name)


def _callable_from_module(module: object, callable_name: str) -> KaggleAgent:
    candidate = getattr(module, callable_name)
    if not callable(candidate):
        raise ValueError(f"{callable_name} is not callable")
    return candidate


def _module_name_for_file(path: Path, source_kind: str) -> str:
    resolved_path = str(path.resolve())
    digest = hashlib.sha256(resolved_path.encode("utf-8")).hexdigest()[:16]
    stem = "".join(
        character if character.isalnum() or character == "_" else "_"
        for character in path.stem
    )
    return f"_ow_eval_{source_kind}_{stem}_{digest}"


__all__ = (
    "KaggleAgent",
    "load_agent_callable",
)
