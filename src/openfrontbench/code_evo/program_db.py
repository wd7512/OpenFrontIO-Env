"""Program database: append-only JSONL of evaluated candidates.

Each entry records the policy source, its aggregate score and per-spawn
breakdown, so the prompt sampler can resurface the best and most diverse
ideas (single-lineage AlphaEvolve: best + one diverse parent per round).
"""

from __future__ import annotations

import json
import random
from pathlib import Path
from typing import Any


def append_entry(db_path: Path, entry: dict[str, Any]) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with db_path.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(entry, sort_keys=True) + "\n")


def load_entries(db_path: Path) -> list[dict[str, Any]]:
    if not db_path.is_file():
        return []
    entries: list[dict[str, Any]] = []
    for line in db_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            parsed = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            entries.append(parsed)
    return entries


def best_entry(entries: list[dict[str, Any]]) -> dict[str, Any] | None:
    scored = [e for e in entries if isinstance(e.get("mean_score"), (int, float))]
    if not scored:
        return None
    return max(scored, key=lambda e: float(e["mean_score"]))


def diverse_entry(
    entries: list[dict[str, Any]],
    exclude_sha: str,
    seed: int = 0,
) -> dict[str, Any] | None:
    """A random scored entry that is not the excluded one (or None)."""
    pool = [
        e
        for e in entries
        if isinstance(e.get("mean_score"), (int, float))
        and e.get("policy_sha256") != exclude_sha
    ]
    if not pool:
        return None
    return random.Random(seed).choice(pool)
