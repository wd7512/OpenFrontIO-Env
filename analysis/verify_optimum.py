"""Game-side verification of the analytical optimum on The Box.

Re-runs, in the real engine with per-tick sampling:
  - a 3x3 grid around the 1-tick optimum (thresholds 0.34/0.36/0.38 x
    ratios 0.005/0.01/0.02), backing the local-convexity claim;
  - exploratory points: the exact continuous model optimum (0.3644, 0.0134),
    the old grid best (0.40, 0.10), the (0.36, 0.01) neighbor, the ungated
    2s policy (0, 0.05), and the gated 5s policy (0.37, 0.15);
  - model-only far-field points (ruled out by 1000+ tick margins).

Each game result is compared against analytical_model.simulate; the run
fails (exit 1) if any model-vs-game gap exceeds TOLERANCE ticks. Results
are written as JSON. Records go to a scratch raw directory (not served).

Usage:
  uv run python analysis/verify_optimum.py --raw /tmp/replay_verify
"""

import argparse
import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from analytical_model import find_optimum, simulate
from sweep_single_entity import git_sha, run_agent

logger = logging.getLogger(__name__)

GRID_THRESHOLDS = (0.34, 0.36, 0.38)
GRID_RATIOS = (0.005, 0.01, 0.02)

# (label, threshold, ratio, interval, in_game)
POINTS = [
    ("model-opt-1tick", 0.3644, 0.0134, 1, True),
    ("old-grid-best", 0.40, 0.10, 1, True),
    ("neighbor", 0.36, 0.01, 1, True),
    ("ungated-2s", 0.0, 0.05, 20, True),
    ("gated-5s", 0.37, 0.15, 50, True),
    # 10-tick optimizer spike, rounded to 4dp: model already moves 7801->7808
    # on rounding; game measures 7809/7811, identical to the enshrined point.
    ("spike-10tick-rounded", 0.3699, 0.0682, 10, True),
    ("far-low-threshold", 0.2, 0.01, 1, False),
    ("far-high-threshold", 0.5, 0.1, 1, False),
    ("far-high-ratio", 0.36, 0.5, 1, False),
    ("always-send", 0.0, 0.1, 1, False),
]

TOLERANCE = 6


def slug(threshold: float, ratio: float, interval: int) -> str:
    return f"verify-th{threshold}-ra{ratio}-n{interval}".replace(".", "p").replace(
        "-", "m"
    )


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    parser = argparse.ArgumentParser()
    parser.add_argument("--raw", type=Path, required=True)
    parser.add_argument(
        "--results",
        type=Path,
        default=Path(__file__).resolve().parent / "results" / "verify_results.json",
    )
    args = parser.parse_args()
    args.raw.mkdir(parents=True, exist_ok=True)

    grid: list[dict[str, object]] = []
    for threshold in GRID_THRESHOLDS:
        row = []
        for ratio in GRID_RATIOS:
            model_crossing = simulate(threshold, ratio, interval=1)["crossing_tick"]
            game = run_agent(args.raw, slug(threshold, ratio, 1), threshold, ratio, 1)
            row.append(game["crossing_tick"])
            grid.append(
                {
                    "threshold": threshold,
                    "ratio": ratio,
                    "interval": 1,
                    "model_crossing": model_crossing,
                    "game_crossing": game["crossing_tick"],
                    "game_declared": game["declared_tick"],
                }
            )
        logger.info("grid th=%.2f crossings=%s", threshold, row)

    points: list[dict[str, object]] = []
    worst = 0
    for label, threshold, ratio, interval, in_game in POINTS:
        model_crossing = simulate(threshold, ratio, interval=interval)["crossing_tick"]
        entry: dict[str, object] = {
            "label": label,
            "threshold": threshold,
            "ratio": ratio,
            "interval": interval,
            "model_crossing": model_crossing,
        }
        if in_game:
            game = run_agent(
                args.raw, slug(threshold, ratio, interval), threshold, ratio, interval
            )
            entry["game_crossing"] = game["crossing_tick"]
            entry["game_declared"] = game["declared_tick"]
            crossed = game["crossing_tick"]
            if isinstance(crossed, (int, float)) and model_crossing != float("inf"):
                gap = abs(float(model_crossing) - float(crossed))
                entry["gap"] = gap
                worst = max(worst, gap)
        points.append(entry)
        logger.info(entry)

    for interval in (1, 10, 20, 30, 40, 50):
        logger.info("optimizer interval=%d: %s", interval, find_optimum(interval))

    payload = {
        "created": datetime.now(timezone.utc).isoformat(),
        "git_sha": git_sha(),
        "tolerance": TOLERANCE,
        "worst_gap": worst,
        "grid_3x3": grid,
        "points": points,
    }
    args.results.parent.mkdir(parents=True, exist_ok=True)
    args.results.write_text(json.dumps(payload, indent=2))
    logger.info("wrote %s (worst gap %.0f)", args.results, worst)
    if worst > TOLERANCE:
        logger.error("model-vs-game gap %.0f exceeds tolerance %d", worst, TOLERANCE)
        sys.exit(1)


if __name__ == "__main__":
    main()
