"""Live smoke wiring: .env.local -> isolated OpenCode playing agent, no key leaks."""

from __future__ import annotations

import json
import logging
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

from openfrontbench.atomic import (
    ensure_fresh_dir,
    write_json_atomic,
    write_text_atomic,
)
from openfrontbench.opencode_launcher import (
    McpServerSpec,
    PROVIDER_BASE_URLS,
    launch_playing_agent,
    redact,
)
from openfrontbench.paths import REPO_ROOT

log = logging.getLogger(__name__)
DEFAULT_PROVIDER = "openrouter"
KEY_ENV_BY_PROVIDER = {
    "openrouter": "OPENROUTER_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
    "openai": "OPENAI_API_KEY",
    "opencode-go": "OPENCODE_API_KEY",
    "opencode-zen": "OPENCODE_ZEN_API_KEY",
}


def parse_dotenv(text: str) -> dict[str, str]:
    """Parse dotenv content without shell evaluation or variable expansion."""
    out: dict[str, str] = {}
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export ") :].strip()
        if "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
            value = value[1:-1]
        if key:
            out[key] = value
    return out


def load_settings(env_file: Path | str) -> dict[str, str]:
    path = Path(env_file)
    if not path.is_file():
        raise ValueError(f"env file not found: {path}")
    return parse_dotenv(path.read_text(encoding="utf-8"))


PROMPTS_DIR = Path(__file__).resolve().parent.parent.parent / "prompts"


def load_prompt(name: str, **values: Any) -> str:
    """Render a prompt template from ``prompts/<name>.md``.

    Templates use ``str.format`` placeholders (``{difficulty}``,
    ``{max_decisions}``, ``{memory_block}``). Literal
    braces in prompt text must be doubled in the .md file.
    """
    template = (PROMPTS_DIR / f"{name}.md").read_text(encoding="utf-8")
    return template.format(**values).strip()


def build_solo_prompt(
    max_decisions: int = 20, difficulty: str = "easy", memory: str | None = None
) -> str:
    if memory and memory.strip():
        memory_block = (
            "PLAYBOOK from previous runs of this format (general strategy — "
            "follow it unless the board says otherwise):\n" + memory.strip()
        )
    else:
        memory_block = ""
    return load_prompt(
        "solo",
        difficulty=difficulty,
        max_decisions=max_decisions,
        memory_block=memory_block,
    )


def _parse_event_line(line: str) -> dict[str, Any] | None:
    """Parse one JSONL line; return None for framing noise."""
    line = line.strip()
    if not line:
        return None
    try:
        event = json.loads(line)
    except json.JSONDecodeError:
        return None
    return event if isinstance(event, dict) else None


def _unwrap_tool_result(output: Any) -> dict[str, Any] | None:
    """Unwrap the double `result`-in-`result` envelope; None if unusable."""
    if not isinstance(output, str):
        return None
    try:
        maybe = json.loads(output)
    except json.JSONDecodeError:
        return None
    if not isinstance(maybe, dict):
        return None
    parsed = maybe
    inner_raw = parsed.get("result")
    if isinstance(inner_raw, str):
        try:
            inner = json.loads(inner_raw)
        except json.JSONDecodeError:
            inner = None
        if isinstance(inner, dict):
            parsed = {**parsed, **inner}
    return parsed


def _extract_decision(
    tool: str, parsed: dict[str, Any] | None
) -> tuple[int | None, int | None]:
    """Return (decision, tick) for end-decision events, else (None, None)."""
    if tool != "game_end_decision" or not parsed:
        return None, None
    decision = parsed.get("decision")
    tick = parsed.get("tick")
    return (
        decision if isinstance(decision, int) else None,
        tick if isinstance(tick, int) else None,
    )


def _extract_snapshot(
    parsed: dict[str, Any],
) -> tuple[str | None, dict[str, Any] | None, list[dict[str, Any]] | None]:
    """Extract winner/human/nations from an overview payload."""
    seen = parsed.get("winner")
    winner = seen if isinstance(seen, str) and seen else None
    human: dict[str, Any] | None = None
    human_raw = parsed.get("human")
    if isinstance(human_raw, dict):
        human = {
            k: human_raw[k]
            for k in ("tiles", "troops")
            if isinstance(human_raw.get(k), int)
        } or None
    nations: list[dict[str, Any]] | None = None
    nations_raw = parsed.get("nations")
    if isinstance(nations_raw, list):
        nations = [
            {k: n[k] for k in ("name", "tiles", "troops", "alive") if k in n}
            for n in nations_raw
            if isinstance(n, dict)
        ] or None
    return winner, human, nations


def _extract_step_usage(
    part: dict[str, Any],
) -> tuple[dict[str, Any] | None, float | None]:
    """Extract tokens/cost from a step_finish part."""
    tokens_raw: Any = part.get("tokens")
    tokens = tokens_raw if isinstance(tokens_raw, dict) else None
    cost_raw: Any = part.get("cost")
    cost = float(cost_raw) if isinstance(cost_raw, (int, float)) else None
    return tokens, cost


_OVERVIEW_TOOLS = frozenset(
    {"game_start_solo_game", "game_get_overview", "game_order_attack"}
)


def _summarise_events(stdout: str) -> dict[str, Any]:
    tool_calls = 0
    decisions: list[int] = []
    ticks: list[int] = []
    winner: str | None = None
    human: dict[str, Any] | None = None
    nations: list[dict[str, Any]] | None = None
    tokens: dict[str, Any] | None = None
    cost: float | None = None
    start_ms: float | None = None
    end_ms: float | None = None
    attacks: list[dict[str, Any]] = []
    builds: list[str] = []
    boats = 0
    tiles_by_decision: dict[int, int] = {}
    gold_end: str | None = None
    last_decision: int | None = None
    for raw_line in stdout.splitlines():
        event = _parse_event_line(raw_line)
        if event is None:
            continue
        etype = event.get("type")
        part_raw: Any = event.get("part")
        part: dict[str, Any] = part_raw if isinstance(part_raw, dict) else {}
        ts = event.get("timestamp")
        if isinstance(ts, (int, float)):
            start_ms = ts if start_ms is None else min(start_ms, ts)
            end_ms = ts if end_ms is None else max(end_ms, ts)
        if etype == "tool_use" and isinstance(part.get("tool"), str):
            tool = str(part["tool"])
            tool_calls += 1
            state_raw: Any = part.get("state")
            state: dict[str, Any] = state_raw if isinstance(state_raw, dict) else {}
            parsed = _unwrap_tool_result(state.get("output"))
            decision, tick = _extract_decision(tool, parsed)
            if decision is not None:
                decisions.append(decision)
            if tick is not None:
                ticks.append(tick)
            if tool in _OVERVIEW_TOOLS and parsed:
                seen_winner, seen_human, seen_nations = _extract_snapshot(parsed)
                if seen_winner is not None:
                    winner = seen_winner
                if isinstance(parsed.get("human"), dict):
                    human = seen_human
                if isinstance(parsed.get("nations"), list):
                    nations = seen_nations
            if parsed is not None:
                decision_raw = parsed.get("decision")
                human_state = parsed.get("human")
                if isinstance(decision_raw, int):
                    last_decision = decision_raw
                    if isinstance(human_state, dict) and isinstance(
                        human_state.get("tiles"), int
                    ):
                        tiles_by_decision[decision_raw] = human_state["tiles"]
                if isinstance(human_state, dict) and isinstance(
                    human_state.get("gold"), str
                ):
                    gold_end = human_state["gold"]
            input_raw: Any = state.get("input")
            inputs: dict[str, Any] = input_raw if isinstance(input_raw, dict) else {}
            if tool == "game_order_attack":
                attacks.append(
                    {
                        "decision": last_decision,
                        "target": inputs.get("target"),
                        "troops": inputs.get("troops"),
                    }
                )
            elif tool == "game_order_build":
                unit = inputs.get("unit")
                if isinstance(unit, str):
                    builds.append(unit)
            elif tool == "game_order_boat_attack":
                boats += 1
        elif etype == "step_finish":
            seen_tokens, seen_cost = _extract_step_usage(part)
            if seen_tokens is not None:
                tokens = seen_tokens
            if seen_cost is not None:
                cost = seen_cost
    summary: dict[str, Any] = {
        "tool_calls": tool_calls,
        "decisions": decisions,
        "ticks": ticks,
        "winner": winner,
    }
    dec_sorted = sorted(tiles_by_decision)

    def tiles_at(decision: int) -> int | None:
        prior = [d for d in dec_sorted if d <= decision]
        return tiles_by_decision[prior[-1]] if prior else None

    summary["metrics"] = {
        "attacks": len(attacks),
        "attacks_after_50": sum(
            1
            for a in attacks
            if isinstance(a.get("decision"), int) and a["decision"] > 50
        ),
        "expand_attacks": sum(1 for a in attacks if a.get("target") == "expand"),
        "nation_attacks": sum(
            1
            for a in attacks
            if isinstance(a.get("target"), str) and a["target"].startswith("nation")
        ),
        "tribe_attacks": sum(
            1
            for a in attacks
            if isinstance(a.get("target"), str) and a["target"].startswith("tribe")
        ),
        "boats": boats,
        "cities": sum(1 for b in builds if b == "city"),
        "defense_posts": sum(1 for b in builds if b == "defense-post"),
        "tiles_50": tiles_at(50),
        "tiles_100": tiles_at(100),
        "tiles_peak": max(tiles_by_decision.values()) if tiles_by_decision else None,
        "gold_end": gold_end,
    }
    if human is not None:
        summary["final_human"] = human
    if nations is not None:
        summary["final_nations"] = nations
    if tokens is not None:
        summary["tokens"] = tokens
    summary["cost"] = cost
    if start_ms is not None and end_ms is not None:
        summary["wall_ms"] = end_ms - start_ms
    return summary


def _default_models_cache() -> Path | None:
    """Host OpenCode models cache, if present.

    The isolated agent gets a fresh ``XDG_CACHE_HOME`` (so the host's global
    config can't leak in), but that also hides the host's refreshed model
    catalog — and OpenCode resolves run-time models from that catalog. A
    brand-new model (e.g. a days-old release) is then "not found" even though
    the provider lists it. Seeding a copy of the host cache into the isolated
    run fixes resolution without weakening anything else.
    """
    candidate = Path.home() / ".cache" / "opencode" / "models.json"
    return candidate if candidate.is_file() else None


def run(
    env_file: Path | str,
    output: Path | str,
    timeout_s: float = 120.0,
    models_cache_source: Path | str | None = None,
    max_decisions: int = 100,
    difficulty: str = "easy",
    memory: str | None = None,
) -> dict[str, Any]:
    """Run one bounded live solo session. Key check happens before any launch.

    Solo only: one human vs 400 tribes and 52 nations on full Europe.
    ``max_decisions`` counts the 50-tick advances. ``difficulty`` is the
    nation bot strength.
    """
    settings = load_settings(env_file)
    provider = (
        settings.get("OPENFRONT_PROVIDER") or DEFAULT_PROVIDER
    ).strip() or DEFAULT_PROVIDER
    model = (settings.get("OPENFRONT_MODEL") or "").strip()
    if not model:
        raise ValueError("OPENFRONT_MODEL is required in the env file")
    if isinstance(max_decisions, bool) or not isinstance(max_decisions, int):
        raise ValueError("max_decisions must be an integer")
    if not 1 <= max_decisions <= 500:
        raise ValueError("max_decisions must be in [1, 500]")
    if difficulty not in ("easy", "medium", "hard", "impossible"):
        raise ValueError(
            "difficulty must be one of easy, medium, hard, impossible, "
            f"got {difficulty!r}"
        )
    key_env = KEY_ENV_BY_PROVIDER.get(provider, "OPENROUTER_API_KEY")
    api_key = (settings.get(key_env) or "").strip()
    if not api_key:
        raise ValueError(f"missing key for {key_env!r}; refusing to start the agent")

    out = ensure_fresh_dir(output)

    python_bin = sys.executable
    if not Path(python_bin).is_absolute():
        raise ValueError("python executable path is not absolute")
    wrapper = REPO_ROOT / "src" / "openfrontbench" / "mcp_scrub_wrapper.py"
    mcp = McpServerSpec(
        name="game",
        command=(python_bin, str(wrapper)),
        cwd=str(REPO_ROOT),
        # The replay tape lands here (record.json, written by the worker);
        # the wrapper only scrubs credential keys, so this passes through,
        # and it is never shown to the agent.
        environment={
            "OPENFRONT_RECORD_DIR": str(out),
        },
    )
    prompt = build_solo_prompt(max_decisions, difficulty, memory=memory)
    t0 = time.monotonic()
    # The agent's working directory must have no `.opencode`/`opencode.json`
    # ancestor (OpenCode discovers project plugins upward from cwd), so it
    # lives in a fresh system temp dir — never inside the user's output dir,
    # which may sit below such an ancestor (e.g. Downloads). Artifacts are
    # copied into `out` below.
    agent_root = Path(tempfile.mkdtemp(prefix="openfront-live-"))
    cache_source = (
        models_cache_source
        if models_cache_source is not None
        else _default_models_cache()
    )
    result = launch_playing_agent(
        run_root=agent_root / "agent",
        model=model,
        mcp=mcp,
        api_key=api_key,
        prompt=prompt,
        timeout_s=float(timeout_s),
        provider=provider,
        key_env_var=key_env,
        base_url=PROVIDER_BASE_URLS.get(provider),
        models_cache_source=cache_source,
    )
    duration_s = time.monotonic() - t0
    secrets = (api_key,)
    summary = _summarise_events(result.process.stdout)
    payload: dict[str, Any] = {
        "model": model,
        "provider": provider,
        "scenario": "solo",
        "difficulty": difficulty,
        "max_decisions": max_decisions,
        "agent_root": str(agent_root),
        "timeout_s": float(timeout_s),
        "duration_s": duration_s,
        "returncode": result.process.returncode,
        "timed_out": result.process.timed_out,
        "summary": summary,
    }
    write_json_atomic(out / "live_result.json", payload)
    write_text_atomic(
        out / "live_events_redacted.jsonl", redact(result.process.stdout, secrets)
    )
    log.info("live smoke complete: %s", json.dumps(summary, sort_keys=True))
    return payload
