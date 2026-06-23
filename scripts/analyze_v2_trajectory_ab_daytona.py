#!/usr/bin/env python3
"""Summarize Planner V2 trajectory A/B Daytona shard results."""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from ow_eval.contracts import MatchResult
from ow_eval.shard_persistence import read_evaluation_shard_run_result
from ow_sim.state import GameState


CURVE_TURNS = (0, 10, 20, 30, 40, 60, 80, 120)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Analyze Planner V2 trajectory A/B Daytona results.",
    )
    parser.add_argument(
        "--root",
        required=True,
        help="Root containing *.shard-result.json files.",
    )
    parser.add_argument(
        "--output-json",
        required=True,
        help="Where to write the JSON summary.",
    )
    args = parser.parse_args(argv)

    summary = analyze_v2_trajectory_ab_daytona(Path(args.root))
    output_path = Path(args.output_json)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(summary, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    print(summary["summary_text"])
    print(summary["markdown_table"])
    return 0


def analyze_v2_trajectory_ab_daytona(root: Path) -> dict[str, object]:
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
    markdown = _markdown_table(aggregate)
    return {
        "summary_text": (
            "v2_trajectory_ab_analysis "
            f"matches={len(rows)} cells={len(aggregate)} "
            f"shards={len(shard_paths)}"
        ),
        "root": str(root),
        "shard_result_paths": [str(path) for path in shard_paths],
        "matches": rows,
        "aggregate_by_cell": aggregate,
        "markdown_table": markdown,
        "unavailable_metrics": [
            "selected_v2_family_mix_per_turn",
            "trajectory_objective_mix_per_turn",
        ],
    }


def _match_row(result: MatchResult, shard_path: Path) -> dict[str, object]:
    metadata = dict(result.config.metadata)
    result_metadata = dict(result.metadata)
    replay_metrics = _replay_metrics(result.replay_path, result.config.controlled_seat)
    no_action_reasons = _reason_counts(
        result_metadata.get("runtime_diagnostic_no_action_reasons")
    )
    metrics = result.metrics
    return {
        "artifact_path": result.artifact_path,
        "budget_guard_count": no_action_reasons.get("budget_guarded", 0),
        "cell": metadata.get("trajectory_ab_cell", "unknown"),
        "controlled_seat": result.config.controlled_seat,
        "enemy_target_action_count": metrics.enemy_target_action_count,
        "episode_steps": metadata.get("episode_steps"),
        "final_planets": metrics.final_planets,
        "final_production": metrics.final_production,
        "final_rank": metrics.final_rank,
        "final_score": metrics.final_score,
        "first_zero_owned_turn": replay_metrics["first_zero_owned_turn"],
        "first_zero_production_turn": replay_metrics["first_zero_production_turn"],
        "label": result.config.label,
        "neutral_target_action_count": metrics.neutral_target_action_count,
        "no_action_count": metrics.no_action_count,
        "no_action_reasons": no_action_reasons,
        "no_action_with_owned_production_count": (
            metrics.no_action_with_owned_production_count
        ),
        "original_label": metadata.get("original_label", result.config.label),
        "own_transfer_action_count": metrics.own_transfer_action_count,
        "owned_planet_curve": replay_metrics["owned_planet_curve"],
        "owned_production_curve": replay_metrics["owned_production_curve"],
        "peak_production": replay_metrics["peak_production"],
        "player_count": result.config.player_count.value,
        "replay_path": result.replay_path,
        "runtime_primary_no_action_reason": result_metadata.get(
            "runtime_diagnostic_primary_no_action_reason"
        ),
        "shard_result_path": str(shard_path),
        "status": result.status.value,
        "strategy_selection_no_action_count": no_action_reasons.get(
            "strategy_selection_no_action",
            0,
        ),
        "survived_turns": metrics.turns_survived,
        "trajectory_second_source": metadata.get("trajectory_second_source"),
    }


def _replay_metrics(
    replay_path_text: str | None,
    controlled_seat: int,
) -> dict[str, object]:
    if replay_path_text is None:
        return _empty_replay_metrics()
    replay_path = Path(replay_path_text)
    if not replay_path.is_file():
        return _empty_replay_metrics()
    payload = json.loads(replay_path.read_text(encoding="utf-8"))
    if not isinstance(payload, Mapping):
        return _empty_replay_metrics()
    records = _controlled_records(payload, controlled_seat)
    owned_counts = []
    production_counts = []
    for record in records:
        observation = record.get("observation")
        if not isinstance(observation, Mapping):
            owned_counts.append(0)
            production_counts.append(0)
            continue
        state = GameState.from_obs(observation)
        owned = tuple(
            planet for planet in state.planets if planet.owner == controlled_seat
        )
        owned_counts.append(len(owned))
        production_counts.append(sum(planet.production for planet in owned))
    return {
        "first_zero_owned_turn": _first_index(owned_counts, 0),
        "first_zero_production_turn": _first_index(production_counts, 0),
        "owned_planet_curve": _curve(owned_counts),
        "owned_production_curve": _curve(production_counts),
        "peak_production": max(production_counts, default=None),
    }


def _empty_replay_metrics() -> dict[str, object]:
    return {
        "first_zero_owned_turn": None,
        "first_zero_production_turn": None,
        "owned_planet_curve": {},
        "owned_production_curve": {},
        "peak_production": None,
    }


def _controlled_records(
    replay_payload: Mapping[str, object],
    controlled_seat: int,
) -> tuple[Mapping[str, object], ...]:
    steps = replay_payload.get("steps")
    if not isinstance(steps, Sequence) or isinstance(steps, (str, bytes)):
        return ()
    records = []
    for step in steps:
        if not isinstance(step, Sequence) or isinstance(step, (str, bytes)):
            continue
        if controlled_seat >= len(step):
            continue
        record = step[controlled_seat]
        if isinstance(record, Mapping):
            records.append(record)
    return tuple(records)


def _first_index(values: list[int], target: int) -> int | None:
    for index, value in enumerate(values):
        if value == target:
            return index
    return None


def _curve(values: list[int]) -> dict[str, int | None]:
    return {
        str(turn): values[turn] if turn < len(values) else None
        for turn in CURVE_TURNS
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
        aggregate[cell] = {
            "match_count": len(items),
            "completed_count": sum(1 for item in items if item["status"] == "completed"),
            "mean_final_rank": _mean(ranks),
            "mean_survived_turns": _mean(survivals),
            "total_no_action_count": sum(int(item["no_action_count"] or 0) for item in items),
            "total_no_action_with_owned_production_count": sum(
                int(item["no_action_with_owned_production_count"] or 0)
                for item in items
            ),
            "total_strategy_selection_no_action_count": sum(
                int(item["strategy_selection_no_action_count"] or 0)
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
        "| Cell | Matches | Complete | Mean rank | Mean survived | No-actions | No-action owned prod | Strategy no-action | Enemy | Neutral | Own transfer |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for cell, item in aggregate.items():
        lines.append(
            "| {cell} | {matches} | {complete} | {rank} | {survived} | {no_action} | {owned_no_action} | {selection_no_action} | {enemy} | {neutral} | {own} |".format(
                cell=cell,
                matches=item["match_count"],
                complete=item["completed_count"],
                rank=_fmt(item["mean_final_rank"]),
                survived=_fmt(item["mean_survived_turns"]),
                no_action=item["total_no_action_count"],
                owned_no_action=item[
                    "total_no_action_with_owned_production_count"
                ],
                selection_no_action=item[
                    "total_strategy_selection_no_action_count"
                ],
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
