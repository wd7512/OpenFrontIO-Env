"""Worklog hygiene check — format and ordering rules for ``WORKLOG.md``.

Pure and stdlib-only; ``check_worklog`` returns violation strings
(empty list = clean).

The worklog shape is::

    # OpenFrontBench worklog

    ## 2026-09-18 — entry title

    - detail bullet
    - detail bullet

Rules enforced:

* The first non-blank line must start with ``# `` (the title).
* Entries are ``## <YYYY-MM-DD> — <title>`` headers at column 0.
* Entry dates must be non-increasing (newest first).
* ``- `` bullets are allowed, but only after the first entry header.
* Indented lines (continuations) are ignored.
* Any other column-0 line is a violation (unexpected header or prose).
"""

from __future__ import annotations

import datetime
import re
from collections.abc import Iterator
from pathlib import Path

_DATE_RE: re.Pattern[str] = re.compile(r"^## (\d{4}-\d{2}-\d{2})\b")
_BULLET_PREFIX = "- "


def _validate_title(lines: list[str]) -> list[str]:
    """Return a violation if the first non-blank line is not a ``# `` title."""
    for line in lines:
        if line.strip():
            if line.startswith("# "):
                return []
            return ["first non-blank line must start with '# ' (title)"]
    return ["file is empty — missing title line"]


def _significant_lines(lines: list[str]) -> Iterator[tuple[int, str]]:
    """Yield ``(line_no, line)`` for non-blank, non-indented lines, skipping the title.

    The title (first significant line) is validated separately by
    ``_validate_title`` and is exempt from the entry rules.
    """
    seen_first = False
    for line_no, line in enumerate(lines, start=1):
        if not line.strip():
            continue
        if line[0] in (" ", "\t"):
            continue
        if not seen_first:
            seen_first = True
            continue
        yield line_no, line


def _validate_entry_date(
    line: str,
    line_no: int,
    prev_date: datetime.date | None,
    prev_date_line: int | None,
) -> tuple[list[str], datetime.date | None, int | None]:
    """Validate one ``## <date> ...`` header line."""
    violations: list[str] = []
    date_match = _DATE_RE.match(line)
    if date_match is None:
        violations.append(
            f"line {line_no}: malformed entry header (expected '## <date>')"
        )
        return violations, prev_date, prev_date_line

    date_str = date_match.group(1)
    try:
        entry_date = datetime.datetime.strptime(date_str, "%Y-%m-%d").date()
    except ValueError:
        violations.append(f"line {line_no}: invalid calendar date '{date_str}'")
        return violations, prev_date, prev_date_line

    if prev_date is not None and entry_date > prev_date:
        violations.append(
            f"line {line_no}: date {date_str} is newer than "
            f"line {prev_date_line} date {prev_date.isoformat()} "
            f"(must be non-increasing)"
        )

    return violations, entry_date, line_no


def _check_line(
    line: str,
    line_no: int,
    seen_entry: bool,
    prev_date: datetime.date | None,
    prev_date_line: int | None,
) -> tuple[list[str], bool, datetime.date | None, int | None]:
    """Classify and validate one non-blank, non-indented line."""
    if line.startswith("## "):
        ev, new_prev, new_line = _validate_entry_date(
            line, line_no, prev_date, prev_date_line
        )
        return ev, True, new_prev, new_line

    if line.startswith(_BULLET_PREFIX):
        if not seen_entry:
            return (
                [f"line {line_no}: bullet before the first entry header"],
                seen_entry,
                prev_date,
                prev_date_line,
            )
        return [], seen_entry, prev_date, prev_date_line

    return (
        [f"line {line_no}: prose or unexpected header (expected '## <date>' or '- ')"],
        seen_entry,
        prev_date,
        prev_date_line,
    )


def check_worklog(path: Path) -> list[str]:
    """Return violation strings for *path* (empty list = clean)."""
    lines = path.read_text(encoding="utf-8").splitlines()

    title_violations = _validate_title(lines)
    if title_violations:
        return title_violations

    seen_entry = False
    prev_date: datetime.date | None = None
    prev_date_line: int | None = None
    violations: list[str] = []

    for line_no, line in _significant_lines(lines):
        ev, seen_entry, prev_date, prev_date_line = _check_line(
            line, line_no, seen_entry, prev_date, prev_date_line
        )
        violations.extend(ev)

    return violations
