# Simulator Cycle 14

## What Was Created

- Added `simulate_launch_orders(...)` to `ow_sim.whatif`.
- Added focused composition tests in `tests/test_whatif_composition.py`.
- Kept the helper as a mechanical wrapper over existing simulator primitives:
  `apply_launch_orders(...)`, `next_game_state_after_tick(...)`, and
  `simulate_ticks(...)`.

Cycle 14 does not add planner, mission, scoring, strategy, action parsing, or
branch comparison behavior.

## Evidence Sources Inspected

- `AGENTS.md`
- `docs/competition-context.md`
- `docs/simulator-cycle-13.md`
- `ow_sim/whatif.py`
- `ow_sim/timeline.py`
- `tests/test_whatif_launches.py`
- existing deterministic fixtures in `tests/fixtures/`

Cycle 14 treats Cycle 13 launch insertion and Cycle 11/12 rollout semantics as
source-of-truth primitives.

## Public API Added

`ow_sim.whatif` now exports:

- `simulate_launch_orders(state, orders, ticks, player_id=None)`

## Composition Semantics

`simulate_launch_orders(...)` validates `ticks` as a non-negative integer and
rejects booleans and non-integers.

It then performs exactly this composition:

```text
launched_state = apply_launch_orders(state, orders, player_id=player_id)
return simulate_ticks(launched_state, ticks)
```

Consequences:

- `ticks=0` returns launch insertion only.
- `ticks=1` is equivalent to
  `next_game_state_after_tick(apply_launch_orders(...))`.
- `ticks>1` is equivalent to
  `simulate_ticks(apply_launch_orders(...), ticks)`.
- launch insertion happens before production and movement for all nonzero
  rollout requests.
- all launch validation remains delegated to `apply_launch_orders(...)`.

## Tests Used

Tests are in `tests/test_whatif_composition.py`.

Covered cases:

- `ticks=0` matches `apply_launch_orders(...)`.
- `ticks=1` matches explicit launch insertion plus
  `next_game_state_after_tick(...)`.
- `ticks>1` matches explicit launch insertion plus `simulate_ticks(...)`.
- Empty orders behave consistently with explicit composition.
- Negative, boolean, float, string, and `None` tick values raise `ValueError`.
- Invalid launch orders raise through Cycle 13 validation.
- Official `kaggle_seed7_2p_step0.json` plus inferred launch rolled forward
  one tick matches `kaggle_seed7_2p_step1_fleet.json` semantically.
- Input state, planets, fleets, comets, and raw observations are not mutated.

## Assumptions Made

- This helper is intentionally not a branching API. It returns one state for one
  typed launch-order sequence and one tick horizon.
- `simulate_ticks(...)` remains the only multi-tick rollout implementation.
- `apply_launch_orders(...)` remains the only launch insertion implementation.
- Returning launch-only state for `ticks=0` is the expected behavior because no
  time advance is requested.

## Simulator Segment Status

This completes the narrow simulator segment needed before planner work:

- official constants and geometry
- parsed state containers
- planet/comet/fleet motion helpers
- collision/removal facts
- combat resolution
- one-tick event summaries and state deltas
- one-tick next-state construction
- idle multi-tick rollout
- typed launch insertion
- launch-plus-rollout composition

The simulator now exposes mechanical state-transition primitives. It still does
not decide which actions are good.

## Outside This Simulator Segment

The following remain outside the simulator segment:

- planner logic
- mission generation
- target selection
- search
- scoring and evaluation
- strategy
- branch comparison
- Kaggle action payload parsing
- reward and termination modeling
- new comet spawning from hidden seed state
- Kaggle submission bundling

## Proposed Next Cycle

The next work should start a separate planner or mission-generation segment.
That segment should consume the simulator APIs here rather than adding strategy
behavior inside `ow_sim`.
