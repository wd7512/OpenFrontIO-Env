"""Keyless regression tests; no model requests."""

import json
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from openfront_mcp.live_smoke import load_settings, run
from openfront_mcp.live_mcp import AuditedSession


def test_missing_key_before_launch(tmp_path):
    env = tmp_path / ".env.local"
    env.write_text("OPENFRONT_MODEL=openrouter/stealth/union-alpha\n")
    with patch("openfront_mcp.live_smoke.launch_playing_agent") as launch:
        with pytest.raises(ValueError, match="key"):
            run(env, tmp_path / "output", 10)
        launch.assert_not_called()


def test_settings_no_shell_execution(tmp_path):
    env = tmp_path / ".env.local"
    env.write_text(
        "OPENROUTER_API_KEY=fake-test-only\nOPENFRONT_PROVIDER=openrouter\nOPENFRONT_MODEL=openrouter/stealth/union-alpha\n"
    )
    settings = load_settings(env)
    assert settings["OPENROUTER_API_KEY"] == "fake-test-only"


def test_real_engine_cap_and_audit(tmp_path):
    trace = tmp_path / "trace.jsonl"
    game = AuditedSession(trace)
    try:
        game.start()
        for n in (1, 2, 3):
            assert game.end_decision(n)["tick"] == 2 + 50 * n
        with pytest.raises(RuntimeError, match="cap"):
            game.end_decision(4)
        game.close()
    finally:
        game.shutdown()
    events = [json.loads(s) for s in trace.read_text().splitlines()]
    assert [
        e["result"]["tick"] for e in events if e["tool"] == "end_decision" and e["ok"]
    ] == [52, 102, 152]
    assert events[-1]["tool"] == "close_game"


def test_run_forwards_models_cache_source(tmp_path):
    env = tmp_path / ".env.local"
    env.write_text(
        "OPENROUTER_API_KEY=fake-test-only\n"
        "OPENFRONT_PROVIDER=openrouter\n"
        "OPENFRONT_MODEL=openrouter/stealth/union-alpha\n"
    )
    cache = tmp_path / "models.json"
    cache.write_text("{}", encoding="utf-8")
    with patch("openfront_mcp.live_smoke.launch_playing_agent") as launch:
        launch.return_value = SimpleNamespace(
            process=SimpleNamespace(
                stdout="", stderr="", returncode=0, timed_out=False
            ),
            run=SimpleNamespace(),
            config={},
            resolved_config=None,
        )
        run(env, tmp_path / "output", 10, models_cache_source=cache)
    _, kwargs = launch.call_args
    assert kwargs["models_cache_source"] == cache


def test_run_auto_cache_missing_means_none(tmp_path):
    env = tmp_path / ".env.local"
    env.write_text(
        "OPENROUTER_API_KEY=fake-test-only\n"
        "OPENFRONT_PROVIDER=openrouter\n"
        "OPENFRONT_MODEL=openrouter/stealth/union-alpha\n"
    )
    with (
        patch("openfront_mcp.live_smoke.launch_playing_agent") as launch,
        patch("openfront_mcp.live_smoke._default_models_cache", return_value=None),
    ):
        launch.return_value = SimpleNamespace(
            process=SimpleNamespace(
                stdout="", stderr="", returncode=0, timed_out=False
            ),
            run=SimpleNamespace(),
            config={},
            resolved_config=None,
        )
        run(env, tmp_path / "output", 10)
    _, kwargs = launch.call_args
    assert kwargs["models_cache_source"] is None


def test_build_match_prompt_orders_the_match_steps():
    from openfront_mcp.live_smoke import build_match_prompt

    prompt = build_match_prompt(2)
    for call in (
        "game_start_1v1_game",
        "game_get_overview",
        "game_order_attack (target=expand, troops=5000)",
        "game_end_decision (decision=1)",
        "game_end_decision (decision=2)",
        "game_get_overview",
        "game_close_game",
    ):
        assert call in prompt
    assert "game_end_decision (decision=3)" not in prompt
    assert prompt.index("game_order_attack") < prompt.index(
        "game_end_decision (decision=1)"
    )


def test_run_rejects_bad_scenario_and_bounds(tmp_path):
    env = tmp_path / ".env.local"
    env.write_text(
        "OPENROUTER_API_KEY=fake-test-only\n"
        "OPENFRONT_PROVIDER=openrouter\n"
        "OPENFRONT_MODEL=openrouter/stealth/union-alpha\n"
    )
    with patch("openfront_mcp.live_smoke.launch_playing_agent") as launch:
        with pytest.raises(ValueError, match="scenario"):
            run(env, tmp_path / "o1", 10, scenario="2v2")
        with pytest.raises(ValueError, match="max_decisions"):
            run(env, tmp_path / "o2", 10, scenario="1v1", max_decisions=0)
        with pytest.raises(ValueError, match="max_decisions"):
            run(env, tmp_path / "o3", 10, scenario="1v1", max_decisions=True)
        launch.assert_not_called()


def test_run_1v1_uses_match_prompt(tmp_path):
    env = tmp_path / ".env.local"
    env.write_text(
        "OPENROUTER_API_KEY=fake-test-only\n"
        "OPENFRONT_PROVIDER=openrouter\n"
        "OPENFRONT_MODEL=openrouter/stealth/union-alpha\n"
    )
    with patch("openfront_mcp.live_smoke.launch_playing_agent") as launch:
        launch.return_value = SimpleNamespace(
            process=SimpleNamespace(
                stdout="", stderr="", returncode=0, timed_out=False
            ),
            run=SimpleNamespace(),
            config={},
            resolved_config=None,
        )
        run(env, tmp_path / "output", 10, scenario="1v1", max_decisions=2)
    _, kwargs = launch.call_args
    assert "game_start_1v1_game" in kwargs["prompt"]
    assert "game_start_smoke_game" not in kwargs["prompt"]


def test_summarise_unwraps_nested_result_envelope():
    from openfront_mcp.live_smoke import _summarise_events

    def tool_event(tool, payload, start, end):
        inner = json.dumps({"result": json.dumps(payload)})
        return json.dumps(
            {
                "type": "tool_use",
                "timestamp": start,
                "sessionID": "ses_probe",
                "part": {
                    "id": "p",
                    "type": "tool",
                    "tool": tool,
                    "state": {
                        "status": "completed",
                        "input": {},
                        "output": inner,
                        "time": {"start": start, "end": end},
                    },
                },
            },
            sort_keys=True,
        )

    stdout = "\n".join(
        [
            tool_event("game_end_decision", {"decision": 1, "tick": 52}, 1000, 2000),
            tool_event("game_end_decision", {"decision": 2, "tick": 102}, 2000, 3000),
        ]
    )
    summary = _summarise_events(stdout)
    assert summary["tool_calls"] == 2
    assert summary["decisions"] == [1, 2]
    assert summary["ticks"] == [52, 102]
