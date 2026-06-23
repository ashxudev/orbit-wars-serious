#!/usr/bin/env python3
"""Prepare a matched Planner V2 trajectory A/B Daytona package.

The package contains four jobs:

* 2P trajectory-off, three historical pressure scenarios
* 2P trajectory-on, the same three scenarios
* 4P trajectory-off, three historical pressure scenarios
* 4P trajectory-on, the same three scenarios

It does not run local matches or Daytona jobs.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import replace
from pathlib import Path
from typing import Sequence

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from ow_eval.contracts import AgentSourceKind, AgentSpec
from ow_eval.experiment_manifest import ExperimentManifest, ExperimentScenario
from ow_eval.shard_jobs import write_evaluation_shard_job_package
from ow_eval.sharding import ShardPlanConfig, build_evaluation_shard_plan


DEFAULT_OUTPUT_ROOT = Path("/tmp/ow-v2-trajectory-ab-daytona")
TWO_PLAYER_MANIFEST = (
    REPO_ROOT / "experiments/manifests/historical-champion-gauntlet-2p-500.json"
)
FOUR_PLAYER_MANIFEST = (
    REPO_ROOT / "experiments/manifests/historical-champion-gauntlet-4p-500.json"
)

TWO_PLAYER_LABELS = (
    "historical-gauntlet-2p-500-seat-1-vs-claude-v31-race-awareness",
    "historical-gauntlet-2p-500-seat-1-vs-claude-v9-hold-aware-capture",
    "historical-gauntlet-2p-500-seat-0-vs-ow2-current-main",
)
FOUR_PLAYER_LABELS = (
    "historical-gauntlet-4p-500-top-score-seat-3",
    "historical-gauntlet-4p-500-mixed-style-seat-2",
    "historical-gauntlet-4p-500-ow2-smoke-reference-seat-0",
)

CELL_SPECS = (
    ("v2-trajectory-ab-2p-off", "2p-off", TWO_PLAYER_MANIFEST, TWO_PLAYER_LABELS, False),
    ("v2-trajectory-ab-2p-on", "2p-on", TWO_PLAYER_MANIFEST, TWO_PLAYER_LABELS, True),
    ("v2-trajectory-ab-4p-off", "4p-off", FOUR_PLAYER_MANIFEST, FOUR_PLAYER_LABELS, False),
    ("v2-trajectory-ab-4p-on", "4p-on", FOUR_PLAYER_MANIFEST, FOUR_PLAYER_LABELS, True),
)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Prepare the Planner V2 trajectory A/B Daytona package.",
    )
    parser.add_argument(
        "--output-root",
        default=str(DEFAULT_OUTPUT_ROOT),
        help="Directory where package files are written.",
    )
    args = parser.parse_args(argv)

    result = prepare_v2_trajectory_ab_package(Path(args.output_root))
    print(result["summary_text"])
    print(f"index_path={result['index_path']}")
    return 0


def prepare_v2_trajectory_ab_package(output_root: Path) -> dict[str, object]:
    """Write the four-cell A/B package and return a JSON-safe summary."""

    output_root.mkdir(parents=True, exist_ok=True)
    manifest_paths = []
    cell_summaries = []
    for name, cell, source_path, labels, enabled in CELL_SPECS:
        manifest = _cell_manifest(name, cell, source_path, labels, enabled)
        path = output_root / cell / f"{name}.manifest.json"
        _write_json(manifest.to_dict(), path)
        manifest_paths.append(path)
        cell_summaries.append(
            {
                "cell": cell,
                "manifest_path": str(path),
                "scenario_count": len(manifest.scenarios),
                "trajectory_second_source": "on" if enabled else "off",
                "scenario_labels": [
                    scenario.label for scenario in manifest.scenarios
                ],
            }
        )

    plan = build_evaluation_shard_plan(
        tuple(manifest_paths),
        ShardPlanConfig(
            matches_per_shard=3,
            output_root=output_root / "package",
            label_prefix="v2-trajectory-ab",
        ),
    )
    package = write_evaluation_shard_job_package(plan)
    summary = {
        "summary_text": (
            "v2_trajectory_ab_package=READY "
            f"jobs={len(package.jobs)} matches={plan.total_matches} "
            f"index_path={package.index_path}"
        ),
        "index_path": package.index_path,
        "jobs": len(package.jobs),
        "matches": plan.total_matches,
        "cells": cell_summaries,
        "job_labels": [job.label for job in package.jobs],
        "episode_steps": sorted(
            {
                dict(match.metadata).get("episode_steps", "")
                for shard in plan.shards
                for match in shard.matches
            }
        ),
    }
    _write_json(summary, output_root / "v2-trajectory-ab-package-summary.json")
    return summary


def _cell_manifest(
    name: str,
    cell: str,
    source_path: Path,
    labels: tuple[str, ...],
    trajectory_enabled: bool,
) -> ExperimentManifest:
    source = _load_manifest(source_path)
    scenario_by_label = {
        scenario.label: scenario
        for scenario in source.scenarios
    }
    selected = []
    for label in labels:
        scenario = scenario_by_label.get(label)
        if scenario is None:
            raise ValueError(f"{source_path} missing scenario {label}")
        selected.append(_ab_scenario(scenario, cell, trajectory_enabled))

    return ExperimentManifest(
        name=name,
        candidate_agent=_candidate_agent(trajectory_enabled),
        scenarios=tuple(selected),
        description=(
            "Planner V2 trajectory second-source A/B cell using matched "
            "historical champion pressure scenarios."
        ),
        version="1",
        metadata=(
            ("episode_steps", "500"),
            ("planner_version", "v2"),
            ("trajectory_ab_cell", cell),
            (
                "trajectory_second_source",
                "on" if trajectory_enabled else "off",
            ),
        ),
    )


def _load_manifest(path: Path) -> ExperimentManifest:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain an object")
    return ExperimentManifest.from_dict(payload)


def _candidate_agent(trajectory_enabled: bool) -> AgentSpec:
    return AgentSpec(
        name=(
            "planner-v2-trajectory-on"
            if trajectory_enabled
            else "planner-v2-trajectory-off"
        ),
        source_kind=AgentSourceKind.MODULAR_AGENT,
        module_path=(
            "agents.orbit_wars_agent_v2"
            if trajectory_enabled
            else "agents.orbit_wars_agent_v2_trajectory_off"
        ),
        callable_name="agent",
        metadata=(
            ("planner_version", "v2"),
            (
                "trajectory_second_source",
                "on" if trajectory_enabled else "off",
            ),
        ),
    )


def _ab_scenario(
    scenario: ExperimentScenario,
    cell: str,
    trajectory_enabled: bool,
) -> ExperimentScenario:
    if scenario.label is None:
        raise ValueError("source scenarios must have labels")
    metadata = dict(scenario.metadata)
    metadata.update(
        {
            "episode_steps": "500",
            "original_label": scenario.label,
            "trajectory_ab_cell": cell,
            "trajectory_second_source": "on" if trajectory_enabled else "off",
        }
    )
    return replace(
        scenario,
        label=f"{cell}-{scenario.label}",
        metadata=tuple(sorted(metadata.items())),
    )


def _write_json(payload: object, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    raise SystemExit(main())
