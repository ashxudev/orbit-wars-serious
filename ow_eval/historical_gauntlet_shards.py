"""Deterministic shard planning for historical champion gauntlet manifests.

This module is plan-only. It reads committed experiment manifests and produces
JSON-safe shard metadata for later local/Daytona packaging cycles. It does not
run matches, create Daytona jobs, write reports, or touch Kaggle.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

from .experiment_manifest import ExperimentManifest


DEFAULT_SHARD_COUNT = 6
DEFAULT_RESULT_ROOT = "generated_results/historical_champion_gauntlet"


@dataclass(frozen=True, slots=True)
class HistoricalChampionShardScenario:
    """One committed gauntlet scenario assigned to one shard."""

    global_index: int
    manifest_name: str
    source_manifest_path: str
    scenario_label: str
    seed: int
    controlled_seat: int
    player_count: int
    opponent_names: tuple[str, ...]
    episode_steps: str

    def to_dict(self) -> dict[str, object]:
        return {
            "controlled_seat": self.controlled_seat,
            "episode_steps": self.episode_steps,
            "global_index": self.global_index,
            "manifest_name": self.manifest_name,
            "opponent_names": list(self.opponent_names),
            "player_count": self.player_count,
            "scenario_label": self.scenario_label,
            "seed": self.seed,
            "source_manifest_path": self.source_manifest_path,
        }


@dataclass(frozen=True, slots=True)
class HistoricalChampionShard:
    """One deterministic shard of historical champion gauntlet scenarios."""

    shard_id: str
    shard_index: int
    scenario_count: int
    scenarios: tuple[HistoricalChampionShardScenario, ...]
    intended_manifest_path: str
    intended_result_path: str
    intended_report_path: str
    recommended_for_probe: bool = False

    def to_dict(self) -> dict[str, object]:
        return {
            "intended_manifest_path": self.intended_manifest_path,
            "intended_report_path": self.intended_report_path,
            "intended_result_path": self.intended_result_path,
            "recommended_for_probe": self.recommended_for_probe,
            "scenario_count": self.scenario_count,
            "scenarios": [scenario.to_dict() for scenario in self.scenarios],
            "shard_id": self.shard_id,
            "shard_index": self.shard_index,
        }


@dataclass(frozen=True, slots=True)
class HistoricalChampionShardPlan:
    """Deterministic shard plan for committed historical champion manifests."""

    source_manifest_paths: tuple[str, ...]
    shard_count: int
    total_scenarios: int
    shards: tuple[HistoricalChampionShard, ...]
    recommended_probe_shard_id: str
    result_root: str
    summary_text: str

    def to_dict(self) -> dict[str, object]:
        return {
            "recommended_probe_shard_id": self.recommended_probe_shard_id,
            "result_root": self.result_root,
            "shard_count": self.shard_count,
            "shards": [shard.to_dict() for shard in self.shards],
            "source_manifest_paths": list(self.source_manifest_paths),
            "summary_text": self.summary_text,
            "total_scenarios": self.total_scenarios,
        }


def default_historical_champion_manifest_paths() -> tuple[Path, Path]:
    """Return the committed full-horizon historical champion manifest paths."""

    root = Path(__file__).resolve().parents[1]
    return (
        root / "experiments" / "manifests" / "historical-champion-gauntlet-2p-500.json",
        root / "experiments" / "manifests" / "historical-champion-gauntlet-4p-500.json",
    )


def build_historical_champion_shard_plan(
    manifest_paths: Sequence[str | Path] | None = None,
    *,
    shard_count: int = DEFAULT_SHARD_COUNT,
    result_root: str = DEFAULT_RESULT_ROOT,
) -> HistoricalChampionShardPlan:
    """Build a deterministic shard plan from committed gauntlet manifests."""

    if shard_count <= 0:
        raise ValueError("shard_count must be positive")
    paths = tuple(
        default_historical_champion_manifest_paths()
        if manifest_paths is None
        else tuple(Path(path) for path in manifest_paths)
    )
    if not paths:
        raise ValueError("at least one manifest path is required")

    scenarios = _read_manifest_scenarios(paths)
    if not scenarios:
        raise ValueError("at least one scenario is required")
    _validate_scenario_labels_are_unique(scenarios)

    shard_buckets: list[list[HistoricalChampionShardScenario]] = [
        [] for _ in range(shard_count)
    ]
    for scenario in scenarios:
        shard_buckets[scenario.global_index % shard_count].append(scenario)

    shards = tuple(
        _build_shard(
            shard_index=index,
            scenarios=tuple(bucket),
            result_root=result_root,
            recommended_for_probe=index == 0,
        )
        for index, bucket in enumerate(shard_buckets)
    )
    recommended_probe_shard_id = shards[0].shard_id
    summary_text = _summary_text(shards, len(scenarios), recommended_probe_shard_id)
    return HistoricalChampionShardPlan(
        source_manifest_paths=tuple(str(path) for path in paths),
        shard_count=shard_count,
        total_scenarios=len(scenarios),
        shards=shards,
        recommended_probe_shard_id=recommended_probe_shard_id,
        result_root=result_root,
        summary_text=summary_text,
    )


def _read_manifest_scenarios(
    paths: tuple[Path, ...],
) -> tuple[HistoricalChampionShardScenario, ...]:
    planned: list[HistoricalChampionShardScenario] = []
    for path in paths:
        manifest = _read_manifest(path)
        for scenario in manifest.scenarios:
            metadata = dict(scenario.metadata)
            episode_steps = metadata.get("episode_steps")
            if episode_steps != "500":
                raise ValueError(
                    f"{path} scenario {scenario.label!r} must have episode_steps=500"
                )
            if scenario.label is None:
                raise ValueError(f"{path} scenario label is required")
            opponent_names = tuple(
                opponent.agent.name for opponent in scenario.opponent_agents
            )
            planned.append(
                HistoricalChampionShardScenario(
                    global_index=len(planned),
                    manifest_name=manifest.name,
                    source_manifest_path=str(path),
                    scenario_label=scenario.label,
                    seed=scenario.seed,
                    controlled_seat=scenario.controlled_seat,
                    player_count=scenario.player_count.value,
                    opponent_names=opponent_names,
                    episode_steps=episode_steps,
                )
            )
    return tuple(planned)


def _read_manifest(path: Path) -> ExperimentManifest:
    if not path.is_file():
        raise ValueError(f"manifest not found: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    return ExperimentManifest.from_dict(payload)


def _validate_scenario_labels_are_unique(
    scenarios: tuple[HistoricalChampionShardScenario, ...],
) -> None:
    seen: set[str] = set()
    for scenario in scenarios:
        if scenario.scenario_label in seen:
            raise ValueError(f"duplicate scenario label: {scenario.scenario_label}")
        seen.add(scenario.scenario_label)


def _build_shard(
    *,
    shard_index: int,
    scenarios: tuple[HistoricalChampionShardScenario, ...],
    result_root: str,
    recommended_for_probe: bool,
) -> HistoricalChampionShard:
    shard_id = f"historical-gauntlet-shard-{shard_index:03d}"
    shard_path = f"{result_root}/shards/{shard_id}"
    return HistoricalChampionShard(
        shard_id=shard_id,
        shard_index=shard_index,
        scenario_count=len(scenarios),
        scenarios=scenarios,
        intended_manifest_path=f"{shard_path}/manifest.json",
        intended_result_path=f"{shard_path}/shard-result.json",
        intended_report_path=f"{shard_path}/report.json",
        recommended_for_probe=recommended_for_probe,
    )


def _summary_text(
    shards: tuple[HistoricalChampionShard, ...],
    total_scenarios: int,
    recommended_probe_shard_id: str,
) -> str:
    counts = ",".join(str(shard.scenario_count) for shard in shards)
    return (
        "historical_champion_shard_plan "
        f"shards={len(shards)} total_scenarios={total_scenarios} "
        f"scenarios_per_shard={counts} "
        f"recommended_probe_shard={recommended_probe_shard_id}"
    )


__all__ = (
    "HistoricalChampionShard",
    "HistoricalChampionShardPlan",
    "HistoricalChampionShardScenario",
    "build_historical_champion_shard_plan",
    "default_historical_champion_manifest_paths",
)
