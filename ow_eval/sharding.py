"""Deterministic shard-plan contracts for local evaluation manifests.

Distributed Evaluation Cycle 0 converts local evaluation manifests or already
expanded match configs into pure shard plans. It does not run matches, write
outputs, start subprocesses, or call Daytona.
"""

from __future__ import annotations

import json
import shlex
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from .contracts import MatchConfig
from .experiment_manifest import ExperimentManifest, manifest_to_match_configs


@dataclass(frozen=True, slots=True)
class ShardPlanConfig:
    """Configuration for deterministic shard planning."""

    shard_count: int | None = None
    matches_per_shard: int | None = None
    output_root: str | Path = "evaluation-shards"
    command_python: str = ".venv/bin/python"
    label_prefix: str | None = "eval-shard"

    def __post_init__(self) -> None:
        if (self.shard_count is None) == (self.matches_per_shard is None):
            raise ValueError("set exactly one of shard_count or matches_per_shard")
        if self.shard_count is not None:
            _validate_positive_int(self.shard_count, "shard_count")
        if self.matches_per_shard is not None:
            _validate_positive_int(self.matches_per_shard, "matches_per_shard")
        if not isinstance(self.output_root, (str, Path)):
            raise ValueError("output_root must be a path")
        object.__setattr__(self, "output_root", str(self.output_root))
        _validate_nonempty_string(self.command_python, "command_python")
        if self.label_prefix is not None:
            _validate_nonempty_string(self.label_prefix, "label_prefix")

    def to_dict(self) -> dict[str, object]:
        """Return a deterministic JSON-safe dictionary."""

        return {
            "shard_count": self.shard_count,
            "matches_per_shard": self.matches_per_shard,
            "output_root": self.output_root,
            "command_python": self.command_python,
            "label_prefix": self.label_prefix,
        }


@dataclass(frozen=True, slots=True)
class EvaluationShard:
    """One deterministic evaluation shard specification."""

    shard_id: str
    label: str
    source_manifest_refs: tuple[str, ...]
    match_labels: tuple[str, ...]
    seeds: tuple[int, ...]
    matches: tuple[MatchConfig, ...]
    planned_manifest_path: str
    planned_report_path: str
    command: str

    def __post_init__(self) -> None:
        _validate_nonempty_string(self.shard_id, "shard_id")
        _validate_nonempty_string(self.label, "label")
        _validate_string_tuple(self.source_manifest_refs, "source_manifest_refs")
        _validate_string_tuple(self.match_labels, "match_labels")
        if not isinstance(self.seeds, tuple):
            raise ValueError("seeds must be a tuple")
        for seed in self.seeds:
            if isinstance(seed, bool) or not isinstance(seed, int):
                raise ValueError("seeds entries must be integers")
        if not isinstance(self.matches, tuple):
            raise ValueError("matches must be a tuple")
        for match in self.matches:
            if not isinstance(match, MatchConfig):
                raise ValueError("matches entries must be MatchConfig")
        _validate_nonempty_string(self.planned_manifest_path, "planned_manifest_path")
        _validate_nonempty_string(self.planned_report_path, "planned_report_path")
        _validate_nonempty_string(self.command, "command")

    @property
    def match_count(self) -> int:
        """Return the number of matches in this shard."""

        return len(self.matches)

    def to_dict(self) -> dict[str, object]:
        """Return a deterministic JSON-safe dictionary."""

        return {
            "shard_id": self.shard_id,
            "label": self.label,
            "source_manifest_refs": list(self.source_manifest_refs),
            "match_labels": list(self.match_labels),
            "seeds": list(self.seeds),
            "match_count": self.match_count,
            "matches": [
                match.to_dict()
                for match in self.matches
            ],
            "planned_manifest_path": self.planned_manifest_path,
            "planned_report_path": self.planned_report_path,
            "command": self.command,
        }


@dataclass(frozen=True, slots=True)
class EvaluationShardPlan:
    """A deterministic shard plan for expanded local evaluation matches."""

    config: ShardPlanConfig
    shards: tuple[EvaluationShard, ...]
    total_matches: int
    summary_text: str

    def __post_init__(self) -> None:
        if not isinstance(self.config, ShardPlanConfig):
            raise ValueError("config must be a ShardPlanConfig")
        if not isinstance(self.shards, tuple):
            raise ValueError("shards must be a tuple")
        for shard in self.shards:
            if not isinstance(shard, EvaluationShard):
                raise ValueError("shards entries must be EvaluationShard")
        if isinstance(self.total_matches, bool) or not isinstance(
            self.total_matches,
            int,
        ) or self.total_matches < 0:
            raise ValueError("total_matches must be a non-negative integer")
        _validate_nonempty_string(self.summary_text, "summary_text")

    def to_dict(self) -> dict[str, object]:
        """Return a deterministic JSON-safe dictionary."""

        return {
            "config": self.config.to_dict(),
            "shards": [
                shard.to_dict()
                for shard in self.shards
            ],
            "total_matches": self.total_matches,
            "summary_text": self.summary_text,
        }


@dataclass(frozen=True, slots=True)
class _ExpandedMatch:
    source_manifest_ref: str
    match: MatchConfig
    label: str


def build_evaluation_shard_plan(
    inputs: Sequence[str | Path | ExperimentManifest | MatchConfig],
    config: ShardPlanConfig | None = None,
) -> EvaluationShardPlan:
    """Build a deterministic shard plan from manifests or match configs."""

    effective_config = config if config is not None else ShardPlanConfig(shard_count=1)
    expanded_matches = _expand_inputs(inputs)
    if not expanded_matches:
        raise ValueError("inputs must expand to at least one match")

    partitions = _partition_matches(expanded_matches, effective_config)
    shards = tuple(
        _build_shard(index, partition, effective_config)
        for index, partition in enumerate(partitions)
        if partition
    )
    return EvaluationShardPlan(
        config=effective_config,
        shards=shards,
        total_matches=len(expanded_matches),
        summary_text=_summary_text(effective_config, shards, len(expanded_matches)),
    )


def _expand_inputs(
    inputs: Sequence[str | Path | ExperimentManifest | MatchConfig],
) -> tuple[_ExpandedMatch, ...]:
    if not isinstance(inputs, Sequence) or isinstance(inputs, (str, bytes)):
        raise ValueError("inputs must be a sequence")
    expanded: list[_ExpandedMatch] = []
    for input_index, item in enumerate(inputs):
        if isinstance(item, MatchConfig):
            label = _match_label(item, len(expanded))
            expanded.append(_ExpandedMatch("match-config", item, label))
        elif isinstance(item, ExperimentManifest):
            expanded.extend(_expand_manifest(item, item.name, len(expanded)))
        elif isinstance(item, (str, Path)):
            path = Path(item)
            manifest = _load_manifest(path)
            expanded.extend(_expand_manifest(manifest, str(path), len(expanded)))
        else:
            raise ValueError(f"inputs[{input_index}] has unsupported type")
    return tuple(expanded)


def _load_manifest(path: Path) -> ExperimentManifest:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, Mapping):
        raise ValueError("manifest JSON must be an object")
    return ExperimentManifest.from_dict(payload)


def _expand_manifest(
    manifest: ExperimentManifest,
    source_ref: str,
    start_index: int,
) -> tuple[_ExpandedMatch, ...]:
    matches = manifest_to_match_configs(manifest)
    return tuple(
        _ExpandedMatch(
            source_manifest_ref=source_ref,
            match=match,
            label=_match_label(match, start_index + index),
        )
        for index, match in enumerate(matches)
    )


def _match_label(match: MatchConfig, index: int) -> str:
    if match.label is not None:
        return match.label
    return f"match-{index:04d}"


def _partition_matches(
    matches: tuple[_ExpandedMatch, ...],
    config: ShardPlanConfig,
) -> tuple[tuple[_ExpandedMatch, ...], ...]:
    if config.shard_count is not None:
        return _partition_by_shard_count(matches, config.shard_count)
    assert config.matches_per_shard is not None
    return tuple(
        matches[index : index + config.matches_per_shard]
        for index in range(0, len(matches), config.matches_per_shard)
    )


def _partition_by_shard_count(
    matches: tuple[_ExpandedMatch, ...],
    shard_count: int,
) -> tuple[tuple[_ExpandedMatch, ...], ...]:
    base_size, remainder = divmod(len(matches), shard_count)
    partitions = []
    cursor = 0
    for shard_index in range(shard_count):
        size = base_size + (1 if shard_index < remainder else 0)
        partitions.append(matches[cursor : cursor + size])
        cursor += size
    return tuple(partitions)


def _build_shard(
    index: int,
    partition: tuple[_ExpandedMatch, ...],
    config: ShardPlanConfig,
) -> EvaluationShard:
    shard_id = f"shard-{index:04d}"
    label_prefix = config.label_prefix if config.label_prefix is not None else "shard"
    label = f"{label_prefix}-{index:04d}"
    output_root = Path(config.output_root)
    planned_manifest_path = output_root / f"{label}.manifest.json"
    planned_report_path = output_root / f"{label}.report.json"
    command = shlex.join(
        (
            config.command_python,
            "scripts/run_evaluation_experiment.py",
            str(planned_manifest_path),
            "--report-output",
            str(planned_report_path),
        )
    )
    return EvaluationShard(
        shard_id=shard_id,
        label=label,
        source_manifest_refs=_unique_source_refs(partition),
        match_labels=tuple(item.label for item in partition),
        seeds=tuple(item.match.seed for item in partition),
        matches=tuple(item.match for item in partition),
        planned_manifest_path=str(planned_manifest_path),
        planned_report_path=str(planned_report_path),
        command=command,
    )


def _unique_source_refs(
    partition: tuple[_ExpandedMatch, ...],
) -> tuple[str, ...]:
    seen = set()
    refs = []
    for item in partition:
        if item.source_manifest_ref in seen:
            continue
        seen.add(item.source_manifest_ref)
        refs.append(item.source_manifest_ref)
    return tuple(refs)


def _summary_text(
    config: ShardPlanConfig,
    shards: tuple[EvaluationShard, ...],
    total_matches: int,
) -> str:
    if config.shard_count is not None:
        strategy = f"shard_count={config.shard_count}"
    else:
        strategy = f"matches_per_shard={config.matches_per_shard}"
    return (
        f"shard_plan=READY shards={len(shards)} matches={total_matches} "
        f"strategy={strategy}"
    )


def _validate_positive_int(value: object, name: str) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(f"{name} must be a positive integer")


def _validate_nonempty_string(value: object, name: str) -> None:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{name} must be a non-empty string")


def _validate_string_tuple(value: tuple[str, ...], name: str) -> None:
    if not isinstance(value, tuple):
        raise ValueError(f"{name} must be a tuple")
    for item in value:
        _validate_nonempty_string(item, name)


__all__ = (
    "EvaluationShard",
    "EvaluationShardPlan",
    "ShardPlanConfig",
    "build_evaluation_shard_plan",
)
