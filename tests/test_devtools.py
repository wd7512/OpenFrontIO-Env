"""Tests for the dev-tools hygiene checks (worklog, test names, encoding)."""

from __future__ import annotations

from pathlib import Path

from openfront_harbor.cli import main as harbor_main
from openfront_harbor.devtools import run_checks
from openfront_harbor.devtools.char_encoding import check_char_encoding
from openfront_harbor.devtools.test_names import check_test_names
from openfront_harbor.devtools.worklog import check_worklog

_CLEAN_WORKLOG = "# Title\n\n## 2026-09-18 — did a thing\n\n- detail\n"


def _write(path: Path, text: str) -> Path:
    path.write_text(text, encoding="utf-8")
    return path


def test_worklog_rules(tmp_path: Path) -> None:
    assert check_worklog(_write(tmp_path / "w.md", _CLEAN_WORKLOG)) == []
    missing = _write(tmp_path / "m.md", "## 2026-09-18 — no title\n")
    assert any("title" in v for v in check_worklog(missing))
    early = _write(tmp_path / "e.md", "# T\n\n- stray\n\n## 2026-09-18 — x\n")
    assert any("before the first entry" in v for v in check_worklog(early))
    rising = _write(
        tmp_path / "r.md", "# T\n\n## 2026-09-18 — b\n\n## 2026-09-19 — a\n"
    )
    assert any("non-increasing" in v for v in check_worklog(rising))
    bad_head = _write(tmp_path / "h.md", "# T\n\n## someday — x\n")
    assert any("malformed entry header" in v for v in check_worklog(bad_head))


def test_test_names_duplicates(tmp_path: Path) -> None:
    tests = tmp_path / "tests"
    tests.mkdir()
    _write(tests / "test_a.py", "def test_same():\n    pass\n")
    assert check_test_names(tests) == []
    _write(tests / "test_b.py", "def test_same():\n    pass\ndef helper():\n    pass\n")
    violations = check_test_names(tests)
    assert len(violations) == 1 and "test_same" in violations[0]


def test_char_encoding_flags(tmp_path: Path) -> None:
    _write(tmp_path / "ok.py", "x = 1\n")
    _write(tmp_path / "pyproject.toml", "[project]\nname = 'x'\n")
    assert check_char_encoding(tmp_path) == []
    _write(tmp_path / "bad.md", "# hi \U0001f600\n")
    assert any("U+1F600" in v for v in check_char_encoding(tmp_path))


def _clean_tree(tmp_path: Path) -> tuple[Path, Path, Path]:
    worklog = _write(tmp_path / "WORKLOG.md", _CLEAN_WORKLOG)
    tests = tmp_path / "tests"
    tests.mkdir()
    _write(tests / "test_a.py", "def test_devtools_fixture_probe():\n    pass\n")
    return tmp_path, tests, worklog


def test_run_checks_dispatch(tmp_path: Path) -> None:
    root, tests, worklog = _clean_tree(tmp_path)
    assert run_checks(root, tests, worklog, "worklog,test-names,char-encoding") == 0
    assert run_checks(root, tests, worklog, "nope") == 2
    _write(tests / "test_b.py", "def test_devtools_fixture_probe():\n    pass\n")
    assert run_checks(root, tests, worklog, "test-names") == 1


def test_cli_dev_tools(tmp_path: Path) -> None:
    root, tests, worklog = _clean_tree(tmp_path)
    rc = harbor_main(
        [
            "dev-tools",
            "check",
            "--repo-root",
            str(root),
            "--tests-dir",
            str(tests),
            "--worklog",
            str(worklog),
        ]
    )
    assert rc == 0
