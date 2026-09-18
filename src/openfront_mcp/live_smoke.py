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
    PROVIDER_BASE_URLS,
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

    Templates use ``str.format`` placeholders (``{steps}``,
    ``{max_decisions}``, ``{difficulty}``, ``{memory_block}``). Literal
    braces in prompt text must be doubled in the .md file.
    """
    template = (PROMPTS_DIR / f"{name}.md").read_text(encoding="utf-8")
    return template.format(**values).strip()


def build_smoke_prompt(max_decisions: int = 3) -> str:
    steps = ["game_start_smoke_game", "game_get_overview"]
    steps += [f"game_end_decision (decision={n})" for n in range(1, max_decisions + 1)]
    steps += ["game_get_overview", "game_close_game"]
    rendered_steps = "\n".join(f"- {s}" for s in steps)
    return load_prompt("smoke", steps=rendered_steps)


def build_match_prompt(max_decisions: int = 6) -> str:
    steps = ["game_start_1v1_game", "game_get_overview"]
    for n in range(1, max_decisions + 1):
        steps += [
            "game_get_overview (FIRST — size your order off what you see)",
            "game_order_attack (target=expand, troops=half your current troops)",
            f"game_end_decision (decision={n})",
        ]
    steps += ["game_get_overview", "game_close_game"]
    rendered_steps = "\n".join(f"- {s}" for s in steps)
    return load_prompt("match", steps=rendered_steps)


def build_solo_prompt(
    max_decisions: int = 20, difficulty: str = "easy", memory: str | None = None
) -> str:
    if memory and memory.strip():
        memory_block = (
            "NOTES FROM A PREVIOUS MATCH (same format, learned the hard way — "
            "follow what worked, avoid what failed):\n" + memory.strip()
        )
    else:
        memory_block = ""
    return load_prompt(
        "solo",
        difficulty=difficulty,
        max_decisions=max_decisions,
        memory_block=memory_block,
    )


def build_campaign_prompt(max_decisions: int = 45) -> str:
    return load_prompt("campaign", max_decisions=max_decisions)


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
    memory: str | None = None,
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
        build_solo_prompt(max_decisions, difficulty, memory=memory)
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
        base_url=PROVIDER_BASE_URLS.get(provider),
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
