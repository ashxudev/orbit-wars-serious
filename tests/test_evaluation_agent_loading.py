"""Tests for Evaluation Harness Cycle 2 agent loading."""

from __future__ import annotations

import importlib
import tempfile
import unittest
from pathlib import Path

from ow_eval import (
    AgentSourceKind,
    AgentSpec,
    BaselineName,
    builtin_baseline_spec,
    load_agent_callable,
)


class EvaluationAgentLoadingTests(unittest.TestCase):
    def test_agent_loading_imports_and_exports_are_available(self) -> None:
        module = importlib.import_module("ow_eval.agent_loading")

        self.assertIs(module.load_agent_callable, load_agent_callable)

    def test_loads_modular_agent_callable(self) -> None:
        spec = AgentSpec(
            name="runtime-agent",
            source_kind=AgentSourceKind.MODULAR_AGENT,
            module_path="agents.orbit_wars_agent",
            callable_name="agent",
        )

        agent = load_agent_callable(spec)

        self.assertTrue(callable(agent))
        self.assertEqual(agent({"remainingOverageTime": 0.0}, {}), [])

    def test_loads_builtin_baseline_as_noop_agent(self) -> None:
        spec = AgentSpec(name="idle", source_kind=AgentSourceKind.BUILTIN_BASELINE)

        agent = load_agent_callable(spec)

        self.assertEqual(agent({"step": 0}, {}), [])
        self.assertIsNot(agent({"step": 0}, {}), agent({"step": 1}, {}))

    def test_loads_explicit_builtin_baseline_from_registry(self) -> None:
        spec = builtin_baseline_spec(BaselineName.NEAREST_NEUTRAL)

        agent = load_agent_callable(spec)

        self.assertEqual(agent({"planets": [[1]]}, {}), [])

    def test_explicit_unknown_builtin_baseline_raises_value_error(self) -> None:
        spec = AgentSpec(
            name="bad",
            source_kind=AgentSourceKind.BUILTIN_BASELINE,
            metadata=(("baseline", "unknown"),),
        )

        with self.assertRaisesRegex(ValueError, "unknown builtin baseline: unknown"):
            load_agent_callable(spec)

    def test_loads_python_file_agent_without_sys_path_parent(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "file_agent.py"
            path.write_text(
                "def agent(observation, configuration=None):\n"
                "    return [[1, 0.5, 3]]\n",
                encoding="utf-8",
            )
            spec = AgentSpec(
                name="file-agent",
                source_kind=AgentSourceKind.PYTHON_FILE,
                file_path=str(path),
            )

            agent = load_agent_callable(spec)

        self.assertEqual(agent({}, {}), [[1, 0.5, 3]])

    def test_loads_submission_file_agent(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "submission.py"
            path.write_text(
                "def agent(observation, configuration=None):\n"
                "    return [[2, 1.0, 4]]\n",
                encoding="utf-8",
            )
            spec = AgentSpec(
                name="submission",
                source_kind=AgentSourceKind.SUBMISSION_FILE,
                file_path=str(path),
            )

            agent = load_agent_callable(spec)

        self.assertEqual(agent({}, {}), [[2, 1.0, 4]])

    def test_file_agent_uses_custom_callable_name(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "custom.py"
            path.write_text(
                "def alternate(observation, configuration=None):\n"
                "    return [[3, 1.5, 5]]\n",
                encoding="utf-8",
            )
            spec = AgentSpec(
                name="custom",
                source_kind=AgentSourceKind.PYTHON_FILE,
                file_path=str(path),
                callable_name="alternate",
            )

            agent = load_agent_callable(spec)

        self.assertEqual(agent({}, {}), [[3, 1.5, 5]])

    def test_missing_file_path_raises_clear_value_error(self) -> None:
        spec = AgentSpec(name="missing-path", source_kind=AgentSourceKind.PYTHON_FILE)

        with self.assertRaisesRegex(
            ValueError,
            "file_path is required for python_file",
        ):
            load_agent_callable(spec)

    def test_missing_file_raises_clear_value_error(self) -> None:
        spec = AgentSpec(
            name="missing-file",
            source_kind=AgentSourceKind.SUBMISSION_FILE,
            file_path="/tmp/does-not-exist-ow-eval-agent.py",
        )

        with self.assertRaisesRegex(
            ValueError,
            "submission_file file not found: /tmp/does-not-exist-ow-eval-agent.py",
        ):
            load_agent_callable(spec)

    def test_missing_callable_raises_attribute_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "missing_callable.py"
            path.write_text("VALUE = 1\n", encoding="utf-8")
            spec = AgentSpec(
                name="missing-callable",
                source_kind=AgentSourceKind.PYTHON_FILE,
                file_path=str(path),
            )

            with self.assertRaises(AttributeError):
                load_agent_callable(spec)

    def test_noncallable_callable_name_raises_value_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "noncallable.py"
            path.write_text("agent = 123\n", encoding="utf-8")
            spec = AgentSpec(
                name="noncallable",
                source_kind=AgentSourceKind.PYTHON_FILE,
                file_path=str(path),
            )

            with self.assertRaisesRegex(ValueError, "agent is not callable"):
                load_agent_callable(spec)

    def test_same_filename_in_different_directories_does_not_collide(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            first_dir = Path(tmp) / "one"
            second_dir = Path(tmp) / "two"
            first_dir.mkdir()
            second_dir.mkdir()
            first_path = first_dir / "agent.py"
            second_path = second_dir / "agent.py"
            first_path.write_text(
                "def agent(observation, configuration=None):\n"
                "    return [[1, 0.0, 1]]\n",
                encoding="utf-8",
            )
            second_path.write_text(
                "def agent(observation, configuration=None):\n"
                "    return [[2, 0.0, 2]]\n",
                encoding="utf-8",
            )

            first_agent = load_agent_callable(
                AgentSpec(
                    name="first",
                    source_kind=AgentSourceKind.PYTHON_FILE,
                    file_path=str(first_path),
                )
            )
            second_agent = load_agent_callable(
                AgentSpec(
                    name="second",
                    source_kind=AgentSourceKind.PYTHON_FILE,
                    file_path=str(second_path),
                )
            )

        self.assertEqual(first_agent({}, {}), [[1, 0.0, 1]])
        self.assertEqual(second_agent({}, {}), [[2, 0.0, 2]])


if __name__ == "__main__":
    unittest.main()
