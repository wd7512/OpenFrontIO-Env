"""Fixed-spawn registry loading and validation.

``config/spawns/<map>.json`` pins the N spawn tiles every candidate plays
from, so scores are comparable across iterations. The file is hashed into
the evaluation manifest.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Spawn:
    id: str
    x: int
    y: int


@dataclass(frozen=True)
class SpawnRegistry:
    map: str
    spawns: tuple[Spawn, ...]
    sha256: str
    raw: dict[str, object]


class SpawnError(ValueError):
    """The spawn registry is missing or malformed."""


def load_registry(path: Path) -> SpawnRegistry:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as error:
        raise SpawnError(f"cannot read spawn registry {path}: {error}") from error
    try:
        data = json.loads(text)
    except json.JSONDecodeError as error:
        raise SpawnError(f"spawn registry is not valid JSON: {error}") from error
    if not isinstance(data, dict):
        raise SpawnError("spawn registry must be a JSON object")
    name = data.get("map")
    if not isinstance(name, str) or not name:
        raise SpawnError("spawn registry needs a non-empty 'map' string")
    entries = data.get("spawns")
    if not isinstance(entries, list) or not entries:
        raise SpawnError("spawn registry needs a non-empty 'spawns' list")
    spawns: list[Spawn] = []
    seen: set[str] = set()
    for entry in entries:
        if not isinstance(entry, dict):
            raise SpawnError(f"spawn entry must be an object: {entry!r}")
        sid = entry.get("id")
        x, y = entry.get("x"), entry.get("y")
        if not isinstance(sid, str) or not sid or sid in seen:
            raise SpawnError(f"spawn ids must be unique strings: {entry!r}")
        for value in (x, y):
            if isinstance(value, bool) or not isinstance(value, int):
                raise SpawnError(f"spawn coords must be integers: {entry!r}")
        seen.add(sid)
        spawns.append(Spawn(id=sid, x=x, y=y))
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    raw: dict[str, object] = dict(data)
    return SpawnRegistry(map=name, spawns=tuple(spawns), sha256=digest, raw=raw)
