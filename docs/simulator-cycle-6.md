# Simulator Cycle 6

## What Was Created

- Added pure launch legality, launch spawn, point aiming, and distance-based ETA
  helpers to `ow_sim.forecast`.
- Preserved Cycle 3-5 planet, comet, and existing-fleet motion behavior.
- Added focused `unittest` coverage for launch legality, spawn math,
  fixture-backed launch movement, aiming, ETA edge cases, invalid inputs, and
  non-mutation.

## Evidence Sources Inspected

- Workspace docs:
  - `AGENTS.md`
  - `docs/competition-context.md`
  - `docs/simulator-cycle-0.md`
  - `docs/simulator-cycle-1.md`
  - `docs/simulator-cycle-2.md`
  - `docs/simulator-cycle-3.md`
  - `docs/simulator-cycle-4.md`
  - `docs/simulator-cycle-5.md`
- Local official environment package:
  `/Users/user/dev/hackathons/orbit-wars-serious/.venv`
- Official interpreter source:
  `/Users/user/dev/hackathons/orbit-wars-serious/.venv/lib/python3.12/site-packages/kaggle_environments/envs/orbit_wars/orbit_wars.py`
- Official deterministic fixtures:
  - `tests/fixtures/kaggle_seed7_2p_step0.json`
  - `tests/fixtures/kaggle_seed7_2p_step1_fleet.json`

## Official Launch Rule Implemented

The official interpreter creates a fleet only when:

```text
source planet exists
source.owner == player_id
source.ships >= ships
ships > 0
```

It then subtracts ships from the source planet, spawns the fleet just outside
the source planet, appends the row to `fleets`, and increments
`next_fleet_id`.

Cycle 6 implements only pure query/construction pieces:

- `can_launch_from_planet(...)` checks the core legality rule.
- `launch_spawn_position(...)` computes the official spawn point.
- `launch_fleet(...)` returns a standalone parsed `Fleet`.

Cycle 6 does not mutate source ships, append to `GameState.fleets`, increment
`GameState.next_fleet_id`, or advance time.

## Spawn Position Semantics

The official spawn formula is:

```text
start_x = source.x + cos(angle) * (source.radius + 0.1)
start_y = source.y + sin(angle) * (source.radius + 0.1)
```

The fixture test validates this source rule end-to-end:

1. Load the official step-0 state.
2. Read the observed step-1 launched fleet's source id, angle, and ships.
3. Build a spawned fleet from the step-0 source planet.
4. Advance that spawned fleet one tick with Cycle 5 movement.
5. Assert the result matches the official step-1 fleet position.

## Point Aiming Semantics

Point aiming uses the direct heading formula:

```text
angle = atan2(target_y - origin_y, target_x - origin_x)
```

Same-point aiming raises `ValueError` because returning an arbitrary angle would
hide an invalid query.

## ETA Semantics

The ETA helpers are distance-based query helpers only:

```text
ticks = ceil(distance / fleet_speed(ships))
```

For circle targets, the effective distance is:

```text
max(0, distance(start, center) - radius)
```

This is not collision resolution, moving-target interception, or path safety.
It only answers how many straight-line movement ticks are needed to cover a
static distance at the official fleet speed.

## Public API Added

- `can_launch_from_planet(source, player_id, ships)`
- `launch_spawn_position(source, angle)`
- `launch_fleet(next_fleet_id, player_id, source, angle, ships)`
- `angle_to_point(origin, target)`
- `angle_from_planet_to_point(source, target)`
- `fleet_ticks_to_reach_distance(distance_value, ships,
  max_speed=DEFAULT_MAX_FLEET_SPEED)`
- `fleet_ticks_to_reach_point(start, target, ships,
  max_speed=DEFAULT_MAX_FLEET_SPEED)`
- `fleet_ticks_to_reach_circle(start, center, radius, ships,
  max_speed=DEFAULT_MAX_FLEET_SPEED)`

All helpers are exported through `ow_sim.forecast.__all__`.

## Tests And Fixtures Used

Tests are in `tests/test_forecast_launch_arrival.py`.

Covered cases:

- Launch legality for owner mismatch, insufficient ships, exact ship count,
  zero ships, negative ships, and invalid ship values.
- Spawn positions for cardinal angles and a non-cardinal angle.
- `launch_fleet(...)` field values, raw row shape, and source/state
  non-mutation.
- Official step0-to-step1 fixture validation for spawn plus one movement tick.
- `angle_to_point(...)` cardinal and quadrant cases.
- `angle_from_planet_to_point(...)` using the planet center.
- Same-point aiming rejection.
- ETA zero distance, exact division, ceiling behavior, circle radius
  subtraction, already-inside-circle behavior, and invalid inputs.

## Assumptions Made

- `can_launch_from_planet(...)` returns `False` for legal-shape requests that
  fail the official core rule, including zero or negative ship counts.
- Non-integer ship values are rejected with `ValueError`; the official
  interpreter sanitizes action ships with `int(...)`, but this simulator layer
  works with parsed integer state and explicit pure queries.
- `launch_fleet(...)` rejects illegal launches with `ValueError` rather than
  constructing rows the official interpreter would not append.
- ETA helpers ignore planets, comets, the sun, board bounds, and moving-target
  effects. Those are later simulator layers.

## What Remains Deferred

- Planner logic.
- Launch command selection.
- Mission generation.
- State mutation and timeline simulation.
- Production.
- Combat.
- Ownership transfer.
- Sun death.
- Out-of-bounds removal.
- Planet/fleet collision resolution.
- Moving-target interception.
- Swept planet/fleet collision handling.
- Evaluation.
- Bot strategy.
- Kaggle submission bundling.

## Proposed Next Cycle

Cycle 7 should implement collision or arrival validation as the next narrow
standalone layer:

1. Confirm official fleet-vs-static-planet collision ordering and strictness.
2. Use existing fleet path, planet path, and geometry helpers to test
   deterministic collision queries.
3. Keep collision as query helpers before mutating timelines.
4. Defer combat, ownership transfer, production timelines, and planning until
   collision/arrival facts are trustworthy.
