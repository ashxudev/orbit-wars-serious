# Simulator Cycle 0

## What Was Created

- Added the initial `ow_sim` package with module boundaries for constants,
  provisional state containers, geometry, forecasting, combat, timelines,
  what-if analysis, and validation.
- Added conservative placeholder dataclasses for `Planet`, `Fleet`, and
  `GameState`.
- Added the only unambiguous geometry helper for this cycle: Euclidean distance.
- Added unittest smoke tests for imports, placeholder state construction, and
  the distance helper.
- Added `scripts/validate_sim.py` to run the simulator test suite.

## What Was Intentionally Not Implemented

- No bot logic.
- No planner.
- No mission generator.
- No evaluator.
- No machine learning.
- No Kaggle submission path.
- No copied historical agent code.
- No production, movement, collision, sun-death, arrival, or combat mechanics.
- No parser for official observations or replays.

## Information Still Needed

- Official observation schema for planets, fleets, players, ticks, and optional
  comet or rotating-planet fields.
- Exact fleet speed formula and any rounding behavior.
- Planet production cadence and timing.
- Collision rules for planets, the board boundary, and the sun.
- Combat ordering, especially for simultaneous arrivals on the same tick.
- Replay or deterministic environment transitions for validation fixtures.
- Differences in required state handling between two-player and four-player
  games.

## Proposed Next Cycle

Cycle 1 should focus on state schema and official input or replay inspection:

1. Capture representative official observations and replay transitions.
2. Document the confirmed schema without adding strategy code.
3. Add parser tests for normal observations, empty fleets, missing optional
   fields, rotating planets, and comet-like objects if present.
4. Replace provisional state fields only where the schema is confirmed.
