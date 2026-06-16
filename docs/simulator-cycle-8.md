# Simulator Cycle 8

## What Was Created

- Replaced the Cycle 0 `ow_sim.combat` placeholder with pure combat resolution
  query helpers.
- Added frozen result dataclasses for incoming fleet combat and planet combat.
- Added focused `unittest` coverage for fleet-owner aggregation,
  top-vs-second survivor behavior, planet reinforcement, damage, capture,
  exact-zero defense, attacker ties, multi-owner official behavior, and
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
- Local official interpreter source:
  `/Users/user/dev/hackathons/orbit-wars-serious/.venv/lib/python3.12/site-packages/kaggle_environments/envs/orbit_wars/orbit_wars.py`

The inspected official combat block starts after fleet removal. Its input is
already grouped as `combat_lists[planet_id] = [fleets_that_hit_planet]`.

## Official Fleet-Owner Aggregation Rule

Incoming fleets are summed by owner before resolving fleet-vs-fleet combat:

```text
player_ships[owner] += fleet.ships
```

Cycle 8 exposes this through:

```text
fleet_ships_by_owner(fleets)
```

## Top-Vs-Second Survivor Rule

The official interpreter sorts owner totals descending and compares only the
largest and second-largest totals:

- If there is only one fleet owner, that owner's full total survives.
- If the top two totals tie, no incoming fleet force survives.
- Otherwise, the top owner survives with `top_ships - second_ships`.
- Third and later owners do not further reduce the survivor.

Cycle 8 exposes this through:

```text
resolve_fleet_combat(fleets)
```

The result is `FleetCombatWinner(owner, ships)`, where `owner=None` and
`ships=0` represents no surviving incoming fleet force.

## Planet Combat Semantics

After fleet-owner combat, the surviving incoming force is applied to the
planet:

- No survivor leaves the planet unchanged.
- If the survivor owner already owns the planet, surviving ships are added to
  the planet garrison.
- If the survivor owner does not own the planet, surviving ships subtract from
  the planet garrison.
- Ownership changes only if subtraction makes the planet ship count strictly
  negative.
- If subtraction reaches exactly zero, the existing planet owner remains and
  ships become zero.
- On capture, the new garrison is the absolute overkill amount.

Cycle 8 exposes this through:

```text
resolve_planet_combat(planet, fleets)
```

The result is `PlanetCombatResult(owner, ships, winner_owner, winner_ships)`.

## Public API Added

`ow_sim.combat` exports:

- `FleetCombatWinner`
- `PlanetCombatResult`
- `fleet_ships_by_owner(fleets)`
- `resolve_fleet_combat(fleets)`
- `resolve_planet_combat(planet, fleets)`

All helpers are pure. They do not mutate `Planet`, `Fleet`, `GameState`, raw
tuple fields, or input sequences.

## Tests Used

Tests are in `tests/test_combat_resolution.py`.

Covered cases:

- Fleet aggregation for one fleet.
- Fleet aggregation for multiple fleets from the same owner.
- Fleet aggregation for multiple owners.
- Fleet combat with no fleets.
- Fleet combat with one owner.
- Fleet combat with two owners and a clear winner.
- Fleet combat with two tied owners.
- Fleet combat with three owners where the third owner is ignored by the
  official top-minus-second rule.
- Fleet combat with a three-owner top tie.
- Planet combat with no arrivals.
- Same-owner reinforcement.
- Neutral planet capture.
- Enemy damage without capture.
- Enemy attack that exactly reduces ships to zero and preserves owner.
- Enemy capture with overkill amount.
- Tied attackers leaving the planet unchanged.
- Multi-owner survivor reinforcement.
- Multi-owner survivor capture.
- Non-mutation of planets, fleets, and raw tuple fields.

## Assumptions Made

- `resolve_planet_combat(...)` receives fleets that have already hit the planet.
  Collision detection and fleet removal are Cycle 7 concerns.
- The official source uses normal Python sort order for descending ship totals.
  Tied top totals intentionally produce no survivor, so tie ordering does not
  affect the public result.
- `FleetCombatWinner.owner=None` is clearer for a pure API than the official
  temporary internal `-1` owner used when survivor ships are zero.
- Parsed fleet ship counts are trusted as integer values from `GameState`.

## What Remains Deferred

- Fleet removal mutation.
- Planet row mutation.
- GameState mutation.
- Production.
- Combat integration with collision events.
- Ownership and ship-count timeline simulation.
- What-if state insertion.
- Comet expiry mutation.
- Planner logic.
- Mission generation.
- Evaluation.
- Bot strategy.
- Kaggle submission bundling.

## Proposed Next Cycle

Cycle 9 should integrate collision events and combat results as pure event
queries without mutating `GameState`:

1. Confirm how to group `FleetRemovalEvent(reason=planet)` events by planet id.
2. Build pure arrival/combat event summaries from existing fleets for one tick.
3. Return predicted post-combat planet facts without changing parsed state.
4. Keep production, timelines, hypothetical launches, and planner behavior
   deferred until event grouping is source-faithful and tested.
