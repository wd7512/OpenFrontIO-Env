"""Vendor replay-bridge guard: vendor/OpenFrontIO is a git submodule that
is not initialized in this checkout, so its files are invisible to git —
a re-sync silently wipes the replay bridge. These marker tests turn that
invisibility into a loud failure: if any bridge hunk goes missing, the
suite goes red and served replays diverge again (cf. OF000018).
"""

from __future__ import annotations

from pathlib import Path

VENDOR = Path(__file__).resolve().parent.parent / "vendor" / "OpenFrontIO"
REPO_ROOT = Path(__file__).resolve().parent.parent

BRIDGE_MARKERS = {
    # Tapes serve sidecar behavior; the loader threads it to the runner.
    "src/core/Schemas.ts": "nationBehavior: z.string().optional(),",
    "src/client/Main.ts": "lobby.nationBehavior",
    "src/client/JoinLobbyModal.ts": "fetchReplayBehavior",
    # The runner branches custom behavior into nation executions.
    "src/core/GameRunner.ts": "nationBehaviors ?? this.nationBehavior",
    "src/core/execution/ExecutionManager.ts": "nationExecutions(behavior",
    # Dev server must serve engine/ sources from outside the client root.
    "vite.config.ts": '"../../.."',
    # Duel tapes: per-nation behaviors in spawn order, taking precedence
    # over the uniform behavior when present.
    "src/core/Schemas.ts:nationBehaviors": "nationBehaviors: z.array(z.string()).optional(),",
    "src/client/Main.ts:nationBehaviors": "lobby.nationBehaviors",
    "src/client/JoinLobbyModal.ts:nationBehaviors": "fetchReplayBehaviors",
    "src/core/GameRunner.ts:nationBehaviors": "gameStart.nationBehaviors",
    "src/core/execution/ExecutionManager.ts:nationBehaviors": "behavior?: string | string[]",
}


def test_vendor_replay_bridge_intact() -> None:
    missing = []
    for rel, marker in BRIDGE_MARKERS.items():
        # Keys may carry a ":tag" suffix to allow several markers per file.
        path = VENDOR / rel.split(":")[0]
        if not path.is_file() or marker not in path.read_text():
            missing.append(f"{rel} :: {marker}")
    assert not missing, f"vendor replay bridge damaged: {missing}"


def test_vendor_patch_and_ci_step_pinned() -> None:
    """The bridge must be reproducible on a pristine checkout: the patch
    file must exist and CI must apply it right after submodule init,
    otherwise fresh checkouts go red in test_vendor_replay_bridge_intact
    (or worse, silently diverge replays)."""
    patch = REPO_ROOT / "vendor-patches" / "replay-bridge.patch"
    assert patch.is_file(), "tracked vendor patch missing"
    for _rel, marker in BRIDGE_MARKERS.items():
        assert marker in patch.read_text(), marker
    ci = REPO_ROOT / ".github" / "workflows" / "ci.yml"
    assert "apply_vendor_patches" in ci.read_text(), "CI apply step missing"
