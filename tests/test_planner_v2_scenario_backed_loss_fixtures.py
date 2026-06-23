"""Scenario-backed V2 loss fixtures from latest local full-500 probes."""

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
from ow_planner_v2 import EvaluatedPlan, PlannerV2Config
from ow_planner_v2.diagnostics import planner_v2_diagnostics


FIXTURE_DIR = (
    Path(__file__).resolve().parent
    / "fixtures"
    / "planner_v2_scenario_backed_losses"
)

REQUIRED_CASE_IDS = {
    "two_p_scenario_backed_loss_t020_p1",
    "two_p_scenario_backed_loss_t040_p1",
    "two_p_scenario_backed_loss_t054_p1",
    "two_p_scenario_backed_loss_t060_p1",
    "four_p_scenario_backed_loss_t020_p3",
    "four_p_scenario_backed_loss_t040_p3",
    "four_p_scenario_backed_loss_t060_p3",
    "four_p_scenario_backed_loss_t080_p3",
}

CLASSIFICATION_BUCKETS = {
    "missing_plan",
    "pruned_plan",
    "scored_wrong",
    "runtime_budget_bound",
    "source_less_terminal",
}


def fixture_paths() -> tuple[Path, ...]:
    return tuple(sorted(FIXTURE_DIR.glob("*.json")))


def load_case(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def run_v2(observation: object, config: PlannerV2Config) -> dict[str, object]:
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
            planner_v2_config=config,
        ),
    )
    if result.v2_result is None:
        raise AssertionError("planner v2 result missing")
    actions = planner_result_to_actions(result)
    diagnostics = planner_v2_diagnostics(result.v2_result)
    owned = tuple(
        planet for planet in state.planets if planet.owner == state.player_id
    )
    return {
        "actions": actions,
        "diagnostics": diagnostics,
        "owned": owned,
        "result": result.v2_result,
        "state": state,
    }


def target_class(state: object, plan: EvaluatedPlan | None) -> str | None:
    if plan is None or not plan.plan.missions:
        return None
    target_id = plan.plan.missions[0].target_planet_id
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


def worst_outcome(plan: EvaluatedPlan | None) -> dict[str, object] | None:
    if plan is None or plan.scenario_evaluation is None:
        return None
    outcomes = tuple(
        outcome for outcome in plan.scenario_evaluation.outcomes if outcome.valid
    )
    if not outcomes:
        return None
    return {
        "eliminated": any(outcome.eliminated for outcome in outcomes),
        "own_production": min(outcome.own_production for outcome in outcomes),
        "score": min(outcome.score for outcome in outcomes),
        "source_loss": any(outcome.source_planet_lost_ids for outcome in outcomes),
        "vulnerable_loss": any(
            outcome.vulnerable_planet_lost_ids for outcome in outcomes
        ),
    }


def survival_improving_plan(
    plan: EvaluatedPlan,
    baseline: EvaluatedPlan | None,
) -> bool:
    candidate = worst_outcome(plan)
    base = worst_outcome(baseline)
    if candidate is None or base is None:
        return False
    return (
        not bool(candidate["eliminated"])
        and int(candidate["own_production"]) > 0
        and int(candidate["own_production"]) >= int(base["own_production"])
        and not bool(candidate["source_loss"])
        and not bool(candidate["vulnerable_loss"])
        and float(candidate["score"]) > float(base["score"])
    )


def classify_fixture(
    state: object,
    baseline_result: object,
    offline_result: object,
) -> tuple[str, tuple[str, ...]]:
    owned = tuple(
        planet for planet in state.planets if planet.owner == state.player_id
    )
    if not owned:
        return "source_less_terminal", ()

    runtime_selected = baseline_result.selected_plan
    runtime_selected_id = (
        None if runtime_selected is None else runtime_selected.plan.plan_id
    )
    offline_by_id = {
        plan.plan.plan_id: plan for plan in offline_result.evaluated_plans
    }
    baseline = (
        offline_by_id.get(runtime_selected_id)
        if runtime_selected_id is not None
        else None
    )
    if baseline is None:
        baseline = runtime_selected
    if baseline is None:
        return "missing_plan", ()

    survival_plans = tuple(
        plan
        for plan in offline_result.evaluated_plans
        if survival_improving_plan(plan, baseline)
    )
    if not survival_plans:
        return "missing_plan", ()

    survival_ids = tuple(plan.plan.plan_id for plan in survival_plans)
    runtime_evaluated_ids = {
        plan.plan.plan_id for plan in baseline_result.evaluated_plans
    }
    if not any(plan_id in runtime_evaluated_ids for plan_id in survival_ids):
        return "pruned_plan", survival_ids
    if runtime_selected_id not in survival_ids:
        return "scored_wrong", survival_ids
    return "missing_plan", survival_ids


def summarize(run: dict[str, object]) -> dict[str, object]:
    result = run["result"]
    state = run["state"]
    diagnostics = run["diagnostics"]
    actions = run["actions"]
    owned = run["owned"]
    selected = result.selected_plan
    report = result.funnel_diagnostics.action_set_report
    evaluated_action_sets = tuple(plan.plan for plan in result.evaluated_plans)
    family_presence = _family_presence(
        pre_cap=report.single_action_sets,
        kept=report.kept_action_sets,
        evaluated=evaluated_action_sets,
    )
    return {
        "action_count": len(actions),
        "kept_action_set_count": len(report.kept_action_sets),
        "mission_family_counts": diagnostics["planner_v2_mission_family_counts"],
        "no_action_reason": result.no_action_reason or "actions_emitted",
        "owned_planet_count": len(owned),
        "owned_production": sum(planet.production for planet in owned),
        "pre_cap_action_set_count": len(report.single_action_sets),
        "pruned_action_set_count": len(report.pruned_action_sets),
        "prune_reason_counts": diagnostics["planner_v2_prune_reason_counts"],
        "selected_family": (
            None
            if selected is None or not selected.plan.missions
            else selected.plan.missions[0].family.value
        ),
        "selected_plan_id": None if selected is None else selected.plan.plan_id,
        "selected_target_class": target_class(state, selected),
        "selected_worst_outcome": worst_outcome(selected),
        **family_presence,
    }


def _family_presence(
    *,
    pre_cap: tuple[object, ...],
    kept: tuple[object, ...],
    evaluated: tuple[object, ...],
) -> dict[str, bool]:
    groups = {
        "safe_expand": {"safe_expand"},
        "urgent_defend": {"urgent_defend"},
        "hold_or_recapture": {"hold_capture", "recapture"},
        "denial": {"enemy_production_denial"},
    }
    result: dict[str, bool] = {}
    for name, family_names in groups.items():
        result[f"{name}_pre_cap"] = _has_family(pre_cap, family_names)
        result[f"{name}_kept"] = _has_family(kept, family_names)
        result[f"{name}_evaluated"] = _has_family(evaluated, family_names)
    for label, plans in (
        ("pre_cap", pre_cap),
        ("kept", kept),
        ("evaluated", evaluated),
    ):
        result[f"defend_expand_combo_{label}"] = any(
            {"urgent_defend", "safe_expand"}.issubset(
                {mission.family.value for mission in plan.missions}
            )
            for plan in plans
        )
    return result


def _has_family(plans: tuple[object, ...], family_names: set[str]) -> bool:
    return any(
        plan.missions and plan.missions[0].family.value in family_names
        for plan in plans
    )


class PlannerV2ScenarioBackedLossFixtureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.results = {}
        for path in fixture_paths():
            payload = load_case(path)
            observation = payload["observation"]
            cls.results[payload["case_id"]] = {
                "baseline": run_v2(
                    observation,
                    PlannerV2Config(max_action_sets=4),
                ),
                "offline": run_v2(
                    observation,
                    PlannerV2Config(max_action_sets=16, horizons=(10, 25, 50, 80)),
                ),
                "wider_short_horizon": run_v2(
                    observation,
                    PlannerV2Config(max_action_sets=8, horizons=(10,)),
                ),
            }

    def test_fixture_set_exists_and_is_compact(self) -> None:
        paths = fixture_paths()

        self.assertEqual(len(paths), 8)
        self.assertEqual(
            {load_case(path)["case_id"] for path in paths},
            REQUIRED_CASE_IDS,
        )
        for path in paths:
            with self.subTest(path=path.name):
                payload = load_case(path)
                self.assertNotIn("steps", payload)
                self.assertIn("observation", payload)
                self.assertNotIn("steps", payload["observation"])
                self.assertIn(payload["classification_bucket"], CLASSIFICATION_BUCKETS)
                self.assertIn(payload["player_count"], (2, 4))
                self.assertTrue(str(payload["source_replay_path"]).startswith("/tmp/"))
                self.assertTrue(str(payload["source_result_path"]).startswith("/tmp/"))

    def test_expected_diagnostics_match_runtime_and_offline_configs(self) -> None:
        for path in fixture_paths():
            payload = load_case(path)
            case_id = payload["case_id"]
            with self.subTest(case=case_id):
                baseline = summarize(self.results[case_id]["baseline"])
                offline = summarize(self.results[case_id]["offline"])
                wider_short_horizon = summarize(
                    self.results[case_id]["wider_short_horizon"]
                )

                self.assertEqual(baseline, payload["expected_baseline_runtime"])
                self.assertEqual(offline, payload["expected_offline_diagnostic"])
                self.assertEqual(
                    wider_short_horizon,
                    payload["expected_wider_short_horizon_diagnostic"],
                )

    def test_mechanical_classification_matches_fixture_bucket(self) -> None:
        for path in fixture_paths():
            payload = load_case(path)
            case_id = payload["case_id"]
            with self.subTest(case=case_id):
                state = self.results[case_id]["baseline"]["state"]
                baseline = self.results[case_id]["baseline"]["result"]
                offline = self.results[case_id]["offline"]["result"]

                bucket, survival_ids = classify_fixture(state, baseline, offline)

                self.assertEqual(bucket, payload["classification_bucket"])
                self.assertEqual(
                    list(survival_ids),
                    payload["survival_improving_offline_plan_ids"],
                )

    def test_bucket_distribution_documents_dominant_remaining_surface_gap(self) -> None:
        counts: dict[str, int] = {}
        for path in fixture_paths():
            bucket = str(load_case(path)["classification_bucket"])
            counts[bucket] = counts.get(bucket, 0) + 1

        self.assertEqual(counts.get("missing_plan"), 5)
        self.assertEqual(counts.get("scored_wrong"), 2)
        self.assertEqual(counts.get("source_less_terminal"), 1)

    def test_wider_short_horizon_diagnostic_keeps_at_least_runtime_width(self) -> None:
        for path in fixture_paths():
            payload = load_case(path)
            if payload["classification_bucket"] == "source_less_terminal":
                continue
            with self.subTest(case=payload["case_id"]):
                baseline = payload["expected_baseline_runtime"]
                wider_short_horizon = payload[
                    "expected_wider_short_horizon_diagnostic"
                ]

                self.assertGreaterEqual(
                    wider_short_horizon["kept_action_set_count"],
                    baseline["kept_action_set_count"],
                )


if __name__ == "__main__":
    unittest.main()
