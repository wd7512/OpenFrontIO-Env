"""Stub archive server for replay viewing in the real game client.

Usage: uv run python scripts/serve_archive.py <run-dir> [port]
Serves GET /game/<gameID> with the run's game_record.json (the exact
endpoint JoinLobbyModal.checkArchivedGame fetches); everything else 404s
so the client falls through to the archive path. Read-only.
"""

from __future__ import annotations

import json
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


def make_handler(run_dir: Path):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, format, *args):  # noqa: A002 - stdlib signature
            pass

        def do_GET(self):
            parts = self.path.strip("/").split("/")
            data = None
            if len(parts) == 2 and parts[0] == "game":
                record_path = run_dir / "game_record.json"
                if record_path.exists():
                    record = json.loads(record_path.read_text())
                    if record.get("info", {}).get("gameID") == parts[1]:
                        data = record_path.read_bytes()
            if data is None:
                self.send_response(404)
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                return
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_OPTIONS(self):
            self.send_response(204)
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Headers", "Content-Type")
            self.end_headers()

    return Handler


def main() -> None:
    run_dir = Path(sys.argv[1])
    port = int(sys.argv[2]) if len(sys.argv) > 2 else 8787
    server = ThreadingHTTPServer(("127.0.0.1", port), make_handler(run_dir))
    print(f"archive stub for {run_dir} on http://127.0.0.1:{port}")
    server.serve_forever()


if __name__ == "__main__":
    main()
