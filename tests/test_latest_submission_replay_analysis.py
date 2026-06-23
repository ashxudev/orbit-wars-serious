"""Tests for latest-submission replay diagnostics."""

from __future__ import annotations

import unittest

from scripts.analyze_latest_submission_replays import (
    add_action_rows,
    source_losses_after_launch,
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


if __name__ == "__main__":
    unittest.main()
