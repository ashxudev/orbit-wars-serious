"""Materialize planned evaluation shards as experiment manifest JSON files.

Distributed Evaluation Cycle 5 makes planned shard command inputs concrete by
writing one shard-local ``ExperimentManifest`` at each shard's
``planned_manifest_path``. It does not run matches, spawn subprocesses, call
Daytona, or add parallel orchestration.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from .contracts import AgentSpec
from .experiment_manifest import ExperimentManifest, ExperimentScenario
from .sharding import EvaluationShard, EvaluationShardPlan


@dataclass(frozen=True, slots=True)
class EvaluationShardManifestWriteResult:
    """Result from materializing every shard manifest in a shard plan."""

    shard_plan: EvaluationShardPlan
    manifest_paths: tuple[str, ...]
    commands: tuple[str, ...]
    summary_text: str

    def __post_init__(self) -> None:
        if not isinstance(self.shard_plan, EvaluationShardPlan):
            raise ValueError("shard_plan must be an EvaluationShardPlan")
        if not isinstance(self.manifest_paths, tuple):
            raise ValueError("manifest_paths must be a tuple")
        for path in self.manifest_paths:
            _validate_nonempty_string(path, "manifest path")
        if not isinstance(self.commands, tuple):
            raise ValueError("commands must be a tuple")
        for command in self.commands:
            _validate_nonempty_string(command, "command")
        _validate_nonempty_string(self.summary_text, "summary_text")

    def to_dict(self) -> dict[str, object]:
        """Return a deterministic JSON-safe dictionary."""

        return {
            "shard_plan": self.shard_plan.to_dict(),
            "manifest_paths": list(self.manifest_paths),
            "commands": list(self.commands),
            "summary_text": self.summary_text,
        }


def shard_to_experiment_manifest(shard: EvaluationShard) -> ExperimentManifest:
    """Convert one planned shard into a shard-local experiment manifest."""

    if not isinstance(shard, EvaluationShard):
        raise ValueError("shard must be an EvaluationShard")
    if not shard.matches:
        raise ValueError("shard must contain at least one match")

    candidate_agent = _candidate_agent_for_shard(shard)
    return ExperimentManifest(
        name=shard.label,
        candidate_agent=candidate_agent,
        scenarios=tuple(
            ExperimentScenario(
                seed=match.seed,
                player_count=match.player_count,
                controlled_seat=match.controlled_seat,
                opponent_agents=match.opponent_agents,
                label=match.label,
                metadata=match.metadata,
            )
            for match in shard.matches
        ),
        description=f"Materialized evaluation shard {shard.shard_id}",
        metadata=(
            ("shard_id", shard.shard_id),
            ("shard_label", shard.label),
            ("source_manifest_refs", ",".join(shard.source_manifest_refs)),
            ("match_labels", ",".join(shard.match_labels)),
        ),
    )


def write_evaluation_shard_manifest(shard: EvaluationShard) -> Path:
    """Write one shard-local experiment manifest to its planned path."""

    if not isinstance(shard, EvaluationShard):
        raise ValueError("shard must be an EvaluationShard")
    manifest = shard_to_experiment_manifest(shard)
    output_path = Path(shard.planned_manifest_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(manifest.to_dict(), sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    return output_path


def write_evaluation_shard_manifests(
    plan: EvaluationShardPlan,
) -> EvaluationShardManifestWriteResult:
    """Write every planned shard manifest and return deterministic metadata."""

    if not isinstance(plan, EvaluationShardPlan):
        raise ValueError("plan must be an EvaluationShardPlan")
    manifest_paths = tuple(
        str(write_evaluation_shard_manifest(shard))
        for shard in plan.shards
    )
    commands = tuple(shard.command for shard in plan.shards)
    return EvaluationShardManifestWriteResult(
        shard_plan=plan,
        manifest_paths=manifest_paths,
        commands=commands,
        summary_text=(
            f"shard_manifests=WRITTEN shards={len(plan.shards)} "
            f"manifests={len(manifest_paths)}"
        ),
    )


def _candidate_agent_for_shard(shard: EvaluationShard) -> AgentSpec:
    candidate_agent = shard.matches[0].candidate_agent
    for index, match in enumerate(shard.matches[1:], start=1):
        if match.candidate_agent != candidate_agent:
            raise ValueError(
                f"shard matches must use the same candidate_agent; "
                f"match {index} differs"
            )
    return candidate_agent


def _validate_nonempty_string(value: object, name: str) -> None:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{name} must be a non-empty string")


__all__ = (
    "EvaluationShardManifestWriteResult",
    "shard_to_experiment_manifest",
    "write_evaluation_shard_manifest",
    "write_evaluation_shard_manifests",
)
