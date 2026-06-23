# 9am Push Run Log

## Current Baseline

- Active workspace: `/Users/user/dev/hackathons/orbit-wars-serious`.
- Current serious live submissions remain far below the historical fallback:
  - `53925932` / `orbit_wars_v2_submission.py`: public score `423.2`.
  - `53894832` / `orbit_wars_v1_submission.py`: public score `407.3`.
  - Historical fallback `53555669` / `claude-v3-wide-search-forecast`:
    public score `912.2`.
- Known fallback file:
  `/tmp/orbit_wars_claude_v3_wide_search_forecast_submission.py`.
  SHA256: `cd547e3f8f9d93be8c8e2441cb3cc9f52050222114279cbe1192dbcc99a33875`.

## Top-Player Benchmark

Existing read-only top-player analysis under `/tmp/ow-top-player-analysis`
reported current rank 1 as `Isaiah @ Tufa Labs`, public score `1834.0`.
The sampled wins reached production/rank advantage around turn `20` and
preserved production into the endgame with a broad target mix.

Working interpretation: the serious V2 agent is not merely missing isolated
actions. It is failing to create and retain the early production curve that top
agents reach by about turn `20`.

## Daytona Evidence

Previous-commit fragile-base guard probe:

- Commit: `3f8514b`.
- Root: `/tmp/ow-9am-v2-fragile-guard-probe/`.
- Plan: `/tmp/ow-9am-v2-fragile-guard-probe/daytona-shard-jobs-004-005.json`.
- Report: `/tmp/ow-9am-v2-fragile-guard-probe/daytona-real-report-004-005.json`.
- Result: completed, `10` full-500 historical matches, `0` execution errors.

Aggregate:

| Mode | Matches | Mean survived | Mean final rank | Mean final production | Collapse rate |
|---|---:|---:|---:|---:|---:|
| 2P | `6` | `103.67` | `2.0` | `0.0` | `1.0` |
| 4P | `4` | `173.0` | `2.0` | `1.25` | `0.75` |

Decision: not promotable, no live submission.

## Current Source Change

Added a V2-only, 4P-scoped trajectory continuation bridge:

- trajectory facts for preservation targets and denial unlock;
- 4P preservation reinforce candidate surface;
- mission objective/target metadata;
- preservation-target scenario-loss accounting;
- scoring components for preserve-before-deny behavior;
- compact fixture updates and focused tests.

This is planner infrastructure, not a promotion-ready agent. The hardest 4P
fixtures still often report no useful action after preservation accounting,
which means the bridge exposes the gap more clearly but does not solve top-10
strength by itself.

## Validation So Far

```text
.venv/bin/python -m unittest tests.test_planner_v2_trajectory_continuation tests.test_planner_v2_scoring tests.test_planner_v2_scenario_eval tests.test_planner_v2_mission_generation
Ran 26 tests in 0.054s
OK

.venv/bin/python -m unittest tests.test_planner_v2_trajectory_continuation tests.test_planner_v2_trajectory_loss_fixtures tests.test_planner_v2_trajectory_divergence_fixtures tests.test_planner_v2_scenario_selection_fixtures tests.test_planner_v2_scenario_backed_loss_fixtures tests.test_v2_replay_leak_fixtures tests.test_runtime_planner_pipeline tests.test_planner_v2_scoring tests.test_planner_v2_scenario_eval tests.test_planner_v2_mission_generation tests.test_planner_v2_mission_surface_completeness
Ran 71 tests in 162.416s
OK
```

Pending before any promotion decision:

- fresh current-commit Daytona probe if this bridge is considered for further
  evidence.

Completed validation:

```text
.venv/bin/python -m unittest discover -s tests
Ran 1530 tests in 394.662s
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

## Submission Status

- Exploratory live submissions used in this push: `0`.
- Final submissions used in this push: `0`.
- Current serious V2 path is not promotable on evidence.
- Next-best fallback candidate remains
  `/tmp/orbit_wars_claude_v3_wide_search_forecast_submission.py`.
