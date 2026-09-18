"""Evidence summary writer (T4, keyless).

Writes ``evidence/<run-id>/summary.json`` with the run id, job, ports, and
gate result — never secrets. Mirrors the fresh-dir policy: refuses to
overwrite an existing evidence dir.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)


def write_evidence(
    evidence_dir: Path | str,
    run_id: str,
    plan: dict[str, Any],
    checks: dict[str, Any],
) -> Path:
    """Write the evidence summary; raise if the run dir already exists."""
    out_dir = Path(evidence_dir) / run_id
    if out_dir.exists():
        raise FileExistsError(
            f"evidence dir already exists (refusing to overwrite): {out_dir}"
        )
    safe_plan = plan if isinstance(plan, dict) else {}
    safe_checks = checks if isinstance(checks, dict) else {}
    raw_ports = safe_plan.get("ports", [])
    raw_losses = safe_checks.get("losses", [])
    summary: dict[str, Any] = {
        "run_id": run_id,
        "job": str(safe_plan.get("job", run_id)),
        "ports": list(raw_ports) if isinstance(raw_ports, list) else [],
        "gate_pass": bool(safe_checks.get("gate_pass", False)),
        "losses": list(raw_losses) if isinstance(raw_losses, list) else [],
    }
    out_dir.mkdir(parents=True)
    out = out_dir / "summary.json"
    out.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    log.info("evidence summary written to %s", out)
    return out
