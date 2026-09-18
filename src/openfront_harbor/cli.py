"""Console entry `openfront-harbor` (T3 skeleton + T4 dry-run plan/gates, keyless)."""

from __future__ import annotations

import argparse
import logging
import shutil
import sys
from pathlib import Path

log = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parents[2]


def _parse_ports(raw: str) -> list[int]:
    ports: list[int] = []
    for chunk in raw.split(","):
        chunk = chunk.strip()
        if not chunk:
            continue
        try:
            ports.append(int(chunk))
        except ValueError as exc:
            raise ValueError(f"invalid port {chunk!r} in {raw!r}") from exc
    return ports


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="openfront-harbor",
        description="Keyless harbor skeleton: preflight, dry-run plan, "
        "reconcile gate, evidence summary.",
    )
    sub = parser.add_subparsers(dest="command")
    preflight = sub.add_parser(
        "preflight", help="fail-closed local checks (no network, no keys)"
    )
    preflight.add_argument(
        "--repo-root",
        type=Path,
        default=REPO_ROOT,
        help="repository root to check (default: inferred from install location)",
    )
    plan = sub.add_parser("plan", help="dry-run plan for a job config (no live run)")
    plan.add_argument("--config", type=Path, required=True, help="job YAML to plan")
    plan.add_argument("--jobs-dir", type=Path, required=True, help="base jobs dir")
    plan.add_argument("--run-id", required=True, help="run id for the plan")
    reconcile = sub.add_parser(
        "reconcile", help="ledger-loss gate for a run (no network, no keys)"
    )
    reconcile.add_argument("--runs-dir", type=Path, required=True, help="runs dir")
    reconcile.add_argument("--run-id", required=True, help="run id to gate")
    reconcile.add_argument(
        "--ports", required=True, help="expected cell ports, comma-separated"
    )
    evidence = sub.add_parser(
        "evidence", help="write evidence summary (requires --gate-pass)"
    )
    evidence.add_argument(
        "--evidence-dir", type=Path, required=True, help="base evidence dir"
    )
    evidence.add_argument("--run-id", required=True, help="run id for the summary")
    evidence.add_argument(
        "--gate-pass",
        action="store_true",
        help="confirm the reconcile gate passed (required)",
    )
    evidence.add_argument("--job", default="", help="job name recorded in summary")
    evidence.add_argument(
        "--ports", default="", help="cell ports recorded, comma-separated"
    )
    return parser


def _run_preflight(repo_root: Path) -> int:
    from openfront_harbor.reconcile.preflight import run_preflight

    errors = run_preflight(repo_root)
    if shutil.which("docker") is None:
        # Warn-only in T3: docker presence is not required for unit checks.
        log.warning("docker CLI not found on PATH (warn-only in T3 skeleton)")
    # .env.local is explicitly NOT required in the keyless skeleton.
    if errors:
        for line in errors:
            log.error("preflight: %s", line)
        return 1
    log.info("openfront-harbor preflight ok")
    return 0


def _run_reconcile(args: argparse.Namespace) -> int:
    from openfront_harbor.reconcile.reconcile import gate_evidence

    try:
        ports = _parse_ports(args.ports)
    except ValueError as exc:
        log.error("reconcile: %s", exc)
        return 1
    if gate_evidence(Path(args.runs_dir), args.run_id, ports):
        log.info("reconcile gate PASS for run %s", args.run_id)
        return 0
    log.error("reconcile gate FAIL for run %s", args.run_id)
    return 1


def _run_evidence(args: argparse.Namespace) -> int:
    from openfront_harbor.evidence import write_evidence

    if not args.gate_pass:
        log.error("evidence requires --gate-pass (reconcile gate must pass first)")
        return 1
    try:
        ports = _parse_ports(args.ports)
    except ValueError as exc:
        log.error("evidence: %s", exc)
        return 1
    plan = {"run_id": args.run_id, "job": args.job or args.run_id, "ports": ports}
    checks = {"gate_pass": True, "losses": []}
    try:
        out = write_evidence(Path(args.evidence_dir), args.run_id, plan, checks)
    except (FileExistsError, OSError) as exc:
        log.error("evidence: %s", exc)
        return 1
    log.info("evidence summary written to %s", out)
    return 0


def main(argv: list[str] | None = None) -> int:
    """Entry point for the `openfront-harbor` console script."""
    logging.basicConfig(
        level=logging.INFO, format="%(levelname)s %(name)s: %(message)s"
    )
    parser = _build_parser()
    args = parser.parse_args(argv)
    if args.command == "preflight":
        return _run_preflight(Path(args.repo_root))
    if args.command == "plan":
        from openfront_harbor.runner import run_dry

        return run_dry(args)
    if args.command == "reconcile":
        return _run_reconcile(args)
    if args.command == "evidence":
        return _run_evidence(args)
    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
