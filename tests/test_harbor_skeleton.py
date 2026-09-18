"""Keyless unit checks for the T3 harbor skeleton (no docker, no network)."""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def test_preflight_passes_on_skeleton() -> None:
    from openfront_harbor.reconcile.preflight import run_preflight

    assert run_preflight(REPO_ROOT) == []


def test_load_job_yaml_parses_smoke_job_name() -> None:
    from openfront_harbor.config.job_spec import load_job_yaml

    spec = load_job_yaml(REPO_ROOT / "jobs/tests/live-smoke-openfront-k1.yaml")
    assert spec.job_name == "live-smoke-openfront-k1"
    assert spec.n_attempts == 1
    assert "plains-smoke" in spec.datasets
    assert 8801 in spec.ports


def test_cache_dir_and_is_complete_tmp(tmp_path: Path) -> None:
    from openfront_harbor.execution.docker_extract import cache_dir, is_complete

    entry = cache_dir(tmp_path, "sha256:abc123")
    assert entry == tmp_path / ".cache" / "harness" / "abc123"
    assert not is_complete(entry)
    entry.mkdir(parents=True)
    assert not is_complete(entry)
    (entry / ".complete").write_text("", encoding="utf-8")
    assert is_complete(entry)


def test_cli_help_exits_zero() -> None:
    import pytest

    from openfront_harbor.cli import main

    with pytest.raises(SystemExit) as excinfo:
        main(["--help"])
    assert excinfo.value.code == 0


def test_cli_preflight_exits_zero() -> None:
    from openfront_harbor.cli import main

    assert main(["preflight", "--repo-root", str(REPO_ROOT)]) == 0


def test_task_files_exist() -> None:
    for rel in [
        "tasks/plains-smoke/task.toml",
        "tasks/plains-smoke/environment/Dockerfile",
        "tasks/plains-smoke/instruction.md",
        "tasks/plains-smoke/tests/test.sh",
        "jobs/tests/live-smoke-openfront-k1.yaml",
        "config/pinned-images-amd64-native.toml",
    ]:
        assert (REPO_ROOT / rel).is_file(), f"missing {rel}"
