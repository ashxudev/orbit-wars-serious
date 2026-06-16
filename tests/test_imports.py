"""Import smoke tests for simulator module boundaries."""

from __future__ import annotations

import importlib
import unittest


MODULES = (
    "ow_sim",
    "ow_sim.constants",
    "ow_sim.state",
    "ow_sim.geometry",
    "ow_sim.forecast",
    "ow_sim.collision",
    "ow_sim.combat",
    "ow_sim.timeline",
    "ow_sim.whatif",
    "ow_sim.validate",
)


class ImportTests(unittest.TestCase):
    def test_every_module_imports(self) -> None:
        for module_name in MODULES:
            with self.subTest(module=module_name):
                importlib.import_module(module_name)
