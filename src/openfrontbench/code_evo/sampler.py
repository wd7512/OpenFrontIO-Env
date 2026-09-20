"""Prompt sampler: best + one diverse parent -> coding prompt."""

from __future__ import annotations

from pathlib import Path
from typing import Any


def render_coding_prompt(
    template: str,
    best: dict[str, Any],
    diverse: dict[str, Any] | None,
    best_source: str,
    diverse_source: str | None,
) -> str:
    """Fill the code-evo template with parent programs and their scores."""
    return template.format(
        best_score=best.get("mean_score"),
        best_summary=_summarize(best),
        best_source=best_source,
        diverse_score=(diverse or {}).get("mean_score", "n/a"),
        diverse_summary=_summarize(diverse) if diverse else "n/a",
        diverse_source=diverse_source or "n/a",
    ).strip()


def _summarize(entry: dict[str, Any] | None) -> str:
    if not entry:
        return "n/a"
    spawns = entry.get("spawns", [])
    parts = []
    if isinstance(spawns, list):
        for spawn in spawns:
            if not isinstance(spawn, dict):
                continue
            parts.append(
                f"{spawn.get('spawn_id')}: peak={spawn.get('tiles_peak')} "
                f"final={spawn.get('final_tiles')} "
                f"ticks={spawn.get('ticks')} "
                f"errors={spawn.get('policy_errors')} "
                f"out={spawn.get('outcome')} "
                f"gpeak={spawn.get('gold_peak')} "
                f"city={spawn.get('city_ever')}"
            )
    return "; ".join(parts) or "n/a"


def load_template(prompts_dir: Path, name: str = "code_evo") -> str:
    return (prompts_dir / f"{name}.md").read_text(encoding="utf-8")
