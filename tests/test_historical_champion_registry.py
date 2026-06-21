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
HISTORICAL_ROOTS = (
    Path("/Users/user/dev/hackathons/orbit-wars"),
    Path("/Users/user/dev/hackathons/orbit-wars-2"),
    Path("/Users/user/dev/hackathons/orbit-wars-claude"),
)
STRONG_SCORE_FLOOR = 800.0


def load_registry() -> dict[str, Any]:
    return json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))


def registry_entries() -> list[dict[str, Any]]:
    entries = load_registry()["entries"]
    assert isinstance(entries, list)
    return entries


def agent_spec_from_entry(entry: dict[str, Any]) -> AgentSpec:
    return AgentSpec(
        name=str(entry["name"]),
        source_kind=AgentSourceKind(str(entry["source_kind"])),
        file_path=str(entry["source_file_path"]),
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

                self.assertTrue(path.is_file(), str(path))
                self.assertTrue(
                    any(path.is_relative_to(root) for root in HISTORICAL_ROOTS),
                    str(path),
                )
                self.assertIsNone(entry["skip_reason"])

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
