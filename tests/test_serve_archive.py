"""Archive stub tests: serves the run's record for its gameID, 404s otherwise."""

from __future__ import annotations

import importlib.util
import json
import threading
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path
from typing import Any


def _archive_mod() -> Any:
    path = Path(__file__).resolve().parent.parent / "scripts" / "serve_archive.py"
    spec = importlib.util.spec_from_file_location("serve_archive", path)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _serve(run_dir: Path) -> tuple[ThreadingHTTPServer, int]:
    mod = _archive_mod()
    server = ThreadingHTTPServer(("127.0.0.1", 0), mod.make_handler(run_dir))
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, port


def test_serves_record_for_game_id(tmp_path) -> None:
    (tmp_path / "game_record.json").write_text(
        json.dumps({"info": {"gameID": "ENGINE01"}})
    )
    server, port = _serve(tmp_path)
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/game/ENGINE01") as res:
            assert res.status == 200
            assert json.loads(res.read())["info"]["gameID"] == "ENGINE01"
    finally:
        server.shutdown()


def test_404_for_unknown_id_and_paths(tmp_path) -> None:
    (tmp_path / "game_record.json").write_text(
        json.dumps({"info": {"gameID": "ENGINE01"}})
    )
    server, port = _serve(tmp_path)
    try:
        for path in ("/game/NOPE1234", "/other/ENGINE01"):
            try:
                urllib.request.urlopen(f"http://127.0.0.1:{port}{path}")
            except urllib.error.HTTPError as exc:
                assert exc.code == 404
            else:
                raise AssertionError(f"{path} should 404")
    finally:
        server.shutdown()
