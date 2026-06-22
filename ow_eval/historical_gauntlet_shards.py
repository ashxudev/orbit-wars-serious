"""Deterministic shard planning for historical champion gauntlet manifests.

This module is plan-only. It reads committed experiment manifests and produces
JSON-safe shard metadata for later local/Daytona packaging cycles. It does not
run matches, create Daytona jobs, write reports, or touch Kaggle.
"""

from __future__ import annotations

import json
import shutil
import shlex
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Sequence

from .contracts import MatchConfig
from .contracts import AgentSourceKind
from .experiment_manifest import ExperimentManifest
from .experiment_manifest import manifest_to_match_configs
from .shard_jobs import EvaluationShardJob
from .shard_jobs import EvaluationShardJobPackageResult
from .shard_jobs import write_evaluation_shard_job_package
from .sharding import EvaluationShard
from .sharding import EvaluationShardPlan
from .sharding import ShardPlanConfig


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


def select_historical_champion_shard(
    plan: HistoricalChampionShardPlan,
    shard_id: str | None = None,
) -> HistoricalChampionShard:
    """Select a deterministic shard from a historical champion shard plan."""

    if not isinstance(plan, HistoricalChampionShardPlan):
        raise ValueError("plan must be a HistoricalChampionShardPlan")
    selected_shard_id = shard_id or plan.recommended_probe_shard_id
    for shard in plan.shards:
        if shard.shard_id == selected_shard_id:
            return shard
    raise ValueError(f"unknown historical champion shard id: {selected_shard_id}")


def build_historical_champion_evaluation_shard_plan(
    plan: HistoricalChampionShardPlan | None = None,
    *,
    shard_id: str | None = None,
    output_root: str | Path = DEFAULT_RESULT_ROOT,
    command_python: str = ".venv/bin/python",
) -> EvaluationShardPlan:
    """Convert one historical champion shard into existing shard contracts."""

    historical_plan = plan if plan is not None else build_historical_champion_shard_plan()
    historical_shard = select_historical_champion_shard(historical_plan, shard_id)
    matches_by_label = _match_configs_by_label(historical_plan.source_manifest_paths)
    matches = tuple(
        _match_for_scenario(matches_by_label, scenario)
        for scenario in historical_shard.scenarios
    )
    output_dir = Path(output_root) / historical_shard.shard_id
    planned_manifest_path = str(output_dir / "manifest.json")
    planned_report_path = str(output_dir / "report.json")
    evaluation_shard = EvaluationShard(
        shard_id=historical_shard.shard_id,
        label=historical_shard.shard_id,
        source_manifest_refs=tuple(
            dict.fromkeys(
                scenario.source_manifest_path
                for scenario in historical_shard.scenarios
            )
        ),
        match_labels=tuple(scenario.scenario_label for scenario in historical_shard.scenarios),
        seeds=tuple(scenario.seed for scenario in historical_shard.scenarios),
        matches=matches,
        planned_manifest_path=planned_manifest_path,
        planned_report_path=planned_report_path,
        command=_shard_command(command_python, planned_manifest_path, planned_report_path),
    )
    config = ShardPlanConfig(
        shard_count=1,
        output_root=str(output_root),
        command_python=command_python,
        label_prefix="historical-gauntlet",
    )
    return EvaluationShardPlan(
        config=config,
        shards=(evaluation_shard,),
        total_matches=len(matches),
        summary_text=(
            "historical_champion_package_plan "
            f"shard_id={historical_shard.shard_id} matches={len(matches)} "
            f"output_root={output_root}"
        ),
    )


def write_historical_champion_probe_shard_package(
    output_root: str | Path,
    *,
    plan: HistoricalChampionShardPlan | None = None,
    shard_id: str | None = None,
    command_python: str = ".venv/bin/python",
    materialize_manifests: bool = True,
) -> EvaluationShardJobPackageResult:
    """Materialize the recommended probe shard as a standard shard job package."""

    evaluation_plan = build_historical_champion_evaluation_shard_plan(
        plan,
        shard_id=shard_id,
        output_root=output_root,
        command_python=command_python,
    )
    package = write_evaluation_shard_job_package(
        evaluation_plan,
        materialize_manifests=materialize_manifests,
    )
    return _materialize_historical_python_files(package)


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


def _match_configs_by_label(
    source_manifest_paths: tuple[str, ...],
) -> dict[str, MatchConfig]:
    matches: dict[str, MatchConfig] = {}
    for path in source_manifest_paths:
        manifest = _read_manifest(Path(path))
        for match in manifest_to_match_configs(manifest):
            if match.label is None:
                raise ValueError(f"{path} match label is required")
            if match.label in matches:
                raise ValueError(f"duplicate match label: {match.label}")
            matches[match.label] = match
    return matches


def _match_for_scenario(
    matches_by_label: dict[str, MatchConfig],
    scenario: HistoricalChampionShardScenario,
) -> MatchConfig:
    try:
        match = matches_by_label[scenario.scenario_label]
    except KeyError as exc:
        raise ValueError(f"missing match config for {scenario.scenario_label}") from exc
    metadata = dict(match.metadata)
    if metadata.get("episode_steps") != "500":
        raise ValueError(f"{scenario.scenario_label} must have episode_steps=500")
    return match


def _shard_command(
    command_python: str,
    planned_manifest_path: str,
    planned_report_path: str,
) -> str:
    return " ".join(
        shlex.quote(part)
        for part in (
            command_python,
            "scripts/run_evaluation_experiment.py",
            planned_manifest_path,
            "--report-output",
            planned_report_path,
        )
    )


def _read_manifest(path: Path) -> ExperimentManifest:
    if not path.is_file():
        raise ValueError(f"manifest not found: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    return ExperimentManifest.from_dict(payload)


def _materialize_historical_python_files(
    package: EvaluationShardJobPackageResult,
) -> EvaluationShardJobPackageResult:
    rewritten_jobs = []
    for job in package.jobs:
        extra_upload_paths = _rewrite_job_manifest_python_files(job)
        rewritten_job = replace(
            job,
            extra_upload_paths=tuple(
                dict.fromkeys((*job.extra_upload_paths, *extra_upload_paths))
            ),
        )
        _write_json(rewritten_job.to_dict(), rewritten_job.job_path)
        rewritten_jobs.append(rewritten_job)
    rewritten_package = replace(package, jobs=tuple(rewritten_jobs))
    _write_json(rewritten_package.to_dict(), rewritten_package.index_path)
    return rewritten_package


def _rewrite_job_manifest_python_files(job: EvaluationShardJob) -> tuple[str, ...]:
    manifest_path = Path(job.manifest_path)
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    agent_dir = manifest_path.parent / "agent_files"
    source_to_dest: dict[str, str] = {}
    for agent in _iter_manifest_agent_payloads(payload):
        if agent.get("source_kind") != AgentSourceKind.PYTHON_FILE.value:
            continue
        source_path = _python_file_path(agent, job.label)
        dest_path = source_to_dest.get(str(source_path))
        if dest_path is None:
            dest_path = str(_copy_historical_agent_file(source_path, agent, agent_dir))
            source_to_dest[str(source_path)] = dest_path
        agent["file_path"] = dest_path
    if source_to_dest:
        _write_json(payload, manifest_path)
    return tuple(source_to_dest.values())


def _iter_manifest_agent_payloads(payload: object):
    if not isinstance(payload, dict):
        raise ValueError("manifest payload must be an object")
    candidate = payload.get("candidate_agent")
    if isinstance(candidate, dict):
        yield candidate
    scenarios = payload.get("scenarios")
    if not isinstance(scenarios, list):
        raise ValueError("manifest scenarios must be a list")
    for scenario_index, scenario in enumerate(scenarios):
        if not isinstance(scenario, dict):
            raise ValueError(f"scenario[{scenario_index}] must be an object")
        opponents = scenario.get("opponent_agents")
        if not isinstance(opponents, list):
            raise ValueError(f"scenario[{scenario_index}].opponent_agents must be a list")
        for opponent_index, opponent in enumerate(opponents):
            if not isinstance(opponent, dict):
                raise ValueError(
                    f"scenario[{scenario_index}].opponent_agents[{opponent_index}] "
                    "must be an object"
                )
            agent = opponent.get("agent")
            if not isinstance(agent, dict):
                raise ValueError(
                    f"scenario[{scenario_index}].opponent_agents[{opponent_index}].agent "
                    "must be an object"
                )
            yield agent


def _python_file_path(agent: dict[str, object], label: str) -> Path:
    value = agent.get("file_path")
    if not isinstance(value, str) or not value:
        name = agent.get("name")
        raise ValueError(f"python_file agent {name!r} in {label} requires file_path")
    path = Path(value)
    if not path.is_file():
        raise ValueError(f"python_file agent path not found for {label}: {path}")
    return path


def _copy_historical_agent_file(
    source_path: Path,
    agent: dict[str, object],
    agent_dir: Path,
) -> Path:
    agent_name = agent.get("name")
    safe_name = _safe_filename(agent_name if isinstance(agent_name, str) else "agent")
    dest_path = agent_dir / f"{safe_name}__{source_path.name}"
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    if not dest_path.exists():
        shutil.copy2(source_path, dest_path)
    return dest_path


def _safe_filename(value: str) -> str:
    cleaned = "".join(
        char if char.isalnum() or char in {"-", "_", "."} else "_"
        for char in value
    ).strip("._")
    return cleaned or "agent"


def _write_json(payload: object, path: str | Path) -> Path:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(payload, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    return output_path


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
    "build_historical_champion_evaluation_shard_plan",
    "build_historical_champion_shard_plan",
    "default_historical_champion_manifest_paths",
    "select_historical_champion_shard",
    "write_historical_champion_probe_shard_package",
)
