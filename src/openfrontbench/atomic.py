"""Single authoritative fresh-dir + atomic-write policy.

Lives in ``openfrontbench`` (rather than a neutral package) so it ships
inside the built wheel, which only includes ``src/openfrontbench``.
``openfront_harbor`` reuses it as a leaf primitive — it imports nothing
outside the standard library, so the dependency direction stays flat.

Every track (benchmark episodes, harbor ledgers, evidence summaries, live
smoke artifacts) shares these two ideas:

* Fresh dir: never overwrite an existing output — fail closed.
* Atomic write: tmp file + flush/fsync + ``os.replace`` so readers never
  see a half-written JSON document.

``OutputExistsError`` subclasses both ``FileExistsError`` and ``ValueError``
so existing ``except (FileExistsError, OSError)`` and ``except ValueError``
handlers both keep working.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


class OutputExistsError(FileExistsError, ValueError):
    """An output directory already exists; refusing to overwrite."""


def ensure_fresh_dir(path: Path | str) -> Path:
    """Create *path* (with parents); raise ``OutputExistsError`` if it exists.

    ``OSError`` from ``mkdir`` itself propagates unwrapped so callers can
    map it to their own error type.
    """
    out = Path(path)
    if out.exists():
        raise OutputExistsError(
            f"output path already exists (refusing to overwrite): {out}"
        )
    out.mkdir(parents=True)
    return out


def write_text_atomic(path: Path | str, text: str) -> Path:
    """Write *text* atomically via hidden tmp + flush/fsync + ``os.replace``."""
    out = Path(path)
    tmp = out.with_name(f".{out.name}.tmp")
    with tmp.open("w", encoding="utf-8") as fd:
        fd.write(text)
        fd.flush()
        os.fsync(fd.fileno())
    os.replace(tmp, out)
    return out


def write_json_atomic(path: Path | str, payload: dict[str, Any]) -> Path:
    """Write *payload* as sorted JSON atomically."""
    return write_text_atomic(
        Path(path), json.dumps(payload, indent=2, sort_keys=True) + "\n"
    )
