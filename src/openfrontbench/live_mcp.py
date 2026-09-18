"""Server-side audited session: real engine + ordered trace, decision cap 3."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from openfrontbench.session import GameSession, SessionError

MAX_DECISIONS = 3


class AuditedSession:
    """Wraps GameSession, appending one JSON object per call to trace_path."""

    def __init__(self, trace_path: Path | str) -> None:
        self._trace_path = Path(trace_path)
        self._game = GameSession()
        self._seq = 0
        self._fh = self._trace_path.open("w", encoding="utf-8")

    def _emit(
        self, tool: str, ok: bool, result: Any = None, error: str | None = None
    ) -> None:
        self._seq += 1
        payload: dict[str, Any] = {
            "seq": self._seq,
            "ts": time.time(),
            "tool": tool,
            "ok": ok,
        }
        if result is not None:
            payload["result"] = result
        if error is not None:
            payload["error"] = error
        self._fh.write(json.dumps(payload, sort_keys=True) + "\n")
        self._fh.flush()

    def start(self) -> dict[str, Any]:
        try:
            result = self._game.start()
        except (SessionError, RuntimeError) as exc:
            self._emit("start_smoke_game", False, error=str(exc))
            raise
        self._emit("start_smoke_game", True, result=result)
        return result

    def end_decision(self, expected: int) -> dict[str, Any]:
        if isinstance(expected, bool) or not isinstance(expected, int):
            self._emit("end_decision", False, error="decision must be an integer")
            raise RuntimeError("decision must be an integer")
        if expected > MAX_DECISIONS:
            self._emit(
                "end_decision", False, error=f"decision cap {MAX_DECISIONS} reached"
            )
            raise RuntimeError(f"decision cap {MAX_DECISIONS} reached")
        try:
            result = self._game.end_decision(expected)
        except (SessionError, RuntimeError) as exc:
            self._emit("end_decision", False, error=str(exc))
            raise RuntimeError(str(exc)) from exc
        self._emit("end_decision", True, result=result)
        return result

    def overview(self) -> dict[str, Any]:
        result = self._game.overview()
        self._emit("get_overview", True, result=result)
        return result

    def close(self) -> dict[str, Any]:
        result = self._game.close()
        self._emit("close_game", True, result=result)
        return result

    def shutdown(self) -> None:
        try:
            self._game.shutdown()
        finally:
            try:
                self._fh.close()
            except OSError:
                pass
