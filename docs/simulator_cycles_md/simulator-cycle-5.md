# Simulator Cycle 5

## What Was Created

- Added pure fleet speed and straight-line movement helpers to
  `ow_sim.forecast`.
- Preserved existing Cycle 3 and Cycle 4 planet/comet forecast behavior.
- Added a targeted official step-2 fleet fixture generated from the existing
  deterministic step-1 launch scenario.
- Added focused `unittest` coverage for speed formula values, invalid ship
  counts, cardinal movement, future positions, tick intervals, official fixture
  movement, and non-mutation.

## Evidence Sources Inspected

- Workspace docs:
  - `AGENTS.md`
  - `docs/competition-context.md`
  - `docs/simulator_cycles_md/simulator-cycle-0.md`
  - `docs/simulator_cycles_md/simulator-cycle-1.md`
  - `docs/simulator_cycles_md/simulator-cycle-2.md`
  - `docs/simulator_cycles_md/simulator-cycle-3.md`
  - `docs/simulator_cycles_md/simulator-cycle-4.md`
- Local official environment package:
  `/Users/user/dev/hackathons/orbit-wars-serious/.venv`
- Official interpreter source:
  `/Users/user/dev/hackathons/orbit-wars-serious/.venv/lib/python3.12/site-packages/kaggle_environments/envs/orbit_wars/orbit_wars.py`
- Official environment config and README:
  - `/Users/user/dev/hackathons/orbit-wars-serious/.venv/lib/python3.12/site-packages/kaggle_environments/envs/orbit_wars/orbit_wars.json`
  - `/Users/user/dev/hackathons/orbit-wars-serious/.venv/lib/python3.12/site-packages/kaggle_environments/envs/orbit_wars/README.md`
- Official deterministic fixtures:
  - `tests/fixtures/kaggle_seed7_2p_step1_fleet.json`
  - `tests/fixtures/kaggle_seed7_2p_step2_fleet.json`

## Official Fleet Speed Formula

The official interpreter computes speed from the number of ships in the fleet:

```text
speed = 1.0 + (max_speed - 1.0) * (log(ships) / log(1000)) ** 1.5
speed = min(speed, max_speed)
```

The default `max_speed` is `DEFAULT_MAX_FLEET_SPEED = 6.0`, confirmed from the
official `shipSpeed` config.

Cycle 5 rejects non-positive or non-integer ship counts with `ValueError`
before applying the logarithmic formula.

## Movement Semantics Implemented

The official interpreter advances each active fleet by one straight-line tick:

```text
x += cos(angle) * speed
y += sin(angle) * speed
```

Cycle 5 implements only this pure projection for already parsed `Fleet` rows.
The helpers do not mutate the `Fleet` or `GameState` objects passed to them.

The implemented semantics are:

- `fleet_position_after_ticks(fleet, dt)` returns the position after `dt`
  movement ticks from the fleet's current parsed position.
- `fleet_path_for_tick(fleet, dt=1)` returns the segment from `dt - 1` to `dt`.
- `dt=0` is valid for position projection and returns the current parsed
  position.
- `dt` must be an integer greater than or equal to `0` for position projection.
- `dt` must be an integer greater than or equal to `1` for path intervals.

## Public API Added

- `fleet_speed(ships, max_speed=DEFAULT_MAX_FLEET_SPEED)`
- `fleet_step_delta(angle, ships, max_speed=DEFAULT_MAX_FLEET_SPEED)`
- `fleet_position_after_ticks(fleet, dt, max_speed=DEFAULT_MAX_FLEET_SPEED)`
- `fleet_path_for_tick(fleet, dt=1, max_speed=DEFAULT_MAX_FLEET_SPEED)`

## Tests And Fixtures Used

Tests are in `tests/test_forecast_fleet_motion.py`.

Covered cases:

- Official speed formula values for representative ship counts.
- `ships = 1` speed equals `1.0`.
- Large fleet speed is capped at `DEFAULT_MAX_FLEET_SPEED`.
- Speed is monotonic for representative positive ship counts.
- Invalid ship counts raise `ValueError`.
- Cardinal angle movement covers right, up, left, and down.
- `fleet_position_after_ticks(...)` uses current position plus
  `dt * speed * direction`.
- `fleet_path_for_tick(...)` returns expected old/new positions for `dt=1` and
  `dt>1`.
- The parsed official step-1 fleet projects to the official step-2 fleet
  position.
- Helpers do not mutate parsed fleet or state data.

The step-2 fixture was generated with local official environment evidence:

```text
kaggle_environments.make("orbit_wars", configuration={"seed": 7}, debug=True)
```

The actions were the existing step-1 launch scenario followed by one idle tick.

## Assumptions Made

- `Fleet.angle` is the official heading in radians and remains constant for
  straight-line projection.
- `Fleet.ships` does not change during travel, matching the official README and
  interpreter movement block.
- Existing in-flight movement begins from the current parsed fleet position,
  not from the launch source.
- Launch start position was inspected in the official source, but launch
  spawning is intentionally not implemented in this cycle.
- Bounds removal, sun death, planet collision, swept moving-planet collision,
  and arrival/combat behavior are separate simulator layers and are not part of
  straight-line projection.

## What Remains Deferred

- Aiming.
- Launch command generation.
- Launch spawning as simulator state insertion.
- Arrival prediction.
- Planet/fleet collision resolution.
- Sun death.
- Out-of-bounds removal.
- Production.
- Combat.
- Timelines.
- What-if simulation.
- Mission generation.
- Evaluation.
- Bot logic.
- Kaggle submission bundling.

## Proposed Next Cycle

Cycle 6 should implement launch spawning / aiming / arrival prediction only if
those can stay a narrow standalone layer. Otherwise, collision resolution should
come next because fleet path segments now exist.

A conservative Cycle 6 launch/arrival scope would be:

1. Confirm legal launch sanitization and spawn position from the official source.
2. Add pure launch-spawn helper tests without planner decisions.
3. Add target-angle helper tests for point targets.
4. Add arrival-time estimation as a query helper, not as combat resolution.
5. Keep production, combat, timeline state mutation, mission generation, and
   evaluation deferred.
