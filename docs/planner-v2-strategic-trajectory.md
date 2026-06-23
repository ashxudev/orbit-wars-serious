# Planner V2 Strategic Trajectory Surface

This V2-only segment starts from the controlled-search diagnostic baseline in
commit `9dbecef Add planner V2 controlled search diagnostics`. The previous
diagnostic pass showed that most late collapse windows were `missing_plan`: by
the time V2 had to select one action, no evaluated one-turn plan mechanically
improved survival. This segment therefore moves earlier in the game and records
trajectory facts before collapse.

V2 remains opt-in through `agents.orbit_wars_agent_v2`. V1/default submission
behavior, runtime safety, simulator mechanics, action conversion, submission
bundling, Daytona, and Kaggle behavior are unchanged.

## Trajectory Fixtures

Fresh local full-500 V2 probes were run under `/tmp` to regenerate replay/result
artifacts:

| Probe | Report | Replay | Result |
|---|---|---|---|
| 2P Claude v31 race-awareness | `/tmp/ow-planner-v2-trajectory-local-2p-report.json` | `/tmp/ow-eval-artifacts/planner-v2-trajectory-local-2p-match-0000-replay.json` | `/tmp/ow-eval-artifacts/planner-v2-trajectory-local-2p-match-0000-result.json` |
| 4P top-score pool | `/tmp/ow-planner-v2-trajectory-local-4p-report.json` | `/tmp/ow-eval-artifacts/planner-v2-trajectory-local-4p-match-0000-replay.json` | `/tmp/ow-eval-artifacts/planner-v2-trajectory-local-4p-match-0000-result.json` |

Committed compact fixtures:

- `tests/fixtures/planner_v2_trajectory_losses/`

Fixture windows:

| Scenario | Turns | Player | Purpose |
|---|---:|---:|---|
| `historical-gauntlet-2p-500-seat-1-vs-claude-v31-race-awareness` | `0`, `5`, `10`, `15`, `20`, `30`, `40`, `54` | `1` | show the early production curve that leads to unrecoverable 2P collapse |
| `historical-gauntlet-4p-500-top-score-seat-3` | `0`, `5`, `10`, `15`, `20`, `30`, `40`, `60` | `3` | show why V2 stays single-source/low-production through the 4P opening |

Each fixture stores the single observation only, plus current V2 planner
diagnostics: owned planets, owned production, owned ships, neutral production
remaining, selected family/target class, selected scenario outcome summary,
action-set funnel counts, and trajectory labels/objectives.

## Trajectory Diagnosis

New V2 fact surface:

- `ow_planner_v2.trajectory.diagnose_trajectory(...)`

The report is JSON-safe and records:

- turn and trajectory phase;
- owned planet count, production, ships, and fleet ships;
- best/nearest productive neutral targets;
- whether a second production source is secured;
- single-source fragility;
- source-drain risk;
- expansion deficit;
- production gap to the leader;
- recommended trajectory objectives.

Objective labels include:

- `secure_second_source`
- `preserve_primary_source`
- `capture_nearest_productive_neutral`
- `delay_enemy_denial_until_base_secured`
- `hold_recent_capture`
- `deny_after_stabilizing`

The planner result now carries `trajectory_diagnosis`, and
`planner_v2_diagnostics(...)` exposes compact trajectory labels/objectives.

## Fixture Characterization

| Fixture group | Dominant labels |
|---|---|
| 2P turns `0`-`20` | `single_source_fragile`, `source_drained`, `late_denial_before_base`, then `under_expanded` |
| 2P turns `30`-`54` | `second_source_secured`, but still `source_drained` / `production_gap_to_leader` |
| 4P turns `0`-`15` | `single_source_fragile`, frequent `source_drained`, `late_denial_before_base` |
| 4P turns `20`-`60` | persistent `under_expanded`, `single_source_fragile`, production gap to leader |

This confirms the late `missing_plan` collapse is seeded earlier: V2 often
enters pressure windows without a stable second production base, or with a
drained source that cannot support follow-up defense.

## Implemented V2 Surface

The bounded V2 surface now adds `trajectory_second_source` neutral-capture
candidates when trajectory facts recommend securing a second source. The surface
is reserve-preserving:

- it only targets productive neutral planets;
- it requires enough ships to capture while keeping a source reserve;
- it flows through normal candidate evaluation, commitment, action-set
  construction, scenario evaluation, scoring, selection, and action conversion;
- it does not add a runtime fallback.

## Local Full-500 Gate

The same two local probes were rerun after adding trajectory facts/surfaces:

```text
.venv/bin/python scripts/run_evaluation_experiment.py /tmp/ow-v2-trajectory-2p.manifest.json --report-output /tmp/ow-planner-v2-trajectory-local-2p-report.json
.venv/bin/python scripts/run_evaluation_experiment.py /tmp/ow-v2-trajectory-4p.manifest.json --report-output /tmp/ow-planner-v2-trajectory-local-4p-report.json
```

| Probe | Previous baseline survival | Current survival | Final rank | No-action evidence |
|---|---:|---:|---:|---|
| 2P Claude v31 race-awareness | `160` | `89` | `2` | `strategy_selection_no_action:23`, `budget_guard_budget_exhausted:4`, `budget_guard_low_budget:4`, `no_owned_planets:3` |
| 4P top-score pool | `201` | `240` | `2` | `no_owned_planets:174`, `budget_guard_budget_exhausted:14`, `budget_guard_low_budget:10`, `strategy_selection_no_action:1` |

Interpretation:

- 4P survival improved materially, and the new trajectory fixtures show the
  intended early under-expansion/single-source pressure.
- 2P survival regressed, so this is not promotion-ready.
- Because local evidence is mixed, no Daytona probe was launched.
- The next V2 segment should isolate why the 2P trajectory surface worsens
  survival despite improving the mechanical second-source objective. The likely
  next question is whether the reserve-preserving neutral target still leaves
  timing/defense worse than the prior action, or whether the selected trajectory
  action creates a delayed source-drain race.

## Verification

Focused trajectory fixture check:

```text
.venv/bin/python -m unittest tests.test_planner_v2_trajectory_loss_fixtures
Ran 5 tests in 9.684s
OK
```

Final validation:

```text
.venv/bin/python -m unittest tests.test_planner_v2_trajectory_loss_fixtures tests.test_planner_v2_scenario_backed_loss_fixtures tests.test_planner_v2_scenario_selection_fixtures tests.test_planner_v2_scenario_eval tests.test_planner_v2_scoring tests.test_planner_v2_fallback tests.test_planner_v2_daytona_leak_fixtures tests.test_planner_v2_mission_surface_completeness tests.test_runtime_planner_pipeline
Ran 52 tests in 38.679s
OK

.venv/bin/python -m unittest discover -s tests
Ran 1506 tests in 297.582s
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

## Status

This segment produced source-controlled trajectory evidence and a bounded V2
trajectory surface, but it is not a promotion segment. V2 remains opt-in, and no
Daytona or Kaggle command was run.
