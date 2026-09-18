"""Ledger-loss reconcile gate (keyless, pure filesystem check).

Each expected proxy cell must leave ``ready.json`` (ready-file handshake)
and ``usage.jsonl`` (usage ledger) under its ledger dir. Any gap is
reported as loss and fails the evidence gate — evidence is never written
for an unverified run.
"""

from __future__ import annotations

import logging
from pathlib import Path

from openfront_harbor.proxy.ledger import ledger_paths

log = logging.getLogger(__name__)


def check_ledger_loss(
    runs_dir: Path | str, run_id: str, expected_ports: list[int] | tuple[int, ...]
) -> list[str]:
    """Verify each expected cell ledger; return loss descriptions (empty = ok)."""
    run_dir = Path(runs_dir) / run_id
    losses: list[str] = []
    for port in expected_ports:
        paths = ledger_paths(run_dir, int(port))
        for key in ("ready", "usage"):
            candidate = paths[key]
            if not candidate.is_file():
                losses.append(f"cell-{int(port)}: missing {candidate.name}")
    if losses:
        log.error("ledger loss for run %s: %s", run_id, "; ".join(losses))
    else:
        log.info(
            "ledger gate: no loss for run %s (%d cell(s))",
            run_id,
            len(list(expected_ports)),
        )
    return losses


def gate_evidence(
    runs_dir: Path | str, run_id: str, expected_ports: list[int] | tuple[int, ...]
) -> bool:
    """True only when every expected cell ledger is intact (no loss)."""
    return not check_ledger_loss(runs_dir, run_id, expected_ports)
