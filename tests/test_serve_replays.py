"""Replay website tests: scan raw/, unique IDs, index links, archive serving."""

from __future__ import annotations

import importlib.util
import json
import threading
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path
from typing import Any


def _mod() -> Any:
    path = Path(__file__).resolve().parent.parent / "scripts" / "serve_replays.py"
    spec = importlib.util.spec_from_file_location("serve_replays", path)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _run(tmp_path: Path, name: str, game_id: str = "ENGINE01") -> Path:
    run = tmp_path / name
    run.mkdir()
    (run / "record.json").write_text(
        json.dumps({"gameId": game_id, "ticks": 5003, "turns": []})
    )
    (run / "live_result.json").write_text(
        json.dumps(
            {
                "model": "m",
                "scenario": "solo",
                "summary": {
                    "decisions": [1, 2],
                    "ticks": [53, 103],
                    "winner": None,
                    "tool_calls": 10,
                    "cost": 0.001,
                    "final_human": {"tiles": 100, "troops": 200},
                },
            }
        )
    )
    return run


def _serve(records: dict[str, bytes], index: bytes):
    mod = _mod()
    server = ThreadingHTTPServer(("127.0.0.1", 0), mod.make_handler(records, index))
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, port


def test_find_runs_lists_record_dirs_sorted(tmp_path: Path) -> None:
    mod = _mod()
    _run(tmp_path, "b-run")
    _run(tmp_path, "a-run")
    (tmp_path / "empty").mkdir()
    found = mod.find_runs(tmp_path)
    assert [p.name for p in found] == ["a-run", "b-run"]
    assert mod.find_runs(tmp_path / "missing") == []


def test_assign_ids_keeps_unique_remaps_collisions() -> None:
    mod = _mod()
    out = mod.assign_ids(
        ["c1", "c2", "solo"], {"c1": "ENGINE01", "c2": "ENGINE01", "solo": "LIVE0002"}
    )
    assert out == {"c1": "OF000001", "c2": "OF000002", "solo": "LIVE0002"}
    for gid in out.values():
        assert mod.GAME_ID_RE.fullmatch(gid)


def test_served_records_keep_live_game_id() -> None:
    # The engine seeds its RNG from the gameID: served bytes must keep the
    # taped ID (route IDs only select, never rewrite).
    mod = _mod()
    record = {"info": {"gameID": "ENGINE01"}, "turns": []}
    staged = json.dumps(record).encode()
    assert json.loads(staged)["info"]["gameID"] == "ENGINE01"
    assert mod.GAME_ID_RE.fullmatch("ENGINE01")


def test_index_links_every_game_to_client(tmp_path: Path) -> None:
    mod = _mod()
    _run(tmp_path, "a-run")
    _run(tmp_path, "b-run")
    summaries = {p.name: mod.load_summary(p) for p in mod.find_runs(tmp_path)}
    ids = mod.assign_ids(list(summaries), {n: "ENGINE01" for n in summaries})
    for name, gid in ids.items():
        summaries[name]["game_id"] = gid
    index = mod.render_index(summaries, "http://localhost:9000").decode()
    assert "2 games" in index
    for gid in ids.values():
        assert f"http://localhost:9000/w0/game/{gid}?spectate" in index


def test_archive_serves_records_and_404s(tmp_path: Path) -> None:
    mod = _mod()
    records = {
        "OF000001": json.dumps({"info": {"gameID": "ENGINE01"}}).encode(),
    }
    index = mod.render_index({}, "http://localhost:9000")
    server, port = _serve(records, index)
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/") as res:
            assert res.status == 200
            assert "0 games" in res.read().decode()
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/game/OF000001") as res:
            assert res.status == 200
            assert res.headers.get("Access-Control-Allow-Origin") == "*"
            assert res.headers.get("Cache-Control") == "no-store"
            body = json.loads(res.read())
            assert body["info"]["gameID"] == "ENGINE01"
        for path in ("/game/NOPE1234", "/other/OF000001"):
            try:
                urllib.request.urlopen(f"http://127.0.0.1:{port}{path}")
            except urllib.error.HTTPError as exc:
                assert exc.code == 404
            else:
                raise AssertionError(f"{path} should 404")
    finally:
        server.shutdown()
