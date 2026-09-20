"""Unified per-game ``summary.json`` schema.

Every finished game, regardless of pipeline (live LLM play, code-evo
eval, scripted benchmark), writes the same summary shape into its run
dir next to ``record.json``. The replay index reads this first and
falls back to legacy ``live_result.json`` for pre-unification runs.
"""

from __future__ import annotations

import datetime
import json
from pathlib import Path
from typing import Any

from openfrontbench.atomic import write_json_atomic

SUMMARY_VERSION = 1
SUMMARY_FILENAME = "summary.json"


def utc_now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")


def build_summary(
    *,
    game: str,
    experiment: str | None = None,
    pipeline: str | None = None,
    model: str | None = None,
    policy_sha256: str | None = None,
    map: str | None = None,
    spawn_id: str | None = None,
    difficulty: str | None = None,
    config: dict[str, Any] | None = None,
    decisions: int | None = None,
    tick_first: int | None = None,
    tick_last: int | None = None,
    winner: str | None = None,
    tiles_peak: int | None = None,
    tiles_final: int | None = None,
    troops_final: int | None = None,
    score: float | None = None,
    wall_s: float | None = None,
    cost: float | None = None,
    tool_calls: int | None = None,
    tool_errors: int | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a versioned summary dict (JSON-serializable)."""
    return {
        "version": SUMMARY_VERSION,
        "game": game,
        "experiment": experiment,
        "pipeline": pipeline,
        "model": model,
        "policy_sha256": policy_sha256,
        "map": map,
        "spawn_id": spawn_id,
        "difficulty": difficulty,
        "config": dict(config or {}),
        "decisions": decisions,
        "tick_first": tick_first,
        "tick_last": tick_last,
        "winner": winner,
        "tiles_peak": tiles_peak,
        "tiles_final": tiles_final,
        "troops_final": troops_final,
        "score": score,
        "wall_s": wall_s,
        "cost": cost,
        "tool_calls": tool_calls,
        "tool_errors": tool_errors,
        "extra": dict(extra or {}),
        "created_at": utc_now(),
    }


def write_summary(run_dir: Path, summary: dict[str, Any]) -> Path:
    """Atomically write ``summary.json`` into *run_dir*."""
    return write_json_atomic(run_dir / SUMMARY_FILENAME, summary)


def _as_int(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    return value if isinstance(value, int) else None


def _as_float(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    return None


def from_live_result(game: str, live: dict[str, Any]) -> dict[str, Any]:
    """Map a legacy ``live_result.json`` payload onto the unified schema."""
    inner = live.get("summary")
    inner = inner if isinstance(inner, dict) else {}
    decisions_raw = inner.get("decisions")
    decisions = len(decisions_raw) if isinstance(decisions_raw, list) else None
    ticks_raw = inner.get("ticks")
    ticks = ticks_raw if isinstance(ticks_raw, list) else []
    tick_first = ticks[0] if ticks and isinstance(ticks[0], int) else None
    tick_last = ticks[-1] if ticks and isinstance(ticks[-1], int) else None
    final_human = inner.get("final_human")
    final_human = final_human if isinstance(final_human, dict) else {}
    metrics = inner.get("metrics")
    metrics = metrics if isinstance(metrics, dict) else {}
    winner = inner.get("winner")
    scenario = live.get("scenario")
    model = live.get("model")
    difficulty = live.get("difficulty")
    return build_summary(
        game=game,
        pipeline="live",
        model=model if isinstance(model, str) else None,
        difficulty=difficulty if isinstance(difficulty, str) else None,
        config={"scenario": scenario, "max_decisions": live.get("max_decisions")},
        decisions=decisions,
        tick_first=tick_first,
        tick_last=tick_last,
        winner=winner if isinstance(winner, str) else None,
        tiles_peak=_as_int(metrics.get("tiles_peak")),
        tiles_final=_as_int(final_human.get("tiles")),
        troops_final=_as_int(final_human.get("troops")),
        wall_s=_as_float(live.get("duration_s")),
        cost=_as_float(inner.get("cost")),
        tool_calls=_as_int(inner.get("tool_calls")),
        tool_errors=_as_int(metrics.get("tool_errors")),
        extra={"scenario": scenario, "metrics": metrics},
    )


def read_summary(run_dir: Path) -> dict[str, Any] | None:
    """Read unified summary, falling back to legacy ``live_result.json``."""
    summary_path = run_dir / SUMMARY_FILENAME
    if summary_path.is_file():
        try:
            parsed = json.loads(summary_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            parsed = None
        if isinstance(parsed, dict) and parsed:
            return parsed
    live_path = run_dir / "live_result.json"
    if live_path.is_file():
        try:
            live = json.loads(live_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            live = None
        if isinstance(live, dict) and live:
            return from_live_result(run_dir.name, live)
    return None
