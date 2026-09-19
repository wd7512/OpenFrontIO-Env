"""Ownership-grid parity at engine level: coarse map snapshots for rendering.

The worker exposes a downsampled ownership grid (water / unowned land /
human / tribe / per-nation classes) with run-length encoding, plus a
nation legend. One frame is tens of KB — cheap enough to capture every
decision and render a timelapse afterwards.
"""

from __future__ import annotations

import pytest

from openfrontbench.engine import (
    BRITANNIA_MAP_DIR,
    EngineError,
    EngineWorker,
)


def _start(engine: EngineWorker, **kwargs):
    params = {
        "nations": 1,
        "difficulty": "easy",
        "map_size": "compact",
        "spawn": None,
        "tribes": 0,
    }
    params.update(kwargs)
    return engine.start(**params)


def test_grid_dims_and_legend() -> None:
    with EngineWorker(map_dir=BRITANNIA_MAP_DIR) as engine:
        _start(engine)
        grid = engine.grid(step=12)
        assert grid["cols"] > 0 and grid["rows"] > 0
        assert grid["step"] == 12
        assert len(grid["nations"]) == 1
        assert grid["nations"][0]["name"]
        # Legend maps every nation char back to its raw player id.
        raw_id = grid["nations"][0]["id"]
        assert raw_id in grid["legend"].values()


def test_grid_cells_decode_and_hold_human() -> None:
    with EngineWorker(map_dir=BRITANNIA_MAP_DIR) as engine:
        _start(engine)
        # Spawn is 52 tiles — sub-sample at step 12. Clear spawn immunity,
        # expand once, so human land must cover sampled cells.
        engine.advance(60)
        engine.attack("expand", 20000)
        engine.advance(50)
        grid = engine.grid(step=12)
        cells = grid["cells"]
        assert isinstance(cells, str) and len(cells) > 0
        # RLE round-trip: decode length must equal cols * rows.
        legend = grid["legend"]
        count = 0
        i = 0
        while i < len(cells):
            char = cells[i]
            assert char in legend, char
            i += 1
            digits = ""
            while i < len(cells) and cells[i].isdigit():
                digits += cells[i]
                i += 1
            count += int(digits) if digits else 1
        assert count == grid["cols"] * grid["rows"]
        # Human holds land at spawn: class "H" must appear.
        assert "H" in legend.values() or "H" in set(
            cells[i] for i in range(len(cells)) if not cells[i].isdigit()
        )


def test_grid_bad_step_rejected() -> None:
    with EngineWorker(map_dir=BRITANNIA_MAP_DIR) as engine:
        _start(engine)
        with pytest.raises(EngineError):
            engine.grid(step=0)
