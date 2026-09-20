"""Experiment dirs: one dir per experiment, games nested inside."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from openfrontbench.atomic import write_json_atomic
from openfrontbench.run_summary import utc_now

EXPERIMENT_FILENAME = "experiment.json"


def write_experiment(
    root: Path,
    *,
    name: str,
    kind: str,
    config: dict[str, Any] | None = None,
    notes: str | None = None,
) -> Path:
    """Write ``experiment.json`` into an existing experiment dir."""
    payload: dict[str, Any] = {
        "version": 1,
        "name": name,
        "kind": kind,
        "config": dict(config or {}),
        "notes": notes,
        "created_at": utc_now(),
    }
    return write_json_atomic(root / EXPERIMENT_FILENAME, payload)


def read_experiment(root: Path) -> dict[str, Any] | None:
    """Read ``experiment.json`` or None when absent/unusable."""
    import json

    path = root / EXPERIMENT_FILENAME
    if not path.is_file():
        return None
    try:
        parsed = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return parsed if isinstance(parsed, dict) else None
