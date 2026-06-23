#!/usr/bin/env python3
"""Prepare a matched fallback source-guard A/B Daytona package."""

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


DEFAULT_OUTPUT_ROOT = Path("/tmp/ow-fallback-source-guard-ab-daytona")
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
    (
        "fallback-source-guard-ab-base",
        "base",
        AgentSpec(
            name="claude-v3-wide-search-forecast",
            source_kind=AgentSourceKind.PYTHON_FILE,
            file_path="historical_opponents/agents/claude_v3_wide_search_forecast.py",
            callable_name="agent",
            metadata=(("variant", "base"),),
        ),
    ),
    (
        "fallback-source-guard-ab-source-guard",
        "source-guard",
        AgentSpec(
            name="fallback-source-guard",
            source_kind=AgentSourceKind.MODULAR_AGENT,
            module_path="agents.fallback_source_guard",
            callable_name="agent",
            metadata=(("variant", "source_guard"),),
        ),
    ),
)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Prepare fallback source-guard A/B Daytona package.",
    )
    parser.add_argument(
        "--output-root",
        default=str(DEFAULT_OUTPUT_ROOT),
        help="Directory where package files are written.",
    )
    args = parser.parse_args(argv)

    result = prepare_fallback_source_guard_ab_package(Path(args.output_root))
    print(result["summary_text"])
    print(f"index_path={result['index_path']}")
    return 0


def prepare_fallback_source_guard_ab_package(output_root: Path) -> dict[str, object]:
    """Write the two-cell A/B package and return a JSON-safe summary."""

    output_root.mkdir(parents=True, exist_ok=True)
    selected = _selected_scenarios()
    manifest_paths = []
    cell_summaries = []
    for name, cell, candidate_agent in CELL_SPECS:
        manifest = _cell_manifest(name, cell, candidate_agent, selected)
        path = output_root / cell / f"{name}.manifest.json"
        _write_json(manifest.to_dict(), path)
        manifest_paths.append(path)
        cell_summaries.append(
            {
                "cell": cell,
                "manifest_path": str(path),
                "scenario_count": len(manifest.scenarios),
                "scenario_labels": [scenario.label for scenario in manifest.scenarios],
            }
        )

    plan = build_evaluation_shard_plan(
        tuple(manifest_paths),
        ShardPlanConfig(
            matches_per_shard=3,
            output_root=output_root / "package",
            label_prefix="fallback-source-guard-ab",
        ),
    )
    package = write_evaluation_shard_job_package(plan)
    summary = {
        "summary_text": (
            "fallback_source_guard_ab_package=READY "
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
    _write_json(summary, output_root / "fallback-source-guard-ab-package-summary.json")
    return summary


def _selected_scenarios() -> tuple[ExperimentScenario, ...]:
    scenarios_by_label: dict[str, ExperimentScenario] = {}
    for path in (TWO_PLAYER_MANIFEST, FOUR_PLAYER_MANIFEST):
        manifest = _load_manifest(path)
        scenarios_by_label.update(
            {scenario.label or "": scenario for scenario in manifest.scenarios}
        )
    labels = TWO_PLAYER_LABELS + FOUR_PLAYER_LABELS
    selected = []
    for label in labels:
        scenario = scenarios_by_label.get(label)
        if scenario is None:
            raise ValueError(f"missing historical pressure scenario {label}")
        selected.append(scenario)
    return tuple(selected)


def _cell_manifest(
    name: str,
    cell: str,
    candidate_agent: AgentSpec,
    source_scenarios: tuple[ExperimentScenario, ...],
) -> ExperimentManifest:
    return ExperimentManifest(
        name=name,
        candidate_agent=candidate_agent,
        scenarios=tuple(_ab_scenario(scenario, cell) for scenario in source_scenarios),
        description=(
            "Matched fallback baseline versus source-guard reserve candidate "
            "historical pressure scenarios."
        ),
        version="1",
        metadata=(
            ("episode_steps", "500"),
            ("fallback_source_guard_ab_cell", cell),
        ),
    )


def _ab_scenario(scenario: ExperimentScenario, cell: str) -> ExperimentScenario:
    if scenario.label is None:
        raise ValueError("source scenarios must have labels")
    metadata = dict(scenario.metadata)
    metadata.update(
        {
            "episode_steps": "500",
            "fallback_source_guard_ab_cell": cell,
            "original_label": scenario.label,
        }
    )
    return replace(
        scenario,
        label=f"{cell}-{scenario.label}",
        metadata=tuple(sorted(metadata.items())),
    )


def _load_manifest(path: Path) -> ExperimentManifest:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain an object")
    return ExperimentManifest.from_dict(payload)


def _write_json(payload: object, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    raise SystemExit(main())
