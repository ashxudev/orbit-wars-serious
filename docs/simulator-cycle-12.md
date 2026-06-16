# Simulator Cycle 12

## What Was Created

- Added `simulate_ticks(state, ticks)` to `ow_sim.timeline`.
- Added focused rollout tests in `tests/test_timeline_rollout.py`.
- Kept rollout as a thin wrapper over Cycle 11
  `next_game_state_after_tick(...)`.

Cycle 12 advances existing parsed state only. It does not process actions,
insert hypothetical launches, spawn new comets, branch timelines, or add
planner behavior.

## Evidence Sources Inspected

- `AGENTS.md`
- `docs/competition-context.md`
- `docs/simulator-cycle-11.md`
- `ow_sim/timeline.py`
- `tests/test_timeline_next_state.py`
- Existing deterministic fixtures in `tests/fixtures/`

Cycle 12 treats Cycle 11 as the source of truth for one-tick mutation
semantics.

## Public API Added

`ow_sim.timeline` now exports:

- `simulate_ticks(state, ticks)`

## Rollout Semantics

`simulate_ticks(...)` validates that `ticks` is an integer greater than or
equal to zero.

- `ticks=0` returns the input `GameState` object directly.
- `ticks=1` returns `next_game_state_after_tick(state)`.
- `ticks>1` repeatedly applies `next_game_state_after_tick(...)` once per tick.

Because every nonzero step delegates to Cycle 11, rollout preserves the same
production, movement, comet expiry, fleet removal, and combat order as the
one-tick constructor.

## Metadata Handling

Rollout preserves the metadata carried by Cycle 11:

- known ticks increment once per simulated tick
- unknown ticks remain `None`
- `player_id` is preserved
- `angular_velocity` is preserved
- `next_fleet_id` is preserved
- existing comet metadata advances once per simulated tick
- `remaining_overage_time` is preserved
- returned states after nonzero ticks have `raw_observation=None`

## Tests Used

Tests are in `tests/test_timeline_rollout.py`.

Covered cases:

- `ticks=0` returns the input state and does not mutate fixture raw data.
- `ticks=1` equals `next_game_state_after_tick(state)`.
- `ticks>1` equals explicit repeated one-tick application.
- Negative, boolean, and non-integer tick counts raise `ValueError`.
- Official `kaggle_seed7_2p_step1_fleet.json` rolled forward one tick matches
  `kaggle_seed7_2p_step2_fleet.json` semantically.
- Existing comet metadata advances across multiple rollout ticks.
- Fixture-backed state, planets, fleets, comets, and raw observations are not
  mutated.

## Assumptions Made

- Rollout is idle: it never processes actions or inserts new fleets.
- New comet spawning remains out of scope because it depends on hidden episode
  seed state that is not present in parsed agent observations.
- Returning the same object for `ticks=0` is acceptable because no simulation
  step is requested and the state dataclasses are frozen.

## What Remains Deferred

- Action processing.
- Hypothetical launch insertion.
- What-if branching APIs.
- New comet spawning.
- Planner logic.
- Mission generation.
- Strategy.
- Evaluation.
- Reward and termination modeling.
- Kaggle submission bundling.

## Proposed Next Cycle

Cycle 13 should add a narrow what-if launch insertion layer only if it can
construct source-faithful launched fleets and source ship deductions without
mixing in planner or mission-selection logic.
