"""Real Daytona execution safety-gate contracts.

Distributed Evaluation Cycle 19 defines an explicit opt-in boundary for future
real Daytona execution. It does not import Daytona, call Daytona, create
sandboxes, use credentials, execute commands, upload/download files, or run
matches.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass

from .daytona_jobs import DEFAULT_SANDBOX_NAME_PREFIX, DEFAULT_WORKING_DIR


DEFAULT_DAYTONA_API_KEY_ENV_VAR = "DAYTONA_API_KEY"
DEFAULT_GITHUB_TOKEN_ENV_VAR = "GITHUB_TOKEN"
ALLOW_REAL_DAYTONA_ENV_VAR = "OW_EVAL_ALLOW_REAL_DAYTONA"
DAYTONA_API_KEY_ENV_VAR_NAME_ENV_VAR = "DAYTONA_API_KEY_ENV_VAR"
DAYTONA_API_URL_ENV_VAR = "DAYTONA_API_URL"
DAYTONA_TARGET_ENV_VAR = "DAYTONA_TARGET"
GITHUB_TOKEN_ENV_VAR_NAME_ENV_VAR = "GITHUB_TOKEN_ENV_VAR"
REQUIRE_GITHUB_TOKEN_ENV_VAR = "OW_EVAL_REQUIRE_GITHUB_TOKEN"
DAYTONA_DOTENV_PATH_ENV_VAR = "OW_EVAL_DOTENV_PATH"
DAYTONA_PROJECT_ID_ENV_VAR = "DAYTONA_PROJECT_ID"
DAYTONA_WORKSPACE_ID_ENV_VAR = "DAYTONA_WORKSPACE_ID"
DAYTONA_SNAPSHOT_ID_ENV_VAR = "DAYTONA_SNAPSHOT_ID"
DAYTONA_IMAGE_ENV_VAR = "DAYTONA_IMAGE"
DAYTONA_WORKING_DIR_ENV_VAR = "DAYTONA_WORKING_DIR"
DAYTONA_SANDBOX_NAME_PREFIX_ENV_VAR = "DAYTONA_SANDBOX_NAME_PREFIX"


@dataclass(frozen=True, slots=True)
class DaytonaRealExecutionConfig:
    """Explicit real-Daytona execution intent and environment references."""

    allow_real_daytona: bool = False
    api_key_env_var: str | None = DEFAULT_DAYTONA_API_KEY_ENV_VAR
    api_url: str | None = None
    target: str | None = None
    github_token_env_var: str | None = DEFAULT_GITHUB_TOKEN_ENV_VAR
    require_github_token: bool = False
    project_id: str | None = None
    workspace_id: str | None = None
    snapshot_id: str | None = None
    image: str | None = None
    default_working_dir: str = DEFAULT_WORKING_DIR
    sandbox_name_prefix: str | None = DEFAULT_SANDBOX_NAME_PREFIX

    def __post_init__(self) -> None:
        if not isinstance(self.allow_real_daytona, bool):
            raise ValueError("allow_real_daytona must be a boolean")
        _validate_optional_nonempty_string(self.api_key_env_var, "api_key_env_var")
        _validate_optional_nonempty_string(self.api_url, "api_url")
        _validate_optional_nonempty_string(self.target, "target")
        _validate_optional_nonempty_string(
            self.github_token_env_var,
            "github_token_env_var",
        )
        if not isinstance(self.require_github_token, bool):
            raise ValueError("require_github_token must be a boolean")
        _validate_optional_nonempty_string(self.project_id, "project_id")
        _validate_optional_nonempty_string(self.workspace_id, "workspace_id")
        _validate_optional_nonempty_string(self.snapshot_id, "snapshot_id")
        _validate_optional_nonempty_string(self.image, "image")
        _validate_nonempty_string(self.default_working_dir, "default_working_dir")
        _validate_optional_nonempty_string(
            self.sandbox_name_prefix,
            "sandbox_name_prefix",
        )

    def to_dict(self) -> dict[str, object]:
        """Return a deterministic JSON-safe dictionary."""

        return {
            "allow_real_daytona": self.allow_real_daytona,
            "api_key_env_var": self.api_key_env_var,
            "api_url": self.api_url,
            "target": self.target,
            "github_token_env_var": self.github_token_env_var,
            "require_github_token": self.require_github_token,
            "project_id": self.project_id,
            "workspace_id": self.workspace_id,
            "snapshot_id": self.snapshot_id,
            "image": self.image,
            "default_working_dir": self.default_working_dir,
            "sandbox_name_prefix": self.sandbox_name_prefix,
        }


@dataclass(frozen=True, slots=True)
class DaytonaRealExecutionReadiness:
    """Structured readiness result for real Daytona execution."""

    config: DaytonaRealExecutionConfig
    ready: bool
    missing_env_vars: tuple[str, ...] = ()
    exit_code: int = 2
    summary_text: str = ""
    error_text: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.config, DaytonaRealExecutionConfig):
            raise ValueError("config must be a DaytonaRealExecutionConfig")
        if not isinstance(self.ready, bool):
            raise ValueError("ready must be a boolean")
        _validate_string_tuple(self.missing_env_vars, "missing_env_vars")
        if isinstance(self.exit_code, bool) or not isinstance(self.exit_code, int):
            raise ValueError("exit_code must be an integer")
        _validate_nonempty_string(self.summary_text, "summary_text")
        _validate_optional_nonempty_string(self.error_text, "error_text")

    @property
    def passed(self) -> bool:
        """Return true when real Daytona execution is explicitly ready."""

        return self.ready and self.exit_code == 0

    def to_dict(self) -> dict[str, object]:
        """Return a deterministic JSON-safe dictionary."""

        return {
            "config": self.config.to_dict(),
            "ready": self.ready,
            "passed": self.passed,
            "missing_env_vars": list(self.missing_env_vars),
            "exit_code": self.exit_code,
            "summary_text": self.summary_text,
            "error_text": self.error_text,
        }


def read_daytona_real_execution_config_from_env(
    env: Mapping[str, str] | None = None,
) -> DaytonaRealExecutionConfig:
    """Build a real-execution config from environment-like string mappings."""

    _load_dotenv_if_using_process_env(env)
    effective_env = os.environ if env is None else env
    _validate_env_mapping(effective_env)
    api_key_env_var = _env_optional(
        effective_env,
        DAYTONA_API_KEY_ENV_VAR_NAME_ENV_VAR,
        default=DEFAULT_DAYTONA_API_KEY_ENV_VAR,
    )
    github_token_env_var = _env_optional(
        effective_env,
        GITHUB_TOKEN_ENV_VAR_NAME_ENV_VAR,
        default=DEFAULT_GITHUB_TOKEN_ENV_VAR,
    )
    return DaytonaRealExecutionConfig(
        allow_real_daytona=_env_flag(effective_env, ALLOW_REAL_DAYTONA_ENV_VAR),
        api_key_env_var=api_key_env_var,
        api_url=_env_optional(effective_env, DAYTONA_API_URL_ENV_VAR),
        target=_env_optional(effective_env, DAYTONA_TARGET_ENV_VAR),
        github_token_env_var=github_token_env_var,
        require_github_token=_env_flag(effective_env, REQUIRE_GITHUB_TOKEN_ENV_VAR),
        project_id=_env_optional(effective_env, DAYTONA_PROJECT_ID_ENV_VAR),
        workspace_id=_env_optional(effective_env, DAYTONA_WORKSPACE_ID_ENV_VAR),
        snapshot_id=_env_optional(effective_env, DAYTONA_SNAPSHOT_ID_ENV_VAR),
        image=_env_optional(effective_env, DAYTONA_IMAGE_ENV_VAR),
        default_working_dir=_env_optional(
            effective_env,
            DAYTONA_WORKING_DIR_ENV_VAR,
            default=DEFAULT_WORKING_DIR,
        )
        or DEFAULT_WORKING_DIR,
        sandbox_name_prefix=_env_optional(
            effective_env,
            DAYTONA_SANDBOX_NAME_PREFIX_ENV_VAR,
            default=DEFAULT_SANDBOX_NAME_PREFIX,
        ),
    )


def validate_daytona_real_execution_readiness(
    config: DaytonaRealExecutionConfig | None = None,
    env: Mapping[str, str] | None = None,
) -> DaytonaRealExecutionReadiness:
    """Return structured real-Daytona readiness without performing real work."""

    effective_config = (
        config
        if config is not None
        else read_daytona_real_execution_config_from_env(env)
    )
    if not isinstance(effective_config, DaytonaRealExecutionConfig):
        raise ValueError("config must be a DaytonaRealExecutionConfig")
    _load_dotenv_if_using_process_env(env)
    effective_env = os.environ if env is None else env
    _validate_env_mapping(effective_env)

    errors: list[str] = []
    missing_env_vars: list[str] = []
    if not effective_config.allow_real_daytona:
        errors.append("real Daytona execution is not explicitly allowed")
    if effective_config.api_key_env_var is None:
        errors.append("api_key_env_var is required")
    else:
        if _env_value_missing(effective_env, effective_config.api_key_env_var):
            missing_env_vars.append(effective_config.api_key_env_var)
    if effective_config.require_github_token and effective_config.github_token_env_var is None:
        errors.append("github_token_env_var is required")
    elif effective_config.require_github_token and effective_config.github_token_env_var is not None:
        if _env_value_missing(effective_env, effective_config.github_token_env_var):
            missing_env_vars.append(effective_config.github_token_env_var)

    if missing_env_vars:
        errors.append("missing env vars: " + ", ".join(missing_env_vars))

    ready = not errors
    return DaytonaRealExecutionReadiness(
        config=effective_config,
        ready=ready,
        missing_env_vars=tuple(missing_env_vars),
        exit_code=0 if ready else 2,
        summary_text=(
            "daytona_real_execution_readiness="
            f"{'READY' if ready else 'BLOCKED'} "
            f"allow_real_daytona={effective_config.allow_real_daytona} "
            f"target_configured={effective_config.target is not None} "
            f"github_token_required={effective_config.require_github_token} "
            f"missing_env_vars={len(missing_env_vars)} "
            f"exit_code={0 if ready else 2}"
        ),
        error_text="; ".join(errors) if errors else None,
    )


def _load_dotenv_if_using_process_env(env: Mapping[str, str] | None) -> None:
    if env is not None:
        return
    try:
        from dotenv import load_dotenv
    except Exception:  # noqa: BLE001 - dotenv is optional setup sugar.
        return
    dotenv_path = os.environ.get(DAYTONA_DOTENV_PATH_ENV_VAR)
    if dotenv_path is not None and dotenv_path.strip():
        load_dotenv(dotenv_path.strip(), override=False)
    else:
        load_dotenv(override=False)


def _env_value_missing(env: Mapping[str, str], name: str) -> bool:
    value = env.get(name)
    return value is None or not value.strip()


def _env_flag(env: Mapping[str, str], name: str) -> bool:
    value = env.get(name)
    if value is None:
        return False
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _env_optional(
    env: Mapping[str, str],
    name: str,
    *,
    default: str | None = None,
) -> str | None:
    value = env.get(name)
    if value is None:
        return default
    stripped = value.strip()
    return stripped or None


def _validate_env_mapping(value: object) -> None:
    if not isinstance(value, Mapping):
        raise ValueError("env must be a mapping")
    for key, item in value.items():
        if not isinstance(key, str):
            raise ValueError("env keys must be strings")
        if not isinstance(item, str):
            raise ValueError(f"env[{key}] must be a string")


def _validate_string_tuple(value: object, name: str) -> None:
    if not isinstance(value, tuple):
        raise ValueError(f"{name} must be a tuple")
    for index, item in enumerate(value):
        if not isinstance(item, str) or not item:
            raise ValueError(f"{name}[{index}] must be a non-empty string")


def _validate_optional_nonempty_string(value: object, name: str) -> None:
    if value is not None:
        _validate_nonempty_string(value, name)


def _validate_nonempty_string(value: object, name: str) -> None:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{name} must be a non-empty string")


__all__ = (
    "DaytonaRealExecutionConfig",
    "DaytonaRealExecutionReadiness",
    "read_daytona_real_execution_config_from_env",
    "validate_daytona_real_execution_readiness",
)
