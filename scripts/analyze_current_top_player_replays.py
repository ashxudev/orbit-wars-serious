from __future__ import annotations

import argparse
import json
import math
import re
import sys
import time
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import requests


COMPETITION = "orbit-wars"
BOARD_CENTER = 50.0
ROTATION_RADIUS_LIMIT = 50.0
DEFAULT_OUTPUT_DIR = Path("docs/top_player_analysis")
DEFAULT_REPLAY_DIR = DEFAULT_OUTPUT_DIR / "top_player_replay_downloads"


@dataclass(frozen=True, slots=True)
class PlanetView:
    planet_id: int
    owner: int
    x: float
    y: float
    radius: float
    ships: float
    production: float
    is_comet: bool
    is_moving: bool


def slugify(text: str) -> str:
    return re.sub(r"[^a-zA-Z0-9]+", "_", text.strip()).strip("_").lower() or "team"


def dense_ranks(values: list[float]) -> list[int]:
    ordered = sorted(set(values), reverse=True)
    return [ordered.index(value) + 1 for value in values]


def is_static_planet(row: list[Any]) -> bool:
    x = float(row[2])
    y = float(row[3])
    radius = float(row[4])
    return math.hypot(x - BOARD_CENTER, y - BOARD_CENTER) + radius >= ROTATION_RADIUS_LIMIT


def planet_views(planets: list[list[Any]], comet_ids: set[int]) -> list[PlanetView]:
    views = []
    for row in planets:
        planet_id = int(row[0])
        is_comet = planet_id in comet_ids
        views.append(
            PlanetView(
                planet_id=planet_id,
                owner=int(row[1]),
                x=float(row[2]),
                y=float(row[3]),
                radius=float(row[4]),
                ships=float(row[5]),
                production=float(row[6]),
                is_comet=is_comet,
                is_moving=is_comet or not is_static_planet(row),
            )
        )
    return views


def infer_player_count(planets: list[list[Any]], fleets: list[list[Any]], rewards: list[Any]) -> int:
    owners = [idx for idx in range(len(rewards))]
    owners.extend(int(planet[1]) for planet in planets if int(planet[1]) >= 0)
    owners.extend(int(fleet[1]) for fleet in fleets if int(fleet[1]) >= 0)
    return max(2, max(owners) + 1)


def owner_stats(
    planets: list[list[Any]],
    fleets: list[list[Any]],
    player_count: int,
    comet_ids: set[int],
) -> dict[str, list[float]]:
    stats = {
        "planets": [0.0] * player_count,
        "production": [0.0] * player_count,
        "planet_ships": [0.0] * player_count,
        "fleet_ships": [0.0] * player_count,
        "total_ships": [0.0] * player_count,
        "comets": [0.0] * player_count,
        "moving_planets": [0.0] * player_count,
    }
    for planet in planet_views(planets, comet_ids):
        if 0 <= planet.owner < player_count:
            stats["planets"][planet.owner] += 1.0
            stats["production"][planet.owner] += planet.production
            stats["planet_ships"][planet.owner] += planet.ships
            stats["total_ships"][planet.owner] += planet.ships
            if planet.is_comet:
                stats["comets"][planet.owner] += 1.0
            if planet.is_moving:
                stats["moving_planets"][planet.owner] += 1.0
    for fleet in fleets:
        owner = int(fleet[1])
        if 0 <= owner < player_count:
            ships = float(fleet[6])
            stats["fleet_ships"][owner] += ships
            stats["total_ships"][owner] += ships
    return stats


def frame_observation(frame: list[dict[str, Any]], player_index: int) -> dict[str, Any]:
    if player_index >= len(frame):
        return {}
    return frame[player_index].get("observation") or {}


def infer_action_target(
    planets: list[list[Any]],
    action: list[Any],
    comet_ids: set[int],
) -> PlanetView | None:
    if len(action) < 2:
        return None
    source_id = int(action[0])
    angle = float(action[1])
    views = planet_views(planets, comet_ids)
    by_id = {planet.planet_id: planet for planet in views}
    source = by_id.get(source_id)
    if source is None:
        return None
    dx = math.cos(angle)
    dy = math.sin(angle)
    best: tuple[float, float, PlanetView] | None = None
    for planet in views:
        if planet.planet_id == source_id:
            continue
        vx = planet.x - source.x
        vy = planet.y - source.y
        projection = vx * dx + vy * dy
        if projection <= 0:
            continue
        miss = abs(vx * dy - vy * dx)
        if miss <= planet.radius + 1.25:
            score = (miss, projection)
            if best is None or score < (best[0], best[1]):
                best = (miss, projection, planet)
    return best[2] if best else None


def get_leaderboard(top_n: int = 1) -> list[dict[str, Any]]:
    from kaggle import api
    from kagglesdk.competitions.types.competition_api_service import ApiGetLeaderboardRequest

    request = ApiGetLeaderboardRequest()
    request.competition_name = COMPETITION
    request.page_size = max(top_n, 20)
    with api.build_kaggle_client() as kaggle:
        response = kaggle.competitions.competition_api_client.get_leaderboard(request)
    rows = []
    for idx, row in enumerate(response.submissions or [], start=1):
        rows.append(
            {
                "rank": idx,
                "team_id": int(row.team_id),
                "team_name": row.team_name,
                "submission_date": str(row.submission_date),
                "score": float(row.score),
            }
        )
    return rows[:top_n]


def list_team_public_submissions(team_id: int) -> list[dict[str, Any]]:
    from kaggle import api
    from kagglesdk.competitions.types.competition_api_service import (
        ApiListTeamPublicSubmissionsRequest,
    )

    request = ApiListTeamPublicSubmissionsRequest()
    request.team_id = int(team_id)
    with api.build_kaggle_client() as kaggle:
        response = kaggle.competitions.competition_api_client.list_team_public_submissions(request)
    rows = []
    for row in response.submissions or []:
        try:
            public_score = float(row.public_score)
        except (TypeError, ValueError):
            public_score = None
        rows.append(
            {
                "id": int(row.id),
                "date_submitted": str(row.date_submitted),
                "public_score": public_score,
            }
        )
    return sorted(
        rows,
        key=lambda row: ((row["public_score"] or -9999.0), row["date_submitted"]),
        reverse=True,
    )


def select_public_submission(
    submissions: list[dict[str, Any]],
    leaderboard_score: float,
) -> dict[str, Any]:
    matching = [
        row
        for row in submissions
        if row.get("public_score") is not None
        and abs(float(row["public_score"]) - leaderboard_score) < 0.05
    ]
    if matching:
        return sorted(matching, key=lambda row: row["date_submitted"], reverse=True)[0]
    if not submissions:
        raise RuntimeError("top team has no public submissions")
    return submissions[0]


def list_submission_episodes(submission_id: int) -> list[dict[str, Any]]:
    from kaggle import api
    from kagglesdk.competitions.types.competition_api_service import (
        ApiListSubmissionEpisodesRequest,
    )

    request = ApiListSubmissionEpisodesRequest()
    request.submission_id = int(submission_id)
    with api.build_kaggle_client() as kaggle:
        response = kaggle.competitions.competition_api_client.list_submission_episodes(request)
    rows = []
    for episode in response.episodes or []:
        agents = []
        for agent in episode.agents or []:
            agents.append(
                {
                    "submission_id": int(agent.submission_id),
                    "index": int(agent.index),
                    "reward": float(agent.reward),
                    "state": str(agent.state),
                    "team_name": agent.team_name,
                    "team_id": int(agent.team_id),
                }
            )
        rows.append(
            {
                "id": int(episode.id),
                "create_time": str(episode.create_time),
                "end_time": str(episode.end_time),
                "state": str(episode.state),
                "type": str(episode.type),
                "agents": agents,
            }
        )
    public_rows = [row for row in rows if "EPISODE_TYPE_PUBLIC" in row["type"]]
    return sorted(public_rows, key=lambda row: row["end_time"], reverse=True)


def download_replay(episode_id: int, output_path: Path, sleep_seconds: float) -> None:
    if output_path.exists():
        return
    output_path.parent.mkdir(parents=True, exist_ok=True)
    response = requests.get(
        f"https://www.kaggleusercontent.com/episodes/{episode_id}.json",
        timeout=120,
    )
    response.raise_for_status()
    output_path.write_text(
        json.dumps(response.json(), separators=(",", ":")),
        encoding="utf-8",
    )
    if sleep_seconds > 0:
        time.sleep(sleep_seconds)


def target_index_for_replay(
    replay: dict[str, Any],
    team_name: str,
    team_id: int,
    episode: dict[str, Any],
) -> int:
    team_names = replay.get("info", {}).get("TeamNames") or []
    if team_name in team_names:
        return int(team_names.index(team_name))
    for agent in episode.get("agents") or []:
        if int(agent.get("team_id", -1)) == int(team_id):
            return int(agent.get("index", 0))
    raise RuntimeError(f"team not found in replay: {team_name} ({team_id})")


def action_label(target: PlanetView | None, actor_index: int, player_index: int) -> str:
    if target is None:
        return "unknown"
    if target.owner == -1:
        base = "neutral"
    elif target.owner == player_index:
        base = "own"
    elif actor_index == player_index:
        base = "enemy"
    else:
        base = "our-planet"
    flags = []
    if target.is_comet:
        flags.append("comet")
    elif target.is_moving:
        flags.append("moving")
    return base + ("/" + ",".join(flags) if flags else "")


def summarize_turn_actions(
    actions: list[dict[str, Any]],
    limit: int = 6,
) -> str:
    parts = []
    for item in actions[:limit]:
        target = item.get("target")
        target_text = "?" if target is None else f"p{target['id']}"
        parts.append(
            f"{item['ships']:.0f} from p{item['source']} to {target_text} "
            f"({item['label']})"
        )
    if len(actions) > limit:
        parts.append(f"+{len(actions) - limit} more")
    return "; ".join(parts)


def analyze_replay(
    replay_path: Path,
    target: dict[str, Any],
    submission: dict[str, Any],
    episode: dict[str, Any],
    *,
    include_action_rows: bool = False,
) -> dict[str, Any]:
    replay = json.loads(replay_path.read_text(encoding="utf-8"))
    steps = replay.get("steps") or []
    rewards = replay.get("rewards") or [state.get("reward", 0) for state in steps[-1]]
    player_index = target_index_for_replay(
        replay,
        str(target["team_name"]),
        int(target["team_id"]),
        episode,
    )
    team_names = replay.get("info", {}).get("TeamNames") or []
    curves: list[dict[str, Any]] = []
    action_rows: list[dict[str, Any]] = []
    capture_events: list[dict[str, Any]] = []
    pressure_events: list[dict[str, Any]] = []
    previous_owners: dict[int, int] = {}
    action_counts = Counter()
    target_ship_mix = Counter()

    for turn, frame in enumerate(steps):
        obs = frame_observation(frame, player_index)
        planets = obs.get("planets") or []
        fleets = obs.get("fleets") or []
        comet_ids = {int(pid) for pid in obs.get("comet_planet_ids", []) or []}
        if not planets:
            continue
        player_count = infer_player_count(planets, fleets, rewards)
        stats = owner_stats(planets, fleets, player_count, comet_ids)
        total_ships = stats["total_ships"]
        ranks = dense_ranks(total_ships)
        player_total = total_ships[player_index]
        leader_index = max(range(player_count), key=lambda idx: total_ships[idx])
        curves.append(
            {
                "turn": turn,
                "rank": ranks[player_index],
                "total": player_total,
                "production": stats["production"][player_index],
                "planets": stats["planets"][player_index],
                "planet_ships": stats["planet_ships"][player_index],
                "fleet_ships": stats["fleet_ships"][player_index],
                "leader": leader_index,
                "leader_total": total_ships[leader_index],
                "comets": stats["comets"][player_index],
                "moving": stats["moving_planets"][player_index],
            }
        )
        current_owners = {int(row[0]): int(row[1]) for row in planets}
        for planet in planet_views(planets, comet_ids):
            previous_owner = previous_owners.get(planet.planet_id)
            if previous_owner is not None and previous_owner != planet.owner:
                if planet.owner == player_index or previous_owner == player_index:
                    capture_events.append(
                        {
                            "turn": turn,
                            "planet": planet.planet_id,
                            "from": previous_owner,
                            "to": planet.owner,
                            "ships": planet.ships,
                            "production": planet.production,
                            "kind": (
                                "comet"
                                if planet.is_comet
                                else "moving"
                                if planet.is_moving
                                else "static"
                            ),
                        }
                    )
        previous_owners = current_owners

        turn_own_actions = []
        incoming_this_turn = 0.0
        for actor_index, state in enumerate(frame):
            actions = state.get("action") or []
            if not isinstance(actions, list):
                continue
            for raw_action in actions:
                if not isinstance(raw_action, list) or len(raw_action) < 3:
                    continue
                ships = float(raw_action[2])
                target_planet = infer_action_target(planets, raw_action, comet_ids)
                label = action_label(target_planet, actor_index, player_index)
                if actor_index == player_index:
                    action_counts["actions"] += 1
                    action_counts["ships_sent"] += ships
                    action_counts[label] += 1
                    target_ship_mix[label] += ships
                    row = {
                        "turn": turn,
                        "source": int(raw_action[0]),
                        "angle": float(raw_action[1]),
                        "ships": ships,
                        "label": label,
                        "target": (
                            None
                            if target_planet is None
                            else {
                                "id": target_planet.planet_id,
                                "owner": target_planet.owner,
                                "ships": target_planet.ships,
                                "production": target_planet.production,
                                "is_comet": target_planet.is_comet,
                                "is_moving": target_planet.is_moving,
                            }
                        ),
                    }
                    action_rows.append(row)
                    turn_own_actions.append(row)
                elif target_planet is not None and target_planet.owner == player_index:
                    incoming_this_turn += ships
        if incoming_this_turn > 0:
            pressure_events.append(
                {
                    "turn": turn,
                    "incoming_ships": incoming_this_turn,
                    "rank": ranks[player_index],
                    "production": stats["production"][player_index],
                    "total": player_total,
                }
            )
        if turn_own_actions:
            action_counts["turns_with_actions"] += 1

    first_prod_lead = None
    first_rank_1 = None
    for point in curves:
        turn = int(point["turn"])
        obs = frame_observation(steps[turn], player_index)
        planets = obs.get("planets") or []
        fleets = obs.get("fleets") or []
        comet_ids = {int(pid) for pid in obs.get("comet_planet_ids", []) or []}
        stats = owner_stats(
            planets,
            fleets,
            infer_player_count(planets, fleets, rewards),
            comet_ids,
        )
        total = stats["total_ships"][player_index]
        prod = stats["production"][player_index]
        if first_rank_1 is None and all(
            total > value for idx, value in enumerate(stats["total_ships"]) if idx != player_index
        ):
            first_rank_1 = turn
        if first_prod_lead is None:
            if all(
                prod > value for idx, value in enumerate(stats["production"]) if idx != player_index
            ):
                first_prod_lead = turn

    final = curves[-1] if curves else {}
    top_action_turns = sorted(
        (
            {
                "turn": turn,
                "ships": sum(row["ships"] for row in rows),
                "summary": summarize_turn_actions(rows),
            }
            for turn, rows in _group_by_turn(action_rows).items()
        ),
        key=lambda row: row["ships"],
        reverse=True,
    )[:8]
    capture_summary = summarize_capture_events(capture_events, player_index)
    result = {
        "episode_id": int(episode["id"]),
        "episode_end_time": episode["end_time"],
        "episode_type": episode["type"],
        "team_id": int(target["team_id"]),
        "team_name": target["team_name"],
        "team_names": team_names,
        "leaderboard_rank": int(target["rank"]),
        "leaderboard_score": float(target["score"]),
        "submission_id": int(submission["id"]),
        "submission_public_score": submission.get("public_score"),
        "players": len(rewards),
        "target_index": player_index,
        "steps": len(steps),
        "reward": float(rewards[player_index]) if player_index < len(rewards) else None,
        "final": final,
        "first_prod_lead": first_prod_lead,
        "first_rank_1": first_rank_1,
        "peak_production": max((point["production"] for point in curves), default=0.0),
        "peak_total": max((point["total"] for point in curves), default=0.0),
        "actions": int(action_counts["actions"]),
        "turns_with_actions": int(action_counts["turns_with_actions"]),
        "ships_sent": round(float(action_counts["ships_sent"]), 1),
        "target_mix_counts": dict(sorted(action_counts.items())),
        "target_mix_ships": {
            key: round(value, 1) for key, value in sorted(target_ship_mix.items())
        },
        "top_action_turns": top_action_turns,
        "capture_events": capture_events,
        "capture_summary": capture_summary,
        "pressure_events": pressure_events,
        "curves_sample": sample_curve(curves),
        "replay_path": str(replay_path),
    }
    if include_action_rows:
        result["action_rows"] = action_rows
    return result


def _group_by_turn(rows: list[dict[str, Any]]) -> dict[int, list[dict[str, Any]]]:
    grouped: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[int(row["turn"])].append(row)
    return grouped


def summarize_capture_events(
    capture_events: list[dict[str, Any]],
    player_index: int,
) -> dict[str, Any]:
    gained = [row for row in capture_events if int(row["to"]) == player_index]
    lost = [row for row in capture_events if int(row["from"]) == player_index]
    gained_by_kind = Counter(row["kind"] for row in gained)
    lost_by_kind = Counter(row["kind"] for row in lost)
    return {
        "gained": len(gained),
        "lost": len(lost),
        "gained_by_kind": dict(sorted(gained_by_kind.items())),
        "lost_by_kind": dict(sorted(lost_by_kind.items())),
        "first_gains": gained[:8],
        "first_losses": lost[:8],
    }


def sample_curve(curves: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not curves:
        return []
    wanted = [0, 10, 20, 40, 60, 80, 100, 150, 200, 250, len(curves) - 1]
    rows = []
    seen = set()
    for turn in wanted:
        if turn < 0:
            continue
        point = curves[min(turn, len(curves) - 1)]
        key = int(point["turn"])
        if key in seen:
            continue
        seen.add(key)
        rows.append(
            {
                "turn": key,
                "rank": int(point["rank"]),
                "total": round(float(point["total"]), 1),
                "production": round(float(point["production"]), 1),
                "planets": int(point["planets"]),
                "planet_ships": round(float(point["planet_ships"]), 1),
                "fleet_ships": round(float(point["fleet_ships"]), 1),
                "comets": int(point["comets"]),
                "moving": int(point["moving"]),
            }
        )
    return rows


def write_metadata(
    output_dir: Path,
    target: dict[str, Any],
    submission: dict[str, Any],
    episodes: list[dict[str, Any]],
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "leaderboard_rank_1.json").write_text(
        json.dumps(target, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    (output_dir / "selected_public_submission.json").write_text(
        json.dumps(submission, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    (output_dir / "selected_public_episodes.json").write_text(
        json.dumps(episodes, indent=2, sort_keys=True),
        encoding="utf-8",
    )


def aggregate_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    if not rows:
        return {}
    wins = sum(1 for row in rows if row["reward"] == 1.0)
    return {
        "episodes": len(rows),
        "wins": wins,
        "win_rate": wins / len(rows),
        "players": dict(Counter(str(row["players"]) for row in rows)),
        "mean_final_rank": mean([row["final"].get("rank") for row in rows]),
        "mean_final_production": mean([row["final"].get("production") for row in rows]),
        "mean_final_total": mean([row["final"].get("total") for row in rows]),
        "mean_actions": mean([row["actions"] for row in rows]),
        "mean_ships_sent": mean([row["ships_sent"] for row in rows]),
        "first_prod_lead_median": median(
            [row["first_prod_lead"] for row in rows if row["first_prod_lead"] is not None]
        ),
        "first_rank_1_median": median(
            [row["first_rank_1"] for row in rows if row["first_rank_1"] is not None]
        ),
    }


def mean(values: list[Any]) -> float | None:
    nums = [float(value) for value in values if isinstance(value, (int, float))]
    if not nums:
        return None
    return sum(nums) / len(nums)


def median(values: list[Any]) -> float | None:
    nums = sorted(float(value) for value in values if isinstance(value, (int, float)))
    if not nums:
        return None
    mid = len(nums) // 2
    if len(nums) % 2:
        return nums[mid]
    return (nums[mid - 1] + nums[mid]) / 2


def fmt(value: Any, digits: int = 1) -> str:
    if value is None:
        return "n/a"
    if isinstance(value, float):
        return f"{value:.{digits}f}"
    return str(value)


def write_report(
    path: Path,
    target: dict[str, Any],
    submission: dict[str, Any],
    rows: list[dict[str, Any]],
    replay_dir: Path,
) -> None:
    aggregate = aggregate_rows(rows)
    lines = [
        "# Current Top Player Replay Analysis",
        "",
        f"- Competition: `{COMPETITION}`",
        f"- Current rank 1 team: `{target['team_name']}`",
        f"- Team ID: `{target['team_id']}`",
        f"- Leaderboard score: `{target['score']}`",
        f"- Selected public submission: `{submission['id']}` "
        f"(public score `{submission.get('public_score')}`)",
        f"- Episodes analyzed: `{len(rows)}` most recent public episodes from that submission",
        f"- Replay downloads: `{replay_dir}`",
        "",
        "## Aggregate Signals",
        "",
        "| Metric | Value |",
        "|---|---:|",
        f"| Win rate in sample | {fmt(aggregate.get('win_rate'), 3)} |",
        f"| Player-count mix | {json.dumps(aggregate.get('players', {}), sort_keys=True)} |",
        f"| Mean final rank | {fmt(aggregate.get('mean_final_rank'), 2)} |",
        f"| Mean final production | {fmt(aggregate.get('mean_final_production'))} |",
        f"| Mean final total ships | {fmt(aggregate.get('mean_final_total'))} |",
        f"| Mean actions | {fmt(aggregate.get('mean_actions'))} |",
        f"| Mean ships launched | {fmt(aggregate.get('mean_ships_sent'))} |",
        f"| Median first production lead | t{fmt(aggregate.get('first_prod_lead_median'), 0)} |",
        f"| Median first rank 1 | t{fmt(aggregate.get('first_rank_1_median'), 0)} |",
        "",
        "## Technical Takeaways",
        "",
    ]
    lines.extend(technical_takeaways(rows))
    lines.extend(
        [
            "",
            "## Episode Index",
            "",
            "| Episode | End time | Players | Reward | Final rank | Final prod | Actions | Ships sent | First prod lead | First rank 1 |",
            "|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for row in rows:
        lines.append(
            f"| {row['episode_id']} | {row['episode_end_time']} | {row['players']} | "
            f"{fmt(row['reward'])} | {row['final'].get('rank', 'n/a')} | "
            f"{fmt(row['final'].get('production'))} | {row['actions']} | "
            f"{fmt(row['ships_sent'])} | {fmt(row['first_prod_lead'], 0)} | "
            f"{fmt(row['first_rank_1'], 0)} |"
        )
    lines.extend(["", "## Episode Notes", ""])
    for row in rows:
        lines.extend(episode_notes(row))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def technical_takeaways(rows: list[dict[str, Any]]) -> list[str]:
    labels = Counter()
    ships = Counter()
    for row in rows:
        labels.update(
            {
                key: value
                for key, value in row["target_mix_counts"].items()
                if key not in {"actions", "ships_sent", "turns_with_actions"}
            }
        )
        ships.update(row["target_mix_ships"])
    lines = []
    if labels:
        target_text = ", ".join(f"`{key}` {value}" for key, value in labels.most_common(8))
        lines.append(f"- Launch targeting is broad, not single-mode: {target_text}.")
    if ships:
        ship_text = ", ".join(f"`{key}` {value:.0f}" for key, value in ships.most_common(8))
        lines.append(f"- Ship spend by inferred target class: {ship_text}.")
    prod_leads = [row["first_prod_lead"] for row in rows if row["first_prod_lead"] is not None]
    rank_ones = [row["first_rank_1"] for row in rows if row["first_rank_1"] is not None]
    if prod_leads:
        lines.append(
            f"- Economy lead usually appears early: first production lead range "
            f"t{min(prod_leads)}-t{max(prod_leads)}, median t{fmt(median(prod_leads), 0)}."
        )
    if rank_ones:
        lines.append(
            f"- Rank-1 total-ship position is also early: range "
            f"t{min(rank_ones)}-t{max(rank_ones)}, median t{fmt(median(rank_ones), 0)}."
        )
    capture_counts = [row["capture_summary"]["gained"] for row in rows]
    loss_counts = [row["capture_summary"]["lost"] for row in rows]
    lines.append(
        f"- Ownership churn is accepted: average gains {fmt(mean(capture_counts))}, "
        f"average losses {fmt(mean(loss_counts))}; the agent keeps tempo instead of freezing after first capture."
    )
    pressure = [sum(event["incoming_ships"] for event in row["pressure_events"]) for row in rows]
    lines.append(
        f"- It tolerates large incoming attacks: mean inferred incoming pressure "
        f"{fmt(mean(pressure))} ships/game while continuing launches."
    )
    return lines


def episode_notes(row: dict[str, Any]) -> list[str]:
    lines = [
        f"### Episode {row['episode_id']}",
        "",
        f"- `{row['players']}P`, reward `{row['reward']}`, final rank `{row['final'].get('rank')}`, "
        f"final production `{fmt(row['final'].get('production'))}`, final total `{fmt(row['final'].get('total'))}`.",
        f"- First production lead: `t{fmt(row['first_prod_lead'], 0)}`; first rank 1: `t{fmt(row['first_rank_1'], 0)}`.",
        f"- Actions: `{row['actions']}` launches over `{row['turns_with_actions']}` turns, ships sent `{fmt(row['ships_sent'])}`.",
        f"- Target mix counts: `{json.dumps(row['target_mix_counts'], sort_keys=True)}`.",
        f"- Target mix ships: `{json.dumps(row['target_mix_ships'], sort_keys=True)}`.",
        "",
        "Curve checkpoints:",
        "",
        "| Turn | Rank | Total | Prod | Planets | Planet ships | Fleet ships | Comets | Moving |",
        "|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for point in row["curves_sample"]:
        lines.append(
            f"| {point['turn']} | {point['rank']} | {point['total']} | "
            f"{point['production']} | {point['planets']} | {point['planet_ships']} | "
            f"{point['fleet_ships']} | {point['comets']} | {point['moving']} |"
        )
    lines.extend(["", "Largest launch turns:", ""])
    for item in row["top_action_turns"][:5]:
        lines.append(f"- t{item['turn']}: `{fmt(item['ships'])}` ships: {item['summary']}.")
    summary = row["capture_summary"]
    lines.extend(
        [
            "",
            f"Ownership events: `{summary['gained']}` gains, `{summary['lost']}` losses; "
            f"gained by kind `{json.dumps(summary['gained_by_kind'], sort_keys=True)}`, "
            f"lost by kind `{json.dumps(summary['lost_by_kind'], sort_keys=True)}`.",
        ]
    )
    if summary["first_gains"]:
        gain_text = "; ".join(
            f"t{event['turn']} p{event['planet']} {event['kind']} prod {event['production']} ships {event['ships']}"
            for event in summary["first_gains"][:6]
        )
        lines.append(f"- First gains: {gain_text}.")
    if summary["first_losses"]:
        loss_text = "; ".join(
            f"t{event['turn']} p{event['planet']} {event['kind']} prod {event['production']} ships {event['ships']}"
            for event in summary["first_losses"][:6]
        )
        lines.append(f"- First losses: {loss_text}.")
    if row["pressure_events"]:
        largest = sorted(row["pressure_events"], key=lambda event: event["incoming_ships"], reverse=True)[:4]
        pressure_text = "; ".join(
            f"t{event['turn']} incoming {fmt(event['incoming_ships'])}, rank {event['rank']}, prod {fmt(event['production'])}"
            for event in largest
        )
        lines.append(f"- Largest inferred pressure turns: {pressure_text}.")
    lines.append("")
    return lines


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--replay-dir", type=Path, default=DEFAULT_REPLAY_DIR)
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--sleep", type=float, default=0.2)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.limit <= 0:
        raise SystemExit("--limit must be positive")
    target = get_leaderboard(1)[0]
    submissions = list_team_public_submissions(int(target["team_id"]))
    submission = select_public_submission(submissions, float(target["score"]))
    episodes = list_submission_episodes(int(submission["id"]))[: args.limit]
    if len(episodes) < args.limit:
        raise RuntimeError(f"only {len(episodes)} public episodes available")

    team_dir = args.replay_dir / f"rank_01_{slugify(str(target['team_name']))}"
    rows = []
    for episode in episodes:
        replay_path = team_dir / f"episode-{int(episode['id'])}-replay.json"
        download_replay(int(episode["id"]), replay_path, args.sleep)
        rows.append(analyze_replay(replay_path, target, submission, episode))

    args.output_dir.mkdir(parents=True, exist_ok=True)
    args.replay_dir.mkdir(parents=True, exist_ok=True)
    write_metadata(args.output_dir, target, submission, episodes)
    (args.output_dir / "episode_analysis.json").write_text(
        json.dumps(rows, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    write_report(
        args.output_dir / "current_top_player_technical_report.md",
        target,
        submission,
        rows,
        args.replay_dir,
    )
    print(f"rank_1={target['team_name']} score={target['score']} submission={submission['id']}")
    print(f"episodes={','.join(str(row['episode_id']) for row in rows)}")
    print(f"wrote {args.output_dir / 'current_top_player_technical_report.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
