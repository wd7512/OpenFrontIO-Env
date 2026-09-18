"""Unit checks for the harbor gates: generic process + worked example.

Process tests use synthetic files in tmp_path and arbitrary ports; only
the `example_*` tests touch real repo files. No docker, no network.
"""

from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]


def test_preflight_reports_missing_files(tmp_path: Path) -> None:
    from openfront_harbor.reconcile.preflight import run_preflight

    errors = run_preflight(tmp_path, required_files=["a.txt", "sub/b.txt"])
    assert any("a.txt" in e for e in errors)
    assert any("sub/b.txt" in e for e in errors)
    (tmp_path / "a.txt").write_text("x", encoding="utf-8")
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "b.txt").write_text("", encoding="utf-8")
    errors = run_preflight(tmp_path, required_files=["a.txt", "sub/b.txt"])
    assert any("empty" in e for e in errors)


def test_preflight_checks_expected_version(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import importlib.metadata

    from openfront_harbor.reconcile.preflight import run_preflight

    monkeypatch.setattr(importlib.metadata, "version", lambda _name: "9.9.9")
    errors = run_preflight(tmp_path, expected_harbor_version="0.0.0")
    assert any("9.9.9" in e and "0.0.0" in e for e in errors)
    assert run_preflight(tmp_path, expected_harbor_version="9.9.9") == []


def test_example_preflight_passes_on_repo() -> None:
    from openfront_harbor import example
    from openfront_harbor.reconcile.preflight import run_preflight

    assert (
        run_preflight(
            REPO_ROOT,
            expected_harbor_version=example.EXPECTED_HARBOR_VERSION,
            required_files=example.REQUIRED_FILES,
        )
        == []
    )


def test_example_job_yaml_parses() -> None:
    from openfront_harbor import example
    from openfront_harbor.config.job_spec import load_job_yaml

    spec = load_job_yaml(REPO_ROOT / example.SMOKE_JOB)
    assert spec.job_name == "live-smoke-openfront-k1"
    assert spec.n_attempts == 1
    assert "plains-smoke" in spec.datasets
    assert example.BASE_PORT in spec.ports


def test_load_job_yaml_rejects_bad_name(tmp_path: Path) -> None:
    from openfront_harbor.config.job_spec import load_job_yaml

    bad = tmp_path / "bad.yaml"
    bad.write_text("job_name: 'not a name!'\nn_attempts: 1\n", encoding="utf-8")
    with pytest.raises(ValueError, match="job_name"):
        load_job_yaml(bad)


def test_regex_fallback_parses_generic_tasks(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import sys

    from openfront_harbor.config.job_spec import load_job_yaml

    monkeypatch.setitem(sys.modules, "yaml", None)
    job = tmp_path / "job.yaml"
    job.write_text(
        "job_name: generic-job\n"
        "n_attempts: 2\n"
        "datasets:\n"
        "  - path: tasks\n"
        "    task_names:\n"
        "      - alpha-task\n"
        "      - beta-task\n"
        "agents:\n"
        "  - name: agent-a\n"
        "    kwargs:\n"
        "      proxy_base_url: http://proxy.local:9101/api\n"
        "  - name: agent-b\n"
        "    kwargs:\n"
        "      proxy_base_url: http://proxy.local:9102/api\n",
        encoding="utf-8",
    )
    spec = load_job_yaml(job)
    assert spec.job_name == "generic-job"
    assert spec.n_attempts == 2
    assert spec.datasets == ("alpha-task", "beta-task")
    assert spec.ports == (9101, 9102)


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
    from openfront_harbor.cli import main

    with pytest.raises(SystemExit) as excinfo:
        main(["--help"])
    assert excinfo.value.code == 0


def test_cli_preflight_exits_zero() -> None:
    from openfront_harbor.cli import main

    assert main(["preflight", "--repo-root", str(REPO_ROOT)]) == 0


def test_example_files_exist() -> None:
    from openfront_harbor import example

    for rel in [*example.REQUIRED_FILES, example.SMOKE_JOB]:
        assert (REPO_ROOT / rel).is_file(), f"missing {rel}"
