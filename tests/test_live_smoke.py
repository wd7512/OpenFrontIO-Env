"""Keyless regression tests; no model requests."""

import json
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from openfrontbench.live_smoke import load_settings, run
from openfrontbench.live_mcp import AuditedSession


def test_missing_key_before_launch(tmp_path):
    env = tmp_path / ".env.local"
    env.write_text("OPENFRONT_MODEL=openrouter/stealth/union-alpha\n")
    with patch("openfrontbench.live_smoke.launch_playing_agent") as launch:
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
    with patch("openfrontbench.live_smoke.launch_playing_agent") as launch:
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
        patch("openfrontbench.live_smoke.launch_playing_agent") as launch,
        patch("openfrontbench.live_smoke._default_models_cache", return_value=None),
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


def test_run_records_difficulty_in_payload(tmp_path):
    env = tmp_path / ".env.local"
    env.write_text(
        "OPENROUTER_API_KEY=fake-test-only\n"
        "OPENFRONT_PROVIDER=openrouter\n"
        "OPENFRONT_MODEL=openrouter/stealth/union-alpha\n"
    )
    with patch("openfrontbench.live_smoke.launch_playing_agent") as launch:
        launch.return_value = SimpleNamespace(
            process=SimpleNamespace(
                stdout="", stderr="", returncode=0, timed_out=False
            ),
            run=SimpleNamespace(),
            config={},
            resolved_config=None,
        )
        run(env, tmp_path / "output", 10, difficulty="hard")
    payload = json.loads((tmp_path / "output" / "live_result.json").read_text())
    assert payload["difficulty"] == "hard"
    assert payload["scenario"] == "solo"


def _tool_event(tool: str, result: dict, inputs: dict | None = None) -> str:
    state: dict = {"output": json.dumps({"result": json.dumps(result)})}
    if inputs is not None:
        state["input"] = inputs
    return json.dumps(
        {
            "type": "tool_use",
            "timestamp": 1000,
            "part": {"tool": tool, "state": state},
        }
    )


def test_summarise_metrics_track_passivity_and_builds():
    from openfrontbench.live_smoke import _summarise_events

    def overview(decision: int, tiles: int, gold: str) -> str:
        return _tool_event(
            "game_get_overview",
            {"decision": decision, "human": {"tiles": tiles, "gold": gold}},
        )

    stdout = "\n".join(
        [
            _tool_event(
                "game_start_solo_game",
                {"decision": 0, "human": {"tiles": 52, "gold": "0"}},
            ),
            _tool_event(
                "game_order_attack",
                {"decision": 0},
                {"target": "tribe-1", "percent": 20},
            ),
            _tool_event(
                "game_order_attack",
                {"decision": 0},
                {"target": "expand", "percent": 8},
            ),
            _tool_event("game_order_build", {"decision": 1}, {"unit": "city"}),
            overview(50, 900, "1000"),
            overview(100, 2000, "2500"),
            _tool_event(
                "game_order_attack",
                {"decision": 100},
                {"target": "nation-3", "percent": 25},
            ),
            _tool_event(
                "game_order_boat_attack",
                {"decision": 100},
                {"x": 1, "y": 2, "percent": 15},
            ),
            overview(120, 1500, "9000"),
        ]
    )
    metrics = _summarise_events(stdout)["metrics"]
    assert metrics["attacks"] == 3
    assert metrics["attacks_after_50"] == 1
    assert metrics["expand_attacks"] == 1
    assert metrics["tribe_attacks"] == 1
    assert metrics["nation_attacks"] == 1
    assert metrics["boats"] == 1
    assert metrics["cities"] == 1
    assert metrics["tiles_50"] == 900
    assert metrics["tiles_100"] == 2000
    assert metrics["tiles_peak"] == 2000
    assert metrics["gold_end"] == "9000"


def test_summarise_counts_engaged_attacks_and_order_errors():
    from openfrontbench.live_smoke import _summarise_events

    def overview(decision: int, tiles: int) -> str:
        return _tool_event(
            "game_get_overview",
            {"decision": decision, "human": {"tiles": tiles, "gold": "0"}},
        )

    def failed_order(tool: str, result: dict, inputs: dict) -> str:
        event = json.loads(_tool_event(tool, result, inputs))
        event["part"]["state"]["status"] = "error"
        event["part"]["state"]["error"] = "rejected"
        return json.dumps(event)

    stdout = "\n".join(
        [
            overview(0, 52),
            # Lands: tiles grow before the next decision.
            _tool_event("game_order_attack", {"decision": 0}, {"target": "expand"}),
            overview(1, 60),
            # Silent no-op: tiles flat.
            _tool_event("game_order_attack", {"decision": 1}, {"target": "tribe-2"}),
            overview(2, 60),
            # Rejected order: counted as an error, never as engaged.
            failed_order("game_order_attack", {"decision": 2}, {"target": "nation-9"}),
            overview(3, 60),
        ]
    )
    metrics = _summarise_events(stdout)["metrics"]
    assert metrics["attacks"] == 3
    assert metrics["attacks_engaged"] == 1
    assert metrics["tool_errors"] == 1
    assert metrics["order_errors"] == 1


def test_summarise_decision_payload_feeds_tile_samples():
    """end_decision now carries a compact human snapshot: tiles_peak must be
    sampled every decision, not only on overview calls."""
    from openfrontbench.live_smoke import _summarise_events

    stdout = "\n".join(
        [
            _tool_event(
                "game_end_decision",
                {
                    "decision": 1,
                    "tick": 53,
                    "human": {"tiles": 70, "troops": 900, "gold": "5"},
                    "in_spawn_phase": False,
                    "winner": None,
                },
            ),
            _tool_event(
                "game_end_decision",
                {
                    "decision": 2,
                    "tick": 103,
                    "human": {"tiles": 120, "troops": 950, "gold": "9"},
                    "in_spawn_phase": False,
                    "winner": None,
                },
            ),
        ]
    )
    summary = _summarise_events(stdout)
    assert summary["decisions"] == [1, 2]
    assert summary["metrics"]["tiles_peak"] == 120
    assert summary["metrics"]["gold_end"] == "9"


def test_summarise_captures_provider_api_error():
    from openfrontbench.live_smoke import _summarise_events

    stdout = json.dumps(
        {
            "type": "error",
            "timestamp": 5000,
            "error": {
                "name": "APIError",
                "data": {
                    "message": "Cannot connect to API",
                    "isRetryable": True,
                },
            },
        }
    )
    summary = _summarise_events(stdout)
    assert summary["api_error"] == "APIError: Cannot connect to API"


def test_summarise_captures_winner_from_overviews():
    from openfrontbench.live_smoke import _summarise_events

    stdout = "\n".join(
        [
            _tool_event("game_start_solo_game", {"tick": 3, "winner": None}),
            _tool_event("game_end_decision", {"decision": 1, "tick": 53}),
            _tool_event(
                "game_get_overview", {"tick": 53, "winner": "Deeply Confused Bugs"}
            ),
        ]
    )
    assert _summarise_events(stdout)["winner"] == "Deeply Confused Bugs"


def test_summarise_winner_is_null_when_never_declared():
    from openfrontbench.live_smoke import _summarise_events

    stdout = "\n".join(
        [
            _tool_event("game_start_solo_game", {"tick": 3, "winner": None}),
            _tool_event("game_get_overview", {"tick": 53, "winner": None}),
        ]
    )
    assert _summarise_events(stdout)["winner"] is None


def test_build_solo_prompt_is_win_focused_and_minimal():
    from openfrontbench.live_smoke import build_solo_prompt

    prompt = build_solo_prompt(20)
    assert "game_start_solo_game" in prompt
    assert "400 tribes" in prompt
    assert "52 nations" in prompt
    assert "20" in prompt
    assert '"easy"' in prompt
    # Win-or-die: the only acceptable end is victory or elimination, never
    # an early close (the agent twice closed healthy games to "report").
    assert "win" in prompt and "eliminated" in prompt
    # Stripped down: tool docs live on the MCP server, not in the prompt.
    assert "tribes_list" not in prompt
    assert "game_order_build" not in prompt
    assert "game_close_game" not in prompt


def test_build_solo_prompt_impossible_names_difficulty():
    from openfrontbench.live_smoke import build_solo_prompt

    assert '"impossible"' in build_solo_prompt(40, "impossible")


def test_prompts_live_in_md_files():
    from openfrontbench.live_smoke import PROMPTS_DIR, load_prompt

    assert (PROMPTS_DIR / "solo.md").is_file()
    rendered = load_prompt("solo", difficulty="easy", max_decisions=20, memory_block="")
    assert "400 tribes" in rendered and "52 nations" in rendered
    assert "{difficulty}" not in rendered and "{memory_block}" not in rendered


def test_run_rejects_bad_difficulty(tmp_path):
    from openfrontbench.live_smoke import run

    env = tmp_path / ".env.local"
    env.write_text(
        "OPENROUTER_API_KEY=fake-test-only\n"
        "OPENFRONT_PROVIDER=openrouter\n"
        "OPENFRONT_MODEL=openrouter/stealth/union-alpha\n"
    )
    with pytest.raises(ValueError, match="difficulty must be one of"):
        run(env, tmp_path / "x", 10, difficulty="brutal")


def test_run_rejects_bad_bounds(tmp_path):
    env = tmp_path / ".env.local"
    env.write_text(
        "OPENROUTER_API_KEY=fake-test-only\n"
        "OPENFRONT_PROVIDER=openrouter\n"
        "OPENFRONT_MODEL=openrouter/stealth/union-alpha\n"
    )
    with patch("openfrontbench.live_smoke.launch_playing_agent") as launch:
        with pytest.raises(ValueError, match="max_decisions"):
            run(env, tmp_path / "o2", 10, max_decisions=0)
        with pytest.raises(ValueError, match="max_decisions"):
            run(env, tmp_path / "o3", 10, max_decisions=True)
        launch.assert_not_called()


def test_run_solo_uses_solo_prompt(tmp_path):
    env = tmp_path / ".env.local"
    env.write_text(
        "OPENROUTER_API_KEY=fake-test-only\n"
        "OPENFRONT_PROVIDER=openrouter\n"
        "OPENFRONT_MODEL=openrouter/stealth/union-alpha\n"
    )
    with patch("openfrontbench.live_smoke.launch_playing_agent") as launch:
        launch.return_value = SimpleNamespace(
            process=SimpleNamespace(
                stdout="", stderr="", returncode=0, timed_out=False
            ),
            run=SimpleNamespace(),
            config={},
            resolved_config=None,
        )
        run(env, tmp_path / "output", 10, max_decisions=2)
    _, kwargs = launch.call_args
    assert "game_start_solo_game" in kwargs["prompt"]


def test_summarise_unwraps_nested_result_envelope():
    from openfrontbench.live_smoke import _summarise_events

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


def test_summarise_skips_framing_noise():
    from openfrontbench.live_smoke import _summarise_events

    stdout = "\n".join(
        [
            "",
            "   ",
            "not-json",
            json.dumps([1, 2, 3]),
            json.dumps({"type": "tool_use", "timestamp": 1000, "part": "nope"}),
            _tool_event("game_start_solo_game", {"tick": 3, "winner": None}),
        ]
    )
    summary = _summarise_events(stdout)
    assert summary["tool_calls"] == 1
    assert summary["winner"] is None


def test_summarise_captures_human_nations_tokens_cost_wall():
    from openfrontbench.live_smoke import _summarise_events

    def event_with_ts(tool, result, ts):
        base = json.loads(_tool_event(tool, result))
        base["timestamp"] = ts
        return json.dumps(base)

    stdout = "\n".join(
        [
            event_with_ts(
                "game_get_overview",
                {
                    "tick": 53,
                    "winner": None,
                    "human": {"tiles": 10, "troops": 5, "extra": "x"},
                    "nations": [
                        {
                            "name": "A",
                            "tiles": 3,
                            "troops": 2,
                            "alive": True,
                            "junk": 1,
                        },
                        "not-a-dict",
                    ],
                },
                1000,
            ),
            json.dumps(
                {
                    "type": "step_finish",
                    "timestamp": 3000,
                    "part": {"tokens": {"input": 1, "output": 2}, "cost": 0.5},
                }
            ),
        ]
    )
    summary = _summarise_events(stdout)
    assert summary["final_human"] == {"tiles": 10, "troops": 5}
    assert summary["final_nations"] == [
        {"name": "A", "tiles": 3, "troops": 2, "alive": True}
    ]
    assert summary["tokens"] == {"input": 1, "output": 2}
    assert summary["cost"] == 0.5
    assert summary["wall_ms"] == 2000
