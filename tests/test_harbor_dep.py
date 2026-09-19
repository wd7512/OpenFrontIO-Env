"""Keyless gate for the Python 3.12 + harbor dependency alignment (T2)."""

from __future__ import annotations

import importlib.metadata
import sys
import tomllib
from pathlib import Path


def test_python_requires_312() -> None:
    assert sys.version_info >= (3, 12)


def test_harbor_version_pinned() -> None:
    assert importlib.metadata.version("harbor").startswith("0.21")


def test_pyproject_requires_python_312() -> None:
    pyproject = Path(__file__).resolve().parents[1] / "pyproject.toml"
    with pyproject.open("rb") as fh:
        data = tomllib.load(fh)
    assert "3.12" in data["project"]["requires-python"]
