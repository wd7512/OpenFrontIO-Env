"""Fail-closed preflight checks (keyless).

No network, no docker pull, no API keys. Returns error strings; empty means
pass. All expectations arrive as explicit inputs — see ``example.py`` for
the single worked example.
"""

from __future__ import annotations

import importlib.metadata
import logging
from collections.abc import Sequence
from pathlib import Path

log = logging.getLogger(__name__)


def run_preflight(
    repo_root: Path | str,
    *,
    expected_harbor_version: str | None = None,
    required_files: Sequence[str | Path] = (),
) -> list[str]:
    """Check the local layout without touching network or docker."""
    root = Path(repo_root)
    errors: list[str] = []

    try:
        version = importlib.metadata.version("harbor")
    except importlib.metadata.PackageNotFoundError:
        errors.append("harbor package not installed; run `uv sync --dev`")
        version = ""
    if version and expected_harbor_version and version != expected_harbor_version:
        errors.append(
            f"harbor version {version!r} != expected {expected_harbor_version!r}"
        )

    for rel in required_files:
        candidate = root / rel
        if not candidate.is_file():
            errors.append(f"required file missing: {rel}")
        elif candidate.stat().st_size == 0:
            errors.append(f"required file is empty: {rel}")

    if errors:
        log.error("preflight found %d issue(s)", len(errors))
    else:
        log.info("preflight checks passed")
    return errors
