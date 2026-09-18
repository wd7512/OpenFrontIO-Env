"""Ledger, dry-run plan, reconcile gate, evidence: process + example.

Process tests use synthetic ports and tmp dirs; only the `example_*`
tests use real repo files and example constants. No docker, no network,
no harbor binary, no API keys.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
GRID_JOB = REPO_ROOT / "jobs/active/main-grid-openfront-amd64.yaml"

TEMPLATE = "http://proxy.local:{port}/api"


def _write_job(path: Path, ports: list[int], tasks: list[str]) -> None:
    agents = "\n".join(
        f"  - name: agent-{port}\n"
        f"    kwargs:\n"
        f"      proxy_base_url: http://proxy.local:{port}/api"
        for port in ports
    )
    names = "\n".join(f"      - {task}" for task in tasks)
    path.write_text(
        "job_name: synthetic-job\n"
        "n_attempts: 1\n"
        "datasets:\n"
        "  - path: tasks\n"
        "    task_names:\n"
        f"{names}\n"
        "agents:\n"
        f"{agents}\n",
        encoding="utf-8",
    )


def test_ledger_paths_layout(tmp_path: Path) -> None:
    from openfront_harbor.proxy.ledger import ledger_paths

    paths = ledger_paths(tmp_path, 9101)
    cell = tmp_path / "proxy-ledger" / "cell-9101"
    assert paths["dir"] == cell
    assert paths["usage"] == cell / "usage.jsonl"
    assert paths["summary"] == cell / "attempt-summary.json"
    assert paths["ready"] == cell / "ready.json"
    assert paths["log"] == cell / "proxy.log"


def test_ready_round_trip_and_usage_append(tmp_path: Path) -> None:
    from openfront_harbor.proxy.ledger import (
        append_usage,
        ledger_paths,
        read_ready,
        write_ready,
    )

    cell = ledger_paths(tmp_path, 9101)["dir"]
    write_ready(cell, {"token": "abc123"})
    assert read_ready(cell) == {"token": "abc123"}
    append_usage(cell, {"prompt_tokens": 1})
    append_usage(cell, {"prompt_tokens": 2})
    lines = (cell / "usage.jsonl").read_text(encoding="utf-8").splitlines()
    assert [json.loads(line) for line in lines] == [
        {"prompt_tokens": 1},
        {"prompt_tokens": 2},
    ]


def test_plan_run_uses_given_base_port_and_template(tmp_path: Path) -> None:
    from openfront_harbor.runner import plan_run

    job = tmp_path / "job.yaml"
    _write_job(job, [1, 2], ["alpha-task"])
    plan = plan_run(
        job, tmp_path, "synthetic", base_port=9200, proxy_url_template=TEMPLATE
    )
    assert plan["run_id"] == "synthetic"
    assert plan["job"] == "synthetic-job"
    assert plan["ports"] == [9200, 9201]
    assert plan["cells"][0]["proxy_base_url"] == "http://proxy.local:9200/api"
    assert plan["cells"][1]["ledger_dir"].endswith("cell-9201")
    assert plan["jobs_dir"] == str(tmp_path / "runs" / "synthetic")
    assert plan["dry_run"][:2] == ["harbor", "run"]
    assert "--jobs-dir" in plan["dry_run"]


def test_example_plan_run_smoke_job(tmp_path: Path) -> None:
    from openfront_harbor import example
    from openfront_harbor.runner import plan_run

    plan = plan_run(
        REPO_ROOT / example.SMOKE_JOB,
        tmp_path,
        "smoke-check",
        base_port=example.BASE_PORT,
        proxy_url_template=example.PROXY_URL_TEMPLATE,
    )
    assert plan["job"] == "live-smoke-openfront-k1"
    assert plan["ports"] == [example.BASE_PORT]
    assert plan["cells"][0]["proxy_base_url"] == (
        f"http://host.docker.internal:{example.BASE_PORT}/v1"
    )


def test_example_plan_run_grid_job(tmp_path: Path) -> None:
    from openfront_harbor import example
    from openfront_harbor.runner import plan_run

    plan = plan_run(
        GRID_JOB,
        tmp_path,
        "grid-check",
        base_port=example.BASE_PORT,
        proxy_url_template=example.PROXY_URL_TEMPLATE,
    )
    assert plan["job"] == "main-grid-openfront"
    assert plan["ports"] == [8801, 8802, 8803]
    assert len(plan["cells"]) == 3


def test_check_ledger_loss_detects_missing_ready(tmp_path: Path) -> None:
    from openfront_harbor.proxy.ledger import append_usage
    from openfront_harbor.reconcile.reconcile import check_ledger_loss, gate_evidence

    runs_dir = tmp_path / "runs"
    run_dir = runs_dir / "r1"
    cell = run_dir / "proxy-ledger" / "cell-9101"
    append_usage(cell, {"prompt_tokens": 1})
    losses = check_ledger_loss(runs_dir, "r1", [9101])
    assert any("ready.json" in loss for loss in losses)
    assert gate_evidence(runs_dir, "r1", [9101]) is False


def test_gate_evidence_passes_when_ledgers_intact(tmp_path: Path) -> None:
    from openfront_harbor.proxy.ledger import append_usage, write_ready
    from openfront_harbor.reconcile.reconcile import gate_evidence

    runs_dir = tmp_path / "runs"
    for port in (9101, 9102):
        cell = runs_dir / "r2" / "proxy-ledger" / f"cell-{port}"
        write_ready(cell, {"token": "t"})
        append_usage(cell, {"prompt_tokens": 1})
    assert gate_evidence(runs_dir, "r2", [9101, 9102]) is True


def test_write_evidence_refuses_overwrite(tmp_path: Path) -> None:
    from openfront_harbor.evidence import write_evidence

    plan = {"run_id": "r1", "job": "synthetic-job", "ports": [9101]}
    checks = {"gate_pass": True, "losses": []}
    out = write_evidence(tmp_path, "r1", plan, checks)
    assert out == tmp_path / "r1" / "summary.json"
    summary = json.loads(out.read_text(encoding="utf-8"))
    assert summary["run_id"] == "r1"
    assert summary["job"] == "synthetic-job"
    assert summary["ports"] == [9101]
    assert summary["gate_pass"] is True
    with pytest.raises(FileExistsError):
        write_evidence(tmp_path, "r1", plan, checks)


def test_cli_plan_reconcile_evidence_help_exit_zero() -> None:
    from openfront_harbor.cli import main

    for args in (["plan", "--help"], ["reconcile", "--help"], ["evidence", "--help"]):
        with pytest.raises(SystemExit) as excinfo:
            main(args)
        assert excinfo.value.code == 0


def test_cli_evidence_requires_gate_pass(tmp_path: Path) -> None:
    from openfront_harbor.cli import main

    rc = main(["evidence", "--evidence-dir", str(tmp_path), "--run-id", "r9-no-gate"])
    assert rc == 1
    assert not (tmp_path / "r9-no-gate").exists()
