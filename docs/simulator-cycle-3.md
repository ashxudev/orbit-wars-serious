# Simulator Cycle 3

## What Was Created

- Implemented non-comet planet motion helpers in `ow_sim.forecast`.
- Added tests for static planets, orbiting planets, boundary classification,
  observation-step indexing, one-tick path intervals, comet deferral, and
  missing `initial_planets`.
- Reused existing deterministic official fixtures from Cycle 1. No broad replay
  dumps were added.

## Evidence Sources Inspected

- Workspace docs:
  - `AGENTS.md`
  - `docs/competition-context.md`
  - `docs/simulator-cycle-0.md`
  - `docs/simulator-cycle-1.md`
  - `docs/simulator-cycle-2.md`
- Local official environment package:
  `/Users/user/dev/hackathons/orbit-wars-serious/.venv`
- Official interpreter source:
  `/Users/user/dev/hackathons/orbit-wars-serious/.venv/lib/python3.12/site-packages/kaggle_environments/envs/orbit_wars/orbit_wars.py`
- Official deterministic observations:
  - `tests/fixtures/kaggle_seed7_2p_step0.json`
  - `tests/fixtures/kaggle_seed7_2p_step50_comet.json`

## Official Planet-Motion Rule Implemented

The official interpreter computes non-comet planet end-of-tick positions from:

- the matching row in `initial_planets`
- `angular_velocity`
- the sun center `(50, 50)`
- the planet radius
- `ROTATION_RADIUS_LIMIT = 50`

For a non-comet planet, the official rule is:

```text
orbital_radius = distance(initial_position, SUN_CENTER)
orbiting = orbital_radius + planet_radius < ROTATION_RADIUS_LIMIT
current_angle = initial_angle + angular_velocity * interpreter_step
```

Static planets keep their current/static position. Orbiting planets are
projected from their initial position, not by accumulating drift from the
current position.

## Public API Added

- `is_orbiting_planet(planet)`
- `planet_orbit_radius(initial_planet)`
- `planet_initial_angle(initial_planet)`
- `planet_position_at_step(state, planet_id, step)`
- `planet_position_after_ticks(state, planet_id, dt)`
- `planet_path_for_tick(state, planet_id, dt=1)`

All helpers are pure and deterministic. They do not mutate `GameState` or any
contained `Planet`.

## Step-Index Semantics

The official interpreter computes the next position during a tick using the
current observation's `step` value. The Kaggle framework then exposes that
position in the following observation.

Generated deterministic observations confirm this mapping:

- Observation step `0` is the initial planet position.
- Observation step `1` is still the initial planet position.
- Observation step `N > 0` corresponds to the official angle offset
  `angular_velocity * (N - 1)`.

Accordingly, `planet_position_at_step(state, planet_id, step)` returns the
position for an observation step, not an internal interpreter call.

`planet_position_after_ticks(state, planet_id, dt)` returns the position at:

```text
state.step + dt
```

`planet_path_for_tick(state, planet_id, dt=1)` returns:

```text
(
  position_at_step(state.step + dt - 1),
  position_at_step(state.step + dt),
)
```

This matches the old/new position concept needed later for swept collision
checks while still avoiding collision behavior in Cycle 3.

## Tests And Fixtures Used

Tests are in `tests/test_forecast_planet_motion.py`.

Covered cases:

- Static non-comet planet stays fixed across future observation steps.
- Orbiting planet at step 0 equals its initial position.
- Orbiting planet at step 50 matches the deterministic official fixture.
- Orbit radius remains constant for an orbiting planet.
- Boundary classification uses strict
  `orbital_radius + planet_radius < ROTATION_RADIUS_LIMIT`.
- `planet_position_after_ticks` uses `state.step + dt`.
- `planet_path_for_tick` returns old/new positions for one future tick.
- Comet planets return `None`.
- Missing `initial_planets` does not crash.

## Assumptions Made

- `Planet.initial_position`, populated by the Cycle 1 parser from
  `initial_planets`, is the preferred classification source.
- If a planet has no matching initial row and is provably static from its
  current position, returning the current position is acceptable because no
  future motion needs to be invented.
- If a planet has no matching initial row and appears orbiting from its current
  position, projection returns `None` because the initial angle cannot be
  trusted.
- If `angular_velocity` is missing for an orbiting planet, projection returns
  `None`.

## Comet Handling Decision

Comet planets are explicitly deferred. They are present in `planets`, but their
motion uses `comets[].paths` and `path_index`, not the non-comet orbit rule.

Cycle 3 forecast helpers return `None` for comet planets so Cycle 4 can add
temporary-planet motion without changing this API shape.

## What Remains Deferred

- Comet / temporary planet motion.
- Fleet speed formula.
- Fleet movement.
- Aiming.
- Arrival prediction.
- Simulator collision resolution.
- Production.
- Combat.
- Timelines.
- What-if simulation.
- Mission generation.
- Evaluation.
- Bot logic.
- Kaggle submission bundling.

## Proposed Next Cycle

Cycle 4 should implement comet / temporary planet motion only:

1. Parse and validate `comets[].planet_ids`, `paths`, and `path_index` behavior.
2. Project comet positions from official path indices.
3. Handle first placement, active path movement, and expiry semantics.
4. Add tests against deterministic official observations around comet spawn and
   expiry.
5. Keep fleet movement, production, combat, timelines, and planning out of
   Cycle 4.
