#!/usr/bin/env python3
"""Keyless lit-review batch runner (dry-run only).

Reads numbered questions (``N. text`` lines) from a questions file,
renders one prompt per question from a proposal context file, and
prepares one stub report per question.

Keyless policy: this module never launches agents, never touches the
network, and never imports ``subprocess``. Live execution is refused
(see :func:`main`); only ``--dry-run`` stub reports are produced.
"""

from __future__ import annotations

import argparse
import logging
import os
import re
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

logger = logging.getLogger(__name__)

QUESTION_RE = re.compile(r"^\s*(\d+)\.\s+(.*)")

PROMPT_TEMPLATE = """You are a research assistant writing a short literature review report.

STUDY CONTEXT:
{proposal}

RESEARCH QUESTION (Q{num}):
{question}

Use verifiable primary sources only. Cite every factual claim with a DOI
or arXiv identifier; never invent references, titles, or results. Mark
anything you cannot verify as pending.
"""


def extract_questions(path: str | Path) -> list[tuple[int, str]]:
    """Parse numbered ``N. text`` lines into ``[(num, text)]``."""
    questions: list[tuple[int, str]] = []
    text = Path(path).read_text(encoding="utf-8")
    for line in text.splitlines():
        m = QUESTION_RE.match(line)
        if m:
            questions.append((int(m.group(1)), m.group(2).strip()))
    return questions


def slug(text: str) -> str:
    """Return a filename-safe slug: lowercase, alnum runs joined, ≤8 words."""
    words = re.findall(r"[a-z0-9]+", text.lower())
    return "-".join(words[:8]) or "question"


def prompt_for(num: int, question: str, proposal: str) -> str:
    """Render :data:`PROMPT_TEMPLATE` for one question."""
    return PROMPT_TEMPLATE.format(num=num, question=question, proposal=proposal)


def report_path(reports_dir: str | Path, num: int, question_slug: str) -> Path:
    """Return the stub report path for question ``num``."""
    return Path(reports_dir) / f"Q{num:02d}-{question_slug}.md"


def stub_report(num: int, question: str) -> str:
    """Render the dry-run stub report body (never a live result)."""
    return (
        f"<!-- DRY-RUN stub for Q{num:02d}: keyless placeholder. -->\n\n"
        f"### Question\nQ{num:02d}: {question}\n\n"
        "### Findings\n[pending live run]\n\n"
        "### Sources\n[pending live run]\n"
    )


def process_question(
    num: int,
    question: str,
    proposal: str,
    reports_dir: str | Path,
    dry_run: bool = True,
) -> dict:
    """Process one question in dry-run mode; idempotent skip-if-exists.

    Never calls ``subprocess``: with ``dry_run=True`` a stub report is
    written; with ``dry_run=False`` a ``live-refused`` status is returned.
    """
    _ = proposal  # context reserved for a future live runner
    outfile = report_path(reports_dir, num, slug(question))
    if outfile.exists() and outfile.stat().st_size > 0:
        return {"num": num, "status": "skip", "file": str(outfile)}
    if not dry_run:
        return {
            "num": num,
            "status": "live-refused",
            "file": str(outfile),
            "error": "live runs disabled by keyless policy",
        }
    outfile.parent.mkdir(parents=True, exist_ok=True)
    outfile.write_text(stub_report(num, question), encoding="utf-8")
    return {"num": num, "status": "dry-run", "file": str(outfile)}


def _defaults() -> tuple[Path, Path, Path]:
    batch_dir = Path(__file__).resolve().parent.parent
    iter1 = batch_dir.parent
    return (
        iter1 / "research-questions.md",
        iter1 / "proposal.md",
        batch_dir / "reports",
    )


def build_parser() -> argparse.ArgumentParser:
    d_questions, d_proposal, d_reports = _defaults()
    parser = argparse.ArgumentParser(
        description="Keyless lit-review batch runner (dry-run only)."
    )
    parser.add_argument("--questions", default=str(d_questions))
    parser.add_argument("--proposal", default=str(d_proposal))
    parser.add_argument("--reports-dir", default=str(d_reports))
    parser.add_argument("--start", type=int, default=1)
    parser.add_argument("--end", type=int, default=180)
    parser.add_argument("--concurrency", type=int, default=10)
    parser.add_argument(
        "--dry-run",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="write stub reports (default True)",
    )
    parser.add_argument(
        "--live",
        action="store_true",
        default=False,
        help="refused under the keyless policy",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    args = build_parser().parse_args(argv)

    if args.live or not args.dry_run:
        logger.error(
            "Live batch runs are disabled by the keyless policy: no "
            "subprocess, network, or LLM calls. Re-run with --dry-run "
            "(a future live runner may lift this once keys exist)."
        )
        if os.environ.get("LIVE") != "1":
            logger.error("Refusing --live without explicit LIVE=1 in env.")
        return 1

    questions_file = Path(args.questions)
    proposal_file = Path(args.proposal)
    reports_dir = Path(args.reports_dir)
    if not questions_file.is_file():
        logger.error("questions file not found: %s", questions_file)
        return 1
    if not proposal_file.is_file():
        logger.error("proposal file not found: %s", proposal_file)
        return 1

    proposal = proposal_file.read_text(encoding="utf-8")
    questions = [
        (n, q)
        for n, q in extract_questions(questions_file)
        if args.start <= n <= args.end
    ]
    logger.info(
        "Questions: %d | Concurrency: %d | Range: Q%02d-Q%02d (dry-run)",
        len(questions),
        args.concurrency,
        args.start,
        args.end,
    )

    counts = {"dry-run": 0, "skip": 0}
    with ThreadPoolExecutor(max_workers=args.concurrency) as pool:
        futures = {
            pool.submit(
                process_question,
                n,
                q,
                proposal,
                reports_dir,
                True,
            ): n
            for n, q in questions
        }
        for future in as_completed(futures):
            result = future.result()
            status = str(result["status"])
            counts[status] = counts.get(status, 0) + 1
            logger.info("  %s Q%02d: %s", status.upper(), result["num"], result["file"])

    summary = (
        f"dry-run\nQuestions: {len(questions)} "
        f"| stubs: {counts.get('dry-run', 0)} "
        f"| skipped: {counts.get('skip', 0)}\n"
    )
    reports_dir.mkdir(parents=True, exist_ok=True)
    (reports_dir / "summary.txt").write_text(summary, encoding="utf-8")
    logger.info(summary.strip())
    return 0


if __name__ == "__main__":
    sys.exit(main())
