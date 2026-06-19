"""Skeleton adapter for a future real Daytona SDK client.

Distributed Evaluation Cycle 19 provides the explicit adapter boundary for real
Daytona execution without importing Daytona, creating sandboxes, executing
commands, uploading/downloading files, or running matches. Tests inject fake SDK
clients through this adapter; without an injected client, methods fail closed
with deterministic errors.
"""

from __future__ import annotations

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

    def __post_init__(self) -> None:
        if not isinstance(self.real_execution_config, DaytonaRealExecutionConfig):
            raise ValueError("real_execution_config must be a DaytonaRealExecutionConfig")
        if self.readiness is not None and not isinstance(
            self.readiness,
            DaytonaRealExecutionReadiness,
        ):
            raise ValueError("readiness must be a DaytonaRealExecutionReadiness")

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
        if self.sdk_client is None:
            raise DaytonaSdkUnavailableError(
                "Daytona SDK adapter requires an injected sdk_client in this cycle"
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


__all__ = (
    "DaytonaSdkAdapter",
    "DaytonaSdkAdapterConfig",
    "DaytonaSdkUnavailableError",
)
