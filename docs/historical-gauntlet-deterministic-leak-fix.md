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

At Cycle 0 start, the compact fixture baseline had no action-emitting cases. Five
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

## Cycle 1 Two-Player Early Collapse Candidate Recovery

Cycle 1 fixes deterministic 2P early-collapse candidate starvation for the two
Claude historical gauntlet fixtures:

```text
/Users/user/dev/hackathons/orbit-wars-serious/tests/fixtures/historical_gauntlet_leaks/two_p_collapse_claude_v31_t002_p1.json
/Users/user/dev/hackathons/orbit-wars-serious/tests/fixtures/historical_gauntlet_leaks/two_p_collapse_claude_v9_t001_p1.json
```

Implementation summary:

- Candidate generation now has a narrow early 2P pressure-recovery path that
  only runs when normal validated candidates are empty.
- The recovery path is limited to low-owned, active-2P states at `step <= 10`.
- It scans the existing ordered source-target pairs and creates bounded,
  reserve-preserving pressure candidates for production-bearing neutral/enemy
  targets that are just beyond immediate capture affordability.
- It still validates each launch through the existing simulator-backed outcome
  boundary and honors `max_candidates` and `max_validation_attempts`.
- It does not add a runtime-only fallback, change simulator mechanics, change
  scoring weights, or bypass selection/action conversion.

Before/after target fixture results:

| Fixture | Before compact diagnostic | After default-planner diagnostic | After actual runtime action |
|---|---|---|---|
| `two_p_collapse_claude_v31_t002_p1.json` | `no_candidates_generated`, `0` candidates, `0` actions | `strategy_selection_no_action`, `31` candidates, `0` actions; selection note: below minimum total score | `[[23, 2.3330067382197486, 5]]`; `8` runtime-capped candidates; selected `reserve_preserving` |
| `two_p_collapse_claude_v9_t001_p1.json` | `no_candidates_generated`, `0` candidates, `0` actions | `strategy_selection_no_action`, `31` candidates, `0` actions; selection note: below minimum total score | `[[7, 2.8808254788103143, 4]]`; `8` runtime-capped candidates; selected `reserve_preserving` |

The default planner characterization still reports no action because its
minimum score threshold remains `0.0`. The live/runtime path uses the existing
bounded runtime configuration with `runtime_minimum_total_score=-100.0`, so both
target fixtures now emit legal actions through normal candidate generation,
evaluation, commitment, selection, and action conversion.

Incidental characterization:

- `two_p_control_pressure_ow2_main_t002_p0.json` also moves from
  `no_candidates_generated` to candidate-backed `strategy_selection_no_action`
  under the default planner characterization. It remains a later control-
  pressure policy target; Cycle 1 does not add a dedicated selection policy for
  that leak class.
- The current 4P historical gauntlet fixtures retain their prior
  characterization; the early recovery gate does not apply to late reduced-
  owner 4P states.

Remaining fix queue:

| Priority | Target | Current post-Cycle-1 status |
|---:|---|---|
| `1` | 2P control-pressure response weakness | Candidate recovery is visible for the OW2 control-pressure fixture, but default selection still rejects below the minimum score |
| `2` | 4P plateau candidate-backed no-action | `four_p_top_score_plateau_t080_p3.json` still has candidates but returns `strategy_selection_no_action` |
| `3` | 4P budget-heavy strategy windows | Mixed-style and OW2 reference source windows still need budget-vs-selection separation without weakening budget guards |

## Cycle 2 Two-Player Control-Pressure Selection

Cycle 2 fixes the remaining 2P historical control-pressure compact fixture:

```text
/Users/user/dev/hackathons/orbit-wars-serious/tests/fixtures/historical_gauntlet_leaks/two_p_control_pressure_ow2_main_t002_p0.json
```

Implementation summary:

- Two-player selection now has a narrow below-floor allowance for early
  pressure-recovery candidates produced by the Cycle 1 candidate-generation
  path.
- The allowance requires an existing validated `reserve_preserving` commitment
  and active response-pressure facts, so ordinary below-threshold captures still
  return `below minimum total score`.
- The change does not lower the global score floor, add a runtime fallback,
  widen candidate generation, change scoring weights, or bypass normal
  evaluation/commitment/action conversion.

Before/after target fixture results:

| Fixture | Post-Cycle-1 default diagnostic | Cycle 2 default action | Actual runtime action |
|---|---|---|---|
| `two_p_control_pressure_ow2_main_t002_p0.json` | `strategy_selection_no_action`, `27` candidates, `0` actions; selection note: below minimum total score | `[[16, -2.855917510740959, 1]]`; `27` candidates; selected `reserve_preserving`; selection note: pressure retention preference | `[[16, -1.5868432791875053, 1]]`; `8` runtime-capped candidates; selected `reserve_preserving` |

Cycle 2 also makes the two Cycle 1 Claude collapse fixtures action-emitting
under the default safe path because their recovered candidates carry the same
early pressure-recovery marker and response-pressure facts. This preserves their
actual runtime behavior from Cycle 1 while improving their compact
characterization from candidate-backed no-action to legal reserve-preserving
actions:

| Fixture | Cycle 2 default action | Actual runtime action |
|---|---|---|
| `two_p_collapse_claude_v31_t002_p1.json` | `[[23, 1.5552066198576744, 5]]`; `31` candidates; selected `reserve_preserving` | `[[23, 2.3330067382197486, 5]]`; `8` runtime-capped candidates; selected `reserve_preserving` |
| `two_p_collapse_claude_v9_t001_p1.json` | `[[7, 0.7442724238714199, 4]]`; `31` candidates; selected `reserve_preserving` | `[[7, 2.8808254788103143, 4]]`; `8` runtime-capped candidates; selected `reserve_preserving` |

Remaining fix queue:

| Priority | Target | Current post-Cycle-2 status |
|---:|---|---|
| `1` | 4P plateau candidate-backed no-action | `four_p_top_score_plateau_t080_p3.json` still has candidates but returns `strategy_selection_no_action` |
| `2` | 4P budget-heavy strategy windows | Mixed-style and OW2 reference source windows still need budget-vs-selection separation without weakening budget guards |

## Cycle 3 Four-Player Plateau Selector Recovery

Cycle 3 fixes the candidate-backed 4P plateau compact fixture:

```text
/Users/user/dev/hackathons/orbit-wars-serious/tests/fixtures/historical_gauntlet_leaks/four_p_top_score_plateau_t080_p3.json
```

Implementation summary:

- Four-player selection now treats active 4P rank/leader/swing pressure as a
  valid recovery context when normal 4P selection finds no eligible action.
- In that recovery context, a validated `reserve_preserving` owned-retention
  candidate can be selected instead of returning `strategy_selection_no_action`.
- Candidate ordering now prioritizes owned-retention pairs ahead of neutral
  targets only in active 4P continuation states with existing production, so
  the bounded runtime validation budget can reach conservative retention
  candidates without increasing `max_candidates` or validation breadth.
- The change does not lower global thresholds, weaken budget guards, add a
  runtime-only fallback, change simulator mechanics, or alter action conversion.

Before/after target fixture results:

| Fixture | Pre-Cycle-3 compact diagnostic | Cycle 3 default action | Actual runtime action |
|---|---|---|---|
| `four_p_top_score_plateau_t080_p3.json` | `strategy_selection_no_action`, `36` candidates, `0` actions | `[[19, -2.7307013421618356, 1]]`; `36` candidates; selected `reserve_preserving`; selection note: plateau/rank recovery retention | `[[19, -2.7307013421618356, 1]]`; `7` runtime-capped candidates; selected `reserve_preserving` |

Preservation checks:

- The three fixed 2P historical fixtures still emit legal `reserve_preserving`
  runtime actions.
- `four_p_mixed_style_budget_pressure_t220_p2.json` and
  `four_p_ow2_reference_strategy_pressure_t189_p0.json` remain characterized
  for the next budget-heavy strategy-window cycle; this cycle does not weaken
  budget guards or force those windows.

Remaining fix queue:

| Priority | Target | Current post-Cycle-3 status |
|---:|---|---|
| `1` | 4P budget-heavy strategy windows | Mixed-style and OW2 reference source windows still need budget-vs-selection separation without weakening budget guards |

## Cycle 4 Four-Player Budget-Pressure Split

Cycle 4 resolves the two remaining compact 4P historical gauntlet targets by
separating an intentional no-source no-action from an avoidable reduced-owner
pressure failure:

```text
/Users/user/dev/hackathons/orbit-wars-serious/tests/fixtures/historical_gauntlet_leaks/four_p_mixed_style_budget_pressure_t220_p2.json
/Users/user/dev/hackathons/orbit-wars-serious/tests/fixtures/historical_gauntlet_leaks/four_p_ow2_reference_strategy_pressure_t189_p0.json
```

Implementation summary:

- Runtime diagnostics now report `no_owned_planets` when a parsed state has no
  legal owned source planet and no planner candidates. This keeps eliminated
  compact observations out of the unresolved `no_candidates_generated` bucket.
- Candidate generation now has a bounded reduced-owner pressure-recovery path
  that runs only after ordinary generation produces no candidates in late
  one-owned, reduced-active-owner states.
- The recovery candidate is still validated through the existing outcome
  boundary and uses existing evaluation, response, commitment, two-player
  selection, and action conversion.
- The change does not weaken budget guards, add a runtime fallback, lower
  thresholds, change broad scoring weights, or increase runtime candidate caps.

Before/after target fixture results:

| Fixture | Pre-Cycle-4 compact diagnostic | Cycle 4 default result | Actual runtime result | Classification |
|---|---|---|---|---|
| `four_p_mixed_style_budget_pressure_t220_p2.json` | `no_candidates_generated`, `0` candidates, `0` actions | `no_owned_planets`, `0` candidates, `0` actions | `no_owned_planets`, `0` candidates, `0` actions | `source-less / eliminated compact observation` |
| `four_p_ow2_reference_strategy_pressure_t189_p0.json` | `no_candidates_generated`, `0` candidates, `0` actions | `[[4, -2.558903106652152, 52]]`; `27` candidates; selected `reserve_preserving` | `[[4, -2.558903106652152, 52]]`; `8` runtime-capped candidates; selected `reserve_preserving` | `action_emitted` |

Preservation checks:

- The three fixed 2P historical fixtures still emit legal `reserve_preserving`
  runtime actions.
- `four_p_top_score_plateau_t080_p3.json` still emits its Cycle 3
  `reserve_preserving` plateau/rank recovery action.
- No compact historical gauntlet fixture now remains in the generic unresolved
  `no_candidates_generated` or candidate-backed `strategy_selection_no_action`
  state.

Remaining fix queue:

| Priority | Target | Current post-Cycle-4 status |
|---:|---|---|
| `1` | Full-gauntlet competitive weakness | The compact deterministic historical leak fixtures are now classified or action-emitting; broader losses should move to the next deterministic/autoresearch planning segment |

## Cycle 5 Historical Leak Regression Harness

Cycle 5 adds a measurement-only local regression harness for the committed
historical gauntlet leak fixtures:

```text
/Users/user/dev/hackathons/orbit-wars-serious/ow_eval/historical_leak_regression.py
/Users/user/dev/hackathons/orbit-wars-serious/tests/test_historical_leak_regression.py
```

The harness loads every compact fixture under:

```text
/Users/user/dev/hackathons/orbit-wars-serious/tests/fixtures/historical_gauntlet_leaks/
```

It runs the current runtime path for each fixture, records JSON-safe case
results, and classifies outcomes into:

- `action_emitted`
- `source_less_no_owned_planets`
- `budget_guarded`
- `candidate_starvation_unresolved`
- `strategy_selection_no_action_unresolved`
- `other_no_action`

Stable Cycle 5 summary:

```text
historical_leak_regression cases=6 action_emitting=5 action_rate=0.833333 source_less_no_owned=1 budget_guarded=0 unresolved_no_candidates=0 unresolved_strategy_no_action=0 other_no_action=0 unresolved_deterministic_leaks=0
```

Aggregate status:

| Metric | Value |
|---|---:|
| Total cases | `6` |
| Action-emitting cases | `5` |
| Source-less / no-owned cases | `1` |
| Budget-guarded no-actions | `0` |
| Unresolved `no_candidates_generated` cases | `0` |
| Unresolved `strategy_selection_no_action` cases | `0` |
| Other no-action cases | `0` |
| Unresolved deterministic leaks | `0` |

Current case classifications:

| Fixture | Classification |
|---|---|
| `four_p_mixed_style_budget_pressure_t220_p2.json` | `source_less_no_owned_planets` |
| `four_p_ow2_reference_strategy_pressure_t189_p0.json` | `action_emitted` |
| `four_p_top_score_plateau_t080_p3.json` | `action_emitted` |
| `two_p_collapse_claude_v31_t002_p1.json` | `action_emitted` |
| `two_p_collapse_claude_v9_t001_p1.json` | `action_emitted` |
| `two_p_control_pressure_ow2_main_t002_p0.json` | `action_emitted` |

Cycle 5 does not change planner, runtime, simulator, candidate generation,
scoring, action conversion, budget guards, Daytona tooling, Kaggle behavior, or
submission behavior. It only adds deterministic measurement infrastructure for
later segment handoff.
