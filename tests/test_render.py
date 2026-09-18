"""Capture + render tests: grids land per decision, GIF builds from frames."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from typing import Any

from openfrontbench.engine import EngineWorker, PLAINS_MAP_DIR
from openfrontbench.session import GameSession


def test_capture_writes_one_frame_per_decision(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("OPENFRONT_GRID_DIR", str(tmp_path))
    session = GameSession()
    session.start(nations=1, difficulty="easy", map="plains", tribes=0)
    try:
        session.end_decision(1)
        session.end_decision(2)
    finally:
        session.close()
    lines = (tmp_path / "grids.jsonl").read_text().splitlines()
    assert len(lines) == 2
    first = json.loads(lines[0])
    assert first["decision"] == 1
    assert first["cols"] * first["rows"] > 0
    assert "legend" in first and "nations" in first


def test_no_capture_without_env(monkeypatch, tmp_path) -> None:
    monkeypatch.delenv("OPENFRONT_GRID_DIR", raising=False)
    session = GameSession()
    session.start(nations=1, difficulty="easy", map="plains", tribes=0)
    try:
        session.end_decision(1)
    finally:
        session.close()
    assert not (tmp_path / "grids.jsonl").exists()


def _render_mod() -> Any:
    path = Path(__file__).resolve().parent.parent / "scripts" / "render_timelapse.py"
    spec = importlib.util.spec_from_file_location("render_timelapse", path)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_render_builds_gif(tmp_path) -> None:
    mod = _render_mod()
    frame: dict = {}
    with EngineWorker(map_dir=PLAINS_MAP_DIR) as engine:
        engine.start(
            nations=1, difficulty="easy", map_size="full", spawn=None, tribes=0
        )
        engine.advance(60)
        engine.attack("expand", 20000)
        engine.advance(50)
        frame = engine.grid(step=12)
    frame["decision"] = 1
    (tmp_path / "grids.jsonl").write_text(json.dumps(frame) + "\n" + json.dumps(frame))
    flat = mod.decode_cells(frame["cells"], frame["cols"], frame["rows"])
    assert len(flat) == frame["cols"] * frame["rows"]
    palette = mod.palette_for(frame["legend"], frame["nations"])
    assert set(frame["legend"]) <= set(palette)
    images, summary = mod.render_frames(tmp_path)
    assert len(images) == 2
    out = tmp_path / "game.gif"
    images[0].save(out, save_all=True, append_images=images[1:], duration=400, loop=0)
    assert out.stat().st_size > 0
    assert summary["frames"] == 2
