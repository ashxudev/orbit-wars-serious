#!/usr/bin/env python3
"""Summarize fallback source-guard A/B Daytona shard results."""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from collections.abc import Sequence
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from ow_eval.contracts import MatchResult
from ow_eval.shard_persistence import read_evaluation_shard_run_result


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Analyze fallback source-guard A/B Daytona results.",
    )
    parser.add_argument("--root", required=True, help="Root containing shard results.")
    parser.add_argument("--output-json", required=True, help="Summary JSON path.")
    args = parser.parse_args(argv)

    summary = analyze_fallback_source_guard_ab_daytona(Path(args.root))
    output_path = Path(args.output_json)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(summary, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    print(summary["summary_text"])
    print(summary["markdown_table"])
    return 0


def analyze_fallback_source_guard_ab_daytona(root: Path) -> dict[str, object]:
    """Return a JSON-safe summary for all shard results under ``root``."""

    shard_paths = tuple(sorted(root.glob("**/*.shard-result.json")))
    if not shard_paths:
        raise ValueError(f"no shard-result files under {root}")

    rows = []
    for shard_path in shard_paths:
        shard_result = read_evaluation_shard_run_result(shard_path)
        for result in shard_result.batch_result.results:
            rows.append(_match_row(result, shard_path))

    rows = sorted(rows, key=lambda row: (row["cell"], row["original_label"]))
    aggregate = _aggregate(rows)
    return {
        "summary_text": (
            "fallback_source_guard_ab_analysis "
            f"matches={len(rows)} cells={len(aggregate)} shards={len(shard_paths)}"
        ),
        "root": str(root),
        "shard_result_paths": [str(path) for path in shard_paths],
        "matches": rows,
        "aggregate_by_cell": aggregate,
        "markdown_table": _markdown_table(aggregate),
    }


def _match_row(result: MatchResult, shard_path: Path) -> dict[str, object]:
    metadata = dict(result.config.metadata)
    result_metadata = dict(result.metadata)
    reasons = _reason_counts(result_metadata.get("runtime_diagnostic_no_action_reasons"))
    metrics = result.metrics
    return {
        "artifact_path": result.artifact_path,
        "cell": metadata.get("fallback_source_guard_ab_cell", "unknown"),
        "controlled_seat": result.config.controlled_seat,
        "enemy_target_action_count": metrics.enemy_target_action_count,
        "episode_steps": metadata.get("episode_steps"),
        "final_planets": metrics.final_planets,
        "final_production": metrics.final_production,
        "final_rank": metrics.final_rank,
        "final_score": metrics.final_score,
        "label": result.config.label,
        "neutral_target_action_count": metrics.neutral_target_action_count,
        "no_action_count": metrics.no_action_count,
        "no_action_reasons": reasons,
        "no_action_with_owned_production_count": (
            metrics.no_action_with_owned_production_count
        ),
        "original_label": metadata.get("original_label", result.config.label),
        "own_transfer_action_count": metrics.own_transfer_action_count,
        "player_count": result.config.player_count.value,
        "production_collapse": metrics.production_collapse,
        "replay_path": result.replay_path,
        "shard_result_path": str(shard_path),
        "status": result.status.value,
        "survived_turns": metrics.turns_survived,
    }


def _reason_counts(value: str | None) -> dict[str, int]:
    if not value:
        return {}
    counts: dict[str, int] = {}
    for item in value.split(","):
        if ":" not in item:
            continue
        reason, count_text = item.rsplit(":", 1)
        try:
            counts[reason] = int(count_text)
        except ValueError:
            continue
    return counts


def _aggregate(rows: list[dict[str, object]]) -> dict[str, dict[str, object]]:
    grouped: dict[str, list[dict[str, object]]] = defaultdict(list)
    for row in rows:
        grouped[str(row["cell"])].append(row)

    aggregate = {}
    for cell in sorted(grouped):
        items = grouped[cell]
        ranks = [item["final_rank"] for item in items if item["final_rank"] is not None]
        survivals = [
            item["survived_turns"]
            for item in items
            if item["survived_turns"] is not None
        ]
        productions = [
            item["final_production"]
            for item in items
            if item["final_production"] is not None
        ]
        aggregate[cell] = {
            "match_count": len(items),
            "completed_count": sum(1 for item in items if item["status"] == "completed"),
            "win_count": sum(1 for item in items if item["final_rank"] == 1),
            "mean_final_rank": _mean(ranks),
            "mean_survived_turns": _mean(survivals),
            "mean_final_production": _mean(productions),
            "production_collapse_count": sum(
                1 for item in items if item["production_collapse"]
            ),
            "total_no_action_count": sum(int(item["no_action_count"] or 0) for item in items),
            "total_no_action_with_owned_production_count": sum(
                int(item["no_action_with_owned_production_count"] or 0)
                for item in items
            ),
            "total_enemy_target_action_count": sum(
                int(item["enemy_target_action_count"] or 0) for item in items
            ),
            "total_neutral_target_action_count": sum(
                int(item["neutral_target_action_count"] or 0) for item in items
            ),
            "total_own_transfer_action_count": sum(
                int(item["own_transfer_action_count"] or 0) for item in items
            ),
            "rank_distribution": dict(
                sorted(Counter(str(rank) for rank in ranks).items())
            ),
            "scenario_labels": [str(item["original_label"]) for item in items],
        }
    return aggregate


def _mean(values: list[object]) -> float | None:
    numeric = [float(value) for value in values if isinstance(value, (int, float))]
    if not numeric:
        return None
    return round(sum(numeric) / len(numeric), 4)


def _markdown_table(aggregate: dict[str, dict[str, object]]) -> str:
    lines = [
        "| Cell | Matches | Wins | Mean rank | Mean survived | Mean final prod | Collapses | No-actions | No-action owned prod | Enemy | Neutral | Own transfer |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for cell, item in aggregate.items():
        lines.append(
            "| {cell} | {matches} | {wins} | {rank} | {survived} | {production} | {collapses} | {no_action} | {owned_no_action} | {enemy} | {neutral} | {own} |".format(
                cell=cell,
                matches=item["match_count"],
                wins=item["win_count"],
                rank=_fmt(item["mean_final_rank"]),
                survived=_fmt(item["mean_survived_turns"]),
                production=_fmt(item["mean_final_production"]),
                collapses=item["production_collapse_count"],
                no_action=item["total_no_action_count"],
                owned_no_action=item["total_no_action_with_owned_production_count"],
                enemy=item["total_enemy_target_action_count"],
                neutral=item["total_neutral_target_action_count"],
                own=item["total_own_transfer_action_count"],
            )
        )
    return "\n".join(lines)


def _fmt(value: object) -> str:
    return "n/a" if value is None else str(value)


if __name__ == "__main__":
    raise SystemExit(main())
