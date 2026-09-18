"""Isolated OpenCode launcher and config generator for the OpenFrontBench agent.

This module builds a *self-contained* OpenCode configuration for the playing
agent and launches it in a bounded, isolated child process. It is deliberately
small and dependency-free so it can be unit tested without a model call and
without the future engine API.

Isolation, verified against installed OpenCode 1.17.11 and the official docs
(https://opencode.ai/docs/config, /permissions, /mcp-servers):

* Configuration files are **merged**, not replaced. Precedence is remote ->
  global (``~/.config/opencode/opencode.json``) -> custom (``OPENCODE_CONFIG``)
  -> project (``opencode.json`` found from cwd up to the git root). Therefore a
  custom ``OPENCODE_CONFIG`` alone is *not* isolation: the global config still
  merges in, and a project config still overrides us. We redirect
  ``HOME``/``XDG_*``, set ``OPENCODE_CONFIG`` and refuse a cwd inside any git
  repository. Project *plugins* are discovered upward from the working
  directory (verified: a work dir under Downloads picked up
  ``Downloads/.opencode/plugins`` in the resolved config), so we also refuse
  any run root with a ``.opencode`` or ``opencode.json`` ancestor.
* Managed config (``/Library/Application Support/opencode`` on macOS,
  ``/etc/opencode`` on Linux, macOS managed preferences) overrides everything
  and cannot be excluded, so its presence is a hard, fail-closed error.
* ``permission`` is singular; rules resolve last-match-wins. The wildcard deny
  must therefore be listed before the game MCP allow, and the game server name
  must never be pinned in the legacy ``tools`` map (that would invert the order).
* ``opencode run --pure`` disables external plugins (supported by the installed
  CLI). The model is set in the config, never via ``-m``.

The API takes an absolute MCP argv and cwd from the caller rather than guessing
the engine package layout.
"""

from __future__ import annotations

import json
import logging
import os
import re
import signal
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping, Sequence

log = logging.getLogger(__name__)

CONFIG_SCHEMA = "https://opencode.ai/config.json"
DEFAULT_AGENT_NAME = "game"
DEFAULT_AGENT_PROMPT = (
    "You are the OpenFrontBench playing agent. Play one OpenFront match to win. "
    "Use only the game MCP tools to observe state and submit decisions. "
    "Do not attempt to read files, run shell commands, search the web, or spawn "
    "subagents: those tools are denied. Commit to a strategy in the diary tool "
    "and act on it."
)
DEFAULT_PROVIDER = "anthropic"
DEFAULT_MODEL = "anthropic/claude-sonnet-4-5"
DEFAULT_KEY_ENV_VAR = "ANTHROPIC_API_KEY"

# Custom providers the stock OpenCode binary does not know: endpoint it must
# be pointed at. Public routing info only — no credentials here.
PROVIDER_BASE_URLS: dict[str, str] = {
    "opencode-go": "https://opencode.ai/zen/go/v1",
    "opencode-zen": "https://opencode.ai/zen/v1",
}

# Only these inherited variables reach the OpenCode child. Everything else,
# including every ``OPENCODE_*`` config override and every provider credential,
# is dropped and rebuilt explicitly.
ALLOWED_ENV_KEYS: tuple[str, ...] = (
    "PATH",
    "LANG",
    "LC_ALL",
    "LC_CTYPE",
    "TERM",
    "TZ",
    "TMPDIR",
    "TEMP",
    "TMP",
    "SHELL",
    "USER",
    "LOGNAME",
    "SSL_CERT_FILE",
    "SSL_CERT_DIR",
    "NODE_EXTRA_CA_CERTS",
    "SYSTEMROOT",
    "COMSPEC",
    "PATHEXT",
    "WINDIR",
)

# A deliberately non-secret value used only when running ``opencode debug
# config`` to verify the resolved configuration.
VERIFY_PLACEHOLDER_KEY = "opencode-config-verification-placeholder"
REDACTION = "***REDACTED***"
_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]*$")


class LauncherError(RuntimeError):
    """Base class for launcher failures."""


class InvalidMcpSpecError(LauncherError):
    """The MCP server specification is not absolute or not well formed."""


class IsolationError(LauncherError):
    """The requested run directory is not isolated from repository/global config."""


class MissingApiKeyError(LauncherError):
    """No API key was supplied, so the run must not start."""


class ManagedConfigError(LauncherError):
    """Managed OpenCode config exists and cannot be excluded."""


class ConfigVerificationError(LauncherError):
    """The resolved config does not match the isolation contract."""


def _wildcard_match(value: str, pattern: str) -> bool:
    """Match ``value`` against a simple ``*``/``?`` glob (OpenCode semantics)."""
    parts: list[str] = []
    for char in pattern:
        if char == "*":
            parts.append(".*")
        elif char == "?":
            parts.append(".")
        else:
            parts.append(re.escape(char))
    return re.fullmatch("".join(parts), value) is not None


def permission_action(permission: Mapping[str, Any], tool: str) -> str:
    """Return the effective action for ``tool`` using last-match-wins.

    Mirrors OpenCode's ``Permission.evaluate`` (``findLast`` over the ruleset)
    for a string-valued ``permission`` map. Used to self-check generated configs
    without starting the real binary.
    """
    for name, rule in reversed(list(permission.items())):
        if not _wildcard_match(tool, name):
            continue
        if isinstance(rule, str):
            return rule
        if isinstance(rule, Mapping):
            for pattern, action in reversed(list(rule.items())):
                if _wildcard_match(tool, str(pattern)):
                    return str(action)
    return "ask"


@dataclass(frozen=True)
class McpServerSpec:
    """A local MCP server defined by absolute argv and an absolute cwd.

    The caller (future engine/runner) supplies the real values; the launcher
    never guesses a package layout or module name.
    """

    name: str
    command: tuple[str, ...]
    cwd: str
    environment: Mapping[str, str] = field(default_factory=dict)
    timeout_ms: int = 10_000

    def __post_init__(self) -> None:
        if (
            not isinstance(self.name, str)
            or not _NAME_RE.match(self.name)
            or "*" in self.name
        ):
            raise InvalidMcpSpecError(
                f"MCP server name must match {_NAME_RE.pattern!r}: {self.name!r}"
            )
        command = tuple(str(part) for part in self.command)
        object.__setattr__(self, "command", command)
        if not command:
            raise InvalidMcpSpecError("MCP command must be a non-empty argv")
        if not Path(command[0]).is_absolute():
            raise InvalidMcpSpecError(
                f"MCP argv[0] must be absolute, got {command[0]!r}"
            )
        if not isinstance(self.cwd, str) or not Path(self.cwd).is_absolute():
            raise InvalidMcpSpecError(f"MCP cwd must be absolute, got {self.cwd!r}")
        if not isinstance(self.timeout_ms, int) or self.timeout_ms <= 0:
            raise InvalidMcpSpecError("MCP timeout_ms must be a positive integer")
        env = dict(self.environment)
        for key, value in env.items():
            if not isinstance(key, str) or not isinstance(value, str):
                raise InvalidMcpSpecError("MCP environment must map strings to strings")
        object.__setattr__(self, "environment", env)


@dataclass(frozen=True)
class IsolatedRun:
    """Filesystem layout of one isolated OpenCode run."""

    root: Path
    home: Path
    xdg_config: Path
    xdg_data: Path
    xdg_cache: Path
    xdg_state: Path
    config_file: Path
    work_dir: Path
    events_file: Path


@dataclass(frozen=True)
class ProcessResult:
    """Outcome of a bounded child process."""

    argv: tuple[str, ...]
    returncode: int | None
    stdout: str
    stderr: str
    timed_out: bool
    duration_s: float


@dataclass(frozen=True)
class LaunchResult:
    """Everything a caller needs to audit one playing-agent launch."""

    run: IsolatedRun
    config: Mapping[str, Any]
    resolved_config: Mapping[str, Any] | None
    process: ProcessResult


def build_config(
    *,
    model: str = DEFAULT_MODEL,
    mcp: McpServerSpec | None = None,
    agent_name: str = DEFAULT_AGENT_NAME,
    agent_prompt: str = DEFAULT_AGENT_PROMPT,
    provider: str | None = DEFAULT_PROVIDER,
    key_env_var: str | None = DEFAULT_KEY_ENV_VAR,
    base_url: str | None = None,
) -> dict[str, Any]:
    """Return the isolated OpenCode config as a plain dict.

    The dict never contains a key literal: provider credentials are referenced
    only as ``{env:VAR}`` and the value is injected into the child environment
    at launch time.

    ``mcp=None`` builds a coach config: no match tools, file tools only.
    """
    if not isinstance(model, str) or not model:
        raise ValueError("model must be a non-empty 'provider/model' string")
    if not isinstance(agent_name, str) or not _NAME_RE.match(agent_name):
        raise ValueError(f"agent_name is not a safe identifier: {agent_name!r}")

    if mcp is None:
        permission = {
            "*": "deny",
            "read": "allow",
            "edit": "allow",
            "write": "allow",
        }
    else:
        permission = {"*": "deny", f"{mcp.name}_*": "allow"}
    permission = dict[str, Any](permission)
    config: dict[str, Any] = {
        "$schema": CONFIG_SCHEMA,
        "model": model,
        "small_model": model,
        "autoupdate": False,
        "snapshot": False,
        "share": "disabled",
        "default_agent": agent_name,
        "permission": permission,
        "agent": {
            agent_name: {
                "description": "OpenFrontBench playing agent: game MCP tools only.",
                "mode": "primary",
                "model": model,
                "prompt": agent_prompt,
                "permission": dict(permission),
            }
        },
    }
    if mcp is not None:
        config["mcp"] = {
            mcp.name: {
                "type": "local",
                "command": list(mcp.command),
                "cwd": mcp.cwd,
                "enabled": True,
                "timeout": mcp.timeout_ms,
                "environment": dict(mcp.environment),
            }
        }
    if provider and key_env_var:
        options: dict[str, str] = {"apiKey": "{env:" + key_env_var + "}"}
        if base_url:
            options["baseURL"] = base_url
        config["provider"] = {provider: {"options": options}}
    return config


def build_agent_command(
    *,
    prompt: str,
    agent_name: str = DEFAULT_AGENT_NAME,
    output_format: str = "json",
    pure: bool = True,
    opencode_bin: str = "opencode",
) -> list[str]:
    """Build the ``opencode run`` argv.

    The model is intentionally absent: it lives in the generated config. The
    installed CLI supports ``--format json`` (raw events) and ``--pure`` (no
    external plugins).
    """
    argv = [opencode_bin, "run", "--format", output_format, "--agent", agent_name]
    if pure:
        argv.append("--pure")
    argv.append(prompt)
    return argv


def find_git_root(path: Path | str) -> Path | None:
    """Return the nearest ancestor (or self) containing ``.git``, if any."""
    current = Path(path).expanduser().resolve()
    if current.is_file():
        current = current.parent
    for candidate in (current, *current.parents):
        if (candidate / ".git").exists():
            return candidate
    return None


def prepare_run(root: Path | str, config: Mapping[str, Any]) -> IsolatedRun:
    """Create the isolated directory tree and write the config file.

    Raises ``IsolationError`` if ``root`` is inside a git repository, because
    project configs merge over a custom ``OPENCODE_CONFIG`` and would silently
    weaken the generated permissions. Also raises if any ancestor directory of
    ``root`` holds ``.opencode`` or ``opencode.json``: OpenCode discovers
    project plugins upward from the working directory, so such an ancestor
    would inject foreign plugins into the isolated run.
    """
    root_path = Path(root).expanduser().resolve()
    repo = find_git_root(root_path)
    if repo is not None:
        raise IsolationError(
            f"run root {root_path} is inside the git repository at {repo}; "
            "project config would override the isolated config"
        )
    for candidate in (root_path, *root_path.parents):
        if (candidate / ".opencode").exists() or (candidate / "opencode.json").exists():
            raise IsolationError(
                f"run root {root_path} is below {candidate}, which holds "
                "OpenCode project configuration; it would leak plugins or "
                "config into the isolated run"
            )
    run = IsolatedRun(
        root=root_path,
        home=root_path / "home",
        xdg_config=root_path / "xdg" / "config",
        xdg_data=root_path / "xdg" / "data",
        xdg_cache=root_path / "xdg" / "cache",
        xdg_state=root_path / "xdg" / "state",
        config_file=root_path / "config" / "opencode.json",
        work_dir=root_path / "work",
        events_file=root_path / "events.jsonl",
    )
    for directory in (
        run.root,
        run.home,
        run.xdg_config,
        run.xdg_data,
        run.xdg_cache,
        run.xdg_state,
        run.config_file.parent,
        run.work_dir,
    ):
        directory.mkdir(parents=True, exist_ok=True)
    run.config_file.write_text(
        json.dumps(dict(config), indent=2) + "\n", encoding="utf-8"
    )
    return run


def seed_models_cache(run: IsolatedRun, source: Path | str) -> Path:
    """Copy a host models.json cache into the isolated XDG cache.

    The isolated run gets a fresh ``XDG_CACHE_HOME`` so host config cannot
    leak in — but OpenCode also resolves run-time models from that cache, so
    a model newer than the bundled catalog is "not found" without a seeded
    copy. Only the single cache file is copied; nothing is merged or executed.
    Fails closed when the source is absent.
    """
    src = Path(source)
    if not src.is_file():
        raise LauncherError(f"models cache source not found: {src}")
    dest = run.xdg_cache / "opencode" / "models.json"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(src.read_bytes())
    return dest


def build_isolated_env(
    *,
    run: IsolatedRun,
    base_env: Mapping[str, str] | None = None,
) -> dict[str, str]:
    """Build an environment with no inherited OpenCode config or credentials."""
    base = dict(os.environ) if base_env is None else dict(base_env)
    env: dict[str, str] = {}
    for key in ALLOWED_ENV_KEYS:
        value = base.get(key)
        if value:
            env[key] = value
    if not env.get("PATH"):
        env["PATH"] = os.defpath
    env["HOME"] = str(run.home)
    env["XDG_CONFIG_HOME"] = str(run.xdg_config)
    env["XDG_DATA_HOME"] = str(run.xdg_data)
    env["XDG_CACHE_HOME"] = str(run.xdg_cache)
    env["XDG_STATE_HOME"] = str(run.xdg_state)
    env["OPENCODE_CONFIG"] = str(run.config_file)
    env["OPENCODE_DISABLE_AUTOUPDATE"] = "true"
    return env


def inject_api_key(
    env: Mapping[str, str],
    *,
    api_key: str | None,
    key_env_var: str = DEFAULT_KEY_ENV_VAR,
) -> dict[str, str]:
    """Return ``env`` with exactly one provider key injected, or fail closed."""
    if not key_env_var:
        raise MissingApiKeyError("no API key environment variable was configured")
    if api_key is None or not str(api_key).strip():
        raise MissingApiKeyError(
            f"missing API key for {key_env_var!r}; refusing to start the agent"
        )
    child = dict(env)
    child[key_env_var] = str(api_key)
    return child


def build_child_env(
    *,
    run: IsolatedRun,
    api_key: str | None,
    key_env_var: str = DEFAULT_KEY_ENV_VAR,
    base_env: Mapping[str, str] | None = None,
) -> dict[str, str]:
    """Isolated environment plus the single allowlisted provider key."""
    return inject_api_key(
        build_isolated_env(run=run, base_env=base_env),
        api_key=api_key,
        key_env_var=key_env_var,
    )


def default_managed_config_paths() -> tuple[Path, ...]:
    """Known managed-config locations that override every other config layer."""
    candidates = [
        # macOS system-wide and per-user managed preferences.
        Path("/Library/Application Support/opencode"),
        Path("/Library/Managed Preferences/ai.opencode.managed.plist"),
        Path("/etc/opencode"),
    ]
    user = os.environ.get("USER") or os.environ.get("LOGNAME")
    if user:
        candidates.append(
            Path(f"/Library/Managed Preferences/{user}/ai.opencode.managed.plist")
        )
    return tuple(candidates)


def _is_managed_config(path: Path) -> bool:
    if path.is_file():
        return path.suffix.lower() in {".json", ".jsonc", ".plist"}
    if path.is_dir():
        return any(
            (path / name).is_file()
            for name in ("opencode.json", "opencode.jsonc", "config.json")
        )
    return False


def check_managed_settings(
    paths: Sequence[Path | str] | None = None,
) -> tuple[Path, ...]:
    """Fail closed if managed config exists.

    Managed config has the highest precedence and cannot be excluded by
    ``OPENCODE_CONFIG`` or redirected ``HOME``/``XDG_*`` paths, so a present
    managed config means the isolation contract cannot be guaranteed.
    """
    candidates = tuple(
        Path(p) for p in (default_managed_config_paths() if paths is None else paths)
    )
    conflicts = tuple(path for path in candidates if _is_managed_config(path))
    if conflicts:
        joined = ", ".join(str(path) for path in conflicts)
        raise ManagedConfigError(
            f"managed OpenCode config exists and cannot be excluded: {joined}"
        )
    return ()


def redact(message: str, secrets: Sequence[str] = ()) -> str:
    """Replace every literal secret occurrence with ``***REDACTED***``."""
    out = str(message)
    for secret in secrets:
        if secret:
            out = out.replace(str(secret), REDACTION)
    return out


TERMINATE_GRACE_S = 5.0


def _process_group_alive(pgid: int) -> bool:
    """True while at least one process remains in ``pgid``.

    Signal ``0`` performs error checking without delivering a signal: it
    succeeds while any group member exists and raises ``ProcessLookupError``
    once the group is empty.
    """
    try:
        os.killpg(pgid, 0)
        return True
    except (ProcessLookupError, PermissionError):
        return False


def _wait_for_process_group_to_clear(
    proc: subprocess.Popen[str], pgid: int, timeout_s: float
) -> bool:
    """Wait up to ``timeout_s`` for every member of ``pgid`` to be gone.

    Unlike ``proc.wait`` this does not treat the leader's exit as success: a
    descendant may outlive the leader and keep the inherited stdout pipe open,
    so only an empty group proves cleanup is complete. Returns ``True`` once
    the group is clear, ``False`` when ``timeout_s`` elapses first.
    """
    deadline = time.monotonic() + timeout_s
    while _process_group_alive(pgid):
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return False
        if proc.poll() is None:
            try:
                proc.wait(timeout=min(0.05, remaining))
            except subprocess.TimeoutExpired:
                pass
        else:
            time.sleep(min(0.05, remaining))
    return True


def _terminate_process_group(
    proc: subprocess.Popen[str], *, grace_s: float = TERMINATE_GRACE_S
) -> None:
    """Terminate the child's whole process group, escalating TERM -> KILL.

    ``run_bounded`` starts the child with ``start_new_session=True``, so the
    leader's pid is also the process-group id. The leader exiting does *not*
    mean the group is done: a descendant can ignore SIGTERM and keep the
    inherited stdout pipe open, which would make ``proc.communicate`` block
    forever waiting for EOF. We therefore wait for the whole group to clear,
    bounded by ``grace_s`` per signal, then SIGKILL whatever remains. This
    guarantee covers descendants that stay in the child's process group; it is
    not an OS sandbox for processes that escape it.
    """
    pgid = proc.pid
    if not _process_group_alive(pgid):
        return
    for sig in (signal.SIGTERM, signal.SIGKILL):
        try:
            os.killpg(pgid, sig)
        except (ProcessLookupError, PermissionError):
            return
        if _wait_for_process_group_to_clear(proc, pgid, grace_s):
            return


def run_bounded(
    argv: Sequence[str],
    *,
    env: Mapping[str, str],
    cwd: Path | str,
    timeout_s: float,
    events_path: Path | str | None = None,
    secrets: Sequence[str] = (),
    redact_output: bool = True,
) -> ProcessResult:
    """Run ``argv`` to completion under ``timeout_s`` in its own process group.

    ``stdout`` (OpenCode event stream) is redacted with ``redact`` and written
    to ``events_path`` when supplied; both streams are redacted before
    returning and before logging. Pass ``redact_output=False`` only when the
    caller needs the raw bytes to detect a leak (resolved-config verification).

    On timeout the whole child process group is TERMed, given a bounded grace
    (``TERMINATE_GRACE_S``) to clear, then KILLed, and the final pipe drain is
    itself bounded, so ``run_bounded`` always returns. The cleanup guarantee
    covers descendants that remain in the child's process group; it is not an
    OS sandbox for processes that escape that group.
    """
    argv_list = [str(part) for part in argv]
    if timeout_s <= 0:
        raise ValueError("timeout_s must be positive")
    log.debug("launching: %s", redact(" ".join(argv_list), secrets))
    start = time.monotonic()
    proc = subprocess.Popen(
        argv_list,
        env=dict(env),
        cwd=str(cwd),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        start_new_session=True,
    )
    timed_out = False
    try:
        stdout, stderr = proc.communicate(timeout=timeout_s)
    except subprocess.TimeoutExpired:
        timed_out = True
        _terminate_process_group(proc)
        try:
            stdout, stderr = proc.communicate(timeout=TERMINATE_GRACE_S)
        except subprocess.TimeoutExpired:
            stdout, stderr = "", ""
    duration_s = time.monotonic() - start
    stdout = stdout or ""
    stderr = stderr or ""
    if redact_output:
        stdout = redact(stdout, secrets)
        stderr = redact(stderr, secrets)
    if events_path is not None:
        events_file = Path(events_path)
        events_file.parent.mkdir(parents=True, exist_ok=True)
        events_file.write_text(stdout, encoding="utf-8")
    if stderr:
        log.debug("stderr: %s", redact(stderr, secrets))
    return ProcessResult(
        argv=tuple(argv_list),
        returncode=proc.returncode,
        stdout=stdout,
        stderr=stderr,
        timed_out=timed_out,
        duration_s=duration_s,
    )


def _expect(actual: Any, expected: Any, label: str) -> None:
    if actual != expected:
        raise ConfigVerificationError(
            f"resolved config {label} is {actual!r}, expected {expected!r}"
        )


def verify_resolved_config(
    *,
    run: IsolatedRun,
    env: Mapping[str, str],
    model: str,
    mcp: McpServerSpec,
    agent_name: str = DEFAULT_AGENT_NAME,
    opencode_bin: str = "opencode",
    timeout_s: float = 60.0,
    secrets: Sequence[str] = (),
) -> dict[str, Any]:
    """Ask OpenCode to resolve its own config and assert the contract holds.

    Uses ``opencode debug config --pure`` (no model call) and a placeholder key.
    This catches merge leakage (global config, project config, plugins) that a
    purely static check of the generated file would miss.
    """
    result = run_bounded(
        [opencode_bin, "debug", "config", "--pure"],
        env=env,
        cwd=run.work_dir,
        timeout_s=timeout_s,
        secrets=secrets,
        redact_output=False,
    )
    if result.timed_out:
        raise ConfigVerificationError("'opencode debug config' timed out")
    if result.returncode != 0:
        raise ConfigVerificationError(
            "'opencode debug config' failed "
            f"({result.returncode}): {redact(result.stderr, secrets).strip()[:500]}"
        )
    for secret in secrets:
        if secret and secret in result.stdout:
            raise ConfigVerificationError("resolved config leaked a secret value")
    try:
        resolved = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise ConfigVerificationError(
            f"'opencode debug config' did not return JSON: {exc}"
        ) from exc
    _expect(resolved.get("model"), model, "model")
    _expect(resolved.get("share"), "disabled", "share")
    _expect(resolved.get("snapshot"), False, "snapshot")
    _expect(resolved.get("autoupdate"), False, "autoupdate")
    _expect(resolved.get("default_agent"), agent_name, "default_agent")
    permission = resolved.get("permission") or {}
    _expect(permission.get("*"), "deny", "permission.*")
    _expect(permission.get(f"{mcp.name}_*"), "allow", f"permission.{mcp.name}_*")
    agents = resolved.get("agent") or {}
    _expect(
        (agents.get(agent_name) or {}).get("mode"),
        "primary",
        f"agent.{agent_name}.mode",
    )
    servers = resolved.get("mcp") or {}
    if set(servers) != {mcp.name}:
        raise ConfigVerificationError(
            f"isolated MCP set is {sorted(servers)}, expected only {mcp.name!r}"
        )
    _expect(
        [str(part) for part in servers[mcp.name].get("command", [])],
        list(mcp.command),
        f"mcp.{mcp.name}.command",
    )
    if resolved.get("plugin"):
        raise ConfigVerificationError("plugins leaked into the isolated config")
    return resolved


def launch_playing_agent(
    *,
    run_root: Path | str,
    model: str = DEFAULT_MODEL,
    mcp: McpServerSpec,
    api_key: str | None,
    prompt: str,
    timeout_s: float,
    agent_name: str = DEFAULT_AGENT_NAME,
    agent_prompt: str = DEFAULT_AGENT_PROMPT,
    provider: str | None = DEFAULT_PROVIDER,
    key_env_var: str = DEFAULT_KEY_ENV_VAR,
    base_url: str | None = None,
    opencode_bin: str = "opencode",
    base_env: Mapping[str, str] | None = None,
    managed_paths: Sequence[Path | str] | None = None,
    verify: bool = True,
    secrets: Sequence[str] = (),
    models_cache_source: Path | str | None = None,
) -> LaunchResult:
    """Prepare, verify and run one isolated playing-agent process.

    Ordering is deliberate: managed-config check, then key check, then config
    generation, then (optional) resolved-config verification, and only then the
    real launch. A missing key never reaches a process or a game launch.
    When ``models_cache_source`` is given, a copy of that models.json cache
    is seeded into the isolated XDG cache first (see ``seed_models_cache``).
    """
    check_managed_settings(managed_paths)
    if api_key is None or not str(api_key).strip():
        raise MissingApiKeyError(
            f"missing API key for {key_env_var!r}; refusing to start the agent"
        )
    all_secrets = tuple(s for s in (api_key, *secrets) if s)
    config = build_config(
        model=model,
        mcp=mcp,
        agent_name=agent_name,
        agent_prompt=agent_prompt,
        provider=provider,
        key_env_var=key_env_var,
        base_url=base_url,
    )
    run = prepare_run(run_root, config)
    if models_cache_source is not None:
        seed_models_cache(run, models_cache_source)
    resolved: Mapping[str, Any] | None = None
    if verify:
        verify_env = build_child_env(
            run=run,
            api_key=VERIFY_PLACEHOLDER_KEY,
            key_env_var=key_env_var,
            base_env=base_env,
        )
        resolved = verify_resolved_config(
            run=run,
            env=verify_env,
            model=model,
            mcp=mcp,
            agent_name=agent_name,
            opencode_bin=opencode_bin,
            timeout_s=timeout_s,
            secrets=all_secrets,
        )
    env = build_child_env(
        run=run, api_key=api_key, key_env_var=key_env_var, base_env=base_env
    )
    argv = build_agent_command(
        prompt=prompt, agent_name=agent_name, opencode_bin=opencode_bin
    )
    process = run_bounded(
        argv,
        env=env,
        cwd=run.work_dir,
        timeout_s=timeout_s,
        events_path=run.events_file,
        secrets=all_secrets,
    )
    return LaunchResult(
        run=run, config=config, resolved_config=resolved, process=process
    )
