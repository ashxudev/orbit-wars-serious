"""Tests for constants confirmed from the official Orbit Wars environment."""

from __future__ import annotations

import json
import unittest
import importlib.util
import sysconfig
from pathlib import Path

from ow_sim import constants


def load_official_orbit_wars_module():
    repo_root = Path(__file__).resolve().parents[1]
    relative_module_path = Path(
        "kaggle_environments",
        "envs",
        "orbit_wars",
        "orbit_wars.py",
    )
    project_venv_matches = sorted(
        (repo_root / ".venv" / "lib").glob(
            f"python*/site-packages/{relative_module_path}"
        )
    )
    candidates = [
        *project_venv_matches,
        Path(sysconfig.get_paths()["purelib"]) / relative_module_path,
    ]
    module_path = next((candidate for candidate in candidates if candidate.exists()), None)
    if module_path is None:
        raise RuntimeError(
            "Could not find the official Orbit Wars environment source. "
            "Run tests with .venv/bin/python, or create the local .venv with "
            "kaggle-environments installed."
        )

    spec = importlib.util.spec_from_file_location("_official_orbit_wars", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"could not load official Orbit Wars module from {module_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


official = load_official_orbit_wars_module()


class ConstantsTests(unittest.TestCase):
    def test_constants_match_official_environment_source(self) -> None:
        self.assertEqual(constants.BOARD_MIN, 0.0)
        self.assertEqual(constants.BOARD_SIZE, official.BOARD_SIZE)
        self.assertEqual(constants.BOARD_MAX, official.BOARD_SIZE)
        self.assertEqual(constants.SUN_CENTER, (official.CENTER, official.CENTER))
        self.assertEqual(constants.SUN_RADIUS, official.SUN_RADIUS)
        self.assertEqual(
            constants.ROTATION_RADIUS_LIMIT,
            official.ROTATION_RADIUS_LIMIT,
        )
        self.assertEqual(constants.COMET_RADIUS, official.COMET_RADIUS)
        self.assertEqual(constants.COMET_PRODUCTION, official.COMET_PRODUCTION)
        self.assertEqual(constants.PLANET_CLEARANCE, official.PLANET_CLEARANCE)
        self.assertEqual(constants.MIN_PLANET_GROUPS, official.MIN_PLANET_GROUPS)
        self.assertEqual(constants.MAX_PLANET_GROUPS, official.MAX_PLANET_GROUPS)
        self.assertEqual(constants.MIN_STATIC_GROUPS, official.MIN_STATIC_GROUPS)
        self.assertEqual(
            constants.COMET_SPAWN_STEPS,
            tuple(official.COMET_SPAWN_STEPS),
        )

    def test_default_config_constants_match_official_json(self) -> None:
        config_path = Path(official.__file__).with_name("orbit_wars.json")
        with config_path.open(encoding="utf-8") as fh:
            config = json.load(fh)

        self.assertEqual(
            constants.DEFAULT_EPISODE_STEPS,
            config["configuration"]["episodeSteps"],
        )
        self.assertEqual(
            constants.DEFAULT_MAX_FLEET_SPEED,
            config["configuration"]["shipSpeed"]["default"],
        )
        self.assertEqual(
            constants.DEFAULT_COMET_SPEED,
            config["configuration"]["cometSpeed"]["default"],
        )
        self.assertEqual(
            constants.FINAL_INTERPRETER_STEP,
            constants.DEFAULT_EPISODE_STEPS - 2,
        )

    def test_geometry_tolerance_is_small_positive_float(self) -> None:
        self.assertIsInstance(constants.GEOMETRY_ABS_TOL, float)
        self.assertGreater(constants.GEOMETRY_ABS_TOL, 0.0)
        self.assertLess(constants.GEOMETRY_ABS_TOL, 1e-6)
