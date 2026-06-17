# Simulator Cycle 13

## What Was Created

- Replaced the Cycle 0 `ow_sim.whatif` placeholder with a narrow typed launch
  insertion layer.
- Added `LaunchOrder`, a frozen dataclass for hypothetical source/angle/ships
  launches.
- Added `apply_launch_orders(state, orders, player_id=None)`, a pure helper
  that returns a new `GameState` with launched fleets appended and source ships
  deducted.
- Added focused `unittest` coverage for valid launches, invalid launches,
  sequential source deduction, id assignment, non-mutation, and official fixture
  parity.

Cycle 13 does not advance time. Callers compose launch insertion with Cycle 11
or Cycle 12 when they need future simulation:

```text
next_game_state_after_tick(apply_launch_orders(state, orders))
simulate_ticks(apply_launch_orders(state, orders), ticks)
```

## Evidence Sources Inspected

- `AGENTS.md`
- `docs/competition-context.md`
- `docs/simulator_cycles_md/simulator-cycle-12.md`
- `ow_sim/forecast.py`
- `ow_sim/timeline.py`
- `ow_sim/whatif.py`
- official local interpreter source:
  `/Users/user/dev/hackathons/orbit-wars-serious/.venv/lib/python3.12/site-packages/kaggle_environments/envs/orbit_wars/orbit_wars.py`

The official launch block validates source ownership and ships, deducts source
ships, spawns the fleet just outside the source planet, appends the fleet, and
increments `next_fleet_id` before production and movement.

## Public API Added

`ow_sim.whatif` now exports:

- `LaunchOrder`
- `apply_launch_orders(state, orders, player_id=None)`

`LaunchOrder` contains:

- `source_planet_id`
- `angle`
- `ships`
- `player_id`

The order-level `player_id` is optional. If omitted, `apply_launch_orders`
uses its `player_id` argument, then `state.player_id`. If none is available,
it raises `ValueError`.

## Launch Semantics

Launch orders are applied sequentially:

1. Resolve the effective player id.
2. Find the current source planet in the working planet list.
3. Use the existing Cycle 6 `launch_fleet(...)` helper to validate and build
   the spawned fleet.
4. Deduct launched ships from the working source planet.
5. Append the spawned fleet after existing fleets.
6. Increment the working `next_fleet_id`.

Sequential application means multiple launches from the same source consume the
ships left by earlier orders. If cumulative ships exceed availability, the
helper raises `ValueError`.

## Returned State

For non-empty orders, `apply_launch_orders(...)` returns a new `GameState`:

- `tick` is preserved.
- `player_id` is preserved.
- `planets` keep their order, with changed sources replaced by new `Planet`
  objects.
- existing `fleets` keep their order.
- launched fleets are appended in order.
- `next_fleet_id` advances once per inserted fleet.
- `angular_velocity`, `initial_planets`, `comet_planet_ids`, `comets`, and
  `remaining_overage_time` are preserved.
- `raw_observation` is `None`.

For empty orders, the helper returns the input state directly and performs no
mutation.

## Validation Behavior

The helper raises `ValueError` for:

- missing source planet id
- wrong source owner
- insufficient ships
- zero or negative ships
- boolean or non-integer ships
- missing effective player id
- missing `state.next_fleet_id` for non-empty orders

Typed launch orders intentionally do not mirror the official interpreter's
`int(...)` action sanitization. This layer expects already typed simulator
inputs and rejects invalid ship values.

## Tests Used

Tests are in `tests/test_whatif_launches.py`.

Covered cases:

- Single valid launch deducts source ships, appends one fleet, preserves
  unrelated planets/fleets, and increments `next_fleet_id`.
- Multiple launches from the same source apply sequentially.
- Multiple launches from the same source fail if cumulative ships exceed
  availability.
- Multiple launches from different sources preserve launch order and assign
  consecutive fleet ids.
- Invalid source id, wrong owner, insufficient ships, zero/negative ships,
  boolean/non-integer ships, missing player id, and missing `next_fleet_id`
  raise `ValueError`.
- Empty launch orders return the input state without mutation.
- Input state, planets, fleets, comets, and raw observations are not mutated.
- Official `kaggle_seed7_2p_step0.json` plus the inferred observed launch,
  composed through `next_game_state_after_tick(...)`, matches
  `kaggle_seed7_2p_step1_fleet.json` semantically.

## Assumptions Made

- `apply_launch_orders(...)` is a state insertion helper, not an action parser.
- Launch angle values are trusted as typed numeric inputs, matching the current
  Cycle 6 launch helper behavior.
- New fleets use `state.next_fleet_id` and then consecutive ids.
- Returning the original state for empty orders is acceptable because no
  insertion occurs and state dataclasses are immutable.

## What Remains Deferred

- Planner logic.
- Mission generation.
- Strategy.
- Target selection.
- Search and scoring.
- Branching what-if trees.
- Parsing Kaggle action payloads.
- Inserting launches directly into `simulate_ticks(...)`.
- Reward and termination modeling.
- New comet spawning.
- Kaggle submission bundling.

## Proposed Next Cycle

Cycle 14 should add narrow what-if composition helpers only if they remain
mechanical wrappers around `apply_launch_orders(...)`,
`next_game_state_after_tick(...)`, and `simulate_ticks(...)`. Mission
generation and evaluation should remain separate planner-layer work.
