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

## Daytona A/B Matrix

Cycle: Planner V2 Trajectory Daytona A/B.

Tested commit:

```text
833be58 Add Planner V2 trajectory A/B tooling
```

The A/B run compared matched historical pressure scenarios with only the
`trajectory_second_source` behavior surface toggled. Planner V2 remained
opt-in. V1/default submission behavior was unchanged.

Source-controlled support added for the matrix:

- `PlannerV2Config.enable_trajectory_second_source`, default `True`.
- `agents.orbit_wars_agent_v2_trajectory_off`, which disables only
  `trajectory_second_source` candidate creation while keeping trajectory
  diagnostics and scenario evaluation enabled.
- `scripts/prepare_v2_trajectory_ab_daytona_package.py`.
- `scripts/analyze_v2_trajectory_ab_daytona.py`.

Package and result roots:

```text
/tmp/ow-v2-trajectory-ab-daytona/
/tmp/ow-v2-trajectory-ab-daytona/daytona-real-report.json
/tmp/ow-v2-trajectory-ab-daytona/v2-trajectory-ab-summary.json
```

Commands used:

```text
.venv/bin/python scripts/prepare_v2_trajectory_ab_daytona_package.py --output-root /tmp/ow-v2-trajectory-ab-daytona
.venv/bin/python scripts/prepare_daytona_shard_jobs.py /tmp/ow-v2-trajectory-ab-daytona/package/shard-jobs.index.json --output-path /tmp/ow-v2-trajectory-ab-daytona/daytona-shard-jobs.json --working-dir /workspace/orbit-wars-serious --sandbox-name-prefix ow-v2-trajectory-ab
.venv/bin/python scripts/validate_daytona_shard_jobs.py /tmp/ow-v2-trajectory-ab-daytona/daytona-shard-jobs.json
.venv/bin/python scripts/run_daytona_shard_jobs.py /tmp/ow-v2-trajectory-ab-daytona/daytona-shard-jobs.json --dry-run --json-output /tmp/ow-v2-trajectory-ab-daytona/daytona-dry-run-result.json
.venv/bin/python scripts/run_daytona_real_smoke.py --allow-real-daytona --json-output /tmp/ow-v2-trajectory-ab-daytona/daytona-smoke.json
.venv/bin/python scripts/run_daytona_real_shard_jobs.py /tmp/ow-v2-trajectory-ab-daytona/daytona-shard-jobs.json --allow-real-daytona --json-output /tmp/ow-v2-trajectory-ab-daytona/daytona-real-report.json
.venv/bin/python scripts/analyze_v2_trajectory_ab_daytona.py --root /tmp/ow-v2-trajectory-ab-daytona --output-json /tmp/ow-v2-trajectory-ab-daytona/v2-trajectory-ab-summary.json
```

Daytona execution summary:

```text
daytona_real_cli=COMPLETE plan_path=/tmp/ow-v2-trajectory-ab-daytona/daytona-shard-jobs.json allow_real_daytona=True events=96 operation_plans=4 exit_code=0
daytona_client_execution_report=COMPLETE plan_path=/tmp/ow-v2-trajectory-ab-daytona/daytona-shard-jobs.json jobs=4 events=96 operation_plans=4 exit_code=0
```

Matrix:

| Cell | Mode | Trajectory surface | Scenarios | Episode steps |
|---|---|---|---:|---:|
| `2p-off` | 2P | disabled | `3` | `500` |
| `2p-on` | 2P | enabled | `3` | `500` |
| `4p-off` | 4P | disabled | `3` | `500` |
| `4p-on` | 4P | enabled | `3` | `500` |

Scenarios:

| Mode | Scenario |
|---|---|
| 2P | `historical-gauntlet-2p-500-seat-1-vs-claude-v31-race-awareness` |
| 2P | `historical-gauntlet-2p-500-seat-1-vs-claude-v9-hold-aware-capture` |
| 2P | `historical-gauntlet-2p-500-seat-0-vs-ow2-current-main` |
| 4P | `historical-gauntlet-4p-500-top-score-seat-3` |
| 4P | `historical-gauntlet-4p-500-mixed-style-seat-2` |
| 4P | `historical-gauntlet-4p-500-ow2-smoke-reference-seat-0` |

Aggregate results:

| Cell | Matches | Complete | Mean rank | Mean survived | No-actions | No-action owned prod | Strategy no-action | Enemy | Neutral | Own transfer |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `2p-off` | `3` | `3` | `2.0` | `105.3333` | `166` | `56` | `26` | `17` | `103` | `30` |
| `2p-on` | `3` | `3` | `2.0` | `107.6667` | `174` | `66` | `31` | `16` | `103` | `30` |
| `4p-off` | `3` | `3` | `2.0` | `282.6667` | `487` | `394` | `44` | `27` | `103` | `230` |
| `4p-on` | `3` | `3` | `2.0` | `213.0` | `503` | `324` | `56` | `11` | `101` | `24` |

Per-scenario observations:

| Scenario | Off survival / zero-owned | On survival / zero-owned | Read |
|---|---:|---:|---|
| `2p seat-0 vs ow2-current-main` | `87` / `46` | `87` / `46` | unchanged |
| `2p seat-1 vs claude-v31-race-awareness` | `135` / `84` | `135` / `87` | slight zero-owned delay |
| `2p seat-1 vs claude-v9-hold-aware-capture` | `94` / `76` | `101` / `82` | modest survival/zero-owned improvement |
| `4p mixed-style seat-2` | `163` / `142` | `213` / `183` | material improvement |
| `4p ow2-smoke-reference seat-0` | `500` / none | `184` / `176` | severe regression |
| `4p top-score seat-3` | `185` / `113` | `242` / `99` | longer survival but earlier zero-owned |

Decision:

- The A/B result is `noisy/mixed`.
- The surface is not clearly promotable: it slightly helps two 2P cases and one
  4P case, but it severely regresses the 4P OW2 smoke-reference case.
- No default behavior was changed after the matrix.
- The next useful step is compact divergence-fixture extraction from the
  largest paired differences, especially:
  - `4p ow2-smoke-reference seat-0`, where trajectory-on collapses from a
    completed full-500 run to `184` survived turns;
  - `4p mixed-style seat-2`, where trajectory-on improves survival from `163`
    to `213`;
  - `2p claude-v9 hold-aware/capture`, where trajectory-on modestly improves
    but increases no-action pressure.

Metrics not available in the current shard-result schema:

- selected V2 family mix per turn;
- trajectory objective mix per turn.

The generated package, Daytona plan, client report, shard results, replay
artifacts, and A/B summary remain `/tmp` artifacts and are not source-controlled.

## Verification

Focused trajectory fixture check:

```text
.venv/bin/python -m unittest tests.test_planner_v2_trajectory_loss_fixtures
Ran 5 tests in 9.684s
OK
```

Final validation:

```text
.venv/bin/python -m unittest tests.test_planner_v2_trajectory_loss_fixtures tests.test_planner_v2_trajectory_ab_daytona tests.test_planner_v2_scenario_selection_fixtures tests.test_planner_v2_scenario_eval tests.test_planner_v2_scoring tests.test_planner_v2_fallback
Ran 31 tests in 26.204s
OK

.venv/bin/python -m unittest tests.test_planner_v2_daytona_leak_fixtures tests.test_planner_v2_mission_surface_completeness tests.test_runtime_planner_pipeline
Ran 21 tests in 3.778s
OK

.venv/bin/python -m unittest tests.test_planner_v2_trajectory_loss_fixtures tests.test_planner_v2_scenario_backed_loss_fixtures tests.test_planner_v2_scenario_selection_fixtures tests.test_planner_v2_scenario_eval tests.test_planner_v2_scoring tests.test_planner_v2_fallback tests.test_planner_v2_daytona_leak_fixtures tests.test_planner_v2_mission_surface_completeness tests.test_runtime_planner_pipeline
Ran 52 tests in 38.679s
OK

.venv/bin/python -m unittest discover -s tests
Ran 1511 tests in 289.498s
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
trajectory surface, then tested it with a 12-match matched Daytona A/B matrix.
It is not a promotion segment. V2 remains opt-in, no live Kaggle command was
run, and `trajectory_second_source` remains enabled only for explicit V2 runs.

## 9am Push Evidence

At the start of the 9am push, read-only Kaggle submissions showed the current
serious submissions remained far below the historical archive:

| Ref | File | Public score |
|---:|---|---:|
| `53925932` | `orbit_wars_v2_submission.py` | `423.2` |
| `53894832` | `orbit_wars_v1_submission.py` | `407.3` |
| `53555669` | historical `claude-v3-wide-search-forecast` | `912.2` |

Read-only top-player replay analysis was run to `/tmp/ow-top-player-analysis`.
The current rank-1 public submission was `53958734` from `Isaiah @ Tufa Labs`
with score `1834.0`. The 10 sampled public replays were all 2P wins. Aggregate
signals:

- median first production lead: `t20`;
- median first rank-1 total-ship position: `t20`;
- mean final production: `37.7`;
- mean final total ships: `3759.9`;
- target mix was broad, including enemy, moving enemy, own transfers, neutral,
  and moving/comet targets;
- the top player accepts ownership churn but preserves production into the
  endgame.

This is the useful benchmark for serious-agent work: our V2 collapse windows
are not just failing to emit actions; they are failing to reach and retain the
early production curve top players get by roughly turn 20.

## Trajectory Divergence Fixtures

The Daytona A/B artifacts above were compacted into paired divergence fixtures:

- `tests/fixtures/planner_v2_trajectory_divergences/`

The fixture set captures:

- `4p ow2-smoke-reference seat-0`, where trajectory-on regressed from full
  survival `500` to `184`;
- `4p mixed-style seat-2`, where trajectory-on improved survival from `163` to
  `213`;
- `2p claude-v9 hold-aware/capture`, where trajectory-on improved survival from
  `94` to `101`.

The dominant class is source-drain / target-choice, not candidate starvation.
Several replay branches differ because earlier actions moved the game into a
different state; therefore the fixtures store both replay action context and
current budgetless V2 rerun diagnostics for trajectory-on and trajectory-off.

The first targeted change from these fixtures is a V2 scenario-scoring guard:
when trajectory facts say `delay_enemy_denial_until_base_secured` and the state
is under-expanded or single-source fragile, enemy/leader/rank-pressure plans
receive a base-security ordering penalty. This changes the severe
`four_p_ow2_smoke_on_t150_p0` fixture away from `rank_swing` into
`safe_expand` without adding new candidates or runtime fallback behavior.

Focused validation:

```text
.venv/bin/python -m unittest tests.test_planner_v2_trajectory_divergence_fixtures
Ran 6 tests in 39.510s
OK

.venv/bin/python -m unittest tests.test_planner_v2_trajectory_loss_fixtures tests.test_planner_v2_scenario_backed_loss_fixtures tests.test_planner_v2_scoring tests.test_planner_v2_fallback tests.test_planner_v2_scenario_eval
Ran 29 tests in 20.451s
OK
```

The change still needs broad local/Daytona validation before promotion.

## 4P Trajectory Continuation Bridge

The next 9am-push segment added a V2-only continuation bridge for the case
where a second source has been secured but the base is still drained. This is
not a live-promotion change. It makes the trajectory contract explicit so later
work can test and tune the multi-turn sequence:

```text
secure productive base -> preserve/hold drained source -> unlock denial
```

Source changes:

- `TrajectoryDiagnosis` now records `preservation_target_planet_ids` and
  `denial_unlocked`.
- `MissionPlan` now carries trajectory objective and target metadata.
- `ScenarioOutcome` records preservation-target losses separately from source,
  target-hold, and vulnerable-planet losses.
- `mission_surfaces.py` can generate bounded 4P-only
  `planner_v2_surface:trajectory_preserve_source` reinforce candidates.
- `scoring.py` adds 4P-only preservation/denial-lock components so drained
  secured bases prefer preservation before leader/denial pressure.

The surface is intentionally scoped to 4P. An initial unscoped version changed
the `two_p_trajectory_t054_p1` compact fixture away from a productive neutral
expansion into a hold action; that was rejected as a 2P regression risk. The
scoped version leaves that 2P fixture on `safe_expand` while adding
preservation diagnostics to the 4P source-drain divergence windows.

Validation:

```text
.venv/bin/python -m unittest tests.test_planner_v2_trajectory_continuation tests.test_planner_v2_trajectory_loss_fixtures tests.test_planner_v2_trajectory_divergence_fixtures tests.test_planner_v2_scenario_selection_fixtures tests.test_planner_v2_scenario_backed_loss_fixtures tests.test_v2_replay_leak_fixtures tests.test_runtime_planner_pipeline tests.test_planner_v2_scoring tests.test_planner_v2_scenario_eval tests.test_planner_v2_mission_generation tests.test_planner_v2_mission_surface_completeness
Ran 71 tests in 162.416s
OK
```

Daytona evidence for the previous fragile-base guard at commit `3f8514b` was
captured under `/tmp/ow-9am-v2-fragile-guard-probe/`. The filtered shard-004
and shard-005 run completed 10 full-500 historical matches with zero execution
errors, but every match lost. Aggregate results:

| Mode | Matches | Mean survived | Mean final rank | Mean final production | Collapse rate |
|---|---:|---:|---:|---:|---:|
| 2P | `6` | `103.67` | `2.0` | `0.0` | `1.0` |
| 4P | `4` | `173.0` | `2.0` | `1.25` | `0.75` |

Interpretation: the fragile-base guard is not a promotion candidate. The 4P
continuation bridge should be treated as source-controlled planner
infrastructure and fixture evidence, then validated with a fresh current-commit
Daytona probe before any submission decision.
