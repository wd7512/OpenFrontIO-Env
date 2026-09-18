"""Fail-closed preflight checks for the harbor skeleton (T3, keyless).

No network, no docker pull, no API keys. Returns error strings; empty means pass.
"""

from __future__ import annotations

import importlib.metadata
import logging
from pathlib import Path

log = logging.getLogger(__name__)

EXPECTED_HARBOR_VERSION = "0.21.0"
PINNED_TOML_REL = Path("config/pinned-images-amd64-native.toml")
SMOKE_JOB_REL = Path("jobs/tests/live-smoke-openfront-k1.yaml")
TASK_FILES_REL = (
    Path("tasks/plains-smoke/task.toml"),
    Path("tasks/plains-smoke/environment/Dockerfile"),
    Path("tasks/plains-smoke/instruction.md"),
    Path("tasks/plains-smoke/tests/test.sh"),
)


def run_preflight(repo_root: Path) -> list[str]:
    """Check the local skeleton layout without touching network or docker."""
    root = Path(repo_root)
    errors: list[str] = []

    try:
        version = importlib.metadata.version("harbor")
    except importlib.metadata.PackageNotFoundError:
        errors.append("harbor package not installed; run `uv sync --dev`")
        version = ""
    if version and version != EXPECTED_HARBOR_VERSION:
        errors.append(
            f"harbor version {version!r} != expected {EXPECTED_HARBOR_VERSION!r}"
        )

    pinned = root / PINNED_TOML_REL
    if not pinned.is_file():
        errors.append(f"pinned-images toml missing: {PINNED_TOML_REL}")
    elif pinned.stat().st_size == 0:
        errors.append(f"pinned-images toml is empty: {PINNED_TOML_REL}")

    for rel in TASK_FILES_REL:
        if not (root / rel).is_file():
            errors.append(f"smoke task file missing: {rel}")

    if not (root / SMOKE_JOB_REL).is_file():
        errors.append(f"smoke job yaml missing: {SMOKE_JOB_REL}")

    if errors:
        log.error("preflight found %d issue(s)", len(errors))
    else:
        log.info("preflight skeleton checks passed")
    return errors
