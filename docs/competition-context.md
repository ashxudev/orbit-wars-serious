# Orbit Wars Competition Context

## Objective

Orbit Wars is a Kaggle environment competition where agents control fleets in a continuous 2D space. The goal is to conquer and hold planets, grow production, deny opponents, and finish with the strongest final score or rank.

For a serious top-10 attempt, the agent should be built as a tactical planner with an accurate local model of the game engine. A loose bundle of rules is not enough.

## Core Game Concepts

- The board is a 100 by 100 continuous 2D map.
- The sun is centered at `(50, 50)`.
- Planets can be neutral, owned by a player, rotating around the sun, static, or comet-like.
- Owned planets produce ships over time.
- Agents launch fleets from owned planets by choosing a source planet, angle, and ship count.
- Fleet speed depends on ship count.
- Fleets move continuously and can collide with planets, leave the board, or die to the sun.
- When fleets arrive at a planet, combat is resolved by owner and ship counts.
- Multiple arrivals on the same tick matter.
- The environment can be two-player or four-player.

## Why A Simulator Comes First

Most bad agents lose because they launch into futures that are false. A serious agent needs to predict:

- rotating planet positions
- comet positions and expiry
- fleet travel paths
- ship-speed effects
- collision timing
- sun deaths
- production timing
- simultaneous combat
- future ownership and garrison timelines

The simulator should not decide strategy. It should answer factual questions such as:

- Will this fleet hit the intended target?
- When will it arrive?
- How many ships will the target have then?
- Will the planet be captured?
- Will the capture survive?
- Does the source become vulnerable after the send?

## Recommended Blank-Slate Architecture

Build the agent in layers.

### 1. Engine-Faithful Forward Simulator

Purpose: predict consequences.

Responsibilities:

- parse the observation into compact state
- project planet positions over a horizon
- predict fleet landings
- apply production
- resolve combat
- build planet owner and ship timelines
- support hypothetical launch insertion

The simulator should be deterministic, fast, and heavily tested against replay or environment transitions.

### 2. Mission Generator

Purpose: create plausible options.

Generate missions instead of raw actions:

- capture neutral planet
- attack enemy planet
- defend own planet
- reinforce/front-transfer
- evacuate doomed planet
- coordinate multi-source attack
- late-game liquidation
- FFA leader-targeting strike

Each mission should be translated into legal launch actions only after target, ship count, and angle are validated.

### 3. Mission Evaluator

Purpose: score options.

Evaluate missions by comparing future board value with and without the mission:

- production gained
- production denied
- ships spent
- arrival timing
- capture survival
- enemy response feasibility
- opportunity cost of draining the source
- final rank impact in four-player games

This is the main difference between a planner and a bundle of isolated heuristics.

### 4. Opponent-Response Model

Purpose: estimate punishment and defense.

For each candidate attack, ask:

- Can the opponent reinforce before arrival?
- Can the opponent race the same neutral?
- Can the opponent counterattack the emptied source?
- Is the responding source pinned or threatened?
- In four-player games, does a third party benefit more than we do?

Classify attacks into:

- undefendable
- defendable but still profitable
- pure donation
- race/tie risk
- source-drain bait

### 5. Commitment Policy

Purpose: choose ship sizing.

For important missions, generate variants:

- minimum capture
- capture and hold
- reserve-preserving attack
- full-source attack
- coordinated multi-source attack
- no attack

Strong agents appear willing to fully commit when the future supports it. Full-send should be an evaluated option, not a global rule.

### 6. Separate 2p And 4p Modes

Two-player objective:

- maximize advantage over the single opponent
- deny production
- win direct tactical exchanges

Four-player objective:

- maximize final rank
- survive while behind
- attack current leader when profitable
- avoid becoming an exposed leader too early
- exploit late rank-swing opportunities

Four-player is not simply two-player with more enemies.

### 7. Runtime Architecture

Python can be competitive if the planner is lean.

Per turn:

1. Parse observation into compact arrays.
2. Precompute future planet positions.
3. Predict existing fleet landings.
4. Build ownership/garrison timelines.
5. Generate candidate missions.
6. Cheaply prefilter candidates.
7. Fully evaluate only top candidates.
8. Greedily commit compatible missions.
9. Stop before timeout.
10. Fall back to safe simple behavior if time is low.

Avoid broad tree search unless it is extremely selective and deterministic.

## Suggested Development Modules

Develop modularly first:

```text
ow_sim/
  constants.py
  state.py
  geometry.py
  forecast.py
  combat.py
  timeline.py
  whatif.py
  validate.py
```

Later, bundle into a single Kaggle submission file only after the modular implementation is tested.

## First Build Cycle

Start with:

- constants
- state parsing
- geometry primitives
- unit tests
- a validation script that parses a deterministic local environment observation

Do not start with strategy. The first milestone is trustworthy mechanics.

## Testing Philosophy

Every layer should have tests before building the next layer.

Required validation types:

- unit tests for fleet speed, distance, sun collision, swept collision
- parser tests for normal observations, empty fleets, missing optional fields, and comets
- replay or environment transition validation
- landing prediction validation
- combat edge-case tests
- timeline validation against known replay states

If the simulator is wrong, the planner will become patchwork.

## Current Strategic Belief

For a comfortable top-10 target, a small trained model is probably not required as the primary architecture. The first priority is:

```text
accurate simulator + response-aware tactical planner + full-commit sizing options + 2p/4p objectives + strict runtime control
```

A small model may later help rank or calibrate generated missions, but it should not replace the simulator or mission evaluator.

## Safety Rules

- Do not submit to Kaggle without explicit approval.
- Do not use old agents as the design center.
- Keep raw replay dumps out of tracked source unless explicitly requested.
- Prefer local validation and paired evaluations before any live action.
