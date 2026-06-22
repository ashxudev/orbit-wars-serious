"""Skeleton adapter for a future real Daytona SDK client.

Distributed Evaluation Cycle 19 provides the explicit adapter boundary for real
Daytona execution without importing Daytona, creating sandboxes, executing
commands, uploading/downloading files, or running matches. Tests inject fake SDK
clients through this adapter; without an injected client, methods fail closed
with deterministic errors.
"""

from __future__ import annotations

import importlib
import os
import re
import shlex
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath

from .daytona_client_executor import (
    DaytonaClientCommandResult,
    DaytonaSandboxHandle,
)
from .daytona_operations import (
    DaytonaCommandOperation,
    DaytonaDownloadOperation,
    DaytonaUploadOperation,
)
from .daytona_real_config import (
    DaytonaRealExecutionConfig,
    DaytonaRealExecutionReadiness,
    validate_daytona_real_execution_readiness,
)


class DaytonaSdkUnavailableError(RuntimeError):
    """Raised when real Daytona SDK behavior is unavailable by design."""


class DaytonaSdkProtocolClient:
    """Protocol-shaped facade over an injected low-level Daytona-like client.

    The current fake SDK shape is intentionally narrow:
    - SDK module exposes ``create_client(config)``, ``Client(config)``, or
      ``Session(config)``.
    - The low-level client exposes ``open_sandbox(sandbox_name, working_dir)``,
      ``upload_file(handle, local_path, sandbox_path)``,
      ``run_command(handle, worker_argv, working_dir)``,
      ``download_file(handle, sandbox_path, local_path)``, and
      ``close_sandbox(handle)``.
    """

    def __init__(self, sdk_client: object) -> None:
        self.sdk_client = sdk_client
        self._handles: dict[str, object] = {}
        for method_name in (
            "open_sandbox",
            "upload_file",
            "run_command",
            "download_file",
            "close_sandbox",
        ):
            if not callable(getattr(self.sdk_client, method_name, None)):
                raise DaytonaSdkUnavailableError(
                    "Daytona SDK protocol client requires low-level method "
                    f"{method_name}"
                )

    def open_sandbox(
        self,
        *,
        sandbox_name: str | None,
        working_dir: str,
    ) -> DaytonaSandboxHandle:
        """Open a low-level sandbox and return a protocol handle."""

        low_level_handle = self.sdk_client.open_sandbox(
            sandbox_name=sandbox_name,
            working_dir=working_dir,
        )
        handle = _sandbox_handle_from_low_level(
            low_level_handle,
            sandbox_name=sandbox_name,
            working_dir=working_dir,
        )
        self._handles[handle.handle_id] = low_level_handle
        return handle

    def upload_file(
        self,
        handle: DaytonaSandboxHandle,
        operation: DaytonaUploadOperation,
    ) -> None:
        """Forward one upload operation to the low-level client."""

        low_level_handle = self._low_level_handle(handle)
        self.sdk_client.upload_file(
            low_level_handle,
            operation.local_path,
            operation.sandbox_path,
        )

    def run_command(
        self,
        handle: DaytonaSandboxHandle,
        operation: DaytonaCommandOperation,
    ) -> DaytonaClientCommandResult:
        """Forward one command operation and normalize its result."""

        low_level_handle = self._low_level_handle(handle)
        try:
            result = self.sdk_client.run_command(
                low_level_handle,
                operation.worker_argv,
                operation.working_dir,
                env_var_names=operation.env_var_names,
            )
        except TypeError:
            result = self.sdk_client.run_command(
                low_level_handle,
                operation.worker_argv,
                operation.working_dir,
            )
        return _command_result_from_low_level(result)

    def download_file(
        self,
        handle: DaytonaSandboxHandle,
        operation: DaytonaDownloadOperation,
    ) -> None:
        """Forward one download operation to the low-level client."""

        low_level_handle = self._low_level_handle(handle)
        self.sdk_client.download_file(
            low_level_handle,
            operation.sandbox_path,
            operation.local_path,
        )

    def close_sandbox(self, handle: DaytonaSandboxHandle) -> None:
        """Forward one close operation to the low-level client."""

        low_level_handle = self._low_level_handle(handle)
        self.sdk_client.close_sandbox(low_level_handle)
        self._handles.pop(handle.handle_id, None)

    def _low_level_handle(self, handle: DaytonaSandboxHandle) -> object:
        if not isinstance(handle, DaytonaSandboxHandle):
            raise ValueError("handle must be a DaytonaSandboxHandle")
        low_level_handle = self._handles.get(handle.handle_id)
        if low_level_handle is None:
            raise DaytonaSdkUnavailableError(
                f"Unknown Daytona sandbox handle: {handle.handle_id}"
            )
        return low_level_handle


@dataclass(frozen=True, slots=True)
class _OfficialDaytonaSandboxHandle:
    handle_id: str
    sandbox_name: str | None
    working_dir: str
    sandbox: object


class _OfficialDaytonaLowLevelClient:
    """Low-level facade over the official Daytona SDK sync client."""

    _SESSION_COMMAND_TIMEOUT_SECONDS = 60 * 60 * 2
    _SESSION_POLL_INTERVAL_SECONDS = 5.0

    def __init__(self, sdk_module: object, config: DaytonaRealExecutionConfig) -> None:
        self.sdk_module = sdk_module
        self.config = config
        self.daytona = self._build_daytona_client()

    def open_sandbox(
        self,
        *,
        sandbox_name: str | None,
        working_dir: str,
    ) -> _OfficialDaytonaSandboxHandle:
        params = self._create_params(sandbox_name)
        sandbox = self.daytona.create(params)
        return _OfficialDaytonaSandboxHandle(
            handle_id=_sandbox_handle_id(sandbox, sandbox_name),
            sandbox_name=_sandbox_name(sandbox, sandbox_name),
            working_dir=working_dir,
            sandbox=sandbox,
        )

    def upload_file(
        self,
        handle: _OfficialDaytonaSandboxHandle,
        local_path: str,
        sandbox_path: str,
    ) -> None:
        _ensure_official_handle(handle)
        parent = str(PurePosixPath(sandbox_path).parent)
        if parent and parent != ".":
            handle.sandbox.process.exec(f"mkdir -p {shlex.quote(parent)}")
        handle.sandbox.fs.upload_file(local_path, sandbox_path)

    def run_command(
        self,
        handle: _OfficialDaytonaSandboxHandle,
        worker_argv: tuple[str, ...],
        working_dir: str,
        *,
        env_var_names: tuple[str, ...] = (),
    ) -> DaytonaClientCommandResult:
        _ensure_official_handle(handle)
        env = _env_for_names(env_var_names)
        if _supports_session_commands(handle.sandbox.process):
            return self._run_command_in_session(handle, worker_argv, working_dir, env)
        response = handle.sandbox.process.exec(
            shlex.join(worker_argv),
            cwd=working_dir,
            env=env or None,
        )
        exit_code = _response_exit_code(response)
        return DaytonaClientCommandResult(
            exit_code=exit_code,
            stdout=_response_stdout(response),
            stderr=_response_stderr(response),
            summary_text=f"daytona_sdk_official_command exit_code={exit_code}",
        )

    def _run_command_in_session(
        self,
        handle: _OfficialDaytonaSandboxHandle,
        worker_argv: tuple[str, ...],
        working_dir: str,
        env: dict[str, str],
    ) -> DaytonaClientCommandResult:
        process = handle.sandbox.process
        session_id = _session_id(handle.handle_id)
        command_line = f"cd {shlex.quote(working_dir)} && {shlex.join(worker_argv)}"
        process.create_session(session_id)
        try:
            request = self._session_execute_request(command_line, env)
            response = process.execute_session_command(
                session_id,
                request,
                timeout=15,
            )
            command_id = _session_command_id(response)
            deadline = time.monotonic() + self._SESSION_COMMAND_TIMEOUT_SECONDS
            command = None
            while True:
                command = process.get_session_command(session_id, command_id)
                exit_code = _session_command_exit_code(command)
                if exit_code is not None:
                    break
                if time.monotonic() >= deadline:
                    exit_code = 124
                    break
                time.sleep(self._SESSION_POLL_INTERVAL_SECONDS)
            logs = process.get_session_command_logs(session_id, command_id)
            stdout = _session_logs_stdout(logs)
            stderr = _session_logs_stderr(logs)
            if exit_code == 124 and not stderr:
                stderr = (
                    "Daytona session command timed out after "
                    f"{self._SESSION_COMMAND_TIMEOUT_SECONDS} seconds"
                )
            return DaytonaClientCommandResult(
                exit_code=exit_code,
                stdout=stdout,
                stderr=stderr,
                summary_text=(
                    "daytona_sdk_official_session_command "
                    f"session_id={session_id} command_id={command_id} "
                    f"exit_code={exit_code}"
                ),
            )
        finally:
            process.delete_session(session_id)

    def _session_execute_request(self, command_line: str, env: dict[str, str]) -> object:
        constructor = _sdk_attr(self.sdk_module, "SessionExecuteRequest")
        if not env:
            return constructor(command=command_line, run_async=True)
        try:
            return constructor(command=command_line, run_async=True, env=env)
        except TypeError as exc:
            raise DaytonaSdkUnavailableError(
                "Official Daytona session commands do not support env injection"
            ) from exc

    def download_file(
        self,
        handle: _OfficialDaytonaSandboxHandle,
        sandbox_path: str,
        local_path: str,
    ) -> None:
        _ensure_official_handle(handle)
        Path(local_path).parent.mkdir(parents=True, exist_ok=True)
        handle.sandbox.fs.download_file(sandbox_path, local_path)

    def close_sandbox(self, handle: _OfficialDaytonaSandboxHandle) -> None:
        _ensure_official_handle(handle)
        delete = getattr(handle.sandbox, "delete", None)
        if callable(delete):
            delete()
            return
        stop = getattr(handle.sandbox, "stop", None)
        if callable(stop):
            stop()
            return
        raise DaytonaSdkUnavailableError(
            "Official Daytona sandbox does not provide delete or stop"
        )

    def _build_daytona_client(self) -> object:
        daytona_constructor = _sdk_attr(self.sdk_module, "Daytona")
        config_constructor = _sdk_attr(self.sdk_module, "DaytonaConfig")
        api_key = _required_env_value(self.config.api_key_env_var)
        return daytona_constructor(
            config_constructor(
                api_key=api_key,
                api_url=self.config.api_url,
                target=self.config.target,
            )
        )

    def _create_params(self, sandbox_name: str | None) -> object:
        env_vars = _env_for_names(
            (self.config.github_token_env_var,)
            if self.config.source_mode == "github" and self.config.github_token_env_var
            else ()
        )
        if self.config.snapshot_id is not None:
            constructor = _sdk_attr(self.sdk_module, "CreateSandboxFromSnapshotParams")
            return constructor(
                env_vars=env_vars or None,
                name=sandbox_name,
                snapshot=self.config.snapshot_id,
            )
        if self.config.image is not None:
            constructor = _sdk_attr(self.sdk_module, "CreateSandboxFromImageParams")
            return constructor(
                env_vars=env_vars or None,
                name=sandbox_name,
                image=self.config.image,
            )
        raise DaytonaSdkUnavailableError(
            "Official Daytona SDK execution requires DAYTONA_SNAPSHOT_ID or DAYTONA_IMAGE"
        )


@dataclass(frozen=True, slots=True)
class DaytonaSdkAdapterConfig:
    """Configuration for the skeleton Daytona SDK adapter."""

    real_execution_config: DaytonaRealExecutionConfig = field(
        default_factory=DaytonaRealExecutionConfig,
    )
    readiness: DaytonaRealExecutionReadiness | None = None
    sdk_client: object | None = None
    sdk_module_name: str = "daytona"
    sdk_importer: Callable[[str], object] | None = None
    sdk_client_factory: (
        Callable[[object, DaytonaRealExecutionConfig], object] | None
    ) = None

    def __post_init__(self) -> None:
        if not isinstance(self.real_execution_config, DaytonaRealExecutionConfig):
            raise ValueError("real_execution_config must be a DaytonaRealExecutionConfig")
        if self.readiness is not None and not isinstance(
            self.readiness,
            DaytonaRealExecutionReadiness,
        ):
            raise ValueError("readiness must be a DaytonaRealExecutionReadiness")
        _validate_nonempty_string(self.sdk_module_name, "sdk_module_name")
        if self.sdk_importer is not None and not callable(self.sdk_importer):
            raise ValueError("sdk_importer must be callable when provided")
        if self.sdk_client_factory is not None and not callable(
            self.sdk_client_factory,
        ):
            raise ValueError("sdk_client_factory must be callable when provided")

    def to_dict(self) -> dict[str, object]:
        """Return a deterministic JSON-safe dictionary."""

        return {
            "real_execution_config": self.real_execution_config.to_dict(),
            "readiness": (
                self.readiness.to_dict()
                if self.readiness is not None
                else None
            ),
            "has_sdk_client": self.sdk_client is not None,
            "sdk_module_name": self.sdk_module_name,
            "has_sdk_importer": self.sdk_importer is not None,
            "has_sdk_client_factory": self.sdk_client_factory is not None,
        }


class DaytonaSdkAdapter:
    """Fail-closed adapter matching the injected Daytona sandbox client protocol."""

    def __init__(self, config: DaytonaSdkAdapterConfig | None = None) -> None:
        self.config = config if config is not None else DaytonaSdkAdapterConfig()
        if not isinstance(self.config, DaytonaSdkAdapterConfig):
            raise ValueError("config must be a DaytonaSdkAdapterConfig")
        self.readiness = (
            self.config.readiness
            if self.config.readiness is not None
            else validate_daytona_real_execution_readiness(
                self.config.real_execution_config,
            )
        )
        self.sdk_client = self.config.sdk_client
        self._resolved_client = self.config.sdk_client

    def open_sandbox(
        self,
        *,
        sandbox_name: str | None,
        working_dir: str,
    ) -> DaytonaSandboxHandle:
        """Open a sandbox through an injected fake SDK client."""

        client = self._client()
        method = self._method(client, "open_sandbox")
        handle = method(sandbox_name=sandbox_name, working_dir=working_dir)
        if not isinstance(handle, DaytonaSandboxHandle):
            raise DaytonaSdkUnavailableError(
                "Injected Daytona SDK client open_sandbox must return "
                "DaytonaSandboxHandle"
            )
        return handle

    def upload_file(
        self,
        handle: DaytonaSandboxHandle,
        operation: DaytonaUploadOperation,
    ) -> None:
        """Upload one file through an injected fake SDK client."""

        if not isinstance(handle, DaytonaSandboxHandle):
            raise ValueError("handle must be a DaytonaSandboxHandle")
        if not isinstance(operation, DaytonaUploadOperation):
            raise ValueError("operation must be a DaytonaUploadOperation")
        self._method(self._client(), "upload_file")(handle, operation)

    def run_command(
        self,
        handle: DaytonaSandboxHandle,
        operation: DaytonaCommandOperation,
    ) -> DaytonaClientCommandResult:
        """Run one command through an injected fake SDK client."""

        if not isinstance(handle, DaytonaSandboxHandle):
            raise ValueError("handle must be a DaytonaSandboxHandle")
        if not isinstance(operation, DaytonaCommandOperation):
            raise ValueError("operation must be a DaytonaCommandOperation")
        result = self._method(self._client(), "run_command")(handle, operation)
        if not isinstance(result, DaytonaClientCommandResult):
            raise DaytonaSdkUnavailableError(
                "Injected Daytona SDK client run_command must return "
                "DaytonaClientCommandResult"
            )
        return result

    def download_file(
        self,
        handle: DaytonaSandboxHandle,
        operation: DaytonaDownloadOperation,
    ) -> None:
        """Download one file through an injected fake SDK client."""

        if not isinstance(handle, DaytonaSandboxHandle):
            raise ValueError("handle must be a DaytonaSandboxHandle")
        if not isinstance(operation, DaytonaDownloadOperation):
            raise ValueError("operation must be a DaytonaDownloadOperation")
        self._method(self._client(), "download_file")(handle, operation)

    def close_sandbox(self, handle: DaytonaSandboxHandle) -> None:
        """Close a sandbox through an injected fake SDK client."""

        if not isinstance(handle, DaytonaSandboxHandle):
            raise ValueError("handle must be a DaytonaSandboxHandle")
        self._method(self._client(), "close_sandbox")(handle)

    def _client(self) -> object:
        self._ensure_ready()
        if self._resolved_client is None:
            self._resolved_client = self._resolve_client()
        return self._resolved_client

    def _resolve_client(self) -> object:
        factory = self.config.sdk_client_factory or build_daytona_sdk_protocol_client
        sdk_module = self._import_sdk_module()
        try:
            client = factory(
                sdk_module,
                self.config.real_execution_config,
            )
        except Exception as exc:  # noqa: BLE001 - adapter returns deterministic errors.
            raise DaytonaSdkUnavailableError(
                f"Daytona SDK client factory failed: {type(exc).__name__}: {exc}"
            ) from exc
        self._validate_protocol_client(client, "Daytona SDK client factory returned")
        return client

    def _import_sdk_module(self) -> object:
        importer = self.config.sdk_importer or importlib.import_module
        try:
            return importer(self.config.sdk_module_name)
        except Exception as exc:  # noqa: BLE001 - adapter returns deterministic errors.
            raise DaytonaSdkUnavailableError(
                "Daytona SDK module import failed: "
                f"{self.config.sdk_module_name}: {type(exc).__name__}: {exc}"
            ) from exc

    def _validate_protocol_client(self, client: object, prefix: str) -> None:
        for method_name in (
            "open_sandbox",
            "upload_file",
            "run_command",
            "download_file",
            "close_sandbox",
        ):
            if not callable(getattr(client, method_name, None)):
                raise DaytonaSdkUnavailableError(
                    f"{prefix} an object missing {method_name}"
                )
        if client is None:
            raise DaytonaSdkUnavailableError(
                f"{prefix} None"
            )

    def _ensure_ready(self) -> None:
        if not self.readiness.passed:
            detail = self.readiness.error_text or self.readiness.summary_text
            raise DaytonaSdkUnavailableError(
                "Daytona SDK adapter is not ready for real execution: "
                f"{detail}"
            )

    @staticmethod
    def _method(client: object, name: str):
        method = getattr(client, name, None)
        if not callable(method):
            raise DaytonaSdkUnavailableError(
                f"Injected Daytona SDK client does not provide {name}"
            )
        return method


def build_daytona_sdk_protocol_client(
    sdk_module: object,
    config: DaytonaRealExecutionConfig,
) -> DaytonaSdkProtocolClient:
    """Build the default protocol facade from a Daytona-like SDK module."""

    if not isinstance(config, DaytonaRealExecutionConfig):
        raise ValueError("config must be a DaytonaRealExecutionConfig")
    if _looks_like_official_daytona_sdk(sdk_module):
        return DaytonaSdkProtocolClient(
            _OfficialDaytonaLowLevelClient(sdk_module, config)
        )
    constructor = _sdk_client_constructor(sdk_module)
    try:
        low_level_client = constructor(config)
    except Exception as exc:  # noqa: BLE001 - adapter returns deterministic errors.
        raise DaytonaSdkUnavailableError(
            f"Daytona SDK client construction failed: {type(exc).__name__}: {exc}"
        ) from exc
    return DaytonaSdkProtocolClient(low_level_client)


def _sdk_client_constructor(sdk_module: object):
    for name in ("create_client", "Client", "Session"):
        constructor = getattr(sdk_module, name, None)
        if callable(constructor):
            return constructor
    raise DaytonaSdkUnavailableError(
        "Daytona SDK module must provide create_client, Client, or Session"
    )


def _looks_like_official_daytona_sdk(sdk_module: object) -> bool:
    return callable(getattr(sdk_module, "Daytona", None)) and callable(
        getattr(sdk_module, "DaytonaConfig", None)
    )


def _sdk_attr(sdk_module: object, name: str):
    value = getattr(sdk_module, name, None)
    if not callable(value):
        raise DaytonaSdkUnavailableError(
            f"Official Daytona SDK module missing callable {name}"
        )
    return value


def _required_env_value(name: str | None) -> str:
    if name is None:
        raise DaytonaSdkUnavailableError("api_key_env_var is required")
    value = os.environ.get(name)
    if value is None or not value.strip():
        raise DaytonaSdkUnavailableError(f"missing required env var: {name}")
    return value


def _env_for_names(names: tuple[str, ...]) -> dict[str, str]:
    env: dict[str, str] = {}
    for name in names:
        _validate_nonempty_string(name, "env_var_name")
        value = os.environ.get(name)
        if value is not None:
            env[name] = value
    return env


def _ensure_official_handle(value: object) -> None:
    if not isinstance(value, _OfficialDaytonaSandboxHandle):
        raise DaytonaSdkUnavailableError(
            "Official Daytona low-level client received an unknown sandbox handle"
        )


def _sandbox_handle_id(sandbox: object, fallback_name: str | None) -> str:
    for name in ("handle_id", "id", "sandbox_id", "name"):
        value = getattr(sandbox, name, None)
        if isinstance(value, str) and value:
            return value
    if fallback_name:
        return fallback_name
    return f"daytona-sandbox-{id(sandbox)}"


def _sandbox_name(sandbox: object, fallback_name: str | None) -> str | None:
    for name in ("sandbox_name", "name"):
        value = getattr(sandbox, name, None)
        if isinstance(value, str) and value:
            return value
    return fallback_name


def _response_exit_code(response: object) -> int:
    value = getattr(response, "exit_code", None)
    if value is None and isinstance(response, Mapping):
        value = response.get("exit_code")
    if value is None:
        value = _additional_response_field(response, "code")
    if isinstance(value, bool) or not isinstance(value, int):
        return 2
    return value


def _response_stdout(response: object) -> str | None:
    for name in ("stdout", "result"):
        value = getattr(response, name, None)
        if isinstance(value, str):
            return value
    artifacts = getattr(response, "artifacts", None)
    value = getattr(artifacts, "stdout", None)
    if isinstance(value, str):
        return value
    value = _additional_response_field(response, "stdout")
    return value if isinstance(value, str) else None


def _response_stderr(response: object) -> str | None:
    value = getattr(response, "stderr", None)
    if isinstance(value, str):
        return value
    value = _additional_response_field(response, "stderr")
    return value if isinstance(value, str) else None


def _additional_response_field(response: object, name: str) -> object:
    additional = getattr(response, "additional_properties", None)
    if isinstance(additional, Mapping):
        return additional.get(name)
    return None


def _supports_session_commands(process: object) -> bool:
    return all(
        callable(getattr(process, name, None))
        for name in (
            "create_session",
            "execute_session_command",
            "get_session_command",
            "get_session_command_logs",
            "delete_session",
        )
    )


def _session_id(handle_id: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9_-]+", "-", handle_id).strip("-")
    return f"ow-eval-{safe or 'sandbox'}"


def _session_command_id(response: object) -> str:
    value = getattr(response, "cmd_id", None)
    if value is None and isinstance(response, Mapping):
        value = response.get("cmd_id")
    if value is None:
        value = _additional_response_field(response, "cmd_id")
    if not isinstance(value, str) or not value:
        raise DaytonaSdkUnavailableError(
            "Official Daytona session command response must provide cmd_id"
        )
    return value


def _session_command_exit_code(command: object) -> int | None:
    value = getattr(command, "exit_code", None)
    if value is None and isinstance(command, Mapping):
        value = command.get("exit_code")
    if value is None:
        value = _additional_response_field(command, "exit_code")
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int):
        raise DaytonaSdkUnavailableError(
            "Official Daytona session command exit_code must be an integer"
        )
    return value


def _session_logs_stdout(logs: object) -> str | None:
    for name in ("stdout", "output"):
        value = getattr(logs, name, None)
        if isinstance(value, str):
            return value
    if isinstance(logs, Mapping):
        for name in ("stdout", "output"):
            value = logs.get(name)
            if isinstance(value, str):
                return value
    return None


def _session_logs_stderr(logs: object) -> str | None:
    value = getattr(logs, "stderr", None)
    if isinstance(value, str):
        return value
    if isinstance(logs, Mapping):
        value = logs.get("stderr")
        if isinstance(value, str):
            return value
    return None


def _sandbox_handle_from_low_level(
    value: object,
    *,
    sandbox_name: str | None,
    working_dir: str,
) -> DaytonaSandboxHandle:
    if isinstance(value, DaytonaSandboxHandle):
        return value
    if isinstance(value, str):
        return DaytonaSandboxHandle(
            sandbox_name=sandbox_name,
            working_dir=working_dir,
            handle_id=value,
        )
    handle_id = _low_level_field(value, "handle_id", "id")
    if handle_id is None:
        raise DaytonaSdkUnavailableError(
            "Low-level Daytona sandbox handle must provide handle_id or id"
        )
    low_sandbox_name = _low_level_field(value, "sandbox_name", "name")
    low_working_dir = _low_level_field(value, "working_dir")
    return DaytonaSandboxHandle(
        sandbox_name=low_sandbox_name if low_sandbox_name is not None else sandbox_name,
        working_dir=low_working_dir if low_working_dir is not None else working_dir,
        handle_id=handle_id,
    )


def _command_result_from_low_level(value: object) -> DaytonaClientCommandResult:
    if isinstance(value, DaytonaClientCommandResult):
        return value
    exit_code = _low_level_field(value, "exit_code")
    if exit_code is None:
        raise DaytonaSdkUnavailableError(
            "Low-level Daytona command result must provide exit_code"
        )
    stdout = _low_level_field(value, "stdout")
    stderr = _low_level_field(value, "stderr")
    summary_text = _low_level_field(value, "summary_text")
    return DaytonaClientCommandResult(
        exit_code=exit_code,
        stdout=stdout,
        stderr=stderr,
        summary_text=summary_text
        if summary_text is not None
        else f"daytona_sdk_protocol_command exit_code={exit_code}",
    )


def _low_level_field(value: object, *names: str) -> object:
    if isinstance(value, Mapping):
        for name in names:
            item = value.get(name)
            if item is not None:
                return item
        return None
    for name in names:
        item = getattr(value, name, None)
        if item is not None:
            return item
    return None


def _validate_nonempty_string(value: object, name: str) -> None:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{name} must be a non-empty string")


__all__ = (
    "DaytonaSdkAdapter",
    "DaytonaSdkAdapterConfig",
    "DaytonaSdkProtocolClient",
    "DaytonaSdkUnavailableError",
    "build_daytona_sdk_protocol_client",
)
