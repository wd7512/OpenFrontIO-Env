"""Live smoke wiring: .env.local -> isolated OpenCode playing agent, no key leaks."""

from __future__ import annotations

import json
import logging
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

from openfront_mcp.opencode_launcher import (
    McpServerSpec,
    launch_playing_agent,
    redact,
)

log = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PROVIDER = "openrouter"
KEY_ENV_BY_PROVIDER = {
    "openrouter": "OPENROUTER_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
    "openai": "OPENAI_API_KEY",
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


def build_smoke_prompt(max_decisions: int = 3) -> str:
    steps = ["game_start_smoke_game", "game_get_overview"]
    steps += [f"game_end_decision (decision={n})" for n in range(1, max_decisions + 1)]
    steps += ["game_get_overview", "game_close_game"]
    lines = [
        "Play one single-human smoke scenario to completion using only game MCP tools.",
        "Do exactly these tool calls in order:",
        *[f"- {s}" for s in steps],
        "Then stop. Report decisions and ticks briefly.",
    ]
    return "\n".join(lines)


def build_match_prompt(max_decisions: int = 6) -> str:
    steps = ["game_start_1v1_game", "game_get_overview"]
    for n in range(1, max_decisions + 1):
        steps += [
            "game_order_attack (target=expand, troops=5000)",
            f"game_end_decision (decision={n})",
        ]
    steps += ["game_get_overview", "game_close_game"]
    lines = [
        "Play one 1v1 match (your human vs one nation) to completion using only "
        "game MCP tools. Each decision: FIRST order expansion with "
        "game_order_attack (target must be exactly 'expand', troops a positive "
        "integer you can afford — never more than half your current troops), "
        "THEN advance 50 ticks with game_end_decision. get_overview shows both "
        "sides, your live attacks, and the winner.",
        "Do exactly these tool calls in order (start_1v1_game takes no arguments):",
        *[f"- {s}" for s in steps],
        "Then stop. Report each side's tiles and troops per decision, whether "
        "your attacks landed, and the winner if one is declared.",
    ]
    return "\n".join(lines)


def build_solo_prompt(max_decisions: int = 20, difficulty: str = "easy") -> str:
    lines = [
        "Play one default solo game (your human vs 400 tribes and 52 nations "
        f"on full Europe, bots at {difficulty} difficulty) using only game "
        "MCP tools. Phases, triggered by what you observe:",
        "PHASE 1 — EXPAND: while your tile count is still growing between "
        "decisions, call game_order_attack (target exactly 'expand', troops a "
        "positive integer never more than half your current troops), then "
        "game_end_decision with the next decision integer.",
        "TRIBES: tribes (tribe-1 .. tribe-400 in get_overview tribes_list) "
        "are attackable with game_order_attack once one shows "
        "borders_human true — they never have immunity, and clearing them "
        "is safe expansion. Prefer tribes over nations while tiles grow. "
        "tribes_list shows only bordering tribes (the only attackable "
        "ones); the tribes count tracks the rest.",
        "PHASE 2 — ATTACK NATIONS: only when BOTH hold: (a) your tiles have "
        "stalled across two consecutive overviews (expansion exhausted, "
        "fronts met), AND (b) a nation shows borders_human true AND immune "
        "false in get_overview. Then ONE decisive strike: game_order_attack "
        "with that nation's id and most of your troops (up to three "
        "quarters), not repeated small waves — repeated half-troop waves "
        "bleed out while nations outproduce you. Then game_end_decision as "
        "before.",
        "BUILD: when gold exceeds 150000, buy game_order_build unit "
        "'defense-post' at your spawn tile (x, y from get_overview human "
        "spawn). Cities at 125000+ if richer. Check get_overview units to "
        "confirm. Upgrade the city once with game_order_upgrade_unit when "
        "gold allows.",
        "DIPLOMACY (optional): game_order_embargo can pressure a bordering "
        "nation (action start/stop). Alliance requests and donations exist "
        "but nations rarely answer — do not rely on them.",
        "Cancel a mistargeted attack with game_order_cancel_attack (id from "
        "attacks). Boats and warships need shore + water you cannot see — "
        "skip them unless adjacent water is obvious from your growth.",
        "Start with game_start_solo_game with difficulty "
        f'"{difficulty}" (no other arguments) and one game_get_overview. '
        "Check game_get_overview whenever you need the "
        "state. End with game_get_overview and game_close_game. "
        f"Play at most {max_decisions} decisions, then stop even if no winner.",
        "Then stop. Report tiles and troops per phase, tribe kills, when "
        "contact happened, whether nation attacks landed, what you built, "
        "and the winner if declared.",
    ]
    return "\n".join(lines)


def build_campaign_prompt(max_decisions: int = 45) -> str:
    lines = [
        "Play one full 1v1 campaign (your human vs one nation) using only game "
        "MCP tools. Two phases, triggered by what you observe:",
        "PHASE 1 — EXPAND: while your tile count is still growing between "
        "decisions, call game_order_attack (target exactly 'expand', troops a "
        "positive integer never more than half your current troops), then "
        "game_end_decision with the next decision integer.",
        "PHASE 2 — ATTACK: only when BOTH hold: (a) your tiles have stalled "
        "across two consecutive overviews (expansion exhausted, fronts met), "
        "AND (b) a nation shows borders_human true AND immune false in "
        "get_overview. Then switch the order to game_order_attack with target "
        "exactly 'nation-1' and half your troops, then game_end_decision as "
        "before. Repeat every decision. Border contact alone is NOT enough — "
        "attacking early with small waves bleeds your troops while the nation "
        "outgrows you. Never order nation-1 while it is immune or does not "
        "border you — the order fizzles.",
        "Start with game_start_1v1_game (no arguments) and one "
        "game_get_overview. Check game_get_overview whenever you need the "
        "state. End with game_get_overview and game_close_game. "
        f"Play at most {max_decisions} decisions, then stop even if no winner.",
        "Then stop. Report tiles and troops per phase, when contact happened, "
        "whether your nation attacks landed, and the winner if declared.",
    ]
    return "\n".join(lines)


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
    for line in stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(event, dict):
            continue
        etype = event.get("type")
        part_raw: Any = event.get("part")
        part: dict[str, Any] = part_raw if isinstance(part_raw, dict) else {}
        ts = event.get("timestamp")
        if isinstance(ts, (int, float)):
            start_ms = ts if start_ms is None else min(start_ms, ts)
            end_ms = ts if end_ms is None else max(end_ms, ts)
        if etype == "tool_use" and isinstance(part.get("tool"), str):
            tool_calls += 1
            state_raw: Any = part.get("state")
            state: dict[str, Any] = state_raw if isinstance(state_raw, dict) else {}
            output: Any = state.get("output")
            parsed: dict[str, Any] | None = None
            if isinstance(output, str):
                try:
                    maybe = json.loads(output)
                except json.JSONDecodeError:
                    maybe = None
                if isinstance(maybe, dict):
                    parsed = maybe
                    inner_raw = parsed.get("result")
                    if isinstance(inner_raw, str):
                        try:
                            inner = json.loads(inner_raw)
                        except json.JSONDecodeError:
                            inner = None
                        if isinstance(inner, dict):
                            parsed = {**parsed, **inner}
            if part["tool"] == "game_end_decision" and parsed:
                if isinstance(parsed.get("decision"), int):
                    decisions.append(parsed["decision"])
                if isinstance(parsed.get("tick"), int):
                    ticks.append(parsed["tick"])
            if (
                part["tool"]
                in (
                    "game_start_1v1_game",
                    "game_start_smoke_game",
                    "game_get_overview",
                    "game_order_attack",
                )
                and parsed
            ):
                seen = parsed.get("winner")
                if isinstance(seen, str) and seen:
                    winner = seen
                human_raw = parsed.get("human")
                if isinstance(human_raw, dict):
                    human = {
                        k: human_raw[k]
                        for k in ("tiles", "troops")
                        if isinstance(human_raw.get(k), int)
                    } or None
                nations_raw = parsed.get("nations")
                if isinstance(nations_raw, list):
                    nations = [
                        {
                            k: n[k]
                            for k in ("name", "tiles", "troops", "alive")
                            if k in n
                        }
                        for n in nations_raw
                        if isinstance(n, dict)
                    ] or None
        if etype == "step_finish":
            tokens_raw: Any = part.get("tokens")
            if isinstance(tokens_raw, dict):
                tokens = tokens_raw
            cost_raw: Any = part.get("cost")
            if isinstance(cost_raw, (int, float)):
                cost = float(cost_raw)
    summary: dict[str, Any] = {
        "tool_calls": tool_calls,
        "decisions": decisions,
        "ticks": ticks,
        "winner": winner,
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
    scenario: str = "smoke",
    max_decisions: int = 3,
    difficulty: str = "easy",
) -> dict[str, Any]:
    """Run one bounded live session. Key check happens before any launch.

    ``scenario`` is ``"smoke"`` (single human) or ``"1v1"`` (human vs one
    nation); ``max_decisions`` counts the 50-tick advances. ``difficulty``
    applies to the solo scenario (nation bot strength).
    """
    settings = load_settings(env_file)
    provider = (
        settings.get("OPENFRONT_PROVIDER") or DEFAULT_PROVIDER
    ).strip() or DEFAULT_PROVIDER
    model = (settings.get("OPENFRONT_MODEL") or "").strip()
    if not model:
        raise ValueError("OPENFRONT_MODEL is required in the env file")
    if scenario not in ("smoke", "1v1", "campaign", "solo"):
        raise ValueError(
            f"scenario must be 'smoke', '1v1', 'campaign' or 'solo', got {scenario!r}"
        )
    if isinstance(max_decisions, bool) or not isinstance(max_decisions, int):
        raise ValueError("max_decisions must be an integer")
    if not 1 <= max_decisions <= 60:
        raise ValueError("max_decisions must be in [1, 60]")
    if difficulty not in ("easy", "medium", "hard", "impossible"):
        raise ValueError(
            "difficulty must be one of easy, medium, hard, impossible, "
            f"got {difficulty!r}"
        )
    key_env = KEY_ENV_BY_PROVIDER.get(provider, "OPENROUTER_API_KEY")
    api_key = (settings.get(key_env) or "").strip()
    if not api_key:
        raise ValueError(f"missing key for {key_env!r}; refusing to start the agent")

    out = Path(output)
    if out.exists():
        raise ValueError(f"output path already exists (refusing to overwrite): {out}")
    out.mkdir(parents=True)

    python_bin = sys.executable
    if not Path(python_bin).is_absolute():
        raise ValueError("python executable path is not absolute")
    wrapper = REPO_ROOT / "src" / "openfront_mcp" / "mcp_scrub_wrapper.py"
    mcp = McpServerSpec(
        name="game",
        command=(python_bin, str(wrapper)),
        cwd=str(REPO_ROOT),
        # Grid frames land here (one JSON line per decision) for timelapse
        # rendering; the wrapper only scrubs credential keys, so this passes
        # through, and it is never shown to the agent.
        environment={
            "OPENFRONT_GRID_DIR": str(out),
            "OPENFRONT_RECORD_DIR": str(out),
        },
    )
    prompt = (
        build_solo_prompt(max_decisions, difficulty)
        if scenario == "solo"
        else build_campaign_prompt(max_decisions)
        if scenario == "campaign"
        else build_match_prompt(max_decisions)
        if scenario == "1v1"
        else build_smoke_prompt(max_decisions)
    )
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
        models_cache_source=cache_source,
    )
    duration_s = time.monotonic() - t0
    secrets = (api_key,)
    summary = _summarise_events(result.process.stdout)
    payload: dict[str, Any] = {
        "model": model,
        "provider": provider,
        "scenario": scenario,
        "max_decisions": max_decisions,
        "agent_root": str(agent_root),
        "timeout_s": float(timeout_s),
        "duration_s": duration_s,
        "returncode": result.process.returncode,
        "timed_out": result.process.timed_out,
        "summary": summary,
    }
    (out / "live_result.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n"
    )
    (out / "live_events_redacted.jsonl").write_text(
        redact(result.process.stdout, secrets), encoding="utf-8"
    )
    log.info("live smoke complete: %s", json.dumps(summary, sort_keys=True))
    return payload
