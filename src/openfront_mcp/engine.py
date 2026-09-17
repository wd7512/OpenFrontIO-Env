"""Bounded subprocess wrapper around the real OpenFrontIO engine worker.

``EngineWorker`` owns the Python/<abbr title="Node.js">Node</abbr> boundary for the
persistent engine: it starts ``engine/dist/worker.mjs`` (built from the vendored
upstream TypeScript core), speaks one JSON object per line on stdin/stdout, and
reads every reply under a deadline. Diagnostics from the worker arrive on
stderr and are surfaced in ``EngineError`` messages. Nothing is simulated here —
the worker is the production ``Config``/``createGame``/``SpawnExecution`` tick
loop, wrapped with bounded I/O.
"""

from __future__ import annotations

import json
import logging
import queue
import subprocess
import threading
from collections import deque
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_ENGINE_DIR = REPO_ROOT / "engine"
PLAINS_MAP_DIR = (
    REPO_ROOT / "vendor" / "OpenFrontIO" / "tests" / "testdata" / "maps" / "plains"
)
DEFAULT_TIMEOUT_SECONDS = 60.0


class EngineError(RuntimeError):
    """The engine worker is missing, died, timed out, or rejected a request."""


class EngineWorker:
    """Context-managed, strictly sequential client of the engine worker."""

    def __init__(
        self,
        engine_dir: Path | str | None = None,
        map_dir: Path | str | None = None,
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
    ) -> None:
        self._engine_dir = (
            Path(engine_dir) if engine_dir is not None else DEFAULT_ENGINE_DIR
        )
        self._map_dir = Path(map_dir) if map_dir is not None else PLAINS_MAP_DIR
        self._timeout = float(timeout)
        self._proc: subprocess.Popen[str] | None = None
        self._stdout: queue.Queue[str | None] = queue.Queue()
        self._stderr: deque[str] = deque(maxlen=50)
        self._threads: list[threading.Thread] = []
        self._next_id = 0

    def __enter__(self) -> EngineWorker:
        self._spawn()
        return self

    def __exit__(self, *_exc: object) -> bool:
        self.close()
        return False

    def start(self) -> dict[str, Any]:
        """Boot the fixture and return the initial snapshot."""
        return self._request({"cmd": "start", "mapDir": str(self._map_dir)})

    def query(self) -> dict[str, Any]:
        """Return the current snapshot without advancing the game."""
        return self._request({"cmd": "query"})

    def advance(self, ticks: object) -> dict[str, Any]:
        """Advance ``ticks`` production ticks and return the new snapshot."""
        return self._request({"cmd": "advance", "ticks": ticks})

    def close(self) -> None:
        """Send ``close`` and reap the worker, never raising on teardown."""
        proc, self._proc = self._proc, None
        if proc is None:
            return
        try:
            if proc.poll() is None and proc.stdin is not None:
                proc.stdin.write(
                    json.dumps({"cmd": "close", "id": self._next_id + 1}) + "\n"
                )
                proc.stdin.flush()
        except (BrokenPipeError, OSError, ValueError):
            logger.debug("engine worker stdin already closed during teardown")
        finally:
            try:
                if proc.stdin is not None:
                    proc.stdin.close()
            except (BrokenPipeError, OSError):
                pass
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=5)

    def _spawn(self) -> None:
        bundle = self._engine_dir / "dist" / "worker.mjs"
        if not bundle.exists():
            raise EngineError(
                f"engine bundle not found at {bundle}; build the engine worker "
                f"with `npm install` and `npm run build` in {self._engine_dir}"
            )
        if not (self._engine_dir / "node_modules").is_dir():
            raise EngineError(
                f"engine dependencies are missing in {self._engine_dir}; "
                "run `npm install` there first"
            )
        if not (self._map_dir / "manifest.json").exists():
            raise EngineError(f"engine map fixture not found at {self._map_dir}")
        try:
            self._proc = subprocess.Popen(
                ["node", str(bundle)],
                cwd=str(self._engine_dir),
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                bufsize=1,
            )
        except FileNotFoundError as error:
            raise EngineError(
                "engine worker could not start: `node` was not found on PATH"
            ) from error
        self._pump(self._proc.stdout, self._stdout.put, self._stdout_exhausted)
        self._pump(self._proc.stderr, self._stderr.append, lambda: None)

    def _stdout_exhausted(self) -> None:
        self._stdout.put(None)

    def _pump(
        self,
        stream: Any,
        on_line: Any,
        on_end: Any,
    ) -> None:
        def run() -> None:
            try:
                for line in stream:
                    on_line(line.rstrip("\n"))
            finally:
                on_end()

        thread = threading.Thread(target=run, daemon=True)
        thread.start()
        self._threads.append(thread)

    def _request(self, payload: dict[str, Any]) -> dict[str, Any]:
        proc = self._require_process()
        self._next_id += 1
        request_id = self._next_id
        message = json.dumps({**payload, "id": request_id})
        logger.debug("engine <- %s", message)
        try:
            if proc.stdin is None:
                raise BrokenPipeError("engine worker stdin is unavailable")
            proc.stdin.write(message + "\n")
            proc.stdin.flush()
        except (BrokenPipeError, OSError, ValueError) as error:
            raise EngineError(self._death_message()) from error
        response = self._read_response()
        if response.get("id") != request_id:
            raise EngineError(f"engine worker replied out of order: {response!r}")
        if not response.get("ok"):
            raise EngineError(
                f"engine rejected {payload.get('cmd')!r}: {response.get('error')}"
            )
        result = response.get("result")
        if not isinstance(result, dict):
            raise EngineError(f"engine returned a malformed result: {response!r}")
        return result

    def _read_response(self) -> dict[str, Any]:
        try:
            line = self._stdout.get(timeout=self._timeout)
        except queue.Empty as error:
            raise EngineError(self._death_message(timed_out=True)) from error
        if line is None:
            raise EngineError(self._death_message())
        try:
            decoded = json.loads(line)
        except json.JSONDecodeError as error:
            raise EngineError(
                f"engine worker wrote non-JSON to stdout: {line!r}"
            ) from error
        if not isinstance(decoded, dict):
            raise EngineError(f"engine worker wrote a non-object: {line!r}")
        return decoded

    def _require_process(self) -> subprocess.Popen[str]:
        if self._proc is None:
            raise EngineError(
                "engine worker is not running; use EngineWorker as a context manager"
            )
        if self._proc.poll() is not None:
            raise EngineError(self._death_message())
        return self._proc

    def _death_message(self, timed_out: bool = False) -> str:
        proc = self._proc
        code = proc.poll() if proc is not None else None
        tail = "\n".join(self._stderr) or "(no stderr output)"
        if timed_out:
            return (
                f"engine worker timed out after {self._timeout:.1f}s "
                f"(exit code {code}); stderr:\n{tail}"
            )
        return f"engine worker exited (exit code {code}); stderr:\n{tail}"
