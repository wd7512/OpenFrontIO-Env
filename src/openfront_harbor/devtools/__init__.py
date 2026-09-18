"""Developer-tooling checks for repo hygiene.

Checks live in their own modules — ``worklog.check_worklog``,
``test_names.check_test_names``, and ``char_encoding.check_char_encoding`` —
and this module is the single entry point wired through the CLI:
``run_checks`` (and ``main`` for the ``openfront-harbor dev-tools``
command).  Everything is pure and stdlib-only; checks return violation
strings (empty = clean).

The test-layout check from the sibling harness is deliberately not ported:
``tests/`` here is a flat tree that does not mirror ``src/``, so a mirror
check would demand a test-tree migration first.
"""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

from openfront_harbor.devtools.char_encoding import check_char_encoding
from openfront_harbor.devtools.test_names import check_test_names
from openfront_harbor.devtools.worklog import check_worklog

logger = logging.getLogger(__name__)

__all__ = [
    "check_char_encoding",
    "check_test_names",
    "check_worklog",
    "main",
    "run_checks",
]

_VALID_CHECKS = frozenset({"worklog", "test-names", "char-encoding"})
_DEFAULT_CHECKS = "worklog,test-names,char-encoding"


def _validate_checks(checks: str) -> list[str] | None:
    """Parse and validate the ``--checks`` value.

    Returns the split parts, or ``None`` if invalid (error already logged).
    """
    parts = [s.strip() for s in checks.split(",")]
    invalid = [s for s in parts if s not in _VALID_CHECKS]
    if invalid:
        logger.error("invalid --checks value(s): %s", ", ".join(invalid))
        return None
    return parts


def _collect_violations(
    repo_root: Path,
    tests_dir: Path,
    worklog: Path,
    parts: list[str],
) -> list[str]:
    """Run the selected subset of checks and return all violations."""
    violations: list[str] = []
    if "worklog" in parts:
        violations.extend(check_worklog(worklog))
    if "test-names" in parts:
        violations.extend(check_test_names(tests_dir))
    if "char-encoding" in parts:
        violations.extend(check_char_encoding(repo_root))
    return violations


def _log_and_code(violations: list[str]) -> int:
    """Log each violation as an error; return 1, or 0 with an info line if clean."""
    for v in violations:
        logger.error("%s", v)
    if violations:
        return 1
    logger.info("all checks passed")
    return 0


def run_checks(
    repo_root: Path,
    tests_dir: Path,
    worklog: Path,
    checks: str,
) -> int:
    """Run the selected subset of hygiene checks.

    Returns 0 if clean, 1 if any violation, 2 on invalid ``checks`` value.
    """
    parts = _validate_checks(checks)
    if parts is None:
        return 2
    return _log_and_code(_collect_violations(repo_root, tests_dir, worklog, parts))


def main(argv: list[str] | None = None) -> int:
    """Entry point for ``openfront-harbor dev-tools``."""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    parser = argparse.ArgumentParser(prog="openfront-harbor dev-tools")
    sub = parser.add_subparsers(dest="devtools_command", required=True)
    check = sub.add_parser(
        "check",
        help="verify repo hygiene: worklog, test names, character encoding",
    )
    check.add_argument(
        "--checks",
        default=_DEFAULT_CHECKS,
        help=f"comma-separated subset: {_DEFAULT_CHECKS}",
    )
    check.add_argument("--worklog", type=Path, default=Path("WORKLOG.md"))
    check.add_argument("--tests-dir", type=Path, default=Path("tests"))
    check.add_argument("--repo-root", type=Path, default=Path("."))
    args = parser.parse_args(argv)

    if args.devtools_command != "check":  # pragma: no cover — argparse enforces
        return 2
    return run_checks(
        repo_root=args.repo_root,
        tests_dir=args.tests_dir,
        worklog=args.worklog,
        checks=args.checks,
    )
