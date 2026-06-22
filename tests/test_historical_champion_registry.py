"""Tests for the historical champion gauntlet opponent registry."""

from __future__ import annotations

import json
import unittest
from pathlib import Path
from typing import Any

from ow_eval import AgentSourceKind, AgentSpec
from ow_eval.agent_loading import load_agent_callable


REPO_ROOT = Path(__file__).resolve().parents[1]
REGISTRY_PATH = REPO_ROOT / "experiments" / "historical_champions" / "registry.json"
OPPONENT_MANIFEST_PATH = REPO_ROOT / "historical_opponents" / "manifest.json"
OPPONENT_AGENT_DIR = REPO_ROOT / "historical_opponents" / "agents"
HISTORICAL_ROOTS = (
    Path("/Users/user/dev/hackathons/orbit-wars"),
    Path("/Users/user/dev/hackathons/orbit-wars-2"),
    Path("/Users/user/dev/hackathons/orbit-wars-claude"),
)
STRONG_SCORE_FLOOR = 800.0


def load_registry() -> dict[str, Any]:
    return json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))


def load_opponent_manifest() -> dict[str, Any]:
    return json.loads(OPPONENT_MANIFEST_PATH.read_text(encoding="utf-8"))


def registry_entries() -> list[dict[str, Any]]:
    entries = load_registry()["entries"]
    assert isinstance(entries, list)
    return entries


def agent_spec_from_entry(entry: dict[str, Any]) -> AgentSpec:
    path = Path(str(entry["source_file_path"]))
    file_path = str(path if path.is_absolute() else REPO_ROOT / path)
    return AgentSpec(
        name=str(entry["name"]),
        source_kind=AgentSourceKind(str(entry["source_kind"])),
        file_path=file_path,
        callable_name=str(entry["callable_name"]),
        metadata=(
            ("historical_public_score", str(entry["historical_public_score"])),
            ("historical_submission_ref", str(entry["historical_submission_ref"])),
            ("source_repo", str(entry["source_repo"])),
        ),
    )


class HistoricalChampionRegistryTests(unittest.TestCase):
    def test_registry_exists_and_is_deterministically_formatted(self) -> None:
        self.assertTrue(REGISTRY_PATH.is_file())

        payload = load_registry()
        expected_text = json.dumps(payload, sort_keys=True, indent=2) + "\n"

        self.assertEqual(REGISTRY_PATH.read_text(encoding="utf-8"), expected_text)
        self.assertEqual(payload["name"], "historical-champion-registry")
        self.assertEqual(payload["version"], "v0")

    def test_historical_opponent_manifest_exists_and_is_deterministic(self) -> None:
        self.assertTrue(OPPONENT_MANIFEST_PATH.is_file())

        payload = load_opponent_manifest()
        expected_text = json.dumps(payload, sort_keys=True, indent=2) + "\n"

        self.assertEqual(OPPONENT_MANIFEST_PATH.read_text(encoding="utf-8"), expected_text)
        self.assertEqual(payload["name"], "historical-opponents-manifest")
        self.assertEqual(payload["version"], "v0")
        self.assertEqual(
            tuple(entry["stable_opponent_id"] for entry in payload["entries"]),
            tuple(
                entry["name"]
                for entry in registry_entries()
                if entry["loadability_status"] == "loadable"
            ),
        )

    def test_entries_have_required_gauntlet_fields(self) -> None:
        required_fields = {
            "name",
            "source_repo",
            "source_file_path",
            "source_kind",
            "callable_name",
            "historical_submission_ref",
            "historical_public_score",
            "description",
            "intended_modes",
            "loadability_status",
            "skip_reason",
        }

        names: set[str] = set()
        for entry in registry_entries():
            with self.subTest(name=entry.get("name")):
                self.assertEqual(set(entry), required_fields)
                self.assertNotIn(entry["name"], names)
                names.add(entry["name"])
                self.assertEqual(entry["source_kind"], AgentSourceKind.PYTHON_FILE.value)
                self.assertEqual(entry["callable_name"], "agent")
                self.assertIn(entry["source_repo"], {"orbit-wars", "orbit-wars-2", "orbit-wars-claude"})
                self.assertIn(entry["loadability_status"], {"loadable", "skipped"})
                self.assertEqual(entry["intended_modes"], ["2p", "4p"])

    def test_loadable_entries_point_at_existing_historical_python_files(self) -> None:
        loadable_entries = [
            entry
            for entry in registry_entries()
            if entry["loadability_status"] == "loadable"
        ]

        self.assertGreaterEqual(len(loadable_entries), 8)
        for entry in loadable_entries:
            with self.subTest(name=entry["name"]):
                path = Path(str(entry["source_file_path"]))
                resolved_path = path if path.is_absolute() else REPO_ROOT / path

                self.assertFalse(path.is_absolute(), str(path))
                self.assertTrue(resolved_path.is_file(), str(resolved_path))
                self.assertTrue(resolved_path.is_relative_to(OPPONENT_AGENT_DIR))
                self.assertIsNone(entry["skip_reason"])

    def test_opponent_manifest_records_original_provenance_for_copied_files(self) -> None:
        manifest_entries = load_opponent_manifest()["entries"]
        by_name = {entry["stable_opponent_id"]: entry for entry in manifest_entries}

        for entry in registry_entries():
            if entry["loadability_status"] != "loadable":
                continue
            with self.subTest(name=entry["name"]):
                manifest_entry = by_name[entry["name"]]
                copied_path = OPPONENT_AGENT_DIR / manifest_entry["copied_filename"]

                self.assertTrue(copied_path.is_file())
                self.assertEqual(manifest_entry["callable_name"], "agent")
                self.assertEqual(manifest_entry["source_kind"], AgentSourceKind.PYTHON_FILE.value)
                self.assertIn(manifest_entry["source_repo"], {"orbit-wars-2", "orbit-wars-claude"})
                self.assertTrue(
                    any(Path(manifest_entry["origin_path"]).is_relative_to(root) for root in HISTORICAL_ROOTS),
                    manifest_entry["origin_path"],
                )

    def test_strong_historical_public_score_entries_are_registered(self) -> None:
        strong_entries = [
            entry
            for entry in registry_entries()
            if isinstance(entry["historical_public_score"], (int, float))
            and float(entry["historical_public_score"]) >= STRONG_SCORE_FLOOR
        ]

        self.assertGreaterEqual(len(strong_entries), 8)
        self.assertEqual(
            tuple(entry["name"] for entry in strong_entries[:8]),
            (
                "claude-v3-wide-search-forecast",
                "claude-v28-mode-split-champion",
                "claude-v37-race-fix-mode-split",
                "claude-v14-hammer-discipline",
                "claude-v8-leader-weighted-denial",
                "claude-v9-hold-aware-capture",
                "claude-v31-race-awareness",
                "claude-v62-low-pickoff-bundled",
            ),
        )

    def test_loadable_entries_load_as_callables_without_running_matches(self) -> None:
        for entry in registry_entries():
            if entry["loadability_status"] != "loadable":
                continue
            with self.subTest(name=entry["name"]):
                loaded_agent = load_agent_callable(agent_spec_from_entry(entry))

                self.assertTrue(callable(loaded_agent))

    def test_skipped_entries_are_explicitly_documented(self) -> None:
        skipped_entries = [
            entry
            for entry in registry_entries()
            if entry["loadability_status"] == "skipped"
        ]

        self.assertGreaterEqual(len(skipped_entries), 1)
        self.assertTrue(any(entry["source_repo"] == "orbit-wars" for entry in skipped_entries))
        for entry in skipped_entries:
            with self.subTest(name=entry["name"]):
                path = Path(str(entry["source_file_path"]))

                self.assertTrue(path.is_file(), str(path))
                self.assertIsInstance(entry["skip_reason"], str)
                self.assertIn("loader compatibility", entry["skip_reason"])


if __name__ == "__main__":
    unittest.main()
