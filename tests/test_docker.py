"""Keyless file-content checks for the reproducible Docker base (T1).

No Docker daemon is required: these tests assert on file presence and
content only. Live `docker build` / `docker run` verification is a manual
step covered by docs/docker-runbook.md.
"""

from __future__ import annotations

import os
import stat
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DOCKERFILE = REPO_ROOT / "docker" / "openfront" / "Dockerfile"
BUILD_SCRIPT = REPO_ROOT / "scripts" / "build-openfront.sh"
RUNBOOK = REPO_ROOT / "docs" / "docker-runbook.md"


def _read(path: Path) -> str:
    assert path.is_file(), f"expected file at {path}"
    return path.read_text(encoding="utf-8")


def test_dockerfile_base_and_engine_build() -> None:
    text = _read(DOCKERFILE)
    assert "python:3.12" in text
    assert "engine/dist/worker.mjs" in text or "npm run build" in text


def test_dockerfile_bakes_in_no_secrets() -> None:
    text = _read(DOCKERFILE)
    assert "COPY .env" not in text
    assert "OPENCODE_GO_API_KEY" not in text
    assert "API_KEY" not in text


def test_build_script_guards() -> None:
    text = _read(BUILD_SCRIPT)
    assert "buildx" in text
    assert "--platform linux/amd64" in text
    assert "docker inspect" in text
    assert "--push" not in text


def test_build_script_is_executable() -> None:
    assert os.access(BUILD_SCRIPT, os.X_OK), f"not executable: {BUILD_SCRIPT}"
    mode = BUILD_SCRIPT.stat().st_mode
    assert mode & (stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def test_runbook_covers_build_and_pins() -> None:
    text = _read(RUNBOOK)
    assert "build-openfront.sh" in text
    assert "vendor pin" in text or "pins.md" in text
