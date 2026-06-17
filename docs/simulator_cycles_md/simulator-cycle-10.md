# Simulator Cycle 10

## What Was Created

- Extended `ow_sim.timeline` with pure one-tick state-delta fact helpers.
- Added frozen value objects for fleet movement/removal facts, planet
  movement/combat facts, and a combined one-tick delta.
- Added focused `unittest` coverage for fleet deltas, planet deltas, ordering,
  removal reasons, combat attachment, comet/static/orbiting planet paths,
  invalid `dt`, frozen result objects, and non-mutation.

Cycle 10 still does not build or apply a next `GameState`.

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
- Local official interpreter source:
  `/Users/user/dev/hackathons/orbit-wars-serious/.venv/lib/python3.12/site-packages/kaggle_environments/envs/orbit_wars/orbit_wars.py`

Official source sections rechecked:

- production before movement
- `planet_paths` construction
- comet path-index increment and expiry collection
- fleet movement
- planet, bounds, and sun removal ordering
- planet position application
- expired comet removal
- fleet removal
- combat resolution

## Official Timing Being Summarized

The official engine mutates state in this broad order:

1. Apply production.
2. Compute planet paths.
3. Move fleets and collect planet/bounds/sun removals.
4. Apply planet movement.
5. Remove expired comets.
6. Remove fleets.
7. Resolve combat.

Cycle 10 intentionally summarizes only movement/removal/combat facts from the
existing pure layers. Production, actual planet row mutation, comet expiry
removal, fleet list mutation, and next-observation assembly remain deferred.

## Public API Added

`ow_sim.timeline` now exports:

- `FleetTickDelta`
- `PlanetTickDelta`
- `OneTickStateDelta`
- `fleet_tick_deltas(state, dt=1)`
- `planet_tick_deltas(state, dt=1)`
- `one_tick_state_delta(state, dt=1)`

`FleetTickDelta` contains:

- `fleet_id`
- `old_position`
- `new_position`
- `removed`
- `removal_event`

`PlanetTickDelta` contains:

- `planet_id`
- `old_position`
- `new_position`
- `combat_result`
- `has_arrivals`

`OneTickStateDelta` contains:

- `fleet_deltas`
- `planet_deltas`
- `event_summary`

## Delta Semantics

Fleet deltas:

- Follow `state.fleets` order.
- Use `fleet_path_for_tick(...)` for old/new positions.
- Use Cycle 9's `one_tick_event_summary(...)` removal facts.
- Mark `removed=True` only when a Cycle 7 removal event exists.

Planet deltas:

- Follow `state.planets` order.
- Use `planet_path_for_tick(...)` for old/new positions.
- Set `new_position=None` when no trusted planet path can be projected.
- Attach `PlanetCombatResult` only when Cycle 9 reports arrivals for that
  planet.
- Set `has_arrivals=True` only when a combat result is attached.

Combined deltas:

- Include the exact `OneTickEventSummary` returned by Cycle 9 for the same
  state and `dt`.
- Are immutable value objects.
- Do not mutate `GameState`, `Planet`, `Fleet`, comet metadata, or raw
  observations.

## Tests Used

Tests are in `tests/test_timeline_deltas.py`.

Covered cases:

- No fleets still produce planet movement deltas.
- Active fleet deltas include old/new path facts and no removal event.
- Planet-hit removals are reflected in fleet deltas.
- Bounds and sun removals are reflected in fleet deltas.
- Fleet delta order follows `state.fleets`.
- Planet delta order follows `state.planets`.
- Static planet deltas keep stable old/new positions.
- Orbiting planet deltas use `planet_path_for_tick(...)`.
- Comet planet deltas use comet path semantics.
- Unprojectable planet paths set `new_position=None`.
- Combat results attach only to planets with arrivals.
- Combined deltas reuse the same event summary as `one_tick_event_summary(...)`.
- Invalid `dt=0` raises `ValueError`.
- Result dataclasses are frozen.
- Fixture-backed non-mutation for state, planets, fleets, comets, and raw
  observations.

## Assumptions Made

- `dt` follows existing timeline/collision semantics and must be an integer
  greater than or equal to `1`.
- Duplicate fleet ids are not expected in parsed official state; deltas are
  still returned in fleet tuple order.
- If `planet_path_for_tick(...)` cannot project a planet, the current parsed
  position is still a valid `old_position`, but `new_position` stays unknown.
- A planet can have arrivals only through Cycle 9 planet-hit events.

## What Remains Deferred

- Production deltas.
- Applying planet position changes to a new state.
- Fleet list removal mutation.
- Comet expiry mutation.
- Planet owner/ship mutation.
- Next `GameState` construction.
- Hypothetical launch insertion.
- Multi-tick timeline simulation.
- What-if state mutation.
- Planner logic.
- Mission generation.
- Evaluation.
- Bot strategy.
- Kaggle submission bundling.

## Proposed Next Cycle

Cycle 11 should implement applied one-tick next-state construction only after
reconfirming production, movement application, fleet removal, comet expiry, and
combat mutation order against the official interpreter. It should still avoid
planner, mission, evaluator, and bot logic.
