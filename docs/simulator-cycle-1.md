# Simulator Cycle 1

## What Was Created

- Added `GameState.from_obs(obs)` in `ow_sim.state`.
- Replaced provisional state placeholders with schema-backed dataclasses:
  `Planet`, `Fleet`, `CometGroup`, and `GameState`.
- Added small official observation fixtures under `tests/fixtures/`.
- Added parser tests for normal observations, empty fleets, missing optional
  fields, fleet rows, two-player and four-player shapes, comet metadata,
  angular and initial-planet fields, non-mutation, and invalid row length.
- Created a local project `.venv` and installed `kaggle-environments==1.30.1`
  there for evidence generation. The `.venv` is intentionally ignored.

## Evidence Sources Inspected

- Local package installation:
  `/Users/user/dev/hackathons/orbit-wars-serious/.venv`
- Installed package version:
  `kaggle-environments==1.30.1`
- Packaged environment schema:
  `/Users/user/dev/hackathons/orbit-wars-serious/.venv/lib/python3.12/site-packages/kaggle_environments/envs/orbit_wars/orbit_wars.json`
- Packaged environment README:
  `/Users/user/dev/hackathons/orbit-wars-serious/.venv/lib/python3.12/site-packages/kaggle_environments/envs/orbit_wars/README.md`
- Packaged environment source:
  `/Users/user/dev/hackathons/orbit-wars-serious/.venv/lib/python3.12/site-packages/kaggle_environments/envs/orbit_wars/orbit_wars.py`
- Packaged environment tests:
  `/Users/user/dev/hackathons/orbit-wars-serious/.venv/lib/python3.12/site-packages/kaggle_environments/envs/orbit_wars/test_orbit_wars.py`
- Deterministic local observations generated with:
  `kaggle_environments.make("orbit_wars", configuration={"seed": 7}, debug=True)`

## Fixture Observations

- `tests/fixtures/kaggle_seed7_2p_step0.json`
  - Official reset observation for a two-player game.
- `tests/fixtures/kaggle_seed7_4p_step0.json`
  - Official reset observation for a four-player game.
- `tests/fixtures/kaggle_seed7_2p_step1_fleet.json`
  - Official two-player observation after player 0 launches one fleet.
- `tests/fixtures/kaggle_seed7_2p_step50_comet.json`
  - Official two-player idle observation at first comet spawn.

## Confirmed Top-Level Observation Keys

The local package schema and generated observations confirm these keys:

- `planets`
- `fleets`
- `player`
- `step`
- `angular_velocity`
- `initial_planets`
- `next_fleet_id`
- `comets`
- `comet_planet_ids`
- `remainingOverageTime`

The parser treats these as the confirmed Cycle 1 observation surface. Missing
optional keys default to empty containers or `None` rather than crashing.

## Confirmed Planet Fields

Official planet row format:

```text
[id, owner, x, y, radius, ships, production]
```

Confirmed meanings:

- `id`: integer planet id.
- `owner`: integer player id `0` through `3`, or `-1` for neutral.
- `x`: current x coordinate.
- `y`: current y coordinate.
- `radius`: planet radius.
- `ships`: current garrison ship count.
- `production`: ships produced per turn when owned.

`initial_planets` uses the same row format. The parser links current planets to
their initial `(x, y)` position when available.

## Confirmed Fleet Fields

Official fleet row format:

```text
[id, owner, x, y, angle, from_planet_id, ships]
```

Confirmed meanings:

- `id`: integer fleet id.
- `owner`: integer player id.
- `x`: current x coordinate.
- `y`: current y coordinate.
- `angle`: direction of travel in radians.
- `from_planet_id`: source planet id.
- `ships`: number of ships in the fleet.

Cycle 1 only parses these fields. It does not compute speed, destination,
arrival, or collision outcome.

## Confirmed Player, Tick, And Step Fields

- `player`: current player id for the observation.
- `step`: current observation step.
- `remainingOverageTime`: remaining overage time budget in seconds.
- `next_fleet_id`: next fleet id the environment will assign.

The packaged JSON describes `agentTimeout` as obsolete in favor of
`observation.remainingOverageTime`; `agentTimeout` is configuration, not an
observation field.

## Confirmed Optional And Dynamic Fields

- `angular_velocity`
  - Rotation speed in radians per turn.
  - Parsed only as a scalar; no rotation model is implemented in Cycle 1.
- `initial_planets`
  - Same row format as `planets`.
  - Used only to attach initial positions to parsed `Planet` objects.
- `comets`
  - A list of comet-group mappings.
  - Confirmed group fields are `planet_ids`, `paths`, and `path_index`.
  - `paths` is parsed as groups of `(x, y)` points.
- `comet_planet_ids`
  - Planet ids that identify comet planets also present in `planets`.
  - Parsed into `GameState.comet_planet_ids`.

## Unknown Or Still-Unverified Fields

- No additional observation keys were seen in the local official fixtures.
- No replay-specific wrapper schema was added; Cycle 1 parses only direct agent
  observations.
- The exact lifecycle of every comet path index was not modeled here.
- Configuration values such as `shipSpeed`, `cometSpeed`, board size, and sun
  radius are documented by the environment but are not parsed from observations.

## Exact Assumptions Made

- Observation rows are list-like sequences with exactly seven entries for
  planets and fleets.
- Numeric coordinates, radii, angles, and overage values are parsed as floats.
- Ids, owners, ship counts, production, step, and `next_fleet_id` are parsed as
  integers.
- Missing optional collections are treated as empty.
- Missing optional scalar fields are represented as `None`.
- `raw_observation` is useful for later validation/debugging, so
  `GameState.from_obs` stores a deep copy rather than a shared reference.

## What Remains Deferred

- Planet motion.
- Fleet movement.
- Aiming.
- Arrival prediction.
- Collision detection.
- Production application.
- Combat resolution.
- Timelines.
- What-if launch insertion.
- Mission generation.
- Evaluation.
- Bot logic.
- Kaggle submission bundling.

## Proposed Next Cycle

Cycle 2 should implement constants and core geometry, then prepare for planet
motion:

1. Confirm and centralize official constants from the local package docs/source.
2. Add geometry primitives needed by motion and collision tests.
3. Add tests for orbit/static classification without moving planets yet.
4. Implement planet position projection only after those constants and
   primitives are locked down.
