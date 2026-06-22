# Historical Gauntlet Deterministic Leak Fix

This document starts the Historical Gauntlet Deterministic Leak Fix segment.
Cycle 0 is characterization-only: it records current runtime/planner behavior
on the committed compact historical gauntlet leak fixtures and does not change
agent behavior.

Baseline commit:

```text
09158df Complete historical gauntlet handoff
```

Fixture source:

```text
/Users/user/dev/hackathons/orbit-wars-serious/tests/fixtures/historical_gauntlet_leaks/
```

Focused characterization test:

```text
/Users/user/dev/hackathons/orbit-wars-serious/tests/test_historical_gauntlet_leak_fixtures.py
```

Segment completion sentinel for later cycles:

```text
HISTORICAL_LEAK_FIX_DAYTONA_PROBE_COMPLETE
```

## Cycle 0 Baseline Characterization

The current compact fixture baseline has no action-emitting cases. Five
fixtures reproduce zero-candidate behavior in the compact observation, and one
fixture reproduces candidate-backed 4P strategy no-action. Two 4P compact
fixtures also carry source-window summaries showing budget-guard-heavy or
strategy-selection-heavy behavior in the full artifact-enabled rerun; those
source-window symptoms are recorded separately from the compact observation's
current diagnostic.

| Fixture | Source leak class | Players | Turn | Action count | Action summary | Runtime status | No-action reason | Candidate count | Budget guard status | Selected commitment | Baseline class |
|---|---|---:|---:|---:|---|---|---|---:|---|---|---|
| `four_p_mixed_style_budget_pressure_t220_p2.json` | `four_player_budget_guard_heavy_pressure` | `4` | `220` | `0` | none | `no_action` | `no_candidates_generated` | `0` | source window: `no_candidates_generated:88,budget_guard_budget_exhausted:59,budget_guard_low_budget:14` | none | `candidate_starvation` |
| `four_p_ow2_reference_strategy_pressure_t189_p0.json` | `four_player_strategy_selection_pressure` | `4` | `189` | `0` | none | `no_action` | `no_candidates_generated` | `0` | source window: `no_candidates_generated:54,budget_guard_budget_exhausted:13,budget_guard_low_budget:11,strategy_selection_rejected:4,strategy_selection_no_action:3` | none | `candidate_starvation` |
| `four_p_top_score_plateau_t080_p3.json` | `four_player_plateau_no_action_pressure` | `4` | `80` | `0` | none | `no_action` | `strategy_selection_no_action` | `36` | source window: `no_candidates_generated:108,strategy_selection_rejected:103,strategy_selection_no_action:9,budget_guard_budget_exhausted:2,budget_guard_low_budget:1` | none | `strategy_selection_no_action` |
| `two_p_collapse_claude_v31_t002_p1.json` | `two_player_candidate_starvation_collapse` | `2` | `2` | `0` | none | `no_action` | `no_candidates_generated` | `0` | not exposed | none | `candidate_starvation` |
| `two_p_collapse_claude_v9_t001_p1.json` | `two_player_candidate_starvation_collapse` | `2` | `1` | `0` | none | `no_action` | `no_candidates_generated` | `0` | not exposed | none | `candidate_starvation` |
| `two_p_control_pressure_ow2_main_t002_p0.json` | `two_player_control_pressure` | `2` | `2` | `0` | none | `no_action` | `no_candidates_generated` | `0` | not exposed | none | `candidate_starvation` |

Selection notes:

| Fixture | Selection status | Selection notes |
|---|---|---|
| `four_p_mixed_style_budget_pressure_t220_p2.json` | `rejected` | no bundles |
| `four_p_ow2_reference_strategy_pressure_t189_p0.json` | `rejected` | no bundles |
| `four_p_top_score_plateau_t080_p3.json` | `no_action` | no eligible four-player strategy |
| `two_p_collapse_claude_v31_t002_p1.json` | `rejected` | no bundles |
| `two_p_collapse_claude_v9_t001_p1.json` | `rejected` | no bundles |
| `two_p_control_pressure_ow2_main_t002_p0.json` | `rejected` | no bundles |

Current fix targets for later cycles:

| Priority | Target | Baseline evidence | Later-cycle proof of fix |
|---:|---|---|---|
| `1` | 2P early collapse / candidate starvation | Three 2P fixtures return `no_candidates_generated` with `0` candidates and no emitted action | Candidate generation/selection produces at least one validated, legal response in the same compact fixtures |
| `2` | 2P control-pressure response weakness | `two_p_control_pressure_ow2_main_t002_p0.json` gives a non-Claude pressure case with the same zero-candidate failure | The non-Claude fixture emits a conservative response or reaches a more precise downstream diagnostic instead of zero candidates |
| `3` | 4P plateau candidate-backed no-action | `four_p_top_score_plateau_t080_p3.json` has `36` candidates but returns `strategy_selection_no_action` | 4P selection chooses a safe validated plateau/rank-pressure action through the normal planner path |
| `4` | 4P budget-heavy strategy windows | Mixed-style and OW2 reference fixtures map to source windows with budget guard and strategy-selection no-action summaries | Later fixes separate true budget exhaustion from selector/candidate failures without weakening runtime budget guards |

No compact fixture currently classifies as `action_emitted` or directly as
`budget_guarded`. The budget-heavy issue is visible through the source-window
diagnostic summaries carried in the fixtures, while the compact observations
currently reproduce candidate starvation or strategy no-action.

Cycle 0 does not modify runtime, planner, simulator, scoring, candidate
generation, action conversion, evaluation gates, Daytona tooling, Kaggle
submission behavior, or generated artifacts.
