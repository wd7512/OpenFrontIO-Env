"""Diary — persistent agent memory as JSONL, one entry per line."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Mapping

log = logging.getLogger(__name__)


def append_diary(path: str | Path, entry: Mapping[str, object]) -> None:
    diary = Path(path)
    with diary.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry) + "\n")
    log.debug("diary append %s fields=%d", diary, len(entry))


def read_diary(path: str | Path) -> list[dict[str, object]]:
    diary = Path(path)
    if not diary.exists():
        return []
    entries: list[dict[str, object]] = []
    with diary.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                entries.append(json.loads(line))
    return entries
