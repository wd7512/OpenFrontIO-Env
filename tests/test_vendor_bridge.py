"""Vendor replay-bridge guard: vendor/OpenFrontIO is a git submodule that
is not initialized in this checkout, so its files are invisible to git —
a re-sync silently wipes the replay bridge. These marker tests turn that
invisibility into a loud failure: if any bridge hunk goes missing, the
suite goes red and served replays diverge again (cf. OF000018).
"""

from __future__ import annotations

from pathlib import Path

VENDOR = Path(__file__).resolve().parent.parent / "vendor" / "OpenFrontIO"

BRIDGE_MARKERS = {
    # Tapes serve sidecar behavior; the loader threads it to the runner.
    "src/core/Schemas.ts": "nationBehavior: z.string().optional(),",
    "src/client/Main.ts": "lobby.nationBehavior",
    "src/client/JoinLobbyModal.ts": "fetchReplayBehavior",
    # The runner branches custom behavior into nation executions.
    "src/core/GameRunner.ts": "nationExecutions(this.nationBehavior)",
    "src/core/execution/ExecutionManager.ts": "nationExecutions(behavior",
    # Dev server must serve engine/ sources from outside the client root.
    "vite.config.ts": '"../../.."',
}


def test_vendor_replay_bridge_intact() -> None:
    missing = []
    for rel, marker in BRIDGE_MARKERS.items():
        path = VENDOR / rel
        if not path.is_file() or marker not in path.read_text():
            missing.append(f"{rel} :: {marker}")
    assert not missing, f"vendor replay bridge damaged: {missing}"
