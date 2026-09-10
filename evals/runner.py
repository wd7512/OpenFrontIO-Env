from __future__ import annotations

import logging

from openfront_mcp.scenarios import SCENARIOS

log = logging.getLogger(__name__)


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    for scenario in SCENARIOS:
        log.info(
            "scenario=%s map=%s nations=%d difficulties=%s seeds=%s max_ticks=%d",
            scenario.name,
            scenario.map,
            scenario.nations,
            scenario.difficulties,
            scenario.seeds,
            scenario.max_ticks,
        )


if __name__ == "__main__":
    main()
