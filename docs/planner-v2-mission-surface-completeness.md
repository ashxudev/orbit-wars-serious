# Planner V2 Mission Surface Completeness

This segment uses the two real Daytona Planner V2 probe losses to close a
repeatable mission-surface gap. V2 remains opt-in. V1 default behavior,
runtime safety, simulator mechanics, action conversion, submission bundling,
and live-submission behavior are unchanged.

## Source Evidence

The only source evidence for this segment is the generated Daytona artifact set
from the pushed Planner V2 probe commit:

| Probe | Replay artifact | Result artifact |
|---|---|---|
| 2P `historical-gauntlet-2p-500-seat-1-vs-claude-v31-race-awareness` | `/tmp/ow-planner-v2-daytona-2p/planner-v2-2p-probe-0000.artifacts/planner-v2-2p-probe-0000-match-0000-replay.json` | `/tmp/ow-planner-v2-daytona-2p/planner-v2-2p-probe-0000.artifacts/planner-v2-2p-probe-0000-match-0000-result.json` |
| 4P `historical-gauntlet-4p-500-top-score-seat-3` | `/tmp/ow-planner-v2-daytona-4p/planner-v2-4p-probe-0000.artifacts/planner-v2-4p-probe-0000-match-0000-replay.json` | `/tmp/ow-planner-v2-daytona-4p/planner-v2-4p-probe-0000.artifacts/planner-v2-4p-probe-0000-match-0000-result.json` |

The probe losses were evidence-backed deterministic leaks. Both matches
completed without infrastructure errors, but V2 repeatedly returned no action
while owned production remained available. The compact fixture rerun showed the
same runtime failure in the target windows: `candidate_count=0` and
`runtime_diagnostic_no_action_reason=no_candidates_generated`.

This is a deterministic mission-surface leak, not an autoresearch/tuning
surface: V2 had no launch-backed mission to score in the failing windows. Score
weights cannot select a mission that was never generated.

## Compact Fixtures

The segment extracted compact single-observation fixtures under
`tests/fixtures/planner_v2_daytona_leaks/`.

| Fixture | Leak class | Baseline symptom | Current V2 result |
|---|---|---|---|
| `two_p_claude_v31_t060_p1.json` | 2P production collapse | zero candidates, no action | action emitted, `candidate_count=10`, `enemy_production_denial`, `reserve_preserving` |
| `two_p_claude_v31_t080_p1.json` | 2P production collapse | zero candidates, no action | action emitted, `candidate_count=9`, `enemy_production_denial`, `reserve_preserving` |
| `two_p_claude_v31_t098_p1.json` | 2P last-source collapse | zero candidates, no action | action emitted, `candidate_count=4`, `enemy_production_denial`, `reserve_preserving` |
| `two_p_enemy_denial_absent_t090_p1.json` | 2P strategic denial absence | action emitted but denial surface absent | action emitted, coordinated defense plus `enemy_production_denial` |
| `four_p_top_score_t150_p3.json` | 4P rank-pressure collapse | zero candidates, no action | action emitted, `candidate_count=6`, urgent defense plus leader pressure |
| `four_p_top_score_t176_p3.json` | 4P plateau collapse | zero candidates, no action | action emitted, `candidate_count=4`, `leader_pressure`, `reserve_preserving` |
| `four_p_top_score_t183_p3.json` | 4P last-source collapse | zero candidates, no action | action emitted, `candidate_count=4`, `enemy_production_denial`, `reserve_preserving` |
| `four_p_rank_pressure_absent_t120_p3.json` | 4P rank-pressure absence | action emitted but rank-pressure surface absent | action emitted, `leader_pressure`, `reserve_preserving` |

The tests intentionally assert the post-fix current V2 behavior, while the
fixture metadata retains the source replay/result paths and leak class.

## Implementation

Cycle 1-5 work is consolidated in this change:

- Added `ow_planner_v2.mission_surfaces.generate_surface_candidates(...)`.
- V2 runtime dispatch now appends bounded surface candidates before evaluation
  and commitment when `planner_version="v2"` is explicitly selected.
- Surface candidates cover the missing V2 families:
  - urgent owned-production defense;
  - recapture/hold-style conservative continuation through existing
    `CAPTURE_NEUTRAL` and `ATTACK_ENEMY` candidates;
  - enemy production denial;
  - 4P leader/rank pressure;
  - safe continuation when the legacy V1 candidate surface starves.
- The surface is bounded by `PlannerV2Config.max_surface_candidates`.
- Generated candidates use existing `MissionCandidate` and `LaunchCandidate`
  contracts, then pass through existing evaluation, commitment options,
  Planner V2 scoring/fallback, strategy selection, and runtime action
  conversion.

No runtime-only emergency fallback was added.

## Guardrails

The implementation is deliberately local to opt-in Planner V2:

- `RuntimePlannerConfig.planner_version` still defaults to `"v1"`.
- V1 candidate generation, V1 selection, simulator mechanics, action
  conversion, budget guards, evaluation gates, and submission bundling are not
  changed.
- V2 surface candidates are deterministic, bounded, and source/target-backed.
- The selected fixture actions use validated `reserve_preserving` commitments
  rather than unbounded full-source drains.
- Action mix remains guarded: owned-retention/transfer can participate when
  pressure exists, but the added surface also supplies productive enemy
  denial, leader pressure, and safe continuation options.

## Verification

Focused checks run during this segment:

```text
.venv/bin/python -m unittest tests.test_planner_v2_mission_surface_completeness tests.test_planner_v2_daytona_leak_fixtures
.venv/bin/python -m unittest tests.test_planner_v2_diagnosis tests.test_planner_v2_mission_generation tests.test_planner_v2_action_sets tests.test_planner_v2_scoring tests.test_planner_v2_fallback tests.test_runtime_planner_pipeline
.venv/bin/python -m unittest tests.test_v1_replay_leak_fixtures tests.test_v1_replay_regression tests.test_historical_gauntlet_leak_fixtures tests.test_historical_leak_regression tests.test_runtime_state_adapter tests.test_runtime_turn tests.test_runtime_actions
.venv/bin/python -m unittest discover -s tests
.venv/bin/python scripts/evaluation_gate.py
.venv/bin/python scripts/submission_preflight.py
git diff --check
```

All listed checks passed locally. Full discovery ran `1479` tests. The
evaluation gate reported `gate=PASS`, and submission preflight reported
`submission_preflight=PASS`.

## Remaining Promotion Work

Planner V2 is still not default. The two post-fix full-500 historical Daytona
probes were rerun from pushed commit `a4d7c85 Add planner v2 mission surface
recovery` using GitHub source mode.

| Probe | Package root | Real report | Match result | Replay |
|---|---|---|---|---|
| 2P `historical-gauntlet-2p-500-seat-1-vs-claude-v31-race-awareness` | `/tmp/ow-planner-v2-surface-daytona-2p/` | `/tmp/ow-planner-v2-surface-daytona-2p/daytona-real-report.json` | `/tmp/ow-planner-v2-surface-daytona-2p/package/planner-v2-surface-2p-probe-0000.artifacts/planner-v2-surface-2p-probe-0000-match-0000-result.json` | `/tmp/ow-planner-v2-surface-daytona-2p/package/planner-v2-surface-2p-probe-0000.artifacts/planner-v2-surface-2p-probe-0000-match-0000-replay.json` |
| 4P `historical-gauntlet-4p-500-top-score-seat-3` | `/tmp/ow-planner-v2-surface-daytona-4p/` | `/tmp/ow-planner-v2-surface-daytona-4p/daytona-real-report.json` | `/tmp/ow-planner-v2-surface-daytona-4p/package/planner-v2-surface-4p-probe-0000.artifacts/planner-v2-surface-4p-probe-0000-match-0000-result.json` | `/tmp/ow-planner-v2-surface-daytona-4p/package/planner-v2-surface-4p-probe-0000.artifacts/planner-v2-surface-4p-probe-0000-match-0000-replay.json` |

Both Daytona commands completed successfully:

- 2P: `jobs=1`, `operation_plans=1`, `exit_code=0`, shard
  `matches=1 completed=1 errors=0`.
- 4P: `jobs=1`, `operation_plans=1`, `exit_code=0`, shard
  `matches=1 completed=1 errors=0`.

The post-fix probes show infrastructure success and deterministic progress on
the no-action leak, but not promotion readiness.

| Metric | Old 2P V2 probe | Post-fix 2P probe | Old 4P V2 probe | Post-fix 4P probe |
|---|---:|---:|---:|---:|
| Final rank | `2` | `2` | `2` | `2` |
| Turns survived | `109` | `130` | `244` | `186` |
| Production collapse | `true` | `true` | `true` | `true` |
| First zero-owned turn | `99` | `54` | `184` | `80` |
| No-action count | `47` | `50` | `107` | `106` |
| No-action with owned production | `38` | `2` | `47` | `1` |
| Primary no-action reason | `no_candidates_generated` | `no_owned_planets` | `no_owned_planets` | `no_owned_planets` |
| Enemy-target actions | `5` | `63` | `22` | `80` |
| Neutral-target actions | `39` | `16` | `59` | `0` |
| Own-transfer actions | `20` | `0` | `56` | `0` |

Interpretation:

- The deterministic candidate-starvation/no-action-with-owned-production leak is
  largely closed in these full-horizon probes. The old 2P probe had `38`
  no-actions with owned production; the post-fix probe has `2`. The old 4P
  probe had `47`; the post-fix probe has `1`.
- The failure mode changed rather than disappeared. V2 now acts, but the action
  mix is too aggressive and one-dimensional: enemy-target actions dominate,
  neutral expansion disappears in 4P, and both probes still lose by production
  collapse.
- This is now a deterministic policy/search quality leak, not a runtime
  artifact, Daytona infrastructure, or Kaggle issue. The next fix should tune
  V2 mission-surface selection/search to prioritize safe expansion, hold, and
  source preservation before repeated enemy/leader pressure in fragile early
  positions.

Do not promote V2 yet. The next deterministic segment should extract compact
fixtures from the new post-fix Daytona artifacts around the early collapse
windows:

1. 2P `historical-gauntlet-2p-500-seat-1-vs-claude-v31-race-awareness`.
2. 4P `historical-gauntlet-4p-500-top-score-seat-3`.

Priority fixture targets:

- 2P: turns near `20`, `40`, `54`, and `60`, where the post-fix probe has only
  one owned planet and then loses all ownership despite continuous actions.
- 4P: turns near `20`, `40`, `60`, and `80`, where the post-fix probe remains on
  one low-production planet and then collapses.

Segment sentinel remains pending until the post-fix probes pass:
`PLANNER_V2_MISSION_SURFACE_COMPLETENESS_COMPLETE`.

## Scenario-Backed Selection Follow-Up

The follow-up scenario-selection work replaces V2's static mission-family
ordering with scenario-backed action-set scoring. V2 remains opt-in; V1,
runtime safety, simulator mechanics, action conversion, submission bundling,
and Kaggle/live-submission behavior remain unchanged.

### Source Artifacts And Fixtures

Compact fixtures were extracted from the post-surface Daytona replay artifacts:

- 2P source root: `/tmp/ow-planner-v2-surface-daytona-2p/`.
- 4P source root: `/tmp/ow-planner-v2-surface-daytona-4p/`.

New committed fixture directory:

- `tests/fixtures/planner_v2_scenario_selection/`.

Fixture windows:

| Case group | Turns | Player | Purpose |
|---|---:|---:|---|
| 2P `historical-gauntlet-2p-500-seat-1-vs-claude-v31-race-awareness` | `20`, `40`, `54`, `60` | `1` | one-planet pressure, source-drain, and early-collapse characterization |
| 4P `historical-gauntlet-4p-500-top-score-seat-3` | `20`, `40`, `60`, `80` | `3` | under-expansion, rank/leader pressure, and early-collapse characterization |

The fixtures are compact single-observation cases. They intentionally point to
the `/tmp` replay/result artifacts as provenance but do not commit full replays
or generated reports.

### Implementation Summary

- Added `ScenarioOutcome` and `ScenarioEvaluation` diagnostics to
  `ow_planner_v2.types`.
- Added `ow_planner_v2.scenario_eval.evaluate_action_set_scenarios(...)`.
- Scenario evaluation compares each action set against an idle baseline over
  configured horizons using existing `ow_sim` launch and rollout primitives.
- `ow_planner_v2.scoring.score_action_set_plans(...)` now uses scenario
  outcomes as the dominant score when evaluations are supplied.
- `ow_planner_v2.fallback.select_evaluated_plan(...)` skips invalid scenario
  plans, avoids simulated elimination when viable alternatives exist, and uses
  mission-family order only as a tight close-score tie breaker.
- 4P V2 surface generation now exposes neutral safe-continuation candidates
  before additional enemy-pressure candidates.
- Action-set construction now applies family-diverse pre-scenario pruning
  instead of first-prefix truncation when `max_action_sets` is bounded. The
  selected set prioritizes representative safe expansion, urgent defense,
  recapture/hold, enemy denial, and rank/leader-pressure families.
- The experimental `agents.orbit_wars_agent_v2` entrypoint now evaluates four
  diverse action sets by default. This fixes the prior reviewer blocker where
  the entrypoint used `PlannerV2Config(max_action_sets=1)`, which prevented
  scenario-backed scoring from comparing alternatives. The normal V1 submission
  entrypoint is unchanged.

### Fixture Before/After Characterization

Under bounded V2 runtime configuration, the scenario-selection fixtures now
select safe neutral expansion where it scores above enemy or leader pressure:

| Fixture | Failure class | Current selected family | Target class | Runtime result |
|---|---|---|---|---|
| `two_p_scenario_selection_t020_p1.json` | `over_aggressive_enemy_pressure` | `safe_expand` | neutral | action emitted |
| `two_p_scenario_selection_t040_p1.json` | `over_aggressive_enemy_pressure` | `safe_expand` | neutral | action emitted |
| `two_p_scenario_selection_t054_p1.json` | `early_collapse` | none | none | no owned planets |
| `two_p_scenario_selection_t060_p1.json` | `early_collapse` | `safe_expand` | neutral | action emitted |
| `four_p_scenario_selection_t020_p3.json` | `under_expansion` | `safe_expand` | neutral | action emitted |
| `four_p_scenario_selection_t040_p3.json` | `under_expansion` | `safe_expand` | neutral | action emitted |
| `four_p_scenario_selection_t060_p3.json` | `under_expansion` | `safe_expand` | neutral | action emitted |
| `four_p_scenario_selection_t080_p3.json` | `early_collapse` | none | none | no owned planets |

The new diagnostics include selected horizon, scenario notes, production delta,
planet delta, opponent-production delta, source-lost ids, vulnerable-lost ids,
and elimination flags.

### Local Full-500 Probe Result

The two one-scenario local full-500 probes were rerun with V2 enabled:

```text
.venv/bin/python scripts/run_evaluation_experiment.py /tmp/ow-planner-v2-surface-daytona-2p/planner-v2-surface-2p-probe.manifest.source.json --report-output /tmp/ow-planner-v2-scenario-backed-local-2p-report.json
.venv/bin/python scripts/run_evaluation_experiment.py /tmp/ow-planner-v2-surface-daytona-4p/planner-v2-surface-4p-probe.manifest.source.json --report-output /tmp/ow-planner-v2-scenario-backed-local-4p-report.json
```

Both commands completed the single scheduled match and wrote reports under
`/tmp`, but the experiment CLI returned nonzero because the original probe
manifests still contain multi-scenario promotion thresholds.

| Probe | Completed | Errors | Final rank | Turns survived | Final production | No-action count | Primary no-action evidence |
|---|---:|---:|---:|---:|---:|---:|---|
| 2P Claude v31 race-awareness | `1/1` | `0` | `2` | `160` | `0` | `87` | `no_owned_planets:75`, `strategy_selection_no_action:6`, `budget_guard_low_budget:4`, `budget_guard_budget_exhausted:1` |
| 4P top-score pool | `1/1` | `0` | `2` | `201` | `0` | `156` | `no_owned_planets:135`, `budget_guard_budget_exhausted:15`, `strategy_selection_no_action:4`, `budget_guard_low_budget:1` |

Compared with the last post-surface Daytona probes, this scenario-backed
selection pass shows partial improvement but does not yet earn promotion
evidence:

- Compared with the earlier local scenario-backed run that still used the
  one-action-set bottleneck, 2P survival improved from `106` to `160` turns and
  4P survival improved from `185` to `201` turns.
- Compared with the last post-surface Daytona probes, 2P survival improved
  from `130` to `160` turns and 4P survival improved from `186` to `201` turns.
- Both probes still lose by production collapse.
- Strategy-selection no-action remains visible in both full-horizon probes.
- 4P still has budget-heavy windows under full-horizon pressure.
- The local results support the architecture and reviewer fix, but they do not
  yet justify a real Daytona rerun or V2 promotion.

Because the local full-500 gate still ends in production collapse, no real
Daytona rerun was launched for this cycle.

### Verification

Focused checks run for this scenario-backed selection pass:

```text
.venv/bin/python -m unittest tests.test_planner_v2_scenario_selection_fixtures tests.test_planner_v2_scenario_eval tests.test_planner_v2_scoring tests.test_planner_v2_fallback
.venv/bin/python -m unittest tests.test_planner_v2_daytona_leak_fixtures tests.test_planner_v2_mission_surface_completeness tests.test_runtime_planner_pipeline tests.test_runtime_agent_entrypoint tests.test_planner_v2_action_sets
.venv/bin/python -m unittest tests.test_runtime_state_adapter tests.test_runtime_turn tests.test_runtime_actions tests.test_planner_v2_diagnosis tests.test_planner_v2_mission_generation
```

These focused checks passed locally. Final validation for this change also
passed:

```text
.venv/bin/python -m unittest discover -s tests
Ran 1496 tests in 262.936s
OK

.venv/bin/python scripts/evaluation_gate.py
gate=PASS matches=2 win_rate=1 mean_rank=1 error_rate=0 parity=pass failures=0

.venv/bin/python scripts/submission_preflight.py --quiet-progress
submission_preflight=PASS total=3 passed=3 failed=0 failed_checks=none exit_code=0

git diff --check
PASS
```

### Status

The scenario-backed selector improves compact fixture choices, but the local
full-500 probes show that V2 is still not promotion-ready. The completion
sentinel is therefore not emitted:

`PLANNER_V2_SCENARIO_BACKED_SELECTION_COMPLETE` remains pending.

## Controlled Search Diagnosis Follow-Up

The next pass added minimal V2 funnel diagnostics so collapse windows can be
classified before adding another heuristic. The diagnostics now expose:

- mission family counts;
- pre-cap single action-set count;
- kept action-set count;
- pruned action-set count and prune reason counts;
- selected plan score components, fallback rank, and scenario outcome summary.

### Latest Local Fixture Set

The fixture source is the latest local full-500 probe artifacts, not the older
Daytona artifacts:

| Probe | Report | Replay |
|---|---|---|
| 2P Claude v31 race-awareness | `/tmp/ow-planner-v2-scenario-backed-local-2p-report.json` | `/tmp/ow-eval-artifacts/planner-v2-surface-2p-probe-match-0000-replay.json` |
| 4P top-score pool | `/tmp/ow-planner-v2-scenario-backed-local-4p-report.json` | `/tmp/ow-eval-artifacts/planner-v2-surface-4p-probe-match-0000-replay.json` |

New compact fixtures:

- `tests/fixtures/planner_v2_scenario_backed_losses/`.

The fixtures run two diagnostic configurations:

- baseline runtime-like V2: `max_action_sets=4`, horizons `(10, 25, 50)`;
- offline diagnostic V2: `max_action_sets=16`, horizons `(10, 25, 50, 80)`.

Each fixture is mechanically classified using scenario outcomes. A
survival-improving plan must avoid elimination, retain owned production, match
or improve worst-horizon production, avoid source/vulnerable planet loss, and
beat the selected plan's worst-horizon scenario score.

| Fixture | Bucket | Evidence |
|---|---|---|
| `two_p_scenario_backed_loss_t020_p1.json` | `missing_plan` | no survival-improving offline plan |
| `two_p_scenario_backed_loss_t040_p1.json` | `missing_plan` | no survival-improving offline plan |
| `two_p_scenario_backed_loss_t054_p1.json` | `missing_plan` | no survival-improving offline plan |
| `two_p_scenario_backed_loss_t060_p1.json` | `missing_plan` | no survival-improving offline plan |
| `four_p_scenario_backed_loss_t020_p3.json` | `scored_wrong` | survival-improving plans evaluated offline but baseline selection chooses a worse safe expansion |
| `four_p_scenario_backed_loss_t040_p3.json` | `scored_wrong` | survival-improving plans evaluated offline but baseline selection chooses a worse safe expansion |
| `four_p_scenario_backed_loss_t060_p3.json` | `missing_plan` | no survival-improving offline plan |
| `four_p_scenario_backed_loss_t080_p3.json` | `source_less_terminal` | no owned planets remain |

Dominant diagnosis: `missing_plan` (`5/8` fixtures). The actionable scored-wrong
subset is smaller (`2/8`) and depends on a longer horizon that does not fit
comfortably into the normal one-second runtime when combined with a wider
action-set cap. Because no mechanical survival-improving single-turn plan exists
for the dominant missing-plan cases, this pass did not add a speculative
mission-surface heuristic.

### Rejected Wider-Search Experiment

One narrow search-width experiment was tested locally: `max_action_sets=8` with
single-horizon `(10,)`. It fit the runtime budget, but the full-500 probes got
worse:

| Probe | Baseline survival | Wider-search survival | Result |
|---|---:|---:|---|
| 2P Claude v31 race-awareness | `160` | `128` | regression |
| 4P top-score pool | `201` | `178` | regression |

The runtime-facing V2 cap therefore remains `max_action_sets=4`; the wider
short-horizon run is retained only as diagnostic evidence in the compact
fixtures.

### Diagnostic Segment Verification

The diagnostic segment was stabilized without adding a behavior fix. The V2
Daytona leak fixture characterization test now disables wall-clock runtime
budgeting for committed fixture assertions so full-suite machine load does not
turn a planner-output characterization into a budget-guard assertion.

Current verification results:

```text
.venv/bin/python -m unittest tests.test_planner_v2_scenario_backed_loss_fixtures
Ran 5 tests in 10.354s
OK

.venv/bin/python -m unittest discover -s tests
Ran 1501 tests in 280.974s
OK

.venv/bin/python scripts/evaluation_gate.py
gate=PASS matches=2 win_rate=1 mean_rank=1 error_rate=0 parity=pass failures=0

.venv/bin/python scripts/submission_preflight.py --quiet-progress
submission_preflight=PASS total=3 passed=3 failed=0 failed_checks=none exit_code=0
preflight_check=submission_build status=PASS exit_code=0
preflight_check=submission_parity status=PASS mismatches=0 exit_code=0
preflight_check=regression_gate status=PASS failures=0 exit_code=0

git diff --check
PASS
```

### Next Fix Target

Do not run Daytona from this state. The next deterministic segment should
target the dominant `missing_plan` class by designing and proving new mission
surfaces that create an actually survival-improving plan under the mechanical
definition above. If that still fails, the right next level is strategic
trajectory evaluation rather than more local collapse-window scoring.

`PLANNER_V2_SCENARIO_BACKED_SELECTION_COMPLETE` remains pending.
