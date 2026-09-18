"""Minimal JobSpec for a keyless harbor job config."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

log = logging.getLogger(__name__)

_JOB_NAME_RE = re.compile(r"[A-Za-z0-9_.-]+")


@dataclass(frozen=True)
class JobSpec:
    """Boring subset of a harbor job config used by the runner gates."""

    job_name: str
    n_attempts: int = 1
    image_manifest: dict[str, Any] = field(default_factory=dict)
    datasets: tuple[str, ...] = ()
    ports: tuple[int, ...] = ()


def _regex_fallback(text: str) -> JobSpec:
    """Tiny parser for the known keys when pyyaml is unavailable."""
    name_match = re.search(r"^job_name\s*:\s*(\S+)", text, re.MULTILINE)
    attempts_match = re.search(r"^n_attempts\s*:\s*(\d+)", text, re.MULTILINE)
    job_name = name_match.group(1).strip().strip("\"'") if name_match else "unknown"
    n_attempts = int(attempts_match.group(1)) if attempts_match else 1
    ports = tuple(
        int(m.group(1)) for m in re.finditer(r"proxy_base_url\s*:\s*\S+:(\d+)", text)
    )
    tasks = tuple(
        m.group(1).strip()
        for line in text.splitlines()
        if (m := re.match(r"\s*-\s*([A-Za-z0-9_][A-Za-z0-9_.\-/]*)\s*$", line))
    )
    log.warning("pyyaml unavailable; used regex fallback for job config")
    return JobSpec(
        job_name=job_name,
        n_attempts=n_attempts,
        image_manifest={},
        datasets=tasks,
        ports=ports,
    )


def _extract_datasets(data: dict[str, Any]) -> tuple[str, ...]:
    names: list[str] = []
    datasets = data.get("datasets", []) or []
    if not isinstance(datasets, list):
        return ()
    for dataset in datasets:
        if not isinstance(dataset, dict):
            continue
        task_names = dataset.get("task_names")
        if isinstance(task_names, list):
            names.extend(str(n) for n in task_names)
        elif dataset.get("name"):
            names.append(str(dataset["name"]))
    return tuple(names)


def _extract_ports(data: dict[str, Any]) -> tuple[int, ...]:
    ports: list[int] = []
    agents = data.get("agents", []) or []
    if not isinstance(agents, list):
        return ()
    for agent in agents:
        if not isinstance(agent, dict):
            continue
        kwargs = agent.get("kwargs", {}) or {}
        if not isinstance(kwargs, dict):
            continue
        raw_url = kwargs.get("proxy_base_url")
        if not raw_url:
            continue
        try:
            parsed = urlparse(str(raw_url))
        except ValueError:
            continue
        if parsed.port is not None:
            ports.append(parsed.port)
    return tuple(ports)


def load_job_yaml(path: Path) -> JobSpec:
    """Parse a minimal harbor job YAML file into a JobSpec."""
    text = Path(path).read_text(encoding="utf-8")
    try:
        import yaml  # type: ignore[import-not-found]
    except ImportError:
        return _regex_fallback(text)
    try:
        data = yaml.safe_load(text)
    except Exception as exc:
        raise ValueError(f"could not parse job yaml {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError(f"job config {path} must contain a YAML mapping")
    job_name = str(data.get("job_name") or Path(path).stem)
    if not _JOB_NAME_RE.fullmatch(job_name):
        raise ValueError(f"invalid job_name: {job_name!r}")
    raw_attempts = data.get("n_attempts", 1) or 1
    if isinstance(raw_attempts, bool) or not isinstance(raw_attempts, int):
        raise ValueError(f"n_attempts must be an integer in {path}")
    if raw_attempts < 1:
        raise ValueError(f"n_attempts must be >= 1 in {path}")
    manifest_raw = data.get("image_manifest", {}) or {}
    image_manifest: dict[str, Any] = (
        dict(manifest_raw)
        if isinstance(manifest_raw, dict)
        else {"path": str(manifest_raw)}
    )
    return JobSpec(
        job_name=job_name,
        n_attempts=raw_attempts,
        image_manifest=image_manifest,
        datasets=_extract_datasets(data),
        ports=_extract_ports(data),
    )
