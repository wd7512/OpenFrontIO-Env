"""Readers over the vendored core (vendor/OpenFrontIO/src/core).

Stubbed in step 1; real readers land in step 2 alongside narration.
"""

from __future__ import annotations

from typing import Mapping


def overview(state: Mapping[str, object]) -> Mapping[str, object]:
    raise NotImplementedError(
        "wired in step 2 against vendor/OpenFrontIO/src/core "
        "(GameRunner/GameImpl/GameUpdates)"
    )


def territory(state: Mapping[str, object]) -> Mapping[str, object]:
    raise NotImplementedError(
        "wired in step 2 against vendor/OpenFrontIO/src/core "
        "(GameRunner/GameImpl/GameUpdates)"
    )
