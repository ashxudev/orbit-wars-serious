"""Tests for latest-submission replay diagnostics."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts.analyze_current_top_player_replays import analyze_replay
from scripts.analyze_latest_submission_replays import (
    add_action_rows,
    latest_submission_metadata,
    source_losses_after_launch,
    target_metadata,
)


class LatestSubmissionReplayAnalysisTests(unittest.TestCase):
    def test_add_action_rows_preserves_compact_action_rows_for_diagnostics(self) -> None:
        row = {
            "action_rows": [
                {"turn": 10, "source": 7, "ships": 12.0},
            ],
        }

        result = add_action_rows(row, object(), {}, 123)

        self.assertIs(result, row)
        self.assertEqual(
            result["action_rows"],
            [{"turn": 10, "source": 7, "ships": 12.0}],
        )

    def test_source_losses_after_launch_counts_near_term_source_drain(self) -> None:
        row = {
            "target_index": 0,
            "capture_events": [
                {"from": 0, "planet": 7, "turn": 16},
                {"from": 0, "planet": 8, "turn": 35},
                {"from": 1, "planet": 9, "turn": 12},
            ],
            "action_rows": [
                {"turn": 10, "source": 7},
                {"turn": 20, "source": 8},
                {"turn": 30, "source": 9},
            ],
        }

        self.assertEqual(
            source_losses_after_launch(row),
            {"within_5": 0, "within_10": 1, "within_20": 2},
        )

    def test_submission_metadata_can_describe_source_guard_candidate(self) -> None:
        submission = latest_submission_metadata(
            submission_id=53992217,
            agent_name="fallback_source_guard",
            file_name="orbit_wars_fallback_source_guard_submission.py",
            date_submitted="2026-06-23 22:13:59.840000",
            description="reserve fallback-source-guard",
            public_score=600.0,
        )
        target = target_metadata(submission, team_name="ashxudev", team_id=16193764)

        self.assertEqual(submission["id"], 53992217)
        self.assertEqual(submission["agent_name"], "fallback_source_guard")
        self.assertEqual(target["score"], 600.0)
        self.assertEqual(target["team_id"], 16193764)

    def test_analyze_replay_can_return_compact_action_rows_when_requested(self) -> None:
        replay = {
            "info": {"TeamNames": ["ashxudev", "opponent"]},
            "rewards": [1.0, -1.0],
            "steps": [
                [
                    {
                        "observation": {
                            "player": 0,
                            "step": 0,
                            "remainingOverageTime": 60,
                            "angular_velocity": 0.0,
                            "planets": [
                                [0, 0, 10.0, 50.0, 2.0, 10, 5],
                                [1, -1, 20.0, 50.0, 2.0, 1, 3],
                            ],
                            "fleets": [],
                            "initial_planets": [
                                [0, 0, 10.0, 50.0, 2.0, 10, 5],
                                [1, -1, 20.0, 50.0, 2.0, 1, 3],
                            ],
                        },
                        "action": [[0, 0.0, 5]],
                    },
                    {
                        "observation": {
                            "player": 1,
                            "step": 0,
                            "remainingOverageTime": 60,
                            "angular_velocity": 0.0,
                            "planets": [
                                [0, 0, 10.0, 50.0, 2.0, 10, 5],
                                [1, -1, 20.0, 50.0, 2.0, 1, 3],
                            ],
                            "fleets": [],
                            "initial_planets": [
                                [0, 0, 10.0, 50.0, 2.0, 10, 5],
                                [1, -1, 20.0, 50.0, 2.0, 1, 3],
                            ],
                        },
                        "action": [],
                    },
                ]
            ],
        }
        episode = {
            "id": 1,
            "end_time": "now",
            "type": "EpisodeType.EPISODE_TYPE_PUBLIC",
            "agents": [
                {
                    "index": 0,
                    "team_name": "ashxudev",
                    "team_id": 16193764,
                    "submission_id": 53992217,
                    "reward": 1.0,
                },
                {
                    "index": 1,
                    "team_name": "opponent",
                    "team_id": 1,
                    "submission_id": 1,
                    "reward": -1.0,
                },
            ],
        }
        target = {"rank": -1, "score": 600.0, "team_id": 16193764, "team_name": "ashxudev"}
        submission = {"id": 53992217, "public_score": 600.0}
        with tempfile.TemporaryDirectory() as temp_dir:
            replay_path = Path(temp_dir) / "replay.json"
            replay_path.write_text(json.dumps(replay), encoding="utf-8")

            row = analyze_replay(
                replay_path,
                target,
                submission,
                episode,
                include_action_rows=True,
            )

        self.assertEqual(len(row["action_rows"]), 1)
        self.assertEqual(row["action_rows"][0]["source"], 0)
        self.assertEqual(row["action_rows"][0]["target"]["id"], 1)


if __name__ == "__main__":
    unittest.main()
