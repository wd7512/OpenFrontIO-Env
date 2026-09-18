"""Digest-keyed harness cache path helpers (T3, pure functions only)."""

from __future__ import annotations

from pathlib import Path

COMPLETE_MARKER = ".complete"


def cache_dir(repo_root: Path, digest: str) -> Path:
    """Return the cache directory for one image digest (no I/O)."""
    safe = digest.replace("sha256:", "").replace(":", "_").strip()
    return Path(repo_root) / ".cache" / "harness" / safe


def is_complete(entry: Path) -> bool:
    """Return True when a cache entry has its completion marker."""
    return (Path(entry) / COMPLETE_MARKER).is_file()
