# Planner V2 Mission/Search Engine

Planner V2 is a parallel mission/search boundary behind an explicit runtime
switch. V1 remains the default planner until V2 clears fixture, local gauntlet,
and Daytona promotion evidence.

## Current Boundary

- Package: `ow_planner_v2/`
- Runtime switch: `RuntimePlannerConfig(planner_version="v2")`
- Default runtime behavior: `planner_version="v1"`
- Submission bundling: includes `ow_planner_v2` so generated submissions can
  import the runtime dispatch boundary without relying on repo imports.

The V2 runner reuses existing V1 primitives for candidate generation,
evaluation, response facts, commitment validation, and action conversion. It
does not change simulator mechanics, runtime budget guards, or Kaggle action
format.

## Implemented Stages

1. `diagnose_board(state)` centralizes reusable fact surfaces:
   owned-production threats, own-transfer intent, enemy-denial opportunities,
   4P plateau facts, 4P rank/swing facts, and strategy mode facts.
2. `generate_mission_plans(...)` maps validated candidates into bounded mission
   families such as safe expansion, urgent defense, enemy denial, leader
   pressure, rank swing, hold capture, recapture, funnel/consolidation, and late
   liquidation.
3. `build_action_set_plans(...)` converts missions plus validated commitments
   into action-set plans. It supports single-mission plans and bounded
   coordinated pairs such as defense plus expansion when sources do not overlap.
4. `score_action_set_plans(...)` scores each plan across configured horizons
   and records JSON-safe horizon scores and score components.
5. `select_evaluated_plan(...)` applies the fallback ladder with explicit
   no-action reasons when no bounded plan is legal or above threshold.
6. `planner_v2_result_to_strategy_selection(...)` maps the selected V2 plan back
   into the existing strategy-selection contract so runtime action conversion is
   unchanged.

## Replay Fixtures

Cycle-local V2 characterization fixtures live under
`tests/fixtures/v2_replay_leaks/`. They are compact single-observation fixtures
extracted from the V2 public replay sample:

| Episode | Fixture class |
|---:|---|
| `81217550` | 4P action starvation |
| `81216397` | 4P low-production plateau |
| `81225543` | 2P low-action collapse |
| `81221061` | hold/defense failure |
| `81218141` | own-transfer spam |
| `81214883` | late enemy-denial absence |

`tests/test_v2_replay_leak_fixtures.py` verifies that each fixture parses
through the runtime adapter, matches current V1 runtime diagnostics, and exposes
deterministic opt-in V2 diagnostics.

## Evaluation Metrics

`MatchMetrics` now carries additional report-only V2 promotion signals:

- `action_count_after_t20`
- `no_action_with_owned_production_count`
- inferred `enemy_target_action_count`, `own_transfer_action_count`, and
  `neutral_target_action_count`
- `production_collapse`
- `defense_coverage_count`
- `four_player_rank_pressure_count`
- `early_elimination`

No gate thresholds currently use these fields. They are intended for V2 vs V1
and historical champion comparisons before any default switch.

## Promotion Status

V2 is not default and is not ready for live submission. Remaining promotion work:

- Run selected GitHub-backed Daytona probes with V2 enabled after the current
  V2 branch is committed and pushed.
- Promote `planner_version="v2"` only after objective fixture, local, and
  Daytona evidence beats V1 and historical baselines.

## Promotion / Execution Evidence

Temporary manifests and reports for the first promotion pass were written under
`/tmp/ow-planner-v2-promotion/`; no generated report is source-controlled.

| Check | V1 result | V2 result |
|---|---:|---:|
| Quick 2P smoke | `2/2` completed, `0` errors, win rate `1.0`, mean rank `1.0` | `2/2` completed, `0` errors, win rate `1.0`, mean rank `1.0` |
| Quick 4P smoke | `2/2` completed, `0` errors, win rate `1.0`, mean rank `1.0` | `2/2` completed, `0` errors, win rate `1.0`, mean rank `1.0` |
| Legacy-opponent smoke | `4/4` completed, `0` errors, win rate `1.0`, mean rank `1.0` | `4/4` completed, `0` errors, win rate `1.0`, mean rank `1.0` |
| Competitive-baseline smoke | `6/6` completed, `0` errors, win rate `1.0`, mean rank `1.0` | `6/6` completed, `0` errors, win rate `1.0`, mean rank `1.0` |

Two local full-500 historical champion micro-probes were run with V2 enabled:

| Scenario | V1 result | V2 result |
|---|---:|---:|
| `historical-gauntlet-2p-500-seat-1-vs-claude-v31-race-awareness` | `1/1` completed, `0` errors, win rate `0.0`, mean rank `2.0` | `1/1` completed, `0` errors, win rate `0.0`, mean rank `2.0` |
| `historical-gauntlet-4p-500-top-score-seat-3` | `1/1` completed, `0` errors, win rate `0.0`, mean rank `2.0` | `1/1` completed, `0` errors, win rate `0.0`, mean rank `2.0` |

Interpretation: Planner V2 is locally executable and does not regress the
bounded smoke suites, but it has not yet beaten V1 on the first full-500
historical champion probes. It should remain opt-in.

The V2 implementation was committed and pushed as
`0dc38e4251ad8b32c419db322ab2116011016c66`, then tested through two
GitHub-backed Daytona probes. Both probes used source mode `github`; the
sandbox cloned the pushed commit, and no repo-source package upload was used.

| Daytona probe | Status | Result | Artifact paths |
|---|---|---|---|
| `historical-gauntlet-2p-500-seat-1-vs-claude-v31-race-awareness` | complete, `1/1` match, `0` execution errors | final rank `2`, final score `-1.0`, survived `109` turns, production collapse `true`, no-action count `47`, no-action with owned production `38` | `/tmp/ow-planner-v2-daytona-2p/planner-v2-2p-probe-0000.artifacts/planner-v2-2p-probe-0000-match-0000-replay.json`; `/tmp/ow-planner-v2-daytona-2p/planner-v2-2p-probe-0000.artifacts/planner-v2-2p-probe-0000-match-0000-result.json` |
| `historical-gauntlet-4p-500-top-score-seat-3` | complete, `1/1` match, `0` execution errors | final rank `2`, final score `-1.0`, survived `244` turns, production collapse `true`, no-action count `107`, no-action with owned production `47` | `/tmp/ow-planner-v2-daytona-4p/planner-v2-4p-probe-0000.artifacts/planner-v2-4p-probe-0000-match-0000-replay.json`; `/tmp/ow-planner-v2-daytona-4p/planner-v2-4p-probe-0000.artifacts/planner-v2-4p-probe-0000-match-0000-result.json` |

Daytona execution conclusion: GitHub-backed V2 execution works end to end and
produces replay/result artifacts, but V2 is not promotion-ready. The selected
full-horizon historical probes still lose with production collapse. Next work
should extract compact fixtures from the Daytona artifacts above and improve V2
mission/search policy before any default switch.
