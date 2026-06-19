"""Skeleton adapter for a future real Daytona SDK client.

Distributed Evaluation Cycle 19 provides the explicit adapter boundary for real
Daytona execution without importing Daytona, creating sandboxes, executing
commands, uploading/downloading files, or running matches. Tests inject fake SDK
clients through this adapter; without an injected client, methods fail closed
with deterministic errors.
"""

from __future__ import annotations

import importlib
from collections.abc import Callable
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
        if self.config.sdk_client_factory is None:
            raise DaytonaSdkUnavailableError(
                "Daytona SDK adapter requires an injected sdk_client or "
                "sdk_client_factory in this cycle"
            )
        sdk_module = self._import_sdk_module()
        try:
            client = self.config.sdk_client_factory(
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
        return self.sdk_client

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


def _validate_nonempty_string(value: object, name: str) -> None:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{name} must be a non-empty string")


__all__ = (
    "DaytonaSdkAdapter",
    "DaytonaSdkAdapterConfig",
    "DaytonaSdkUnavailableError",
)
