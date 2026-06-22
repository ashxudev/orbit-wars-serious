"""Deterministic artifact writing for local evaluation matches.

Evaluation Harness Cycle 4 writes optional single-match JSON artifacts only.
It does not run matches, capture batches, build scoreboards, or submit to
Kaggle.
"""

from __future__ import annotations

import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from .contracts import MatchConfig, MatchResult


DEFAULT_EVALUATION_ARTIFACT_DIR = Path("/tmp/ow-eval-artifacts")


@dataclass(frozen=True, slots=True)
class EvaluationArtifactConfig:
    """Config for optional single-match artifact capture."""

    output_dir: str | Path
    write_replay: bool = True
    write_result: bool = True
    prefix: str | None = None

    def __post_init__(self) -> None:
        if isinstance(self.output_dir, str) and not self.output_dir:
            raise ValueError("output_dir must be a non-empty path")
        if not isinstance(self.output_dir, (str, Path)):
            raise ValueError("output_dir must be a path")
        if not isinstance(self.write_replay, bool):
            raise ValueError("write_replay must be a boolean")
        if not isinstance(self.write_result, bool):
            raise ValueError("write_result must be a boolean")
        if self.prefix is not None and not isinstance(self.prefix, str):
            raise ValueError("prefix must be a string")
        if self.prefix == "":
            raise ValueError("prefix must be non-empty when provided")
        object.__setattr__(self, "output_dir", Path(self.output_dir))


def default_evaluation_artifact_config(
    *,
    prefix: str | None = None,
    output_dir: str | Path | None = None,
) -> EvaluationArtifactConfig:
    """Return the default artifact capture config for local match execution."""

    return EvaluationArtifactConfig(
        output_dir=DEFAULT_EVALUATION_ARTIFACT_DIR if output_dir is None else output_dir,
        prefix=prefix,
    )


def write_match_result_artifact(result: MatchResult, path: str | Path) -> Path:
    """Write ``result`` as deterministic JSON and return the written path."""

    return _write_json(result.to_dict(), path)


def write_replay_artifact(
    replay_payload: Mapping[str, object] | Sequence[object],
    path: str | Path,
) -> Path:
    """Write an official replay payload as deterministic JSON."""

    if isinstance(replay_payload, (str, bytes)):
        raise ValueError("replay_payload must be a mapping or sequence")
    if not isinstance(replay_payload, (Mapping, Sequence)):
        raise ValueError("replay_payload must be a mapping or sequence")
    return _write_json(replay_payload, path)


def artifact_paths_for_config(
    config: MatchConfig,
    artifact_config: EvaluationArtifactConfig,
) -> tuple[Path, Path]:
    """Return deterministic replay/result paths under ``output_dir``."""

    base_name = _artifact_base_name(config, artifact_config.prefix)
    output_dir = Path(artifact_config.output_dir)
    return (
        output_dir / f"{base_name}-replay.json",
        output_dir / f"{base_name}-result.json",
    )


def _artifact_base_name(config: MatchConfig, prefix: str | None) -> str:
    if prefix is not None:
        raw_name = prefix
    elif config.label is not None:
        raw_name = config.label
    else:
        raw_name = (
            f"seed-{config.seed}-players-{config.player_count.value}"
            f"-seat-{config.controlled_seat}"
        )

    sanitized = re.sub(r"[^A-Za-z0-9._-]+", "-", raw_name).strip("-._").lower()
    if sanitized:
        return sanitized
    return f"seed-{config.seed}-players-{config.player_count.value}-seat-{config.controlled_seat}"


def _write_json(payload: object, path: str | Path) -> Path:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("w", encoding="utf-8") as fh:
        json.dump(_json_safe_payload(payload), fh, sort_keys=True, indent=2)
        fh.write("\n")
    return destination


def _json_safe_payload(payload: object) -> object:
    if payload is None or isinstance(payload, (bool, int, float, str)):
        return payload
    if isinstance(payload, Mapping):
        return {
            str(key): _json_safe_payload(value)
            for key, value in payload.items()
        }
    if isinstance(payload, Sequence) and not isinstance(payload, (str, bytes)):
        return [
            _json_safe_payload(value)
            for value in payload
        ]
    raise TypeError(f"object of type {type(payload).__name__} is not JSON serializable")


__all__ = (
    "DEFAULT_EVALUATION_ARTIFACT_DIR",
    "EvaluationArtifactConfig",
    "artifact_paths_for_config",
    "default_evaluation_artifact_config",
    "write_match_result_artifact",
    "write_replay_artifact",
)
