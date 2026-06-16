# Simulator Cycle 9

## What Was Created

- Replaced the Cycle 0 `ow_sim.timeline` placeholder with pure one-tick
  event-summary helpers.
- Integrated Cycle 7 fleet removal events with Cycle 8 planet combat results.
- Added frozen result dataclasses for planet arrival combat events and one-tick
  event summaries.
- Added focused `unittest` coverage for removal grouping, planet arrivals,
  combat summaries, event ordering, invalid `dt`, skipped missing planets, and
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
  - `docs/simulator-cycle-6.md`
  - `docs/simulator-cycle-7.md`
  - `docs/simulator-cycle-8.md`
- Local official interpreter source:
  `/Users/user/dev/hackathons/orbit-wars-serious/.venv/lib/python3.12/site-packages/kaggle_environments/envs/orbit_wars/orbit_wars.py`

Official source sections inspected:

- fleet movement loop
- planet/bounds/sun removal ordering
- `combat_lists = {p[0]: [] for p in obs0.planets}`
- appending planet-hit fleets into `combat_lists[planet_id]`
- `fleets_to_remove`
- combat resolution after all movement/removal checks

## Official Combat-List Grouping Behavior

The official interpreter initializes combat groups in planet order:

```text
combat_lists = {p[0]: [] for p in obs0.planets}
```

During fleet movement, only planet-hit removals append to those groups:

```text
combat_lists[planet[0]].append(fleet)
```

Bounds removals and sun removals are removed from the fleet list but do not
participate in planet combat.

Cycle 9 mirrors these facts as returned summaries only. It does not remove
fleets or mutate planets.

## Removal-Event Grouping Semantics

Cycle 9 calls:

```text
fleet_removal_event_for_tick(state, fleet, dt)
```

for each fleet in `state.fleets`, preserving fleet iteration order.

All removal events are included in `OneTickEventSummary.removal_events`.
Only `FleetRemovalReason.PLANET` events become planet arrivals.

The summary also exposes convenience tuples:

- `bounds_fleet_ids`
- `sun_fleet_ids`

These are reporting aids only; they are not state mutation.

## Planet Arrival Ordering

Within each planet group, arriving fleets stay in `state.fleets` order.

Planet combat events are emitted in `state.planets` order, matching official
`combat_lists` insertion order. If a planet id appears in a removal event but
that id is not present in `state.planets`, Cycle 9 skips combat for that id
rather than inventing a planet.

## Cycle 7 And Cycle 8 Integration

Cycle 9 depends on existing source-faithful layers:

- Collision/removal facts come from `ow_sim.collision`.
- Planet combat results come from `ow_sim.combat.resolve_planet_combat(...)`.

It does not reimplement collision detection or combat resolution.

## Public API Added

`ow_sim.timeline` exports:

- `PlanetArrivalCombatEvent`
- `OneTickEventSummary`
- `fleet_removal_events_for_tick(state, dt=1)`
- `planet_arrival_fleets_for_tick(state, dt=1)`
- `planet_arrival_combat_events_for_tick(state, dt=1)`
- `one_tick_event_summary(state, dt=1)`

`PlanetArrivalCombatEvent` contains:

- `planet_id`
- `fleet_ids`
- `fleets`
- `combat_result`

`OneTickEventSummary` contains:

- `removal_events`
- `planet_arrivals`
- `bounds_fleet_ids`
- `sun_fleet_ids`

## Tests Used

Tests are in `tests/test_timeline_events.py`.

Covered cases:

- No fleets produces empty event summaries.
- A fleet hitting a planet appears in removal events and planet arrivals.
- Multiple fleets hitting the same planet are grouped together.
- Arrival fleet order follows `state.fleets`.
- Combat result is produced from grouped arrivals.
- Tied attackers produce an unchanged planet combat result.
- Bounds removal appears in removal events but not planet arrivals.
- Sun removal appears in removal events but not planet arrivals.
- Mixed planet/bounds/sun events are separated correctly.
- Planet combat events are emitted in `state.planets` order, not fleet-hit
  order.
- Missing planet ids in removal events are skipped for combat.
- Invalid `dt=0` raises `ValueError`.
- Helpers do not mutate parsed fixture state, planets, fleets, or raw
  observations.

The non-mutation fixture is:

- `tests/fixtures/kaggle_seed7_2p_step1_fleet.json`

## Assumptions Made

- `dt` must be an integer greater than or equal to `1`, matching existing
  collision/path helper semantics.
- This layer summarizes existing parsed fleets only. It does not insert
  hypothetical launch fleets.
- Summary combat results are predicted facts, not applied planet row updates.
- Bounds and sun removals are useful to report but are intentionally excluded
  from planet combat.
- Missing planet ids should not happen through the real Cycle 7 collision path,
  but the public combat-event helper still skips them defensively.

## What Remains Deferred

- GameState mutation.
- Fleet removal mutation.
- Planet row mutation.
- Production.
- Planet movement mutation.
- Comet expiry mutation.
- Hypothetical launch insertion.
- Full timeline simulation beyond one-tick summaries.
- What-if state mutation.
- Planner logic.
- Mission generation.
- Evaluation.
- Bot strategy.
- Kaggle submission bundling.

## Proposed Next Cycle

Cycle 10 should implement one-tick pure state-delta projection without mutating
the parsed `GameState`:

1. Represent fleet removals, planet movement facts, and combat result facts as
   immutable deltas.
2. Keep production and comet expiry separate unless the source timing is
   reverified.
3. Preserve a clear distinction between returned facts and applied mutable
   state.
4. Continue deferring hypothetical launches, multi-tick timelines, mission
   generation, and planner behavior.
