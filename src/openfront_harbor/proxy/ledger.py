"""Pure per-cell proxy ledger helpers (T4, keyless, no network).

Mirrors the usage-ledger layout from the reference proxy server: each cell
owns ``<jobs-dir>/proxy-ledger/cell-<port>/`` holding ``usage.jsonl``,
``attempt-summary.json``, ``ready.json`` (ready-file handshake), and
``proxy.log``. These helpers touch only the local filesystem.
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)

USAGE_LOG_NAME = "usage.jsonl"
SUMMARY_NAME = "attempt-summary.json"
READY_FILE_NAME = "ready.json"
PROXY_LOG_NAME = "proxy.log"


def ledger_paths(jobs_dir: Path | str, port: int) -> dict[str, Path]:
    """Return the ledger file layout for one proxy cell (pure, creates nothing)."""
    base = Path(jobs_dir) / "proxy-ledger" / f"cell-{int(port)}"
    return {
        "dir": base,
        "usage": base / USAGE_LOG_NAME,
        "summary": base / SUMMARY_NAME,
        "ready": base / READY_FILE_NAME,
        "log": base / PROXY_LOG_NAME,
    }


def write_ready(ledger_dir: Path | str, payload: dict[str, Any]) -> Path:
    """Atomically write the ready-file handshake payload into a cell ledger."""
    if not isinstance(payload, dict):
        raise ValueError("ready payload must be a dict")
    out = Path(ledger_dir) / READY_FILE_NAME
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    os.replace(tmp, out)
    log.info("ledger ready written to %s", out)
    return out


def read_ready(ledger_dir: Path | str) -> dict[str, Any]:
    """Read back the ready-file handshake payload for a cell ledger."""
    raw = (Path(ledger_dir) / READY_FILE_NAME).read_text(encoding="utf-8")
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise ValueError(f"ready.json in {ledger_dir} is not a JSON object")
    return data


def append_usage(ledger_dir: Path | str, record: dict[str, Any]) -> Path:
    """Append one usage record to the cell ledger as a JSONL line."""
    if not isinstance(record, dict):
        raise ValueError("usage record must be a dict")
    ledger = Path(ledger_dir)
    ledger.mkdir(parents=True, exist_ok=True)
    out = ledger / USAGE_LOG_NAME
    with open(out, "a", encoding="utf-8") as fd:
        fd.write(json.dumps(record) + "\n")
    return out
