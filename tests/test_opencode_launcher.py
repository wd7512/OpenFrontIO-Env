"""TDD tests for the isolated OpenCode launcher/config generator.

Every event payload in this file is a SCRIPTED FIXTURE, not output from a real
LLM or OpenCode model session. The only test that touches the real OpenCode
binary is ``test_verify_resolved_config_against_real_opencode``, which runs
``opencode debug config`` (no model call) and is skipped when the binary is
absent.

Isolation facts these tests encode (verified against installed OpenCode
1.17.11 and the official config/permission docs):

* project ``opencode.json`` merges over, and therefore beats, a custom
  ``OPENCODE_CONFIG`` file; so cwd must live outside any git repository;
* ``HOME``/``XDG_*`` must be redirected or the global config leaks back in;
* managed config overrides everything and cannot be excluded, so its presence
  is a hard failure;
* permission is singular and rules resolve last-match-wins, so the wildcard
  deny must precede the game MCP allow.
"""

from __future__ import annotations

import json
import logging
import os
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path

import pytest

from openfront_mcp import opencode_launcher as ol

# A fake secret used to prove values never leak into configs, events or logs.
SECRET = "sk-super-secret-value-1234567890"
MODEL = "anthropic/claude-sonnet-4-5"

# Scripted fixture only: NOT a real LLM result.
SCRIPTED_EVENT_LINES = (
    '{"type":"step_start","sessionID":"scripted-session-0001"}\n'
    '{"type":"text","text":"[scripted fixture] expand north"}\n'
    '{"type":"step_finish","reason":"stop"}\n'
)


def _mcp(tmp_path: Path) -> ol.McpServerSpec:
    work = tmp_path / "mcp-work"
    work.mkdir(exist_ok=True)
    return ol.McpServerSpec(
        name="game",
        command=(sys.executable, "-m", "openfront_mcp"),
        cwd=str(work),
        environment={"OPENFRONT_RUN": "scripted"},
    )


def _config(tmp_path: Path) -> dict:
    return ol.build_config(model=MODEL, mcp=_mcp(tmp_path))


# ---------------------------------------------------------------------------
# config shape
# ---------------------------------------------------------------------------


def test_config_uses_singular_permission_with_wildcard_deny_then_game_allow(
    tmp_path: Path,
) -> None:
    cfg = _config(tmp_path)
    assert "permission" in cfg
    assert "permissions" not in cfg
    assert cfg["permission"]["*"] == "deny"
    assert cfg["permission"]["game_*"] == "allow"
    # Last-match-wins: the wildcard deny must come first so the game allow wins.
    keys = list(cfg["permission"].keys())
    assert keys.index("*") < keys.index("game_*")


def test_config_denies_file_bash_task_skill_web_and_allows_game(tmp_path: Path) -> None:
    cfg = _config(tmp_path)
    perm = cfg["permission"]
    for tool in (
        "read",
        "edit",
        "write",
        "apply_patch",
        "bash",
        "glob",
        "grep",
        "lsp",
        "task",
        "skill",
        "webfetch",
        "websearch",
        "question",
        "todowrite",
    ):
        assert ol.permission_action(perm, tool) == "deny", tool
    assert ol.permission_action(perm, "game_end_decision") == "allow"
    assert ol.permission_action(perm, "game_query_state") == "allow"


def test_config_must_not_pin_game_tools_before_the_wildcard(tmp_path: Path) -> None:
    # A ``tools`` map entry for the game server would be pinned ahead of the
    # wildcard catch-all in the resolved ruleset and invert last-match-wins.
    assert "tools" not in _config(tmp_path)


def test_config_disables_share_snapshot_and_autoupdate(tmp_path: Path) -> None:
    cfg = _config(tmp_path)
    assert cfg["share"] == "disabled"
    assert cfg["snapshot"] is False
    assert cfg["autoupdate"] is False


def test_config_defines_a_custom_primary_game_agent(tmp_path: Path) -> None:
    cfg = _config(tmp_path)
    assert cfg["default_agent"] == "game"
    agent = cfg["agent"]["game"]
    assert agent["mode"] == "primary"
    assert agent["model"] == MODEL
    assert agent["permission"]["*"] == "deny"
    assert agent["permission"]["game_*"] == "allow"


def test_config_places_model_in_config_and_never_in_the_command(tmp_path: Path) -> None:
    cfg = _config(tmp_path)
    assert cfg["model"] == MODEL
    argv = ol.build_agent_command(agent_name="game", prompt="play now")
    assert "-m" not in argv
    assert "--model" not in argv
    assert MODEL not in argv
    assert argv[0] == "opencode"
    assert argv[1] == "run"
    assert "--agent" in argv and "game" in argv
    assert "--pure" in argv
    assert argv[-1] == "play now"


def test_config_never_contains_the_key_literal(tmp_path: Path) -> None:
    cfg = ol.build_config(
        model=MODEL,
        mcp=_mcp(tmp_path),
        provider="anthropic",
        key_env_var="ANTHROPIC_API_KEY",
    )
    blob = json.dumps(cfg)
    assert SECRET not in blob
    assert "{env:ANTHROPIC_API_KEY}" in blob


# ---------------------------------------------------------------------------
# MCP spec
# ---------------------------------------------------------------------------


def test_mcp_spec_requires_absolute_argv0_and_cwd(tmp_path: Path) -> None:
    with pytest.raises(ol.InvalidMcpSpecError):
        ol.McpServerSpec(name="game", command=("python", "-m", "x"), cwd=str(tmp_path))
    with pytest.raises(ol.InvalidMcpSpecError):
        ol.McpServerSpec(name="game", command=(sys.executable,), cwd="relative/path")


def test_mcp_config_carries_command_cwd_and_no_provider_key(tmp_path: Path) -> None:
    spec = _mcp(tmp_path)
    cfg = ol.build_config(model=MODEL, mcp=spec)
    entry = cfg["mcp"]["game"]
    assert entry["type"] == "local"
    assert entry["command"] == list(spec.command)
    assert entry["cwd"] == spec.cwd
    assert entry["environment"] == {"OPENFRONT_RUN": "scripted"}
    assert SECRET not in json.dumps(entry)


# ---------------------------------------------------------------------------
# run directory isolation
# ---------------------------------------------------------------------------


def test_prepare_run_creates_isolated_layout(tmp_path: Path) -> None:
    root = tmp_path / "run"
    cfg = _config(tmp_path)
    run = ol.prepare_run(root, cfg)
    for path in (
        run.home,
        run.xdg_config,
        run.xdg_data,
        run.xdg_cache,
        run.xdg_state,
        run.work_dir,
    ):
        assert path.is_dir()
        assert root == path or root in path.parents
    assert run.config_file.is_dir() is False
    assert json.loads(run.config_file.read_text()) == cfg
    # Fresh isolation: no global opencode config can exist here.
    assert not (run.home / ".config" / "opencode").exists()


def test_prepare_run_refuses_to_run_inside_a_git_repository(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    (repo / ".git").mkdir(parents=True)
    with pytest.raises(ol.IsolationError):
        ol.prepare_run(repo / "runs" / "one", _config(tmp_path))


def test_prepare_run_refuses_a_dotopencode_ancestor(tmp_path: Path) -> None:
    # OpenCode discovers project plugins upward from cwd: a run root below a
    # directory holding `.opencode/plugins` would inherit foreign plugins.
    outer = tmp_path / "outer"
    (outer / ".opencode" / "plugins").mkdir(parents=True)
    with pytest.raises(ol.IsolationError):
        ol.prepare_run(outer / "inner" / "run", _config(tmp_path))


def test_prepare_run_refuses_an_opencode_json_ancestor(tmp_path: Path) -> None:
    outer = tmp_path / "outer"
    outer.mkdir(parents=True)
    (outer / "opencode.json").write_text("{}", encoding="utf-8")
    with pytest.raises(ol.IsolationError):
        ol.prepare_run(outer / "inner" / "run", _config(tmp_path))


def test_seed_models_cache_copies_into_isolated_cache(tmp_path: Path) -> None:
    run = _run(tmp_path)
    source = tmp_path / "models.json"
    source.write_text('{"seed": true}', encoding="utf-8")
    dest = ol.seed_models_cache(run, source)
    assert dest == run.xdg_cache / "opencode" / "models.json"
    assert json.loads(dest.read_text()) == {"seed": True}


def test_seed_models_cache_missing_source_fails_closed(tmp_path: Path) -> None:
    run = _run(tmp_path)
    with pytest.raises(ol.LauncherError):
        ol.seed_models_cache(run, tmp_path / "absent.json")


# ---------------------------------------------------------------------------
# environment isolation
# ---------------------------------------------------------------------------


def _run(tmp_path: Path) -> ol.IsolatedRun:
    return ol.prepare_run(tmp_path / "run", _config(tmp_path))


def test_isolated_env_allowlists_and_drops_inherited_config(tmp_path: Path) -> None:
    base = {
        "PATH": "/usr/bin",
        "LANG": "en_US.UTF-8",
        "HOME": "/home/real-user",
        "OPENCODE_CONFIG": "/evil/global.json",
        "OPENCODE_CONFIG_CONTENT": '{"model":"evil/model"}',
        "OPENCODE_CONFIG_DIR": "/evil/dir",
        "ANTHROPIC_API_KEY": "inherited-anthropic",
        "OPENAI_API_KEY": "inherited-openai",
        "UNRELATED": "nope",
    }
    run = _run(tmp_path)
    env = ol.build_isolated_env(run=run, base_env=base)
    assert env["PATH"] == "/usr/bin"
    assert env["LANG"] == "en_US.UTF-8"
    assert env["HOME"] == str(run.home)
    assert env["XDG_CONFIG_HOME"] == str(run.xdg_config)
    assert env["XDG_DATA_HOME"] == str(run.xdg_data)
    assert env["XDG_CACHE_HOME"] == str(run.xdg_cache)
    assert env["XDG_STATE_HOME"] == str(run.xdg_state)
    assert env["OPENCODE_CONFIG"] == str(run.config_file)
    assert "OPENCODE_CONFIG_CONTENT" not in env
    assert "OPENCODE_CONFIG_DIR" not in env
    assert "ANTHROPIC_API_KEY" not in env
    assert "OPENAI_API_KEY" not in env
    assert "UNRELATED" not in env


def test_child_env_injects_only_the_explicitly_selected_key(tmp_path: Path) -> None:
    base = {"PATH": "/usr/bin", "OPENAI_API_KEY": "other", "OPENCODE_PURE": "true"}
    run = _run(tmp_path)
    env = ol.build_child_env(
        run=run,
        api_key=SECRET,
        key_env_var="ANTHROPIC_API_KEY",
        base_env=base,
    )
    assert env["ANTHROPIC_API_KEY"] == SECRET
    assert "OPENAI_API_KEY" not in env
    assert "OPENCODE_PURE" not in env
    assert env["OPENCODE_CONFIG"] == str(run.config_file)


@pytest.mark.parametrize("bad", [None, "", "   "])
def test_child_env_missing_key_fails_before_any_process(tmp_path: Path, bad) -> None:
    run = _run(tmp_path)
    with pytest.raises(ol.MissingApiKeyError):
        ol.build_child_env(
            run=run,
            api_key=bad,
            key_env_var="ANTHROPIC_API_KEY",
            base_env={},
        )


# ---------------------------------------------------------------------------
# managed settings
# ---------------------------------------------------------------------------


def test_managed_settings_fail_closed(tmp_path: Path) -> None:
    managed = tmp_path / "managed"
    managed.mkdir()
    (managed / "opencode.json").write_text('{"model":"managed/model"}')
    with pytest.raises(ol.ManagedConfigError):
        ol.check_managed_settings([managed])

    plist = tmp_path / "ai.opencode.managed.plist"
    plist.write_text("<plist/>")
    with pytest.raises(ol.ManagedConfigError):
        ol.check_managed_settings([plist])

    clean = tmp_path / "clean"
    clean.mkdir()
    assert ol.check_managed_settings([clean]) == ()


# ---------------------------------------------------------------------------
# bounded subprocess
# ---------------------------------------------------------------------------


def test_run_bounded_times_out_and_cleans_up_the_process_group(tmp_path: Path) -> None:
    pidfile = tmp_path / "child.pid"
    script = f"sleep 30 & echo $! > {pidfile}; wait"
    result = ol.run_bounded(
        ["/bin/sh", "-c", script],
        env=dict(os.environ),
        cwd=str(tmp_path),
        timeout_s=0.5,
    )
    assert result.timed_out is True
    assert result.returncode is not None
    assert result.duration_s < 10

    deadline = time.time() + 3
    while not pidfile.exists() and time.time() < deadline:
        time.sleep(0.02)
    assert pidfile.exists(), "scripted fixture never wrote its child pid"
    child_pid = int(pidfile.read_text().strip())
    with pytest.raises(ProcessLookupError):
        os.kill(child_pid, 0)


def _term_ignoring_descendant(pidfile: Path, hold_s: int) -> str:
    """Python source for a child that ignores SIGTERM and idles ``hold_s``.

    It records its own pid in ``pidfile`` and inherits (never closes) stdout,
    so while it lives ``proc.communicate`` can never see EOF on the launcher's
    captured stdout pipe.
    """
    return (
        "import os, signal, sys, time\n"
        f"signal.signal(signal.SIGTERM, signal.SIG_IGN)\n"
        f"open({str(pidfile)!r}, 'w').write(str(os.getpid()))\n"
        f"time.sleep({hold_s})\n"
    )


def _run_bounded_guarded(code: str, *, cwd: Path, outer_s: float = 20.0) -> dict:
    """Run ``code`` (a program calling ``run_bounded``) behind an outer bound.

    The task is to prove a BROKEN launcher cannot hang the suite: the call is
    made in a subprocess this harness supervises, and the whole outer process
    group is SIGKILLed in a ``finally`` after ``outer_s``. Because a surviving
    launcher descendant lives in the launcher's *inner* process group (which a
    hung launcher never cleans up), any ``*.pid`` file the fixture wrote under
    ``cwd`` is also SIGKILLed so even a RED run leaks nothing. Returns the
    subject's JSON stdout, ``{"outer_timed_out": True}`` on a hang, or an
    ``outer_error`` payload on a subject crash.
    """
    proc = subprocess.Popen(
        [sys.executable, "-c", code],
        cwd=str(cwd),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        start_new_session=True,
    )
    try:
        try:
            stdout, stderr = proc.communicate(timeout=outer_s)
        except subprocess.TimeoutExpired:
            return {"outer_timed_out": True, "outer_stderr": "(outer timeout)"}
        if proc.returncode != 0:
            return {
                "outer_error": proc.returncode,
                "outer_stderr": (stderr or "").strip()[:500],
            }
        return json.loads(stdout)
    finally:
        try:
            os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
        except (ProcessLookupError, PermissionError):
            pass
        proc.wait()
        for pidfile in cwd.glob("*.pid"):
            try:
                os.kill(int(pidfile.read_text().strip()), signal.SIGKILL)
            except (OSError, ValueError):
                pass


def test_run_bounded_escapes_when_leader_dies_on_term_but_descendant_holds_stdout(
    tmp_path: Path,
) -> None:
    """Leader dies on SIGTERM, leaving a TERM-ignoring descendant holding the
    inherited stdout pipe open: ``run_bounded`` must return bounded and the
    descendant must be dead (not merely the leader).
    """
    pidfile = tmp_path / "desc1.pid"
    descendant = _term_ignoring_descendant(pidfile, hold_s=30)
    leader = (
        "import subprocess, sys, time\n"
        f"subprocess.Popen([sys.executable, '-c', {descendant!r}])\n"
        "sys.stdout.write('leader-up\\n')\n"
        "sys.stdout.flush()\n"
        "time.sleep(300)\n"
    )
    code = (
        "import json, os, sys\n"
        "from openfront_mcp import opencode_launcher as ol\n"
        f"res = ol.run_bounded([sys.executable, '-c', {leader!r}], env=dict(os.environ), cwd={str(tmp_path)!r}, timeout_s=1.0)\n"
        "sys.stdout.write(json.dumps({'returncode': res.returncode, 'timed_out': res.timed_out, 'duration_s': res.duration_s}))\n"
    )
    result = _run_bounded_guarded(code, cwd=tmp_path)
    assert result.get("outer_timed_out") is not True, result.get("outer_stderr")
    assert "outer_error" not in result, result.get("outer_stderr")
    assert result["timed_out"] is True
    assert result["duration_s"] < 14
    pid = int(pidfile.read_text().strip())
    with pytest.raises(ProcessLookupError):
        os.kill(pid, 0)


def test_run_bounded_escapes_when_leader_exits_naturally_leaving_descendant(
    tmp_path: Path,
) -> None:
    """Leader exits 0 on its own, leaving a TERM-ignoring descendant holding
    the inherited stdout pipe open: ``run_bounded`` must time out, TERM then
    KILL the whole group, and return bounded with the descendant dead.
    """
    pidfile = tmp_path / "desc2.pid"
    descendant = _term_ignoring_descendant(pidfile, hold_s=30)
    leader = (
        "import subprocess, sys\n"
        f"subprocess.Popen([sys.executable, '-c', {descendant!r}])\n"
        "sys.stdout.write('leader-done\\n')\n"
        "sys.stdout.flush()\n"
        "raise SystemExit(0)\n"
    )
    code = (
        "import json, os, sys\n"
        "from openfront_mcp import opencode_launcher as ol\n"
        f"res = ol.run_bounded([sys.executable, '-c', {leader!r}], env=dict(os.environ), cwd={str(tmp_path)!r}, timeout_s=1.0)\n"
        "sys.stdout.write(json.dumps({'returncode': res.returncode, 'timed_out': res.timed_out, 'duration_s': res.duration_s}))\n"
    )
    result = _run_bounded_guarded(code, cwd=tmp_path)
    assert result.get("outer_timed_out") is not True, result.get("outer_stderr")
    assert "outer_error" not in result, result.get("outer_stderr")
    assert result["timed_out"] is True
    assert result["duration_s"] < 14
    pid = int(pidfile.read_text().strip())
    with pytest.raises(ProcessLookupError):
        os.kill(pid, 0)


def test_run_bounded_reports_nonzero_exit_and_captures_stderr(tmp_path: Path) -> None:
    result = ol.run_bounded(
        ["/bin/sh", "-c", "echo boom >&2; exit 3"],
        env=dict(os.environ),
        cwd=str(tmp_path),
        timeout_s=5,
    )
    assert result.returncode == 3
    assert result.timed_out is False
    assert "boom" in result.stderr


def test_run_bounded_captures_raw_scripted_events_to_file(tmp_path: Path) -> None:
    events = tmp_path / "events.jsonl"
    script = f"import sys; sys.stdout.write({SCRIPTED_EVENT_LINES!r})"
    result = ol.run_bounded(
        [sys.executable, "-c", script],
        env=dict(os.environ),
        cwd=str(tmp_path),
        timeout_s=5,
        events_path=events,
    )
    assert result.stdout == SCRIPTED_EVENT_LINES
    assert events.read_text() == SCRIPTED_EVENT_LINES
    assert "scripted" in events.read_text().lower()


def test_redact_removes_secret_literals() -> None:
    message = ol.redact(f"key={SECRET} again={SECRET}", [SECRET])
    assert SECRET not in message
    assert message.count("***REDACTED***") == 2


def test_run_bounded_redacts_secrets_from_output_and_persisted_events(
    tmp_path: Path,
) -> None:
    events = tmp_path / "events.jsonl"
    script = (
        "import sys\n"
        f"sys.stdout.write('stdout-secret=({SECRET})\\n')\n"
        f"sys.stderr.write('stderr-secret=({SECRET})\\n')\n"
    )
    result = ol.run_bounded(
        [sys.executable, "-c", script],
        env=dict(os.environ),
        cwd=str(tmp_path),
        timeout_s=5,
        events_path=events,
        secrets=(SECRET,),
    )
    assert result.stdout == f"stdout-secret=({ol.REDACTION})\n"
    assert result.stderr == f"stderr-secret=({ol.REDACTION})\n"
    assert SECRET not in result.stdout
    assert SECRET not in result.stderr
    assert events.read_text() == result.stdout
    assert SECRET not in events.read_text()


# ---------------------------------------------------------------------------
# verification against the real installed opencode (no model call)
# ---------------------------------------------------------------------------


def _fake_opencode(tmp_path: Path) -> Path:
    fake = tmp_path / "fake-opencode"
    source = (
        f"#!{sys.executable}\n"
        "import os, sys\n"
        "args = sys.argv[1:]\n"
        "if args[:2] == ['debug', 'config']:\n"
        "    sys.stdout.write(open(os.environ['OPENCODE_CONFIG']).read())\n"
        "    raise SystemExit(0)\n"
        "if args and args[0] == 'run':\n"
        f"    sys.stdout.write({SCRIPTED_EVENT_LINES!r})\n"
        "    raise SystemExit(0)\n"
        "sys.stderr.write('unexpected args: %r' % (args,))\n"
        "raise SystemExit(2)\n"
    )
    fake.write_text(source)
    fake.chmod(fake.stat().st_mode | 0o111)
    return fake


def test_verify_resolved_config_fails_on_model_mismatch(tmp_path: Path) -> None:
    run = _run(tmp_path)
    fake = _fake_opencode(tmp_path)
    env = ol.build_child_env(
        run=run,
        api_key=ol.VERIFY_PLACEHOLDER_KEY,
        key_env_var="ANTHROPIC_API_KEY",
        base_env={},
    )
    with pytest.raises(ol.ConfigVerificationError):
        ol.verify_resolved_config(
            run=run,
            env=env,
            model="anthropic/some-other-model",
            mcp=_mcp(tmp_path),
            agent_name="game",
            opencode_bin=str(fake),
            secrets=(SECRET,),
        )


def test_verify_resolved_config_rejects_a_leaked_secret(tmp_path: Path) -> None:
    run = _run(tmp_path)
    # Tamper: force the resolved config to contain the secret value.
    cfg = json.loads(run.config_file.read_text())
    cfg["username"] = SECRET
    run.config_file.write_text(json.dumps(cfg))
    fake = _fake_opencode(tmp_path)
    env = ol.build_child_env(
        run=run,
        api_key=ol.VERIFY_PLACEHOLDER_KEY,
        key_env_var="ANTHROPIC_API_KEY",
        base_env={},
    )
    with pytest.raises(ol.ConfigVerificationError):
        ol.verify_resolved_config(
            run=run,
            env=env,
            model=MODEL,
            mcp=_mcp(tmp_path),
            agent_name="game",
            opencode_bin=str(fake),
            secrets=(SECRET,),
        )


@pytest.mark.skipif(
    shutil.which("opencode") is None, reason="opencode binary is not installed"
)
def test_verify_resolved_config_against_real_opencode(tmp_path: Path) -> None:
    spec = _mcp(tmp_path)
    cfg = ol.build_config(model=MODEL, mcp=spec)
    run = ol.prepare_run(tmp_path / "real-run", cfg)
    env = ol.build_child_env(
        run=run,
        api_key=ol.VERIFY_PLACEHOLDER_KEY,
        key_env_var="ANTHROPIC_API_KEY",
        base_env=dict(os.environ),
    )
    resolved = ol.verify_resolved_config(
        run=run,
        env=env,
        model=MODEL,
        mcp=spec,
        agent_name="game",
        secrets=(SECRET,),
    )
    # The real binary resolved our isolated config and nothing inherited.
    assert resolved["model"] == MODEL
    assert resolved["share"] == "disabled"
    assert resolved["snapshot"] is False
    assert resolved["autoupdate"] is False
    assert resolved["permission"]["*"] == "deny"
    assert resolved["permission"]["game_*"] == "allow"
    assert list(resolved["mcp"].keys()) == ["game"]
    assert resolved["mcp"]["game"]["command"] == list(spec.command)
    assert resolved.get("plugin", []) == []


# ---------------------------------------------------------------------------
# end-to-end orchestration with a scripted fake binary (no model call)
# ---------------------------------------------------------------------------


def test_launch_requires_a_key_before_running_anything(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def explode(*_args, **_kwargs):
        raise AssertionError("run_bounded must not be called without a key")

    monkeypatch.setattr(ol, "run_bounded", explode)
    with pytest.raises(ol.MissingApiKeyError):
        ol.launch_playing_agent(
            run_root=tmp_path / "run",
            model=MODEL,
            mcp=_mcp(tmp_path),
            api_key=None,
            prompt="play",
            timeout_s=5,
            managed_paths=[],
        )


def test_launch_verifies_then_runs_with_scripted_events(tmp_path: Path) -> None:
    fake = _fake_opencode(tmp_path)
    result = ol.launch_playing_agent(
        run_root=tmp_path / "run",
        model=MODEL,
        mcp=_mcp(tmp_path),
        api_key=SECRET,
        prompt="play the game",
        timeout_s=10,
        opencode_bin=str(fake),
        base_env={"PATH": "/usr/bin"},
        managed_paths=[],
    )
    assert result.process.returncode == 0
    assert result.process.stdout == SCRIPTED_EVENT_LINES
    assert result.run.events_file.read_text() == SCRIPTED_EVENT_LINES
    assert result.resolved_config is not None
    assert result.resolved_config["model"] == MODEL
    # The secret lives only in the child environment, never on disk or in logs.
    assert SECRET not in result.run.config_file.read_text()
    assert SECRET not in result.run.events_file.read_text()


def test_launch_logs_never_contain_the_secret(tmp_path: Path, caplog) -> None:
    fake = _fake_opencode(tmp_path)
    with caplog.at_level(logging.DEBUG):
        ol.launch_playing_agent(
            run_root=tmp_path / "run",
            model=MODEL,
            mcp=_mcp(tmp_path),
            api_key=SECRET,
            prompt="play the game",
            timeout_s=10,
            opencode_bin=str(fake),
            base_env={"PATH": "/usr/bin"},
            managed_paths=[],
        )
    assert SECRET not in caplog.text
