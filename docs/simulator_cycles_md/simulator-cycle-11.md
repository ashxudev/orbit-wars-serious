# Simulator Cycle 11

## What Was Created

- Extended `ow_sim.timeline` with pure one-tick next-state construction for
  existing parsed state.
- Added public helpers for applying production, planet position updates, planet
  combat results, and comet path-index advancement.
- Added focused `unittest` coverage for production, planet movement, fleet
  movement/removal, combat application, comet expiry, metadata preservation,
  non-mutation, unsupported `dt`, and a narrow official fixture transition.

Cycle 11 returns a new `GameState`. It does not mutate the input state or add
launch/planner behavior.

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
  - `docs/simulator_cycles_md/simulator-cycle-7.md`
  - `docs/simulator_cycles_md/simulator-cycle-8.md`
  - `docs/simulator_cycles_md/simulator-cycle-9.md`
  - `docs/simulator_cycles_md/simulator-cycle-10.md`
- Local official interpreter source:
  `/Users/user/dev/hackathons/orbit-wars-serious/.venv/lib/python3.12/site-packages/kaggle_environments/envs/orbit_wars/orbit_wars.py`

Official source sections inspected:

- `process_moves(...)` launch handling, to keep actions out of scope.
- Pre-action expired-comet cleanup.
- Comet spawning, to keep new comet generation out of scope.
- Owned-planet production.
- `planet_paths` construction.
- Comet `path_index` increment and expiry collection.
- Fleet movement and planet/bounds/sun removal order.
- Planet movement application.
- Expired comet removal from planets, initial planets, comet ids, and groups.
- Fleet list removal.
- Combat resolution.
- Observation fields copied to other agents.

## Official Mutation Order Implemented

`next_game_state_after_tick(state, dt=1)` applies this one-tick order:

1. Compute fleet removal and planet-arrival facts from the input state.
2. Determine comet ids whose next path index expires this tick.
3. Apply production to owned planets.
4. Apply planet path end positions where projection is trusted.
5. Remove expired comet planets and their related metadata.
6. Remove fleets with planet, bounds, or sun removal events.
7. Resolve combat against the remaining produced/moved planets.
8. Return a new `GameState` with `tick + 1` when `tick` is known.

This mirrors the official order for the implemented existing-state subset.
Action processing and comet spawning happen in the official interpreter before
production, but they remain deferred here.

## Public API Added

`ow_sim.timeline` now exports:

- `produce_planet(planet)`
- `apply_planet_position(planet, position)`
- `apply_planet_combat_result(planet, result)`
- `advance_comet_groups(state, expired_planet_ids)`
- `next_game_state_after_tick(state, dt=1)`

## Production Semantics

`produce_planet(...)` adds `production` ships only when `planet.owner != -1`.
Neutral planets do not produce. Production happens before movement and before
combat, so arriving fleets fight the produced garrison.

## Planet And Fleet Movement

Planet movement uses `planet_path_for_tick(...)`. If no trusted path is
available, the planet keeps its current position.

Fleet movement uses `fleet_path_for_tick(...)`. Fleets that are not removed are
returned as new `Fleet` objects at their one-tick end position. Removed fleets
are absent from the returned state.

## Fleet Removal Semantics

Fleet removal facts come from the Cycle 7/9 removal grouping:

- planet collision first
- out-of-bounds second
- sun collision third

Planet-hit fleets are grouped by planet for later combat. Bounds and sun
removals do not participate in combat.

## Comet Expiry Semantics

Comet groups advance `path_index` by one. If a comet planet's next path index
is beyond its path length, that planet id is removed from:

- `planets`
- `initial_planets`
- `comet_planet_ids`
- `comets`

The pure `CometGroup` result filters paths together with planet ids to preserve
the workspace invariant that ids and paths use matching slots. Official groups
are generated with same-length paths, so this does not change observed local
fixtures while keeping parsed metadata usable.

Expired comets are removed before combat is applied. If a fleet collides with a
comet during its expiry interval, the fleet is still removed, but no planet
combat is applied because the planet no longer exists in the returned state.

## Combat Application

Combat is resolved with `resolve_planet_combat(...)` against the produced and
moved planet, not the original input planet. The resulting owner and ships are
applied through `apply_planet_combat_result(...)`.

Exact-zero defense preserves the current owner with zero ships. Tied attackers
leave the produced planet unchanged.

## Raw Observation Handling

Returned `GameState.raw_observation` is `None`. Cycle 11 constructs a semantic
next state, not a source-backed observation dictionary. New `Planet`, `Fleet`,
and `CometGroup` objects keep row-shaped `raw` fields for local debugging and
tests.

## Tests Used

Tests are in `tests/test_timeline_next_state.py`.

Covered cases:

- Empty state returns a new `GameState` and does not mutate input.
- Known ticks increment by one.
- Owned planets produce.
- Neutral planets do not produce.
- Static planet positions are preserved.
- Orbiting planet positions advance through `planet_path_for_tick(...)`.
- Active fleets move and remain present.
- Planet-hit, bounds-removed, and sun-removed fleets are removed.
- Combat capture updates returned owner and ships.
- Same-owner arrivals reinforce after production.
- Exact-zero combat preserves owner with zero ships.
- Tied attackers leave only the produced garrison.
- Expired comet planets are removed from planets and comet metadata before
  combat.
- First-placement comets advance metadata and remain present.
- Changed planets and moved fleets are new dataclass instances.
- Fixture state, planets, fleets, comets, and raw observations are not mutated.
- Existing official step-1 to step-2 idle fixture matches the returned next
  state.
- Unsupported `dt=0` and `dt=2` raise `ValueError`.
- Public mutation helpers preserve row-shaped `raw` fields.

## Assumptions Made

- `next_game_state_after_tick(...)` supports only `dt=1`; multi-tick mutation
  must be built as a later layer after each intermediate timing rule is
  validated.
- Existing parsed state has unique official fleet ids.
- New comet spawning is excluded because it depends on hidden episode seed
  state that is not present in agent observations.
- Already-malformed comet metadata is advanced conservatively; missing path
  slots are not used to invent expiry or movement.
- `remaining_overage_time` is preserved because simulator projection does not
  model runtime accounting.

## What Remains Deferred

- Action processing.
- Hypothetical launch insertion.
- New comet spawning.
- Multi-tick timeline simulation.
- What-if branching.
- Production deltas as separate report objects.
- Termination/reward calculation.
- Planner logic.
- Mission generation.
- Evaluation.
- Bot strategy.
- Kaggle submission bundling.

## Proposed Next Cycle

Cycle 12 should build a narrow multi-tick timeline wrapper around
`next_game_state_after_tick(...)`, stopping short of what-if branching and
planner logic. It should validate repeated one-tick application against a small
number of deterministic official idle transitions before adding hypothetical
launch insertion.
