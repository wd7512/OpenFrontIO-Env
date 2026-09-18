#!/usr/bin/env python3
"""T6 keyless lit-review batch runner (dry-run only).

Reads numbered questions from ``detailed_research_questions.md``, injects
``iter_1/proposal_v1.md`` as ``{proposal}`` context plus the matching
per-theme brief, and prepares one stub report per question.

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
CITATION_RE = re.compile(r"doi\.org|arxiv\.|10\.\d{4,}", re.IGNORECASE)
TOOL_LINE_RE = re.compile(r"^\s*[>⚙✗➤•]")
PREAMBLE_RE = re.compile(
    r"^(here|below|this)\s+(is|are|contains|provides|outlines|shows)",
    re.IGNORECASE,
)

PROMPT_TEMPLATE = """You are a research assistant writing a one-page literature review report for the OpenFrontBench study.

STUDY CONTEXT ({{proposal}}):
{proposal}

THEME BRIEF:
{theme_brief}

RESEARCH QUESTION (Q{num}):
{question}

Use verified primary sources only. Verify every citation (DOI or arXiv id); never invent references.

Write a markdown report with exactly these five sections:

### Question
[Repeat the research question verbatim.]

### Key Findings
[3-5 bullet points, one sentence each, each tied to a cited paper.]

### Papers
[Numbered list of at least 2 papers: **[Title]** — [Authors] ([Year]). [DOI or arXiv URL].]

### Gaps
[2-3 sentences on what the literature is missing.]

### Relevance
[2-3 sentences on what this means for OpenFrontBench tick-boundary PMR/RAG, determinism/replay, or the stated design choice.]

STRICT LIMITS: at most 500 words total. Include at least 2 DOI (doi.org) or arXiv identifiers. No preamble, no meta-commentary: start directly with ### Question."""

# Question-number ranges per theme, mirroring grouped_research_questions.md.
THEME_RANGES: dict[int, list[tuple[int, int]]] = {
    1: [(1, 6), (61, 66), (151, 156)],
    2: [(7, 12), (73, 78), (91, 96)],
    3: [(13, 18), (109, 114), (115, 120)],
    4: [(19, 24), (25, 30), (127, 132)],
    5: [(31, 36), (157, 162), (163, 168)],
    6: [(37, 42), (139, 144), (145, 150)],
    7: [(49, 54), (85, 90), (103, 108)],
    8: [(67, 72), (79, 84), (97, 102), (121, 126), (133, 138)],
    9: [(55, 60), (169, 174)],
    10: [(43, 48), (175, 180)],
}


def extract_questions(path: str | Path) -> list[tuple[int, str]]:
    """Parse ``detailed_research_questions.md`` into ``[(num, text)]``."""
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


def theme_for_question(num: int) -> int:
    """Return the theme number (1-10) owning question ``num`` (0 if unknown)."""
    for theme, ranges in THEME_RANGES.items():
        for lo, hi in ranges:
            if lo <= num <= hi:
                return theme
    return 0


def theme_brief_for(num: int, prompts_dir: str | Path) -> str:
    """Load the theme brief text for question ``num`` ("" if unavailable)."""
    theme = theme_for_question(num)
    if theme == 0:
        return ""
    candidate = Path(prompts_dir) / f"theme-{theme}.md"
    if candidate.is_file():
        return candidate.read_text(encoding="utf-8")
    return ""


def prompt_for(num: int, question: str, proposal: str, theme_brief: str) -> str:
    """Render :data:`PROMPT_TEMPLATE` for one question."""
    return PROMPT_TEMPLATE.format(
        num=num, question=question, proposal=proposal, theme_brief=theme_brief
    )


def filter_output(text: str) -> str:
    """Strip tool-preamble lines (``>``, ``⚙``, ``✗``) and pre-header prose."""
    kept: list[str] = []
    started = False
    for line in text.splitlines():
        if line and TOOL_LINE_RE.match(line):
            continue
        stripped = line.strip()
        if not started:
            if stripped.startswith("###") or stripped.startswith("## "):
                started = True
            elif (
                not stripped
                or stripped == "---"
                or PREAMBLE_RE.match(stripped)
                or not stripped.startswith("#")
            ):
                continue
        kept.append(line)
    return "\n".join(kept)


def validate(text: str) -> tuple[bool, str]:
    """Check a report carries a key finding, papers, and ≥2 citations."""
    lower = text.lower()
    problems: list[str] = []
    if "key finding" not in lower:
        problems.append("missing key finding")
    if "paper" not in lower:
        problems.append("missing paper")
    citations = len(CITATION_RE.findall(text))
    if citations < 2:
        problems.append(f"only {citations} citations")
    if problems:
        return False, "; ".join(problems)
    return True, ""


def report_path(reports_dir: str | Path, num: int, question_slug: str) -> Path:
    """Return the stub report path for question ``num``."""
    return Path(reports_dir) / f"Q{num:02d}-{question_slug}.md"


def qlabel(num: int) -> str:
    """Format a question label (``Q01`` … ``Q180``)."""
    return f"Q{num:02d}"


def stub_report(num: int, question: str) -> str:
    """Render the dry-run stub report body (never a live result)."""
    return (
        f"<!-- DRY-RUN stub for {qlabel(num)}: keyless placeholder. -->\n\n"
        f"### Question\n{qlabel(num)}: {question}\n\n"
        "### Key Findings\n- [pending live run]\n\n"
        "### Papers\n1. [pending live run]\n2. [pending live run]\n\n"
        "### Gaps\n[pending live run]\n\n"
        "### Relevance\n[pending live run]\n"
    )


def process_question(
    num: int,
    question: str,
    proposal: str,
    theme_brief: str,
    reports_dir: str | Path,
    dry_run: bool = True,
) -> dict:
    """Process one question in dry-run mode; idempotent skip-if-exists.

    Never calls ``subprocess``: with ``dry_run=True`` a stub report is
    written; with ``dry_run=False`` a ``live-refused`` status is returned.
    """
    _ = (proposal, theme_brief)  # context reserved for the T7 live runner
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


def _defaults() -> tuple[Path, Path, Path, Path]:
    auto_dir = Path(__file__).resolve().parent.parent
    iter3 = auto_dir.parent
    lit = iter3.parent
    return (
        iter3 / "detailed_research_questions.md",
        lit / "iter_1" / "proposal_v1.md",
        iter3 / "research-prompts",
        auto_dir / "reports",
    )


def build_parser() -> argparse.ArgumentParser:
    d_questions, d_proposal, d_prompts, d_reports = _defaults()
    parser = argparse.ArgumentParser(
        description="T6 keyless lit-review batch runner (dry-run only)."
    )
    parser.add_argument("--questions", default=str(d_questions))
    parser.add_argument("--proposal", default=str(d_proposal))
    parser.add_argument("--prompts-dir", default=str(d_prompts))
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
            "(the T7 live runner may lift this once keys exist)."
        )
        if os.environ.get("LIVE") != "1":
            logger.error("Refusing --live without explicit LIVE=1 in env.")
        return 1

    questions_file = Path(args.questions)
    proposal_file = Path(args.proposal)
    prompts_dir = Path(args.prompts_dir)
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
                theme_brief_for(n, prompts_dir),
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
        f"T6 dry-run\nQuestions: {len(questions)} "
        f"| stubs: {counts.get('dry-run', 0)} "
        f"| skipped: {counts.get('skip', 0)}\n"
    )
    reports_dir.mkdir(parents=True, exist_ok=True)
    (reports_dir / "summary.txt").write_text(summary, encoding="utf-8")
    logger.info(summary.strip())
    return 0


if __name__ == "__main__":
    sys.exit(main())
