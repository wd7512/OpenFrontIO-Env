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

from openfrontbench.paths import REPO_ROOT

logger = logging.getLogger(__name__)
DEFAULT_ENGINE_DIR = REPO_ROOT / "engine"
PLAINS_MAP_DIR = (
    REPO_ROOT / "vendor" / "OpenFrontIO" / "tests" / "testdata" / "maps" / "plains"
)
BRITANNIA_MAP_DIR = (
    REPO_ROOT / "vendor" / "OpenFrontIO" / "resources" / "maps" / "britannia"
)
MAPS = {"plains": PLAINS_MAP_DIR, "britannia": BRITANNIA_MAP_DIR}
WORLD_MAP_DIR = REPO_ROOT / "vendor" / "OpenFrontIO" / "resources" / "maps" / "world"
MAPS["world"] = WORLD_MAP_DIR
EUROPE_MAP_DIR = REPO_ROOT / "vendor" / "OpenFrontIO" / "resources" / "maps" / "europe"
MAPS["europe"] = EUROPE_MAP_DIR
MAP_NAMES = tuple(MAPS)
DEFAULT_TIMEOUT_SECONDS = 60.0
MAX_NATIONS = 100
MAX_TRIBES = 500
DIFFICULTIES = ("easy", "medium", "hard", "impossible")
MAP_SIZES = ("full", "compact")


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

    def start(
        self,
        nations: object = 0,
        difficulty: object = "easy",
        map_size: object = "full",
        spawn: object = (50, 50),
        tribes: object = 0,
    ) -> dict[str, Any]:
        """Boot the fixture and return the initial snapshot.

        ``nations`` spawns that many procedurally generated nation opponents
        through the production nation path; ``difficulty`` drives their
        production AI cadence. ``map_size`` is ``"full"`` (fixture bins) or
        ``"compact"`` (production online small: map4x, halved nation spawns).
        ``spawn`` is an ``(x, y)`` tile or ``None`` for seeded random land
        (required on real maps, where no fixed coordinate is safe).
        ``tribes`` spawns that many production neutral tribes
        (GameRunner.init order: nations, tribes from the bots count, win
        check) — solo default online is 400.
        """
        if isinstance(nations, bool) or not isinstance(nations, int):
            raise EngineError(f"nations must be an integer, got {nations!r}")
        if not 0 <= nations <= MAX_NATIONS:
            raise EngineError(f"nations must be in [0, {MAX_NATIONS}], got {nations!r}")
        if not isinstance(difficulty, str) or difficulty not in DIFFICULTIES:
            raise EngineError(
                f"difficulty must be one of {', '.join(DIFFICULTIES)}, "
                f"got {difficulty!r}"
            )
        if not isinstance(map_size, str) or map_size not in MAP_SIZES:
            raise EngineError(
                f"map_size must be one of {', '.join(MAP_SIZES)}, got {map_size!r}"
            )
        if isinstance(tribes, bool) or not isinstance(tribes, int):
            raise EngineError(f"tribes must be an integer, got {tribes!r}")
        if not 0 <= tribes <= MAX_TRIBES:
            raise EngineError(f"tribes must be in [0, {MAX_TRIBES}], got {tribes!r}")
        if spawn is not None:
            if not isinstance(spawn, (tuple, list)) or len(spawn) != 2:
                raise EngineError(
                    f"spawn must be an (x, y) integer pair or None, got {spawn!r}"
                )
            x_raw, y_raw = spawn[0], spawn[1]
            if (
                not isinstance(x_raw, int)
                or isinstance(x_raw, bool)
                or not isinstance(y_raw, int)
                or isinstance(y_raw, bool)
            ):
                raise EngineError(
                    f"spawn must be an (x, y) integer pair or None, got {spawn!r}"
                )
            spawn_x: int | None = x_raw
            spawn_y: int | None = y_raw
        else:
            spawn_x, spawn_y = None, None
        return self._request(
            {
                "cmd": "start",
                "mapDir": str(self._map_dir),
                "spawnX": spawn_x,
                "spawnY": spawn_y,
                "nations": nations,
                "difficulty": difficulty,
                "mapSize": map_size,
                "tribes": tribes,
            }
        )

    def query(self) -> dict[str, Any]:
        """Return the current snapshot without advancing the game."""
        return self._request({"cmd": "query"})

    def advance(self, ticks: object) -> dict[str, Any]:
        """Advance ``ticks`` production ticks and return the new snapshot."""
        return self._request({"cmd": "advance", "ticks": ticks})

    def attack(self, target: object, troops: object) -> dict[str, Any]:
        """Order the human to attack ``target`` (``"nation-N"``) with ``troops``.

        The order goes through the production intent path
        (Executor.createExec -> AttackExecution); validation of the target
        index and troop count happens worker-side against live game state.
        """
        return self._request({"cmd": "attack", "target": target, "troops": troops})

    def cancel_attack(self, attack_id: object) -> dict[str, Any]:
        """Retreat an outgoing attack by its id (production cancel_attack
        intent -> RetreatExecution); validated worker-side against the live
        outgoing attack list."""
        return self._request({"cmd": "cancel_attack", "attackID": attack_id})

    def boat_attack(self, x: object, y: object, troops: object) -> dict[str, Any]:
        """Launch a boat attack at tile (``x``, ``y``) with ``troops``
        (production boat intent -> TransportShipExecution); destination
        bounds are validated worker-side, the engine validates the tile."""
        return self._request({"cmd": "boat", "x": x, "y": y, "troops": troops})

    def cancel_boat(self, unit_id: object) -> dict[str, Any]:
        """Recall a transport ship by its id (production cancel_boat intent
        -> BoatRetreatExecution); validated worker-side against live boats."""
        return self._request({"cmd": "cancel_boat", "unitID": unit_id})

    def build_unit(self, unit: object, x: object, y: object) -> dict[str, Any]:
        """Build ``unit`` (build-menu kebab name) at tile (``x``, ``y``)
        (production build_unit intent -> ConstructionExecution); the menu
        allowlist and bounds are validated worker-side, the engine validates
        costs and tiles."""
        return self._request({"cmd": "build", "unit": unit, "x": x, "y": y})

    def upgrade_unit(self, unit_id: object) -> dict[str, Any]:
        """Upgrade a human unit by its id (production upgrade_structure
        intent); validated worker-side against live human units."""
        return self._request({"cmd": "upgrade", "unitID": unit_id})

    def delete_unit(self, unit_id: object) -> dict[str, Any]:
        """Delete a human unit by its id (production delete_unit intent);
        validated worker-side against live human units."""
        return self._request({"cmd": "delete_unit", "unitID": unit_id})

    def alliance_request(self, target: object) -> dict[str, Any]:
        """Request an alliance with ``target`` (``"nation-N"``/``"tribe-N"``)."""
        return self._request({"cmd": "alliance_request", "target": target})

    def alliance_reject(self, requestor: object) -> dict[str, Any]:
        """Reject an incoming alliance request from ``requestor``."""
        return self._request({"cmd": "alliance_reject", "target": requestor})

    def alliance_extend(self, target: object) -> dict[str, Any]:
        """Extend the alliance with ``target`` (``"nation-N"``/``"tribe-N"``)."""
        return self._request({"cmd": "alliance_extend", "target": target})

    def break_alliance(self, target: object) -> dict[str, Any]:
        """Break the alliance with ``target`` (``"nation-N"``/``"tribe-N"``)."""
        return self._request({"cmd": "break_alliance", "target": target})

    def embargo(self, target: object, action: object) -> dict[str, Any]:
        """Start or stop an embargo on ``target`` (``action`` start|stop)."""
        return self._request({"cmd": "embargo", "target": target, "action": action})

    def donate_gold(self, target: object, amount: object) -> dict[str, Any]:
        """Donate ``amount`` gold to ``target``."""
        return self._request({"cmd": "donate_gold", "target": target, "amount": amount})

    def donate_troops(self, target: object, amount: object) -> dict[str, Any]:
        """Donate ``amount`` troops to ``target``."""
        return self._request(
            {"cmd": "donate_troops", "target": target, "amount": amount}
        )

    def move_warship(self, unit_id: object, x: object, y: object) -> dict[str, Any]:
        """Retarget a warship to patrol tile (``x``, ``y``) (production
        move_warship intent -> MoveWarshipExecution); validated worker-side
        against live human warships and tile bounds."""
        return self._request({"cmd": "move_warship", "unitID": unit_id, "x": x, "y": y})

    def grid(self, step: object = 12) -> dict[str, Any]:
        """Return a read-only downsampled ownership grid (no game mutation).

        ``step`` samples every Nth tile (worker validates >= 4). Result has
        tick/step/cols/rows, RLE ``cells``, a ``legend`` (char -> class or
        nation id) and the ordered ``nations`` list.
        """
        return self._request({"cmd": "grid", "step": step})

    def save_record(self) -> dict[str, Any]:
        """Return the replay tape and write record.json when configured.

        The tape holds every executed game tick with its stamped human
        intents (production turn shape); the worker writes the file itself
        when ``OPENFRONT_RECORD_DIR`` is set, otherwise it is a pure
        in-memory return.
        """
        return self._request({"cmd": "save_record"})

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
