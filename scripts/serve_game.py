"""Serve a live game view over HTTP from captured grid frames.

Usage: uv run python scripts/serve_game.py <run-dir> [port]
Polls <run-dir>/grids.jsonl and serves the latest frame as PNG plus a
page that refreshes every 10s. Read-only: never touches the game.
"""

from __future__ import annotations

import importlib.util
import io
import json
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


def _render_mod():
    path = Path(__file__).resolve().parent / "render_timelapse.py"
    spec = importlib.util.spec_from_file_location("render_timelapse", path)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


PAGE = """<html><head><meta http-equiv="refresh" content="10">
<title>OpenFrontBench live</title></head>
<body style="background:#111;color:#eee;font-family:sans-serif">
<h2>OpenFrontBench live</h2>
<p>refreshes every 10s</p>
<img src="/frame.png" style="max-width:95vw">
</body></html>"""


def make_handler(run_dir: Path, mod):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, format, *args):  # noqa: A002 - stdlib signature
            pass

        def do_GET(self):
            if self.path == "/frame.png":
                lines = (run_dir / "grids.jsonl").read_text().splitlines()
                if not lines:
                    self.send_response(503)
                    self.end_headers()
                    return
                frame = json.loads(lines[-1])
                images, _ = mod.render_frames(run_dir)
                _ = frame
                buf = io.BytesIO()
                images[-1].save(buf, format="PNG")
                data = buf.getvalue()
                self.send_response(200)
                self.send_header("Content-Type", "image/png")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)
            else:
                data = PAGE.encode()
                self.send_response(200)
                self.send_header("Content-Type", "text/html")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

    return Handler


def main() -> None:
    run_dir = Path(sys.argv[1])
    port = int(sys.argv[2]) if len(sys.argv) > 2 else 8901
    mod = _render_mod()
    server = ThreadingHTTPServer(("127.0.0.1", port), make_handler(run_dir, mod))
    print(f"serving {run_dir} on http://127.0.0.1:{port}")
    server.serve_forever()


if __name__ == "__main__":
    main()
