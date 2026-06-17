# Simulator Cycle 4

## What Was Created

- Added comet / temporary planet path-index projection to `ow_sim.forecast`.
- Preserved the Cycle 3 non-comet planet-motion APIs and behavior.
- Integrated comet handling into the generic planet forecast helpers when comet
  metadata is available.
- Added targeted official fixtures for the next active comet observation and
  post-expiry observation.
- Added focused `unittest` coverage for current, future, first-placement,
  active interval, expiry, generic helper, and missing metadata behavior.

## Evidence Sources Inspected

- Workspace docs:
  - `AGENTS.md`
  - `docs/competition-context.md`
  - `docs/simulator_cycles_md/simulator-cycle-0.md`
  - `docs/simulator_cycles_md/simulator-cycle-1.md`
  - `docs/simulator_cycles_md/simulator-cycle-2.md`
  - `docs/simulator_cycles_md/simulator-cycle-3.md`
- Local official environment package:
  `/Users/user/dev/hackathons/orbit-wars-serious/.venv`
- Official interpreter source:
  `/Users/user/dev/hackathons/orbit-wars-serious/.venv/lib/python3.12/site-packages/kaggle_environments/envs/orbit_wars/orbit_wars.py`
- Official deterministic fixtures:
  - `tests/fixtures/kaggle_seed7_2p_step50_comet.json`
  - `tests/fixtures/kaggle_seed7_2p_step51_comet.json`
  - `tests/fixtures/kaggle_seed7_2p_step82_post_comet.json`

## Official Comet-Motion Rule

The official interpreter stores comet metadata in groups:

```text
{
  "planet_ids": [...],
  "paths": [[(x, y), ...], ...],
  "path_index": int
}
```

Each comet planet id maps to the same slot in `planet_ids` and `paths`.
Movement is driven by `path_index`, not by orbital rotation:

```text
current_position = paths[slot][path_index]
future_position_after_dt = paths[slot][path_index + dt]
```

If the requested path index is outside the path, position helpers return
`None`.

## Path-Index Semantics

- At spawn, the official interpreter creates the group with `path_index = -1`
  and comet planets at an off-board placeholder position `(-99, -99)`.
- During the same interpreter tick, it increments to `path_index = 0` and moves
  the comet planet to `paths[slot][0]`.
- In generated observations, the first visible comet observation has
  `path_index = 0` and the planet's position equals `paths[slot][0]`.
- Subsequent observations advance by one path index per tick.
- When the next path index is beyond the path length, the comet expires.

## First-Placement Behavior

For the first placement interval, official `planet_paths` use:

```text
old_position = (-99, -99)
new_position = paths[slot][0]
check_collision = False
```

Cycle 4 exposes this through `comet_path_for_tick(...)` when a state represents
the source-backed pre-placement shape with `path_index = -1`.

## Expiry Behavior

Position helpers treat expiry as absent:

- `comet_position_at_path_index(...)` returns `None` outside the path.
- `comet_position_after_ticks(...)` returns `None` when `path_index + dt` is
  outside the path.
- `planet_position_at_step(...)` and `planet_position_after_ticks(...)` also
  return `None` for expired comet positions.

The one-tick path helper mirrors the official expiry interval:

```text
old_position = last valid path point
new_position = last valid path point
check_collision = True
```

After expiry, official observations no longer include the comet planet or its
group metadata.

## Public API Added Or Changed

Added:

- `comet_group_for_planet(state, planet_id)`
- `comet_position_at_path_index(state, planet_id, path_index)`
- `comet_position_after_ticks(state, planet_id, dt)`
- `comet_path_for_tick(state, planet_id, dt=1)`

Changed:

- `planet_position_at_step(...)` now supports comet planets by translating
  observation-step deltas into path-index deltas.
- `planet_position_after_ticks(...)` now supports comet planets.
- `planet_path_for_tick(...)` keeps the existing two-item non-comet return and
  returns a three-item comet tuple `(old_position, new_position,
  check_collision)`.

If a planet is marked as a comet but no matching group/path metadata exists, all
comet forecast helpers return `None`.

## Tests And Fixtures Used

Tests are in:

- `tests/test_forecast_comet_motion.py`
- `tests/test_forecast_planet_motion.py`

Covered cases:

- Current comet position equals `paths[slot][path_index]`.
- Future comet position advances by `path_index + dt`.
- Step 51 official observation matches projection from step 50.
- Expiry position returns `None` beyond the path length.
- Post-expiry official observation has no comet projection.
- First placement returns off-board old position, first path point, and
  `check_collision = False`.
- Active comet intervals return path old/new positions and
  `check_collision = True`.
- Expiry intervals stay at the last path point and check collisions.
- Generic helpers handle both non-comet and comet planets.
- Missing comet groups or missing path slots fail safely with `None`.

## Assumptions Made

- The path slot is the index where `planet_id` appears in
  `CometGroup.planet_ids`.
- Official observations are internally consistent: visible comet planet
  positions match their path at `path_index`.
- Source-backed first-placement behavior cannot be observed directly by an
  agent because it happens inside the spawn interpreter tick, so the test uses a
  small synthetic state shaped from the official spawn code and deterministic
  fixture path.
- The generic `planet_path_for_tick(...)` return shape is intentionally wider
  for comets so callers can see the official collision-check flag without
  changing non-comet behavior.

## What Remains Deferred

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

Cycle 5 should implement fleet speed + fleet movement only:

1. Confirm the official fleet speed formula from the local source and tests.
2. Add pure speed tests for size boundaries and default max speed.
3. Add pure fleet one-tick movement helpers using parsed `Fleet` rows.
4. Validate movement against deterministic official observations with simple
   launches.
5. Keep aiming, arrivals, collision resolution, production, combat, timelines,
   and planning out of Cycle 5.
