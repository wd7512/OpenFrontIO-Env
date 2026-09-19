"""Dry-run planner for harbor grids (keyless, no live runs).

``plan_run`` is pure: it resolves the job spec, assigns proxy ports from
an explicit base port upward, maps each cell to its proxy ledger dir +
proxy base URL, and returns the ``harbor run`` command that live wiring
would execute. Nothing here spawns processes, touches the network, or
needs API keys. Port and URL values arrive as inputs — see ``example.py``.
"""

from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path
from typing import Any

from openfront_harbor.config.job_spec import load_job_yaml
from openfront_harbor.proxy.ledger import ledger_paths

log = logging.getLogger(__name__)


def plan_run(
    job_yaml: Path | str,
    jobs_dir: Path | str,
    run_id: str,
    *,
    base_port: int,
    proxy_url_template: str,
) -> dict[str, Any]:
    """Build a dry-run plan for a job config (no side effects)."""
    spec = load_job_yaml(Path(job_yaml))
    n_cells = len(spec.ports) if spec.ports else 1
    ports = [int(base_port) + i for i in range(n_cells)]
    run_jobs_dir = Path(jobs_dir) / "runs" / run_id
    cells = [
        {
            "port": port,
            "ledger_dir": str(ledger_paths(run_jobs_dir, port)["dir"]),
            "proxy_base_url": proxy_url_template.format(port=port),
        }
        for port in ports
    ]
    command = [
        "harbor",
        "run",
        "--config",
        str(Path(job_yaml)),
        "--jobs-dir",
        str(run_jobs_dir),
    ]
    plan: dict[str, Any] = {
        "run_id": run_id,
        "job": spec.job_name,
        "job_yaml": str(Path(job_yaml)),
        "jobs_dir": str(run_jobs_dir),
        "n_attempts": spec.n_attempts,
        "datasets": list(spec.datasets),
        "ports": ports,
        "cells": cells,
        "dry_run": command,
    }
    log.info("planned run %s: job=%s cells=%d", run_id, spec.job_name, n_cells)
    return plan


def run_dry(args: argparse.Namespace) -> int:
    """CLI backing for `plan`: emit the JSON plan artifact to stdout."""
    plan = plan_run(
        args.config,
        args.jobs_dir,
        args.run_id,
        base_port=args.base_port,
        proxy_url_template=args.proxy_url_template,
    )
    print(json.dumps(plan, indent=2))
    log.info("dry-run plan for %s printed (no live run started)", plan["run_id"])
    return 0
