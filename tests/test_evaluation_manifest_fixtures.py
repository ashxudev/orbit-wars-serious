"""Tests for canonical local evaluation manifest fixtures."""

from __future__ import annotations

import json
import unittest
from pathlib import Path
from unittest.mock import patch

from ow_eval import (
    AgentSourceKind,
    EvaluationBatchResult,
    ExperimentManifest,
    ExperimentRunResult,
    MatchConfig,
    PlannerAnalysisPack,
    PlayerCount,
    PromotionThresholds,
    ScoreboardRecord,
    available_builtin_baselines,
    manifest_to_match_configs,
    run_evaluation_experiment,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
MANIFEST_DIR = REPO_ROOT / "experiments" / "manifests"
EXPECTED_FIXTURES = (
    "competitive-baseline-smoke.json",
    "quick-2p-smoke.json",
    "quick-4p-smoke.json",
    "promotion-smoke.json",
)
EXPECTED_MATCHES = {
    "competitive-baseline-smoke.json": (
        (7, PlayerCount.TWO_PLAYER, 0, "competitive-2p-seed-7-seat-0-noop", 1),
        (
            8,
            PlayerCount.TWO_PLAYER,
            1,
            "competitive-2p-seed-8-seat-1-nearest-neutral",
            1,
        ),
        (
            9,
            PlayerCount.TWO_PLAYER,
            0,
            "competitive-2p-seed-9-seat-0-nearest-neutral",
            1,
        ),
        (7, PlayerCount.FOUR_PLAYER, 0, "competitive-4p-seed-7-seat-0-mixed", 3),
        (8, PlayerCount.FOUR_PLAYER, 2, "competitive-4p-seed-8-seat-2-mixed", 3),
        (9, PlayerCount.FOUR_PLAYER, 3, "competitive-4p-seed-9-seat-3-mixed", 3),
    ),
    "quick-2p-smoke.json": (
        (7, PlayerCount.TWO_PLAYER, 0, "quick-2p-seed-7-seat-0", 1),
        (8, PlayerCount.TWO_PLAYER, 0, "quick-2p-seed-8-seat-0", 1),
    ),
    "quick-4p-smoke.json": (
        (7, PlayerCount.FOUR_PLAYER, 0, "quick-4p-seed-7-seat-0", 3),
        (8, PlayerCount.FOUR_PLAYER, 2, "quick-4p-seed-8-seat-2", 3),
    ),
    "promotion-smoke.json": (
        (7, PlayerCount.TWO_PLAYER, 0, "promotion-2p-seed-7-seat-0", 1),
        (8, PlayerCount.TWO_PLAYER, 1, "promotion-2p-seed-8-seat-1", 1),
        (7, PlayerCount.FOUR_PLAYER, 0, "promotion-4p-seed-7-seat-0", 3),
    ),
}


def fixture_path(name: str) -> Path:
    return MANIFEST_DIR / name


def load_manifest(name: str) -> ExperimentManifest:
    payload = json.loads(fixture_path(name).read_text(encoding="utf-8"))
    return ExperimentManifest.from_dict(payload)


def passing_run_result(manifest: ExperimentManifest) -> ExperimentRunResult:
    match_count = len(manifest.scenarios)
    threshold = manifest.promotion_thresholds.max_mean_rank
    mean_rank = threshold if threshold is not None else 1.0
    record = ScoreboardRecord(
        agent_name=manifest.candidate_agent.name,
        agent_version=manifest.version,
        commit=None,
        scenario_set=manifest.name,
        match_count=match_count,
        completed_count=match_count,
        win_count=0,
        loss_count=match_count,
        error_count=0,
        win_rate=0.0 if match_count else None,
        error_rate=0.0 if match_count else None,
        mean_rank=mean_rank,
        mean_score=0.0 if match_count else None,
    )
    return ExperimentRunResult(
        manifest=manifest,
        matches=manifest_to_match_configs(manifest),
        batch_result=EvaluationBatchResult(),
        scoreboard_record=record,
        analysis_pack=PlannerAnalysisPack(total_results=match_count),
        summary_text=(
            f"experiment={manifest.name} matches={match_count} "
            f"completed={match_count} errors=0 win_rate=0 mean_rank={mean_rank:.6g} "
            "analysis_items=0"
        ),
    )


class EvaluationManifestFixtureTests(unittest.TestCase):
    def test_expected_manifest_fixture_files_exist(self) -> None:
        self.assertEqual(
            tuple(path.name for path in sorted(MANIFEST_DIR.glob("*.json"))),
            tuple(sorted(EXPECTED_FIXTURES)),
        )

    def test_manifest_fixtures_parse_and_round_trip_deterministically(self) -> None:
        for name in EXPECTED_FIXTURES:
            with self.subTest(name=name):
                manifest = load_manifest(name)
                expected_text = (
                    json.dumps(manifest.to_dict(), sort_keys=True, indent=2) + "\n"
                )

                self.assertEqual(fixture_path(name).read_text(encoding="utf-8"), expected_text)
                self.assertEqual(
                    ExperimentManifest.from_dict(json.loads(expected_text)),
                    manifest,
                )

    def test_manifest_fixtures_expand_to_expected_match_order(self) -> None:
        for name, expected in EXPECTED_MATCHES.items():
            with self.subTest(name=name):
                matches = manifest_to_match_configs(load_manifest(name))

                self.assertTrue(all(isinstance(match, MatchConfig) for match in matches))
                self.assertEqual(
                    tuple(
                        (
                            match.seed,
                            match.player_count,
                            match.controlled_seat,
                            match.label,
                            len(match.opponent_agents),
                        )
                        for match in matches
                    ),
                    expected,
                )

    def test_two_player_and_four_player_fixture_modes_are_canonical(self) -> None:
        competitive = manifest_to_match_configs(
            load_manifest("competitive-baseline-smoke.json")
        )
        quick_2p = manifest_to_match_configs(load_manifest("quick-2p-smoke.json"))
        quick_4p = manifest_to_match_configs(load_manifest("quick-4p-smoke.json"))
        promotion = manifest_to_match_configs(load_manifest("promotion-smoke.json"))

        self.assertTrue(
            all(match.player_count is PlayerCount.TWO_PLAYER for match in quick_2p)
        )
        self.assertTrue(
            all(match.player_count is PlayerCount.FOUR_PLAYER for match in quick_4p)
        )
        self.assertEqual(
            tuple(match.player_count for match in promotion),
            (
                PlayerCount.TWO_PLAYER,
                PlayerCount.TWO_PLAYER,
                PlayerCount.FOUR_PLAYER,
            ),
        )
        self.assertEqual(
            tuple(match.player_count for match in competitive),
            (
                PlayerCount.TWO_PLAYER,
                PlayerCount.TWO_PLAYER,
                PlayerCount.TWO_PLAYER,
                PlayerCount.FOUR_PLAYER,
                PlayerCount.FOUR_PLAYER,
                PlayerCount.FOUR_PLAYER,
            ),
        )

    def test_candidate_and_opponent_agent_specs_use_supported_source_kinds(self) -> None:
        supported_baselines = set(available_builtin_baselines())
        for name in EXPECTED_FIXTURES:
            with self.subTest(name=name):
                manifest = load_manifest(name)

                self.assertEqual(
                    manifest.candidate_agent.source_kind,
                    AgentSourceKind.MODULAR_AGENT,
                )
                self.assertEqual(
                    manifest.candidate_agent.module_path,
                    "agents.orbit_wars_agent",
                )
                for scenario in manifest.scenarios:
                    for opponent in scenario.opponent_agents:
                        self.assertEqual(
                            opponent.agent.source_kind,
                            AgentSourceKind.BUILTIN_BASELINE,
                        )
                        metadata = dict(opponent.agent.metadata)
                        self.assertIn(metadata.get("baseline"), supported_baselines)
                        self.assertIsNone(opponent.agent.module_path)
                        self.assertIsNone(opponent.agent.file_path)

    def test_promotion_thresholds_are_explicit_for_smoke_use(self) -> None:
        for name in EXPECTED_FIXTURES:
            with self.subTest(name=name):
                thresholds = load_manifest(name).promotion_thresholds

                self.assertIsInstance(thresholds, PromotionThresholds)
                self.assertEqual(thresholds.min_win_rate, 0.0)
                self.assertEqual(thresholds.max_error_rate, 0.0)
                self.assertIsNotNone(thresholds.max_mean_rank)
                self.assertIsNotNone(thresholds.min_completed_count)
                self.assertGreaterEqual(thresholds.min_completed_count, 1)

    def test_fixtures_are_compatible_with_cycle_16_cli_without_running_matches(
        self,
    ) -> None:
        seen_manifest_names: list[str] = []

        def fake_runner(
            manifest: ExperimentManifest,
            config: object | None = None,
        ) -> ExperimentRunResult:
            _ = config
            seen_manifest_names.append(manifest.name)
            return passing_run_result(manifest)

        with patch(
            "ow_eval.experiment_cli.run_experiment_manifest",
            side_effect=fake_runner,
        ):
            results = tuple(
                run_evaluation_experiment(fixture_path(name))
                for name in EXPECTED_FIXTURES
            )

        self.assertEqual(
            tuple(result.exit_code for result in results),
            (0,) * len(EXPECTED_FIXTURES),
        )
        self.assertEqual(
            tuple(result.report_path for result in results),
            (None,) * len(EXPECTED_FIXTURES),
        )
        self.assertEqual(
            tuple(result.experiment_report.manifest_name for result in results),
            (
                "competitive-baseline-smoke",
                "quick-2p-smoke",
                "quick-4p-smoke",
                "promotion-smoke",
            ),
        )
        self.assertEqual(
            tuple(seen_manifest_names),
            (
                "competitive-baseline-smoke",
                "quick-2p-smoke",
                "quick-4p-smoke",
                "promotion-smoke",
            ),
        )

    def test_fixtures_are_data_only_json_without_generated_outputs(self) -> None:
        forbidden_terms = (
            "artifact_path",
            "replay_path",
            "scoreboard_record",
            "promotion_decision",
            "match_outputs",
            "generated_submission",
        )
        for name in EXPECTED_FIXTURES:
            with self.subTest(name=name):
                text = fixture_path(name).read_text(encoding="utf-8")

                self.assertTrue(text.endswith("\n"))
                for term in forbidden_terms:
                    self.assertNotIn(term, text)


if __name__ == "__main__":
    unittest.main()
