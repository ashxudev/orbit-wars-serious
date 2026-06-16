"""Shared constants for the Orbit Wars simulator.

Only facts confirmed by the workspace documentation belong here during cycle 0.
Unknown engine values should remain TODOs until verified from official inputs,
replays, or environment transitions.
"""

BOARD_SIZE = 100.0
"""Confirmed continuous board width and height."""

SUN_CENTER = (50.0, 50.0)
"""Confirmed center point of the sun."""

# TODO: Confirm sun radius and fleet death boundary from official observations.
# TODO: Confirm ship production cadence and rounding behavior.
# TODO: Confirm fleet speed formula from environment transitions.
# TODO: Confirm combat resolution order for simultaneous arrivals.
