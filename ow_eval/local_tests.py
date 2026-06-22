"""Local unittest profiling and parallel execution helpers."""

from __future__ import annotations

import os
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Sequence


DEFAULT_TEST_PATTERN = "test_*.py"


@dataclass(frozen=True, slots=True)
class LocalTestModule:
    """One discoverable unittest module."""

    module: str
    path: str

    def __post_init__(self) -> None:
        _validate_nonempty_string(self.module, "module")
        _validate_nonempty_string(self.path, "path")

    def to_dict(self) -> dict[str, object]:
        return {
            "module": self.module,
            "path": self.path,
        }


@dataclass(frozen=True, slots=True)
class LocalTestResult:
    """Result from running one unittest module in a subprocess."""

    module: str
    path: str
    command: tuple[str, ...]
    returncode: int
    duration_seconds: float
    stdout: str = ""
    stderr: str = ""
    timed_out: bool = False

    def __post_init__(self) -> None:
        _validate_nonempty_string(self.module, "module")
        _validate_nonempty_string(self.path, "path")
        _validate_string_tuple(self.command, "command")
        if isinstance(self.returncode, bool) or not isinstance(self.returncode, int):
            raise ValueError("returncode must be an integer")
        if not isinstance(self.duration_seconds, (float, int)) or self.duration_seconds < 0:
            raise ValueError("duration_seconds must be non-negative")
        if not isinstance(self.stdout, str):
            raise ValueError("stdout must be a string")
        if not isinstance(self.stderr, str):
            raise ValueError("stderr must be a string")
        if not isinstance(self.timed_out, bool):
            raise ValueError("timed_out must be a boolean")

    @property
    def passed(self) -> bool:
        return self.returncode == 0 and not self.timed_out

    def to_dict(self, *, include_output: bool = False) -> dict[str, object]:
        payload: dict[str, object] = {
            "module": self.module,
            "path": self.path,
            "command": list(self.command),
            "returncode": self.returncode,
            "duration_seconds": self.duration_seconds,
            "passed": self.passed,
            "timed_out": self.timed_out,
        }
        if include_output:
            payload["stdout"] = self.stdout
            payload["stderr"] = self.stderr
        return payload


@dataclass(frozen=True, slots=True)
class LocalTestRunSummary:
    """Aggregate result for a local test run."""

    results: tuple[LocalTestResult, ...]
    elapsed_seconds: float
    worker_count: int
    summary_text: str

    def __post_init__(self) -> None:
        if not isinstance(self.results, tuple):
            raise ValueError("results must be a tuple")
        for index, result in enumerate(self.results):
            if not isinstance(result, LocalTestResult):
                raise ValueError(f"results[{index}] must be a LocalTestResult")
        if not isinstance(self.elapsed_seconds, (float, int)) or self.elapsed_seconds < 0:
            raise ValueError("elapsed_seconds must be non-negative")
        if isinstance(self.worker_count, bool) or not isinstance(self.worker_count, int):
            raise ValueError("worker_count must be an integer")
        if self.worker_count < 1:
            raise ValueError("worker_count must be positive")
        _validate_nonempty_string(self.summary_text, "summary_text")

    @property
    def passed(self) -> bool:
        return all(result.passed for result in self.results)

    @property
    def exit_code(self) -> int:
        return 0 if self.passed else 1

    @property
    def failed_results(self) -> tuple[LocalTestResult, ...]:
        return tuple(result for result in self.results if not result.passed)

    def slowest(self, limit: int) -> tuple[LocalTestResult, ...]:
        if isinstance(limit, bool) or not isinstance(limit, int):
            raise ValueError("limit must be an integer")
        if limit < 0:
            raise ValueError("limit must be non-negative")
        return tuple(
            sorted(
                self.results,
                key=lambda result: (-result.duration_seconds, result.module),
            )[:limit]
        )

    def to_dict(self, *, include_output: bool = False) -> dict[str, object]:
        return {
            "elapsed_seconds": self.elapsed_seconds,
            "worker_count": self.worker_count,
            "module_count": len(self.results),
            "passed": self.passed,
            "exit_code": self.exit_code,
            "failed_modules": [result.module for result in self.failed_results],
            "summary_text": self.summary_text,
            "results": [
                result.to_dict(include_output=include_output)
                for result in self.results
            ],
        }


def default_worker_count() -> int:
    """Return a conservative local default for parallel module tests."""

    return max(1, min(6, os.cpu_count() or 1))


def discover_test_modules(
    tests_dir: str | Path = "tests",
    *,
    pattern: str = DEFAULT_TEST_PATTERN,
    repo_root: str | Path | None = None,
) -> tuple[LocalTestModule, ...]:
    """Discover unittest module files deterministically."""

    root = Path(repo_root).resolve() if repo_root is not None else Path.cwd().resolve()
    test_root = _path_under_root(root, tests_dir, "tests_dir")
    if not test_root.is_dir():
        raise ValueError(f"tests_dir does not exist: {test_root}")
    _validate_nonempty_string(pattern, "pattern")

    modules: list[LocalTestModule] = []
    for path in sorted(test_root.rglob(pattern)):
        if path.name == "__init__.py" or not path.is_file():
            continue
        relative = path.relative_to(root)
        module = ".".join(relative.with_suffix("").parts)
        modules.append(LocalTestModule(module=module, path=str(relative)))
    return tuple(modules)


def build_unittest_command(
    module: str,
    *,
    python_executable: str = sys.executable,
) -> tuple[str, ...]:
    """Build the subprocess command for one unittest module."""

    _validate_nonempty_string(module, "module")
    _validate_nonempty_string(python_executable, "python_executable")
    return (python_executable, "-m", "unittest", module)


def run_test_module(
    module: LocalTestModule,
    *,
    repo_root: str | Path | None = None,
    python_executable: str = sys.executable,
    timeout_seconds: float | None = None,
) -> LocalTestResult:
    """Run one unittest module in a fresh subprocess."""

    if not isinstance(module, LocalTestModule):
        raise ValueError("module must be a LocalTestModule")
    root = Path(repo_root).resolve() if repo_root is not None else Path.cwd().resolve()
    command = build_unittest_command(
        module.module,
        python_executable=python_executable,
    )
    started = time.perf_counter()
    try:
        completed = subprocess.run(
            command,
            cwd=root,
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
        )
        duration = time.perf_counter() - started
        return LocalTestResult(
            module=module.module,
            path=module.path,
            command=command,
            returncode=completed.returncode,
            duration_seconds=duration,
            stdout=completed.stdout,
            stderr=completed.stderr,
        )
    except subprocess.TimeoutExpired as exc:
        duration = time.perf_counter() - started
        stdout = _timeout_output(exc.stdout)
        stderr = _timeout_output(exc.stderr)
        return LocalTestResult(
            module=module.module,
            path=module.path,
            command=command,
            returncode=124,
            duration_seconds=duration,
            stdout=stdout,
            stderr=stderr or f"timed out after {timeout_seconds} seconds",
            timed_out=True,
        )


def run_test_modules(
    modules: Sequence[LocalTestModule],
    *,
    repo_root: str | Path | None = None,
    python_executable: str = sys.executable,
    workers: int = 1,
    timeout_seconds: float | None = None,
    run_one: Callable[..., LocalTestResult] = run_test_module,
) -> LocalTestRunSummary:
    """Run unittest modules with deterministic result ordering."""

    module_tuple = _module_sequence(modules)
    if isinstance(workers, bool) or not isinstance(workers, int) or workers < 1:
        raise ValueError("workers must be a positive integer")
    root = Path(repo_root).resolve() if repo_root is not None else Path.cwd().resolve()
    started = time.perf_counter()

    if workers == 1 or len(module_tuple) <= 1:
        results = tuple(
            run_one(
                module,
                repo_root=root,
                python_executable=python_executable,
                timeout_seconds=timeout_seconds,
            )
            for module in module_tuple
        )
    else:
        indexed_results: dict[int, LocalTestResult] = {}
        with ThreadPoolExecutor(max_workers=min(workers, len(module_tuple))) as executor:
            futures = {
                executor.submit(
                    run_one,
                    module,
                    repo_root=root,
                    python_executable=python_executable,
                    timeout_seconds=timeout_seconds,
                ): index
                for index, module in enumerate(module_tuple)
            }
            for future in as_completed(futures):
                indexed_results[futures[future]] = future.result()
        results = tuple(indexed_results[index] for index in range(len(module_tuple)))

    elapsed = time.perf_counter() - started
    passed = all(result.passed for result in results)
    return LocalTestRunSummary(
        results=results,
        elapsed_seconds=elapsed,
        worker_count=min(workers, max(1, len(module_tuple))),
        summary_text=(
            f"local_unittest_run={'PASS' if passed else 'FAIL'} "
            f"modules={len(results)} failures={sum(not result.passed for result in results)} "
            f"workers={min(workers, max(1, len(module_tuple)))} "
            f"elapsed_seconds={elapsed:.3f}"
        ),
    )


def _module_sequence(value: Sequence[LocalTestModule]) -> tuple[LocalTestModule, ...]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise ValueError("modules must be a non-string sequence")
    result = tuple(value)
    for index, module in enumerate(result):
        if not isinstance(module, LocalTestModule):
            raise ValueError(f"modules[{index}] must be a LocalTestModule")
    return result


def _path_under_root(root: Path, value: str | Path, name: str) -> Path:
    if not isinstance(value, (str, Path)):
        raise ValueError(f"{name} must be a path")
    path = Path(value)
    if path.is_absolute():
        return path.resolve()
    return (root / path).resolve()


def _timeout_output(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode(errors="replace")
    return str(value)


def _validate_string_tuple(value: object, name: str) -> None:
    if not isinstance(value, tuple):
        raise ValueError(f"{name} must be a tuple")
    for index, item in enumerate(value):
        if not isinstance(item, str) or not item:
            raise ValueError(f"{name}[{index}] must be a non-empty string")


def _validate_nonempty_string(value: object, name: str) -> None:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{name} must be a non-empty string")


__all__ = (
    "DEFAULT_TEST_PATTERN",
    "LocalTestModule",
    "LocalTestResult",
    "LocalTestRunSummary",
    "build_unittest_command",
    "default_worker_count",
    "discover_test_modules",
    "run_test_module",
    "run_test_modules",
)
