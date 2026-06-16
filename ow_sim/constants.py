"""Shared constants confirmed from the official Orbit Wars environment.

Values here are limited to constants verified from the local
``kaggle_environments`` package installed in this workspace. Most runtime
mechanics such as production, collision, combat, and timelines are intentionally
deferred to later simulator cycles.
"""

BOARD_MIN = 0.0
"""Minimum coordinate on each board axis."""

BOARD_SIZE = 100.0
"""Confirmed continuous board width and height."""

BOARD_MAX = BOARD_SIZE
"""Maximum in-bounds coordinate on each board axis."""

SUN_CENTER = (50.0, 50.0)
"""Confirmed center point of the sun."""

SUN_RADIUS = 10.0
"""Confirmed sun radius."""

ROTATION_RADIUS_LIMIT = 50.0
"""Planets rotate when orbital radius plus planet radius is below this."""

DEFAULT_EPISODE_STEPS = 500
"""Default maximum episode length from the official environment config."""

FINAL_INTERPRETER_STEP = DEFAULT_EPISODE_STEPS - 2
"""Step where the official interpreter evaluates final rewards by default."""

DEFAULT_MAX_FLEET_SPEED = 6.0
"""Default maximum fleet speed from the official environment config."""

DEFAULT_COMET_SPEED = 4.0
"""Default comet speed from the official environment config."""

COMET_RADIUS = 1.0
"""Confirmed comet planet radius."""

COMET_PRODUCTION = 1
"""Confirmed comet planet production."""

PLANET_CLEARANCE = 7.0
"""Confirmed minimum generated clearance between planet bodies."""

MIN_PLANET_GROUPS = 5
"""Confirmed minimum number of generated symmetric planet groups."""

MAX_PLANET_GROUPS = 10
"""Confirmed maximum number of generated symmetric planet groups."""

MIN_STATIC_GROUPS = 3
"""Confirmed minimum generated static planet groups."""

COMET_SPAWN_STEPS = (50, 150, 250, 350, 450)
"""Confirmed comet spawn steps."""

GEOMETRY_ABS_TOL = 1e-9
"""Default absolute tolerance for deterministic geometry tests."""
