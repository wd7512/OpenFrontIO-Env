"""Keyless dedup checker for lit-watch seen-list (stdlib only)."""

import argparse
import logging
import re
from pathlib import Path

logger = logging.getLogger(__name__)

ARXIV_RE = re.compile(r"(?:arxiv:\s*)?(\d{4}\.\d{4,5}(?:v\d+)?)", re.IGNORECASE)
DOI_RE = re.compile(r"10\.\d{4,9}/[^\s\"'<>;,\]]+", re.IGNORECASE)


def load_seen(path: str | Path) -> set[str]:
    """Load seen identifiers, skipping `#` comments and blank lines."""
    seen: set[str] = set()
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        seen.add(stripped.lower())
    return seen


def extract_ids(text: str) -> set[str]:
    """Extract arXiv IDs (bare NNNN.NNNNN) and DOIs from free text."""
    ids: set[str] = set()
    for match in ARXIV_RE.finditer(text):
        ids.add(match.group(1).lower())
    for match in DOI_RE.finditer(text):
        doi = match.group(0).rstrip(".,);]").lower()
        ids.add(doi)
    return ids


def check(files: list[str | Path], seen: set[str]) -> dict[str, str]:
    """Classify each extracted ID as NEW (not in seen) or DUPLICATE."""
    normalized = {s.lower() for s in seen}
    result: dict[str, str] = {}
    for file in files:
        text = Path(file).read_text(encoding="utf-8")
        for ident in sorted(extract_ids(text)):
            if ident not in result:
                result[ident] = "DUPLICATE" if ident in normalized else "NEW"
    return result


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    parser = argparse.ArgumentParser(
        description="Check files against lit-watch seen-list."
    )
    parser.add_argument(
        "--seen",
        default=str(Path(__file__).with_name("seen.txt")),
        help="Path to seen.txt ledger.",
    )
    parser.add_argument(
        "--check",
        nargs="+",
        required=True,
        help="One or more files to scan for arXiv IDs / DOIs.",
    )
    args = parser.parse_args(argv)
    seen = load_seen(args.seen)
    result = check(list(args.check), seen)
    new_count = 0
    for ident in sorted(result):
        status = result[ident]
        if status == "NEW":
            new_count += 1
        logger.info("%s %s", status, ident)
    if new_count:
        logger.info("%d NEW identifier(s) found", new_count)
        return 1
    logger.info("no NEW identifiers (all DUPLICATE or none found)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
