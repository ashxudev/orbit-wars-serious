"""Daytona source-mode helpers for real shard execution."""

from __future__ import annotations

import subprocess
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path


DAYTONA_SOURCE_MODE_GITHUB = "github"
DAYTONA_SOURCE_MODE_SNAPSHOT = "snapshot"
DAYTONA_SOURCE_MODE_LOCAL = "local"
DAYTONA_SOURCE_MODES = (
    DAYTONA_SOURCE_MODE_GITHUB,
    DAYTONA_SOURCE_MODE_SNAPSHOT,
    DAYTONA_SOURCE_MODE_LOCAL,
)
DEFAULT_DAYTONA_SOURCE_MODE = DAYTONA_SOURCE_MODE_GITHUB
DEFAULT_DAYTONA_GITHUB_REPO = "https://github.com/ashxudev/orbit-wars-serious.git"
DEFAULT_DAYTONA_GIT_REF = "auto"
DEFAULT_DAYTONA_GITHUB_TOKEN_ENV_VAR = "DAYTONA_GITHUB_TOKEN"
DEFAULT_DAYTONA_GIT_REMOTE = "origin"
DEFAULT_DAYTONA_GIT_BRANCH = "main"
AUTO_DAYTONA_GIT_REF_VALUES = ("auto", "head", "current", "current-head")
COMMIT_PUSH_REQUIRED_MESSAGE = "commit and push before Daytona real run"


@dataclass(frozen=True, slots=True)
class DaytonaGitPreflightResult:
    """Result for local commit/push readiness before real GitHub-mode Daytona."""

    source_mode: str
    repo_root: str
    remote: str
    branch: str
    head_commit: str | None = None
    remote_commit: str | None = None
    ready: bool = False
    dirty_paths: tuple[str, ...] = ()
    missing_remote: bool = False
    exit_code: int = 2
    summary_text: str = ""
    error_text: str | None = None

    def __post_init__(self) -> None:
        _validate_source_mode(self.source_mode)
        _validate_nonempty_string(self.repo_root, "repo_root")
        _validate_nonempty_string(self.remote, "remote")
        _validate_nonempty_string(self.branch, "branch")
        _validate_optional_nonempty_string(self.head_commit, "head_commit")
        _validate_optional_nonempty_string(self.remote_commit, "remote_commit")
        if not isinstance(self.ready, bool):
            raise ValueError("ready must be a boolean")
        _validate_string_tuple(self.dirty_paths, "dirty_paths")
        if not isinstance(self.missing_remote, bool):
            raise ValueError("missing_remote must be a boolean")
        if isinstance(self.exit_code, bool) or not isinstance(self.exit_code, int):
            raise ValueError("exit_code must be an integer")
        _validate_nonempty_string(self.summary_text, "summary_text")
        _validate_optional_nonempty_string(self.error_text, "error_text")

    @property
    def passed(self) -> bool:
        return self.ready and self.exit_code == 0

    def to_dict(self) -> dict[str, object]:
        return {
            "branch": self.branch,
            "dirty_paths": list(self.dirty_paths),
            "error_text": self.error_text,
            "exit_code": self.exit_code,
            "head_commit": self.head_commit,
            "missing_remote": self.missing_remote,
            "passed": self.passed,
            "ready": self.ready,
            "remote": self.remote,
            "remote_commit": self.remote_commit,
            "repo_root": self.repo_root,
            "source_mode": self.source_mode,
            "summary_text": self.summary_text,
        }


def normalize_daytona_source_mode(value: str | None) -> str:
    """Return a normalized supported Daytona source mode."""

    mode = DEFAULT_DAYTONA_SOURCE_MODE if value is None else value.strip().lower()
    _validate_source_mode(mode)
    return mode


def resolve_daytona_git_ref(
    git_ref: str | None,
    *,
    repo_root: str | Path | None = None,
) -> str:
    """Resolve ``auto`` Git refs to the local full HEAD commit SHA."""

    value = DEFAULT_DAYTONA_GIT_REF if git_ref is None else git_ref.strip()
    _validate_nonempty_string(value, "git_ref")
    if value.lower() not in AUTO_DAYTONA_GIT_REF_VALUES:
        return value
    return local_git_commit(repo_root)


def local_git_commit(repo_root: str | Path | None = None) -> str:
    """Return local ``git rev-parse HEAD`` for ``repo_root``."""

    completed = _run_git(("rev-parse", "HEAD"), repo_root=repo_root)
    commit = completed.stdout.strip()
    _validate_nonempty_string(commit, "git_commit")
    return commit


def validate_daytona_git_preflight(
    *,
    source_mode: str = DEFAULT_DAYTONA_SOURCE_MODE,
    repo_root: str | Path | None = None,
    remote: str = DEFAULT_DAYTONA_GIT_REMOTE,
    branch: str = DEFAULT_DAYTONA_GIT_BRANCH,
    fetch: bool = True,
) -> DaytonaGitPreflightResult:
    """Validate that GitHub-mode real Daytona will run a clean pushed commit."""

    mode = normalize_daytona_source_mode(source_mode)
    root = Path(repo_root) if repo_root is not None else Path(__file__).resolve().parents[1]
    _validate_nonempty_string(remote, "remote")
    _validate_nonempty_string(branch, "branch")
    if mode != DAYTONA_SOURCE_MODE_GITHUB:
        return DaytonaGitPreflightResult(
            source_mode=mode,
            repo_root=str(root),
            remote=remote,
            branch=branch,
            ready=True,
            exit_code=0,
            summary_text=(
                "daytona_git_preflight=SKIPPED "
                f"source_mode={mode} exit_code=0"
            ),
        )

    errors: list[str] = []
    dirty_paths: tuple[str, ...] = ()
    head_commit: str | None = None
    remote_commit: str | None = None
    missing_remote = False
    try:
        head_commit = local_git_commit(root)
        dirty_paths = _dirty_paths(root)
        if dirty_paths:
            errors.append("working tree has uncommitted source changes")
        if fetch:
            _run_git(("fetch", remote, branch), repo_root=root)
        remote_commit = _run_git(
            ("rev-parse", f"{remote}/{branch}"),
            repo_root=root,
        ).stdout.strip()
        _validate_nonempty_string(remote_commit, "remote_commit")
        if head_commit != remote_commit:
            errors.append(
                f"local HEAD {head_commit} does not match {remote}/{branch} {remote_commit}"
            )
    except subprocess.CalledProcessError as exc:
        missing_remote = True
        stderr = (exc.stderr or exc.stdout or "").strip()
        errors.append(f"git preflight command failed: {stderr or exc}")
    except Exception as exc:  # noqa: BLE001 - structured boundary.
        errors.append(f"{type(exc).__name__}: {exc}")

    ready = not errors
    error_text = None if ready else f"{COMMIT_PUSH_REQUIRED_MESSAGE}: " + "; ".join(errors)
    return DaytonaGitPreflightResult(
        source_mode=mode,
        repo_root=str(root),
        remote=remote,
        branch=branch,
        head_commit=head_commit,
        remote_commit=remote_commit,
        ready=ready,
        dirty_paths=dirty_paths,
        missing_remote=missing_remote,
        exit_code=0 if ready else 2,
        summary_text=(
            "daytona_git_preflight="
            f"{'PASS' if ready else 'ERROR'} source_mode={mode} "
            f"remote={remote} branch={branch} dirty_paths={len(dirty_paths)} "
            f"exit_code={0 if ready else 2}"
        ),
        error_text=error_text,
    )


def build_github_bootstrap_argv(
    *,
    github_repo: str,
    git_ref: str,
    github_token_env_var: str | None,
    checkout_dir: str,
    python_command: str,
    runner_script: str,
    job_path: str,
) -> tuple[str, ...]:
    """Build a token-free shell bootstrap argv for GitHub-mode Daytona."""

    _validate_nonempty_string(github_repo, "github_repo")
    _validate_nonempty_string(git_ref, "git_ref")
    _validate_optional_nonempty_string(github_token_env_var, "github_token_env_var")
    _validate_nonempty_string(checkout_dir, "checkout_dir")
    _validate_nonempty_string(python_command, "python_command")
    _validate_nonempty_string(runner_script, "runner_script")
    _validate_nonempty_string(job_path, "job_path")
    token_env = github_token_env_var or ""
    script = "\n".join(
        (
            "set -euo pipefail",
            f"REPO_URL={_shell_quote(github_repo)}",
            f"GIT_REF={_shell_quote(git_ref)}",
            f"CHECKOUT_DIR={_shell_quote(checkout_dir)}",
            f"PYTHON_BIN={_shell_quote(python_command)}",
            f"TOKEN_ENV={_shell_quote(token_env)}",
            'if [ ! -x "$PYTHON_BIN" ]; then PYTHON_BIN=python3; fi',
            'TOKEN_VALUE=""',
            'if [ -n "$TOKEN_ENV" ]; then TOKEN_VALUE="${!TOKEN_ENV:-}"; fi',
            'CLONE_URL="$REPO_URL"',
            'if [ -n "$TOKEN_VALUE" ]; then',
            '  CLONE_URL="$("$PYTHON_BIN" -c \'import os,sys,urllib.parse as u; '
            'repo=sys.argv[1]; token=os.environ.get(sys.argv[2], ""); '
            'p=u.urlsplit(repo); print(u.urlunsplit((p.scheme, '
            '"x-access-token:"+u.quote(token)+"@"+p.netloc, p.path, p.query, p.fragment)))\' "$REPO_URL" "$TOKEN_ENV")"',
            "fi",
            'mkdir -p "$(dirname "$CHECKOUT_DIR")"',
            'if command -v git >/dev/null 2>&1; then',
            '  if [ -d "$CHECKOUT_DIR/.git" ]; then',
            '    git -C "$CHECKOUT_DIR" remote set-url origin "$CLONE_URL" || true',
            '    git -C "$CHECKOUT_DIR" fetch origin "$GIT_REF"',
            "  else",
            '    rm -rf "$CHECKOUT_DIR"',
            '    git clone --no-checkout "$CLONE_URL" "$CHECKOUT_DIR"',
            '    git -C "$CHECKOUT_DIR" fetch origin "$GIT_REF"',
            "  fi",
            '  git -C "$CHECKOUT_DIR" checkout --detach "$GIT_REF"',
            '  test "$(git -C "$CHECKOUT_DIR" rev-parse HEAD)" = "$GIT_REF"',
            "else",
            '  "$PYTHON_BIN" -c \'',
            "import io, os, shutil, sys, urllib.parse, urllib.request, zipfile",
            "repo, ref, checkout_dir, token_env = sys.argv[1:5]",
            "parts = urllib.parse.urlsplit(repo)",
            "if parts.netloc != 'github.com':",
            "    raise SystemExit(f'git executable missing and non-GitHub repo unsupported: {parts.netloc}')",
            "repo_path = parts.path.strip('/')",
            "if repo_path.endswith('.git'):",
            "    repo_path = repo_path[:-4]",
            "owner_repo = repo_path.split('/')",
            "if len(owner_repo) != 2 or not all(owner_repo):",
            "    raise SystemExit(f'cannot parse GitHub repo URL: {repo}')",
            "url = f'https://api.github.com/repos/{owner_repo[0]}/{owner_repo[1]}/zipball/{ref}'",
            "headers = {'User-Agent': 'orbit-wars-daytona-bootstrap'}",
            "token = os.environ.get(token_env, '') if token_env else ''",
            "if token:",
            "    headers['Authorization'] = f'Bearer {token}'",
            "request = urllib.request.Request(url, headers=headers)",
            "with urllib.request.urlopen(request, timeout=120) as response:",
            "    payload = response.read()",
            "parent = os.path.dirname(checkout_dir) or '.'",
            "tmp_dir = os.path.join(parent, '.github-archive-checkout-tmp')",
            "shutil.rmtree(tmp_dir, ignore_errors=True)",
            "os.makedirs(tmp_dir, exist_ok=True)",
            "with zipfile.ZipFile(io.BytesIO(payload)) as archive:",
            "    archive.extractall(tmp_dir)",
            "entries = [os.path.join(tmp_dir, name) for name in os.listdir(tmp_dir)]",
            "roots = [path for path in entries if os.path.isdir(path)]",
            "if len(roots) != 1:",
            "    raise SystemExit('unexpected GitHub archive layout')",
            "shutil.rmtree(checkout_dir, ignore_errors=True)",
            "shutil.move(roots[0], checkout_dir)",
            "shutil.rmtree(tmp_dir, ignore_errors=True)",
            "with open(os.path.join(checkout_dir, '.ow-github-source-ref'), 'w', encoding='utf-8') as handle:",
            "    handle.write(ref + '\\n')",
            "' \"$REPO_URL\" \"$GIT_REF\" \"$CHECKOUT_DIR\" \"$TOKEN_ENV\"",
            '  test "$(cat "$CHECKOUT_DIR/.ow-github-source-ref")" = "$GIT_REF"',
            "fi",
            'if [ -f "$CHECKOUT_DIR/requirements.txt" ]; then',
            '  "$PYTHON_BIN" -m pip install -r "$CHECKOUT_DIR/requirements.txt"',
            "fi",
            f"cd \"$CHECKOUT_DIR\"",
            f"{_shell_quote(python_command)} {_shell_quote(runner_script)} {_shell_quote(job_path)}",
        )
    )
    return ("bash", "-lc", script)


def redacted_github_repo_url(github_repo: str) -> str:
    """Return a safe repo URL for plan/report display."""

    _validate_nonempty_string(github_repo, "github_repo")
    if "@" not in github_repo:
        return github_repo
    scheme, rest = github_repo.split("://", 1) if "://" in github_repo else ("", github_repo)
    host_path = rest.split("@", 1)[1]
    return f"{scheme}://<redacted>@{host_path}" if scheme else f"<redacted>@{host_path}"


def _dirty_paths(repo_root: Path) -> tuple[str, ...]:
    completed = _run_git(
        ("status", "--porcelain", "--untracked-files=normal"),
        repo_root=repo_root,
    )
    paths = []
    for line in completed.stdout.splitlines():
        if not line.strip():
            continue
        path = line[3:] if len(line) > 3 else line
        paths.append(path.strip())
    return tuple(paths)


def _run_git(
    args: tuple[str, ...],
    *,
    repo_root: str | Path | None = None,
) -> subprocess.CompletedProcess[str]:
    root = Path(repo_root) if repo_root is not None else Path(__file__).resolve().parents[1]
    return subprocess.run(
        ("git", *args),
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    )


def _shell_quote(value: str) -> str:
    import shlex

    return shlex.quote(value)


def _validate_source_mode(value: object) -> None:
    if value not in DAYTONA_SOURCE_MODES:
        raise ValueError(f"source_mode must be one of {', '.join(DAYTONA_SOURCE_MODES)}")


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
    "AUTO_DAYTONA_GIT_REF_VALUES",
    "COMMIT_PUSH_REQUIRED_MESSAGE",
    "DAYTONA_SOURCE_MODE_GITHUB",
    "DAYTONA_SOURCE_MODE_LOCAL",
    "DAYTONA_SOURCE_MODE_SNAPSHOT",
    "DAYTONA_SOURCE_MODES",
    "DEFAULT_DAYTONA_GIT_BRANCH",
    "DEFAULT_DAYTONA_GIT_REF",
    "DEFAULT_DAYTONA_GIT_REMOTE",
    "DEFAULT_DAYTONA_GITHUB_REPO",
    "DEFAULT_DAYTONA_GITHUB_TOKEN_ENV_VAR",
    "DEFAULT_DAYTONA_SOURCE_MODE",
    "DaytonaGitPreflightResult",
    "build_github_bootstrap_argv",
    "local_git_commit",
    "normalize_daytona_source_mode",
    "redacted_github_repo_url",
    "resolve_daytona_git_ref",
    "validate_daytona_git_preflight",
)
