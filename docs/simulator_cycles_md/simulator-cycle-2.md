# Simulator Cycle 2

## What Was Created

- Updated `ow_sim.constants` with constants confirmed from the local official
  `kaggle-environments==1.30.1` package.
- Updated `ow_sim.geometry` with pure deterministic geometry helpers for later
  planet motion, fleet motion, collision, and timeline cycles.
- Added focused `unittest` coverage for confirmed constants and geometry edge
  cases.
- Preserved the existing `distance((x, y), (x, y))` helper behavior from
  Cycle 0.

## Evidence Sources Inspected

- Local package installation:
  `/Users/user/dev/hackathons/orbit-wars-serious/.venv`
- Packaged environment schema:
  `/Users/user/dev/hackathons/orbit-wars-serious/.venv/lib/python3.12/site-packages/kaggle_environments/envs/orbit_wars/orbit_wars.json`
- Packaged environment README:
  `/Users/user/dev/hackathons/orbit-wars-serious/.venv/lib/python3.12/site-packages/kaggle_environments/envs/orbit_wars/README.md`
- Packaged environment source:
  `/Users/user/dev/hackathons/orbit-wars-serious/.venv/lib/python3.12/site-packages/kaggle_environments/envs/orbit_wars/orbit_wars.py`
- Existing workspace docs:
  `AGENTS.md`, `docs/competition-context.md`,
  `docs/simulator_cycles_md/simulator-cycle-0.md`, and `docs/simulator_cycles_md/simulator-cycle-1.md`

## Constants Confirmed

Confirmed from the official source or packaged environment config:

- `BOARD_MIN = 0.0`
- `BOARD_SIZE = 100.0`
- `BOARD_MAX = 100.0`
- `SUN_CENTER = (50.0, 50.0)`
- `SUN_RADIUS = 10.0`
- `ROTATION_RADIUS_LIMIT = 50.0`
- `DEFAULT_EPISODE_STEPS = 500`
- `FINAL_INTERPRETER_STEP = 498`
- `DEFAULT_MAX_FLEET_SPEED = 6.0`
- `DEFAULT_COMET_SPEED = 4.0`
- `COMET_RADIUS = 1.0`
- `COMET_PRODUCTION = 1`
- `PLANET_CLEARANCE = 7.0`
- `MIN_PLANET_GROUPS = 5`
- `MAX_PLANET_GROUPS = 10`
- `MIN_STATIC_GROUPS = 3`
- `COMET_SPAWN_STEPS = (50, 150, 250, 350, 450)`

The only non-engine value added is `GEOMETRY_ABS_TOL = 1e-9`, a local test
tolerance used for deterministic floating-point assertions.

## Geometry Helpers Implemented

- `distance(a, b)`
- `distance_xy(ax, ay, bx, by)`
- `clamp(value, lower, upper)`
- `angle_between(a, b)`
- `vector_from_angle(angle, magnitude=1.0)`
- `point_to_segment_distance(point, start, end)`
- `segment_circle_intersects(start, end, center, radius)`
- `segment_hits_sun(start, end, center=SUN_CENTER, radius=SUN_RADIUS)`
- `swept_circle_intersects(moving_point_start, moving_point_end,
  circle_center_start, circle_center_end, radius)`
- `is_orbiting_position(position, radius, center=SUN_CENTER,
  rotation_radius_limit=ROTATION_RADIUS_LIMIT)`
- `is_static_position(position, radius, center=SUN_CENTER,
  rotation_radius_limit=ROTATION_RADIUS_LIMIT)`

These helpers are pure functions. They do not mutate inputs, do not depend on
`GameState`, and do not advance any game object.

## Edge Cases Tested

- Constants match the official local environment source and JSON config.
- Existing 3-4-5 `distance` behavior still works.
- Explicit x/y distance works for a 3-4-5 triangle.
- Cardinal angle and vector helpers match right, down, left, and up directions.
- Point-to-segment distance covers:
  - point on segment
  - point beyond an endpoint
  - vertical segment
  - horizontal segment
- Segment-circle intersection covers:
  - direct hit
  - miss
  - tangent contact
- Sun hit helper uses the confirmed sun center and radius and mirrors the
  official strict sun-radius check.
- Swept circle helper covers:
  - stationary hit
  - stationary miss
  - moving chord hit
  - parallel miss
- Orbit/static classification uses the confirmed `orbital_radius + radius < 50`
  threshold without projecting positions.

## Assumptions Made

- `BOARD_MIN` and `BOARD_MAX` are derived from the official `BOARD_SIZE` and
  source checks that use inclusive coordinates from `0` through `BOARD_SIZE`.
- `FINAL_INTERPRETER_STEP` is derived from the official interpreter condition
  `step >= configuration.episodeSteps - 2`; it is documented as an interpreter
  reward-evaluation boundary, not as planner behavior.
- `segment_circle_intersects` treats tangent contact as intersection because it
  is a mathematical geometry helper. `segment_hits_sun` separately mirrors the
  official strict `< SUN_RADIUS` fleet-removal check.

## What Remains Deferred

- Planet position projection.
- Comet position projection.
- Fleet speed formula.
- Fleet movement.
- Aiming.
- Arrival prediction.
- Collision resolution as simulator behavior.
- Production.
- Combat.
- Timelines.
- What-if simulation.
- Mission generation.
- Evaluation.
- Bot logic.
- Kaggle submission bundling.

## Proposed Next Cycle

Cycle 3 should implement planet motion only:

1. Use parsed `initial_planets`, `angular_velocity`, and confirmed constants.
2. Classify planets as rotating or static using the Cycle 2 geometry helper.
3. Project current/future planet positions for non-comet planets.
4. Add tests against deterministic official observations for static planets,
   rotating planets, boundary classification, and step-index behavior.
5. Keep fleet movement, comets, production, combat, timelines, and planning out
   of Cycle 3.
