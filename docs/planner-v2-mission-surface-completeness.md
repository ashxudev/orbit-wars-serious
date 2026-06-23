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

Planner V2 is still not default. The next promotion step is to rerun the two
full-500 historical Daytona probes with this commit after it is committed and
pushed:

1. 2P `historical-gauntlet-2p-500-seat-1-vs-claude-v31-race-awareness`.
2. 4P `historical-gauntlet-4p-500-top-score-seat-3`.

Success requires more than nonzero candidates: the full-horizon probes need to
show reduced production-collapse behavior, lower no-action-with-owned-production
counts, and no new own-transfer spam or unsafe source-drain pattern. If the
probes still lose from repeated collapse, the next deterministic segment should
extract the remaining failure windows and refine V2 search/scoring; if V2 emits
reasonable plans but loses on relative strength, that becomes an
autoresearch/tuning surface.

Segment sentinel remains pending until the post-fix probes pass:
`PLANNER_V2_MISSION_SURFACE_COMPLETENESS_COMPLETE`.
