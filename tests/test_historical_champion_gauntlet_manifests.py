"""Tests for full-horizon historical champion gauntlet manifests."""

from __future__ import annotations

import json
import unittest
from pathlib import Path
from typing import Any

from ow_eval import (
    AgentSourceKind,
    AgentSpec,
    ExperimentManifest,
    PlayerCount,
    manifest_to_match_configs,
)
from ow_eval.agent_loading import load_agent_callable


REPO_ROOT = Path(__file__).resolve().parents[1]
REGISTRY_PATH = REPO_ROOT / "experiments" / "historical_champions" / "registry.json"
MANIFEST_2P_PATH = (
    REPO_ROOT / "experiments" / "manifests" / "historical-champion-gauntlet-2p-500.json"
)
MANIFEST_4P_PATH = (
    REPO_ROOT / "experiments" / "manifests" / "historical-champion-gauntlet-4p-500.json"
)
MANIFEST_PATHS = (MANIFEST_2P_PATH, MANIFEST_4P_PATH)


def load_registry() -> dict[str, Any]:
    return json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))


def load_manifest(path: Path) -> ExperimentManifest:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return ExperimentManifest.from_dict(payload)


def loadable_registry_entries() -> list[dict[str, Any]]:
    return [
        entry
        for entry in load_registry()["entries"]
        if entry["loadability_status"] == "loadable"
    ]


def expected_opponent_names_by_path() -> dict[Path, tuple[str, ...]]:
    names = tuple(entry["name"] for entry in loadable_registry_entries())
    return {
        MANIFEST_2P_PATH: tuple(
            name
            for entry_name in names
            for name in (entry_name, entry_name)
        ),
        MANIFEST_4P_PATH: (
            "claude-v3-wide-search-forecast",
            "claude-v28-mode-split-champion",
            "claude-v37-race-fix-mode-split",
            "claude-v3-wide-search-forecast",
            "claude-v28-mode-split-champion",
            "claude-v37-race-fix-mode-split",
            "claude-v3-wide-search-forecast",
            "claude-v28-mode-split-champion",
            "claude-v37-race-fix-mode-split",
            "claude-v3-wide-search-forecast",
            "claude-v28-mode-split-champion",
            "claude-v37-race-fix-mode-split",
            "claude-v14-hammer-discipline",
            "claude-v8-leader-weighted-denial",
            "claude-v62-low-pickoff-bundled",
            "claude-v14-hammer-discipline",
            "claude-v8-leader-weighted-denial",
            "claude-v62-low-pickoff-bundled",
            "ow2-current-main",
            "ow2-v11-wide-search",
            "claude-main-v62-bundled",
            "ow2-current-main",
            "ow2-v11-wide-search",
            "claude-main-v62-bundled",
        ),
    }


class HistoricalChampionGauntletManifestTests(unittest.TestCase):
    def test_manifests_exist_and_round_trip_deterministically(self) -> None:
        for path in MANIFEST_PATHS:
            with self.subTest(path=path.name):
                self.assertTrue(path.is_file())
                payload = json.loads(path.read_text(encoding="utf-8"))
                manifest = ExperimentManifest.from_dict(payload)
                expected_text = json.dumps(manifest.to_dict(), sort_keys=True, indent=2) + "\n"

                self.assertEqual(path.read_text(encoding="utf-8"), expected_text)
                self.assertEqual(ExperimentManifest.from_dict(json.loads(expected_text)), manifest)

    def test_candidate_agent_is_current_modular_runtime(self) -> None:
        for path in MANIFEST_PATHS:
            with self.subTest(path=path.name):
                manifest = load_manifest(path)

                self.assertEqual(manifest.candidate_agent.name, "orbit-wars-runtime-v2")
                self.assertEqual(manifest.candidate_agent.source_kind, AgentSourceKind.MODULAR_AGENT)
                self.assertEqual(manifest.candidate_agent.module_path, "agents.orbit_wars_agent_v2")

    def test_every_scenario_is_full_horizon_and_schema_valid(self) -> None:
        expected_counts = {
            MANIFEST_2P_PATH: (PlayerCount.TWO_PLAYER, 22),
            MANIFEST_4P_PATH: (PlayerCount.FOUR_PLAYER, 8),
        }

        for path in MANIFEST_PATHS:
            manifest = load_manifest(path)
            expected_player_count, expected_count = expected_counts[path]

            with self.subTest(path=path.name):
                self.assertEqual(len(manifest.scenarios), expected_count)
                self.assertEqual(dict(manifest.metadata).get("episode_steps"), "500")
                for scenario in manifest.scenarios:
                    metadata = dict(scenario.metadata)

                    self.assertEqual(scenario.player_count, expected_player_count)
                    self.assertEqual(metadata.get("episode_steps"), "500")
                    self.assertEqual(metadata.get("registry_version"), "v0")
                    self.assertIn("historical-champion-gauntlet", metadata["scenario_matrix"])
                    self.assertEqual(len(scenario.opponent_agents), expected_player_count.value - 1)

    def test_two_player_matrix_uses_all_loadable_champions_across_both_seats(self) -> None:
        manifest = load_manifest(MANIFEST_2P_PATH)
        loadable_names = tuple(entry["name"] for entry in loadable_registry_entries())

        self.assertEqual(
            tuple(scenario.controlled_seat for scenario in manifest.scenarios),
            tuple(seat for _ in loadable_names for seat in (0, 1)),
        )
        self.assertEqual(
            tuple(
                scenario.opponent_agents[0].agent.name
                for scenario in manifest.scenarios
            ),
            tuple(name for name in loadable_names for _ in (0, 1)),
        )
        self.assertEqual(
            tuple(scenario.seed for scenario in manifest.scenarios[:4]),
            (7210, 7211, 7220, 7221),
        )

    def test_four_player_matrix_includes_required_pool_types(self) -> None:
        manifest = load_manifest(MANIFEST_4P_PATH)
        purposes = tuple(dict(scenario.metadata)["purpose"] for scenario in manifest.scenarios)
        labels = tuple(scenario.label for scenario in manifest.scenarios)

        self.assertGreaterEqual(purposes.count("top-score-champion-pool"), 4)
        self.assertGreaterEqual(purposes.count("mixed-champion-style-pool"), 2)
        self.assertGreaterEqual(purposes.count("orbit-wars-2-smoke-reference-pool"), 2)
        self.assertEqual(
            labels,
            (
                "historical-gauntlet-4p-500-top-score-seat-0",
                "historical-gauntlet-4p-500-top-score-seat-1",
                "historical-gauntlet-4p-500-top-score-seat-2",
                "historical-gauntlet-4p-500-top-score-seat-3",
                "historical-gauntlet-4p-500-mixed-style-seat-0",
                "historical-gauntlet-4p-500-mixed-style-seat-2",
                "historical-gauntlet-4p-500-ow2-smoke-reference-seat-0",
                "historical-gauntlet-4p-500-ow2-smoke-reference-seat-3",
            ),
        )

    def test_only_loadable_registry_entries_are_scheduled(self) -> None:
        loadable_names = {entry["name"] for entry in loadable_registry_entries()}
        skipped_names = {
            entry["name"]
            for entry in load_registry()["entries"]
            if entry["loadability_status"] == "skipped"
        }

        for path in MANIFEST_PATHS:
            with self.subTest(path=path.name):
                manifest = load_manifest(path)
                scheduled_names = {
                    opponent.agent.name
                    for scenario in manifest.scenarios
                    for opponent in scenario.opponent_agents
                }

                self.assertTrue(scheduled_names <= loadable_names)
                self.assertFalse(scheduled_names & skipped_names)

    def test_opponent_paths_exist_and_load_without_running_matches(self) -> None:
        seen_names: set[str] = set()

        for path in MANIFEST_PATHS:
            manifest = load_manifest(path)
            for scenario in manifest.scenarios:
                for opponent in scenario.opponent_agents:
                    agent = opponent.agent
                    if agent.name in seen_names:
                        continue
                    seen_names.add(agent.name)
                    with self.subTest(name=agent.name):
                        self.assertEqual(agent.source_kind, AgentSourceKind.PYTHON_FILE)
                        self.assertIsNotNone(agent.file_path)
                        path = Path(agent.file_path or "")
                        self.assertFalse(path.is_absolute(), str(path))
                        resolved_path = REPO_ROOT / path
                        self.assertTrue(resolved_path.is_file())
                        resolved_agent = AgentSpec(
                            name=agent.name,
                            source_kind=agent.source_kind,
                            file_path=str(resolved_path),
                            callable_name=agent.callable_name,
                            metadata=agent.metadata,
                        )
                        self.assertTrue(callable(load_agent_callable(resolved_agent)))

        self.assertEqual(
            tuple(name for path in MANIFEST_PATHS for name in expected_opponent_names_by_path()[path])[:3],
            (
                "claude-v3-wide-search-forecast",
                "claude-v3-wide-search-forecast",
                "claude-v28-mode-split-champion",
            ),
        )

    def test_manifests_expand_to_match_configs_without_running_matches(self) -> None:
        for path in MANIFEST_PATHS:
            with self.subTest(path=path.name):
                manifest = load_manifest(path)
                matches = manifest_to_match_configs(manifest)

                self.assertEqual(len(matches), len(manifest.scenarios))
                self.assertTrue(
                    all(dict(match.metadata).get("episode_steps") == "500" for match in matches)
                )


if __name__ == "__main__":
    unittest.main()
