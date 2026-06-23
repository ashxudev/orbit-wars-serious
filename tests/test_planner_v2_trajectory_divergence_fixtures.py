"""Planner V2 trajectory A/B divergence fixtures from Daytona artifacts."""

from __future__ import annotations

import json
import unittest
from pathlib import Path

from agents.runtime_actions import planner_result_to_actions
from agents.runtime_planner import (
    PLANNER_VERSION_V2,
    RuntimePlannerConfig,
    run_planner_pipeline,
)
from agents.runtime_state import observation_to_game_state
from ow_planner import CandidateGenerationConfig
from ow_planner_v2 import PlannerV2Config
from ow_planner_v2.diagnostics import planner_v2_diagnostics


FIXTURE_DIR = (
    Path(__file__).resolve().parent
    / "fixtures"
    / "planner_v2_trajectory_divergences"
)

EXPECTED_CASE_COUNT = 32

SEVERE_REGRESSION_CASES = {
    "four_p_ow2_smoke_on_t116_p0",
    "four_p_ow2_smoke_on_t122_p0",
    "four_p_ow2_smoke_on_t150_p0",
    "four_p_ow2_smoke_on_t160_p0",
    "four_p_ow2_smoke_on_t176_p0",
}

IMPROVEMENT_CASES = {
    "four_p_mixed_on_t077_p2",
    "four_p_mixed_on_t091_p2",
    "four_p_mixed_on_t134_p2",
    "two_p_v9_on_t060_p1",
    "two_p_v9_on_t076_p1",
}


def fixture_paths() -> tuple[Path, ...]:
    return tuple(sorted(FIXTURE_DIR.glob("*.json")))


def load_case(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def selected_target_class(state: object, selected: object | None) -> str | None:
    if selected is None or not selected.plan.missions:
        return None
    target_id = selected.plan.missions[0].target_planet_id
    if target_id is None:
        return None
    owner = next(
        (
            planet.owner
            for planet in state.planets
            if planet.planet_id == target_id
        ),
        None,
    )
    if owner is None:
        return "missing"
    if owner == state.player_id:
        return "owned"
    if owner < 0:
        return "neutral"
    return "enemy"


def run_v2(observation: object, *, trajectory_enabled: bool) -> dict[str, object]:
    if not isinstance(observation, dict):
        raise AssertionError("observation must be a dictionary")
    state = observation_to_game_state(observation)
    result = run_planner_pipeline(
        state,
        RuntimePlannerConfig(
            planner_version=PLANNER_VERSION_V2,
            candidate_config=CandidateGenerationConfig(
                max_candidates=8,
                max_validation_attempts=8,
            ),
            planner_v2_config=PlannerV2Config(
                max_action_sets=4,
                enable_trajectory_second_source=trajectory_enabled,
            ),
        ),
    )
    if result.v2_result is None:
        raise AssertionError("planner v2 result missing")
    v2_result = result.v2_result
    diagnostics = planner_v2_diagnostics(v2_result)
    owned = tuple(
        planet for planet in state.planets if planet.owner == state.player_id
    )
    selected = v2_result.selected_plan
    return {
        "action_count": len(planner_result_to_actions(result)),
        "actions": planner_result_to_actions(result),
        "candidate_count": diagnostics.get("planner_v2_candidate_count"),
        "kept_action_set_count": diagnostics.get("planner_v2_kept_action_set_count"),
        "mission_family_counts": diagnostics.get("planner_v2_mission_family_counts"),
        "no_action_reason": v2_result.no_action_reason or "actions_emitted",
        "owned_planet_count": len(owned),
        "owned_production": sum(planet.production for planet in owned),
        "owned_ships": sum(planet.ships for planet in owned),
        "pre_cap_action_set_count": diagnostics.get(
            "planner_v2_pre_cap_action_set_count"
        ),
        "prune_reason_counts": diagnostics.get("planner_v2_prune_reason_counts"),
        "pruned_action_set_count": diagnostics.get(
            "planner_v2_pruned_action_set_count"
        ),
        "selected_family": diagnostics.get("planner_v2_selected_family"),
        "selected_target_class": selected_target_class(state, selected),
        "trajectory": diagnostics.get("planner_v2_trajectory"),
    }


def compact_expected(expected: dict[str, object]) -> dict[str, object]:
    return {
        key: expected[key]
        for key in (
            "action_count",
            "actions",
            "candidate_count",
            "kept_action_set_count",
            "mission_family_counts",
            "no_action_reason",
            "owned_planet_count",
            "owned_production",
            "owned_ships",
            "pre_cap_action_set_count",
            "prune_reason_counts",
            "pruned_action_set_count",
            "selected_family",
            "selected_target_class",
            "trajectory",
        )
    }


class PlannerV2TrajectoryDivergenceFixtureTests(unittest.TestCase):
    def test_fixture_set_exists_and_is_compact(self) -> None:
        paths = fixture_paths()

        self.assertEqual(len(paths), EXPECTED_CASE_COUNT)
        for path in paths:
            with self.subTest(path=path.name):
                payload = load_case(path)
                self.assertIn("observation", payload)
                self.assertNotIn("steps", payload)
                self.assertNotIn("steps", payload["observation"])
                self.assertTrue(str(payload["source_replay_path"]).startswith("/tmp/"))
                self.assertTrue(str(payload["source_result_path"]).startswith("/tmp/"))
                self.assertIn(payload["cell"], {"2p-off", "2p-on", "4p-off", "4p-on"})

    def test_expected_runtime_diagnostics_match_current_v2(self) -> None:
        for path in fixture_paths():
            payload = load_case(path)
            with self.subTest(case=payload["case_id"]):
                off = run_v2(payload["observation"], trajectory_enabled=False)
                on = run_v2(payload["observation"], trajectory_enabled=True)

                self.assertEqual(
                    off,
                    compact_expected(payload["expected_runtime_trajectory_off"]),
                )
                self.assertEqual(
                    on,
                    compact_expected(payload["expected_runtime_trajectory_on"]),
                )

    def test_fixture_set_covers_regression_and_improvement_windows(self) -> None:
        case_ids = {load_case(path)["case_id"] for path in fixture_paths()}

        self.assertTrue(SEVERE_REGRESSION_CASES <= case_ids)
        self.assertTrue(IMPROVEMENT_CASES <= case_ids)

    def test_severe_ow2_regression_fixture_records_terminal_contrast(self) -> None:
        off = load_case(FIXTURE_DIR / "four_p_ow2_smoke_off_t176_p0.json")
        on = load_case(FIXTURE_DIR / "four_p_ow2_smoke_on_t176_p0.json")

        self.assertEqual(off["match_survived_turns"], 500)
        self.assertIsNone(off["match_first_zero_owned_turn"])
        self.assertEqual(on["match_survived_turns"], 184)
        self.assertEqual(on["match_first_zero_owned_turn"], 176)
        self.assertGreater(
            off["expected_runtime_trajectory_off"]["owned_production"],
            on["expected_runtime_trajectory_on"]["owned_production"],
        )

    def test_base_security_guard_delays_rank_pressure_in_severe_regression(self) -> None:
        payload = load_case(FIXTURE_DIR / "four_p_ow2_smoke_on_t150_p0.json")
        selected = payload["expected_runtime_trajectory_on"]

        self.assertIn(
            "delay_enemy_denial_until_base_secured",
            selected["trajectory"]["recommended_objectives"],
        )
        self.assertEqual(selected["selected_family"], "safe_expand")
        self.assertEqual(selected["selected_target_class"], "neutral")
        self.assertNotEqual(selected["selected_family"], "rank_swing")

    def test_mixed_style_improvement_fixture_records_delayed_collapse(self) -> None:
        off = load_case(FIXTURE_DIR / "four_p_mixed_off_t134_p2.json")
        on = load_case(FIXTURE_DIR / "four_p_mixed_on_t134_p2.json")

        self.assertEqual(off["match_survived_turns"], 163)
        self.assertEqual(on["match_survived_turns"], 213)
        self.assertLess(
            off["match_first_zero_owned_turn"],
            on["match_first_zero_owned_turn"],
        )


if __name__ == "__main__":
    unittest.main()
