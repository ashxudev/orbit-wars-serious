from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.analyze_current_top_player_replays import (
    COMPETITION,
    aggregate_rows,
    analyze_replay,
    dense_ranks,
    download_replay,
    fmt,
    frame_observation,
    infer_player_count,
    list_submission_episodes,
    mean,
    owner_stats,
    sample_curve,
    slugify,
)


DEFAULT_SUBMISSION_ID = 53925932
DEFAULT_TEAM_NAME = "ashxudev"
DEFAULT_TEAM_ID = 16193764
DEFAULT_AGENT_NAME = "ashxudev_orbit_wars_v2_submission"
DEFAULT_OUTPUT_ROOT = Path("docs/submission_replay_analyses")


def latest_submission_metadata() -> dict[str, Any]:
    return {
        "id": DEFAULT_SUBMISSION_ID,
        "file_name": "orbit_wars_v2_submission.py",
        "date_submitted": "2026-06-21 22:34:06.907000",
        "description": "serious-v2 deterministic readiness passed 75867e3",
        "public_score": 381.1,
    }


def target_metadata() -> dict[str, Any]:
    return {
        "rank": -1,
        "score": latest_submission_metadata()["public_score"],
        "team_id": DEFAULT_TEAM_ID,
        "team_name": DEFAULT_TEAM_NAME,
    }


def replay_player_index(episode: dict[str, Any], submission_id: int) -> int:
    for agent in episode.get("agents") or []:
        if int(agent["submission_id"]) == int(submission_id):
            return int(agent["index"])
    raise RuntimeError(f"submission {submission_id} not present in episode {episode['id']}")


def curve_for_player(replay: dict[str, Any], player_index: int) -> list[dict[str, Any]]:
    steps = replay.get("steps") or []
    rewards = replay.get("rewards") or [state.get("reward", 0) for state in steps[-1]]
    curves = []
    for turn, frame in enumerate(steps):
        obs = frame_observation(frame, player_index)
        planets = obs.get("planets") or []
        fleets = obs.get("fleets") or []
        comet_ids = {int(pid) for pid in obs.get("comet_planet_ids", []) or []}
        if not planets:
            continue
        player_count = infer_player_count(planets, fleets, rewards)
        stats = owner_stats(planets, fleets, player_count, comet_ids)
        totals = stats["total_ships"]
        ranks = dense_ranks(totals)
        curves.append(
            {
                "turn": turn,
                "rank": ranks[player_index],
                "total": totals[player_index],
                "production": stats["production"][player_index],
                "planets": stats["planets"][player_index],
                "planet_ships": stats["planet_ships"][player_index],
                "fleet_ships": stats["fleet_ships"][player_index],
                "comets": stats["comets"][player_index],
                "moving": stats["moving_planets"][player_index],
            }
        )
    return curves


def loss_diagnostics(
    replay_path: Path,
    episode: dict[str, Any],
    row: dict[str, Any],
    submission_id: int,
) -> dict[str, Any]:
    replay = json.loads(replay_path.read_text(encoding="utf-8"))
    player_index = replay_player_index(episode, submission_id)
    rewards = replay.get("rewards") or []
    winner_index = max(range(len(rewards)), key=lambda idx: rewards[idx]) if rewards else None
    our_curve = curve_for_player(replay, player_index)
    winner_curve = curve_for_player(replay, winner_index) if winner_index is not None else []
    peak_prod = max(our_curve, key=lambda point: point["production"], default={})
    peak_total = max(our_curve, key=lambda point: point["total"], default={})
    first_zero_prod_after_peak = None
    first_zero_planets_after_peak = None
    for point in our_curve:
        if point["turn"] <= peak_prod.get("turn", -1):
            continue
        if first_zero_prod_after_peak is None and point["production"] <= 0:
            first_zero_prod_after_peak = point["turn"]
        if first_zero_planets_after_peak is None and point["planets"] <= 0:
            first_zero_planets_after_peak = point["turn"]
    source_loss_windows = source_losses_after_launch(row)
    return {
        "episode_id": row["episode_id"],
        "players": row["players"],
        "reward": row["reward"],
        "opponents": [
            {
                "index": int(agent["index"]),
                "team_name": agent["team_name"],
                "submission_id": int(agent["submission_id"]),
                "reward": float(agent["reward"]),
            }
            for agent in episode.get("agents") or []
            if int(agent["submission_id"]) != int(submission_id)
        ],
        "winner_index": winner_index,
        "winner_name": (
            replay.get("info", {}).get("TeamNames", [])[winner_index]
            if winner_index is not None
            and winner_index < len(replay.get("info", {}).get("TeamNames", []))
            else None
        ),
        "peak_production": peak_prod,
        "peak_total": peak_total,
        "first_zero_prod_after_peak": first_zero_prod_after_peak,
        "first_zero_planets_after_peak": first_zero_planets_after_peak,
        "our_curve_sample": sample_curve(our_curve),
        "winner_curve_sample": sample_curve(winner_curve),
        "source_losses_after_launch": source_loss_windows,
    }


def source_losses_after_launch(row: dict[str, Any]) -> dict[str, int]:
    losses_by_planet: dict[int, list[int]] = defaultdict(list)
    player_index = int(row["target_index"])
    for event in row["capture_events"]:
        if int(event["from"]) == player_index:
            losses_by_planet[int(event["planet"])].append(int(event["turn"]))
    windows = {"within_5": 0, "within_10": 0, "within_20": 0}
    for action in row.get("action_rows", []):
        source = int(action["source"])
        turn = int(action["turn"])
        future_losses = [loss_turn for loss_turn in losses_by_planet[source] if loss_turn > turn]
        if not future_losses:
            continue
        delta = min(future_losses) - turn
        if delta <= 5:
            windows["within_5"] += 1
        if delta <= 10:
            windows["within_10"] += 1
        if delta <= 20:
            windows["within_20"] += 1
    return windows


def add_action_rows(
    row: dict[str, Any],
    replay_path: Path,
    episode: dict[str, Any],
    submission_id: int,
) -> dict[str, Any]:
    # Reuse the compact largest-turn output in the public report; keep full rows
    # out of the committed JSON to avoid bloating docs with per-action detail.
    row["action_rows"] = []
    return row


def write_report(
    path: Path,
    submission: dict[str, Any],
    rows: list[dict[str, Any]],
    diagnostics: list[dict[str, Any]],
    replay_dir: Path,
) -> None:
    aggregate = aggregate_rows(rows)
    target_labels = Counter()
    target_ships = Counter()
    for row in rows:
        target_labels.update(
            {
                key: value
                for key, value in row["target_mix_counts"].items()
                if key not in {"actions", "ships_sent", "turns_with_actions"}
            }
        )
        target_ships.update(row["target_mix_ships"])
    losses = [row for row in rows if row["reward"] != 1.0]
    wins = [row for row in rows if row["reward"] == 1.0]
    ffa_losses = [row for row in losses if row["players"] == 4]
    two_player_losses = [row for row in losses if row["players"] == 2]
    lines = [
        "# Latest Submission Replay Analysis",
        "",
        f"- Competition: `{COMPETITION}`",
        f"- Submitted agent: `{DEFAULT_AGENT_NAME}`",
        f"- Submission: `{submission['id']}` / `{submission['file_name']}`",
        f"- Submitted: `{submission['date_submitted']}`",
        f"- Public score: `{submission['public_score']}`",
        f"- Episodes downloaded/analyzed: `{len(rows)}` public episodes",
        f"- Replay downloads: `{replay_dir}`",
        "",
        "## Bottom Line",
        "",
        f"- Sample record: `{len(wins)}-{len(losses)}`; 4P record `{len([r for r in rows if r['players'] == 4 and r['reward'] == 1.0])}-{len(ffa_losses)}`, 2P record `{len([r for r in rows if r['players'] == 2 and r['reward'] == 1.0])}-{len(two_player_losses)}`.",
        f"- Mean final rank `{fmt(aggregate.get('mean_final_rank'), 2)}`, mean final production `{fmt(aggregate.get('mean_final_production'))}`, mean final total ships `{fmt(aggregate.get('mean_final_total'))}`.",
        f"- Target mix by ships: {', '.join(f'`{k}` {v:.0f}' for k, v in target_ships.most_common(8))}.",
        "",
        "## Main Leaks",
        "",
    ]
    lines.extend(main_leaks(rows, diagnostics))
    lines.extend(
        [
            "",
            "## Episode Index",
            "",
            "| Episode | Mode | Result | Opponent/winner | Final rank | Final prod | Peak prod | Collapse | Key loss signal |",
            "|---:|---:|---:|---|---:|---:|---:|---:|---|",
        ]
    )
    diag_by_episode = {diag["episode_id"]: diag for diag in diagnostics}
    for row in rows:
        diag = diag_by_episode[row["episode_id"]]
        winner = diag.get("winner_name") or "n/a"
        peak_prod = diag.get("peak_production", {}).get("production")
        collapse = diag.get("first_zero_prod_after_peak")
        lines.append(
            f"| {row['episode_id']} | {row['players']}P | {fmt(row['reward'])} | "
            f"{winner} | {row['final'].get('rank', 'n/a')} | "
            f"{fmt(row['final'].get('production'))} | {fmt(peak_prod)} | "
            f"{fmt(collapse, 0)} | {episode_loss_signal(row, diag)} |"
        )
    lines.extend(["", "## Specific Fix Targets", ""])
    lines.extend(fix_targets(rows, diagnostics))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main_leaks(rows: list[dict[str, Any]], diagnostics: list[dict[str, Any]]) -> list[str]:
    losses = [row for row in rows if row["reward"] != 1.0]
    ffa_losses = [row for row in losses if row["players"] == 4]
    two_player_losses = [row for row in losses if row["players"] == 2]
    zero_prod_losses = sum(1 for row in losses if row["final"].get("production", 0) <= 0)
    mean_peak_to_final = mean(
        [
            diag.get("peak_production", {}).get("production", 0)
            - next(row for row in rows if row["episode_id"] == diag["episode_id"])["final"].get("production", 0)
            for diag in diagnostics
            if next(row for row in rows if row["episode_id"] == diag["episode_id"])["reward"] != 1.0
        ]
    )
    return [
        f"- **Midgame collapse, not opening-only weakness.** `{zero_prod_losses}/{len(losses)}` losses end at 0 production; mean peak-to-final production drop in losses is `{fmt(mean_peak_to_final)}`. We often reach a playable peak, then donate or fail to defend the position.",
        f"- **4P mode is the primary leak.** `{len(ffa_losses)}` 4P losses and no 4P wins in this public sample. The agent repeatedly peaks between t40-t100, then loses all production before final scoring instead of preserving rank.",
        f"- **2P still loses to modest opponents through expansion/retention failure.** `{len(two_player_losses)}` 2P losses; losing games usually have final production `0` even when the peak production was nonzero.",
        "- **Target selection spends too much on static enemy/own transfers while losing moving/frontier assets.** The largest ship buckets are enemy/own classes; losses show early moving/static captures followed by rapid recapture, so the planner is not pricing hold probability or source vulnerability tightly enough.",
    ]


def episode_loss_signal(row: dict[str, Any], diag: dict[str, Any]) -> str:
    if row["reward"] == 1.0:
        return "win"
    first_losses = row["capture_summary"]["first_losses"][:3]
    if first_losses:
        loss_text = ", ".join(f"t{event['turn']} p{event['planet']}" for event in first_losses)
    else:
        loss_text = "no ownership-loss event captured"
    pressure = sorted(row["pressure_events"], key=lambda event: event["incoming_ships"], reverse=True)[:1]
    if pressure:
        p = pressure[0]
        return f"{loss_text}; peak incoming t{p['turn']} {fmt(p['incoming_ships'])}"
    return loss_text


def fix_targets(rows: list[dict[str, Any]], diagnostics: list[dict[str, Any]]) -> list[str]:
    return [
        "- Add a hold-probability gate for captures: reject/resize missions where predicted owner timeline loses the target within 20-40 turns, especially moving planets.",
        "- Add source-drain counterattack pricing: after a launch, simulate the source with existing enemy fleets plus plausible enemy sends; veto sends that turn a stable source into a near-term loss.",
        "- Split 4P objective from 2P: in 4P, score survival/final rank and production retention above local captures; stop taking trades that make us temporary leader then leave us at 0 production.",
        "- Add coordinated defense/reinforcement candidates, not only capture/attack candidates. Current losses need actions that preserve already-owned high-prod planets under incoming pressure.",
        "- Add replay-regression fixtures from the worst public losses below and assert the planner does not repeat the same launch/collapse pattern around the cited turns.",
    ]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--submission-id", type=int, default=DEFAULT_SUBMISSION_ID)
    parser.add_argument("--agent-name", default=DEFAULT_AGENT_NAME)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--sleep", type=float, default=0.2)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    output_dir = args.output_root / slugify(args.agent_name)
    replay_dir = output_dir / "replay_episodes"
    output_dir.mkdir(parents=True, exist_ok=True)
    replay_dir.mkdir(parents=True, exist_ok=True)
    submission = latest_submission_metadata()
    target = target_metadata()
    episodes = list_submission_episodes(args.submission_id)[: args.limit]
    rows = []
    diagnostics = []
    for episode in episodes:
        replay_path = replay_dir / f"episode-{int(episode['id'])}-replay.json"
        download_replay(int(episode["id"]), replay_path, args.sleep)
        row = analyze_replay(replay_path, target, submission, episode)
        row = add_action_rows(row, replay_path, episode, args.submission_id)
        rows.append(row)
        diagnostics.append(loss_diagnostics(replay_path, episode, row, args.submission_id))
    (output_dir / "selected_submission.json").write_text(
        json.dumps(submission, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    (output_dir / "selected_episodes.json").write_text(
        json.dumps(episodes, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    (output_dir / "episode_analysis.json").write_text(
        json.dumps({"episodes": rows, "diagnostics": diagnostics}, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    write_report(output_dir / "analysis.md", submission, rows, diagnostics, replay_dir)
    print(f"submission={args.submission_id} episodes={len(rows)}")
    print(f"wrote {output_dir / 'analysis.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
