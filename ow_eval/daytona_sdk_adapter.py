"""Skeleton adapter for a future real Daytona SDK client.

Distributed Evaluation Cycle 19 provides the explicit adapter boundary for real
Daytona execution without importing Daytona, creating sandboxes, executing
commands, uploading/downloading files, or running matches. Tests inject fake SDK
clients through this adapter; without an injected client, methods fail closed
with deterministic errors.
"""

from __future__ import annotations

import importlib
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field

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
    """Build the default protocol facade from a fake Daytona-like SDK module."""

    if not isinstance(config, DaytonaRealExecutionConfig):
        raise ValueError("config must be a DaytonaRealExecutionConfig")
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
