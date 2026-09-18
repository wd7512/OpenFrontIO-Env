from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _read(name: str) -> str:
    return (ROOT / name).read_text(encoding="utf-8")


def test_ci_guarded_docker_skeleton() -> None:
    text = _read(".github/workflows/ci.yml")
    assert "build-openfront.sh --dry-run" in text
    assert "if [ -f" in text


def test_ci_guarded_harbor_preflight() -> None:
    text = _read(".github/workflows/ci.yml")
    assert "openfront-harbor preflight" in text
    assert "if [ -f" in text


def test_ci_guarded_lit_review() -> None:
    text = _read(".github/workflows/ci.yml")
    assert "test_lit_" in text
    assert "if [ -f" in text


def test_opencode_valid_json() -> None:
    text = _read("opencode.json")
    json.loads(text)


def test_readme_overhaul_tracks() -> None:
    text = _read("README.md")
    assert "3.12" in text
    assert "Overhaul tracks" in text


def test_ledger_branches_and_order() -> None:
    path = ROOT / "docs/overhaul-integration.md"
    assert path.is_file()
    text = path.read_text(encoding="utf-8")
    for branch in ("docker-base", "harbor-skeleton", "lit-review"):
        assert branch in text
    assert "Merge order" in text or "merge order" in text.lower()


def test_agents_mentions_tracks() -> None:
    text = _read("AGENTS.md")
    assert "openfront-harbor" in text
    assert "lit-review" in text
