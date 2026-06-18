"""Reusable agent loading for local evaluation harness runs.

Evaluation Harness Cycle 2 centralizes loading for all current
``AgentSourceKind`` values without importing ``kaggle_environments``.
"""

from __future__ import annotations

import hashlib
import importlib
import importlib.util
import sys
from collections.abc import Callable
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

from .baselines import load_builtin_baseline
from .contracts import AgentSourceKind, AgentSpec


KaggleAgent = Callable[[Any, Any], list[list[int | float]]]
SUBMISSION_ISOLATED_PACKAGE_PREFIXES = ("agents", "ow_planner", "ow_sim")


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
        isolate_submission = agent_spec.source_kind is AgentSourceKind.SUBMISSION_FILE
        return _load_file_agent(agent_spec, isolate_submission=isolate_submission)
    raise ValueError(f"unsupported agent source kind: {agent_spec.source_kind.value}")


def _load_modular_agent(agent_spec: AgentSpec) -> KaggleAgent:
    if agent_spec.module_path is None:
        raise ValueError("module_path is required for modular_agent")

    module = importlib.import_module(agent_spec.module_path)
    return _callable_from_module(module, agent_spec.callable_name)


def _load_file_agent(
    agent_spec: AgentSpec,
    *,
    isolate_submission: bool,
) -> KaggleAgent:
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
    if isolate_submission:
        with _isolated_submission_modules():
            spec.loader.exec_module(module)
    else:
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


@contextmanager
def _isolated_submission_modules() -> Iterator[None]:
    original_meta_path = tuple(sys.meta_path)
    existing_modules = {
        name: module
        for name, module in tuple(sys.modules.items())
        if _is_isolated_submission_module_name(name)
    }
    try:
        for name in existing_modules:
            sys.modules.pop(name, None)
        yield
    finally:
        for name in tuple(sys.modules):
            if _is_isolated_submission_module_name(name):
                sys.modules.pop(name, None)
        sys.modules.update(existing_modules)
        sys.meta_path[:] = original_meta_path


def _is_isolated_submission_module_name(name: str) -> bool:
    return any(
        name == prefix or name.startswith(f"{prefix}.")
        for prefix in SUBMISSION_ISOLATED_PACKAGE_PREFIXES
    )


__all__ = (
    "KaggleAgent",
    "load_agent_callable",
)
