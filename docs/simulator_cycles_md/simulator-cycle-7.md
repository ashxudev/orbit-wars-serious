# Simulator Cycle 7

## What Was Created

- Added `ow_sim.collision`, a pure fleet collision/removal query layer for one
  tick of movement.
- Added import smoke coverage for the new module.
- Added focused `unittest` coverage for planet hits, moving-planet paths, comet
  collision flags, bounds removal, sun removal, official ordering, invalid
  `dt`, and non-mutation.

## Evidence Sources Inspected

- Workspace docs:
  - `AGENTS.md`
  - `docs/competition-context.md`
  - `docs/simulator_cycles_md/simulator-cycle-0.md`
  - `docs/simulator_cycles_md/simulator-cycle-1.md`
  - `docs/simulator_cycles_md/simulator-cycle-2.md`
  - `docs/simulator_cycles_md/simulator-cycle-3.md`
  - `docs/simulator_cycles_md/simulator-cycle-4.md`
  - `docs/simulator_cycles_md/simulator-cycle-5.md`
  - `docs/simulator_cycles_md/simulator-cycle-6.md`
- Local official environment package:
  `/Users/user/dev/hackathons/orbit-wars-serious/.venv`
- Official interpreter source:
  `/Users/user/dev/hackathons/orbit-wars-serious/.venv/lib/python3.12/site-packages/kaggle_environments/envs/orbit_wars/orbit_wars.py`

Official source sections inspected:

- `point_to_segment_distance(...)`
- `swept_pair_hit(...)`
- `planet_paths` construction
- fleet movement and planet/bounds/sun removal ordering
- delayed combat resolution after fleet removal decisions

## Official Collision And Removal Ordering

The official interpreter moves each fleet to its new position, then evaluates
removal in this order:

1. Check swept collisions with planets in `obs0.planets` order.
2. If a planet is hit, queue combat and remove the fleet; do not check bounds
   or sun for that fleet.
3. If no planet is hit, check whether the fleet's new position is outside the
   inclusive board bounds.
4. If still active, check whether the movement segment enters the sun radius.
5. Remove fleets after all movement checks.
6. Resolve combat later.

Cycle 7 mirrors only the query side of steps 1-4. It does not mutate state,
remove fleets, queue combat, or resolve combat.

## Swept Moving-Planet Collision Semantics

Planet collision uses the official swept moving-point versus moving-circle
test:

```text
swept_pair_hit(fleet_old, fleet_new, planet_old, planet_new, planet_radius)
```

This treats the fleet and planet as linearly moving over the same normalized
tick interval. Tangent contact counts as a hit for planets, matching the
official quadratic test.

Cycle 7 uses existing path helpers:

- `fleet_path_for_tick(...)`
- `planet_path_for_tick(...)`

That keeps planet rotation and comet path-index behavior centralized in the
forecast layer.

## Comet Collision-Check Behavior

`planet_path_for_tick(...)` returns a third `check_collision` flag for comet
paths. The official interpreter sets this flag to `False` for first comet
placement from the off-board placeholder, so fleets do not collide with a comet
that appears mid-tick.

Cycle 7 skips comet planet collision checks when this flag is false. Missing or
expired comet path metadata returns no invented hit.

## Bounds And Sun Rules

Bounds removal uses the official new-position check:

```text
0 <= fleet.x <= BOARD_SIZE and 0 <= fleet.y <= BOARD_SIZE
```

Endpoints exactly on the board boundary are still in bounds.

Sun removal uses the official strict segment-distance rule:

```text
point_to_segment_distance(SUN_CENTER, fleet_old, fleet_new) < SUN_RADIUS
```

Tangent contact with the sun radius is not removal.

## Public API Added

`ow_sim.collision` exports:

- `FleetRemovalReason`
- `FleetRemovalEvent`
- `fleet_hits_planet_path(fleet_old, fleet_new, planet_old, planet_new,
  planet_radius)`
- `fleet_hits_planet_on_tick(state, fleet, planet, dt=1)`
- `first_planet_hit_for_fleet_tick(state, fleet, dt=1)`
- `fleet_is_out_of_bounds_after_tick(fleet, dt=1)`
- `fleet_hits_sun_on_tick(fleet, dt=1)`
- `fleet_removal_event_for_tick(state, fleet, dt=1)`

`FleetRemovalReason` is a string-compatible enum with:

- `planet`
- `bounds`
- `sun`

`FleetRemovalEvent` is a frozen dataclass containing:

- `reason`
- `fleet_id`
- `planet_id`
- `old_position`
- `new_position`

## Tests And Fixtures Used

Tests are in `tests/test_collision_queries.py`.

Covered cases:

- Synthetic static-planet hit.
- Static-planet miss.
- Static-planet tangent/touch hit.
- Direct swept moving-planet path hit and miss.
- First hit follows `state.planets` order.
- Orbiting planet collision uses `planet_path_for_tick(...)`.
- Active comet interval can hit when `check_collision=True`.
- First-placement comet interval skips collision when `check_collision=False`.
- Missing comet metadata does not invent a hit.
- Out-of-bounds removal uses the new position.
- Board boundary endpoints are in bounds.
- Sun-crossing segment removes the fleet.
- Tangent sun segment does not remove the fleet.
- Planet hit takes priority over sun.
- Planet hit takes priority over bounds.
- Bounds removal returns before the sun check.
- Sun removal event reports the fleet segment when no planet or bounds removal
  applies.
- Invalid `dt=0` raises consistently for tick queries.
- Parsed fixture state is not mutated by collision queries.

The non-mutation fixture is:

- `tests/fixtures/kaggle_seed7_2p_step1_fleet.json`

## Assumptions Made

- `dt` for one-tick collision queries follows existing path-helper semantics:
  it must be an integer greater than or equal to `1`.
- If `planet_path_for_tick(...)` returns `None`, the collision layer returns no
  hit rather than inventing a path.
- Planet hit priority returns the first hit planet id in `state.planets` order,
  matching the official loop.
- Synthetic tests may place planets near the sun with matching initial metadata
  when orbit projection is required by Cycle 3 semantics.

## What Remains Deferred

- Combat resolution.
- Fleet removal mutation.
- Planet position mutation.
- Comet expiry mutation.
- Production.
- Ownership transfer.
- Ship-count updates.
- Full timelines.
- What-if simulation.
- Planner logic.
- Mission generation.
- Evaluation.
- Bot strategy.
- Kaggle submission bundling.

## Proposed Next Cycle

Cycle 8 should implement combat resolution as a pure query layer only:

1. Confirm official combat grouping and tie behavior from the local source.
2. Add pure helpers that resolve a planet plus arriving fleet rows into a
   post-combat owner/ship result without mutating `GameState`.
3. Cover same-owner reinforcement, neutral capture, enemy capture, multiple
   attackers, and tied attackers.
4. Keep production timelines, fleet removal mutation, what-if state insertion,
   mission generation, and planner behavior deferred.
