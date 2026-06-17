# Mission Evaluation Scoring

This document records the first-pass mission evaluation scoring assumptions as
of Mission Evaluation Cycle 13. The scoring surface is intentionally narrow: it
turns deterministic mission evaluation facts into named score components. It
does not rank, prune, select, or execute candidates.

## Scoring Inputs

Scoring consumes immutable planner evaluation facts:

- `MissionValueFacts`
- `MissionTimingFacts`
- `MissionEvaluationFacts.sources_before`
- `MissionEvaluationFacts.sources_mission`
- `MissionEvaluationFacts.future_delta.sources`

The scoring layer does not rerun simulator rollouts, recompute arrival timing,
call candidate generation, or inspect broader game strategy.

## Component Families

Base value components:

- `production_delta_vs_baseline`: rewards production controlled by the player in
  the mission future versus the idle baseline.
- `target_ship_delta_vs_baseline`: preserves the deterministic target ship delta
  as a score input.
- `source_ship_delta_vs_baseline`: accounts for source ship change versus idle
  baseline.
- `ships_spent`: applies a direct launch ship cost.

Timing components:

- `max_arrival_ticks`: penalizes slower complete mission timing using the latest
  known launch arrival tick.
- `incomplete_timing_penalty`: penalizes otherwise valid missions whose timing
  facts are incomplete.

Capture outcome components:

- `target_captured_by_player`: rewards missions that take a target the player
  did not control in the baseline.
- `target_retained_by_player`: rewards missions that preserve player control of
  a target.
- `target_lost_by_player`: penalizes missions where the player loses target
  control versus the baseline.

Source opportunity components:

- `source_drain_fraction`: penalizes the fraction of before-state source ships
  drained by the mission future.
- `source_depleted_count`: penalizes source planets whose mission-state ship
  count is `<= 0`.
- `incomplete_source_opportunity_penalty`: penalizes otherwise valid missions
  where source before/mission/delta facts are incomplete.

Invalid missions:

- `invalid_mission_penalty` is the only component for invalid mission value
  facts. Timing, outcome, and source opportunity components are not added on
  top of invalid missions.

## Sanity Expectations

The tests lock in these relationships without adding a ranking API:

- Valid productive capture scores above a no-launch neutral outcome.
- Complete timing scores above incomplete timing when all else is equal.
- Faster arrival scores above slower arrival when all else is equal.
- Capturing or retaining target control scores above losing the target when all
  else is equal.
- Non-depleted source missions score above otherwise equivalent depleted-source
  missions.
- Invalid missions score below valid missions.

These are local consistency checks for the scoring policy, not a candidate
selection strategy.

## Assumptions

- Current weights are first-pass continuous-improvement targets, not final
  strategy.
- Component names are stable enough for tests and later tuning scripts.
- Score components are appended in this order: base value, timing, capture
  outcome, source opportunity.
- Scores are meaningful only for comparing facts generated under the same
  evaluation horizon and simulator scope.

## Known Blind Spots

- No opponent reinforcement modeling.
- No neutral race or tie modeling.
- No enemy counterattack or source-threat modeling.
- No four-player rank, swing, diplomacy, or kingmaking modeling.
- No runtime candidate pruning or selection policy.
- No commitment policy for reserving ships across multiple missions.
- No fallback policy for empty, invalid, or time-limited candidate sets.

These blind spots belong to later planner segments. The current layer is only a
deterministic scoring surface that can be tuned or replaced without changing
mission fact extraction.
