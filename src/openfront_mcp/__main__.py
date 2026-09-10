from __future__ import annotations

import logging

from openfront_mcp.server import TOOLS

log = logging.getLogger(__name__)


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    log.info("openfront-mcp scaffold tools: %s", sorted(TOOLS))


if __name__ == "__main__":
    main()
