"""Keyless structure tests for the T7 synthesis → proposal chain (skeletons)."""

from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
LIT = REPO / "docs" / "lit-review"
ITER3 = LIT / "iter_3"
ITER4 = LIT / "iter_4"
ITER5 = LIT / "iter_5"

SYNTHESES = [
    ITER3 / "cline-independent-synthesis.md",
    ITER3 / "cursor-lit-synthesis.md",
    ITER3 / "kiro-lit-synthesis.md",
]


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_three_syntheses_exist_and_cover_q01_q180() -> None:
    for path in SYNTHESES:
        assert path.is_file(), f"{path.name} missing"
        text = _read(path)
        assert ("Q01" in text and "Q180" in text) or "180" in text, (
            f"{path.name} must mention Q01/Q180 or 180Q"
        )


def test_proposal_v4_mentions_rq1_rq2_rq3() -> None:
    proposal = ITER4 / "proposal_v4.md"
    assert proposal.is_file(), "iter_4/proposal_v4.md missing"
    text = _read(proposal)
    for rq in ("RQ1", "RQ2", "RQ3"):
        assert rq in text, f"proposal_v4 must mention {rq}"


def test_candidate_report_has_40_plus_table_rows() -> None:
    report = ITER4 / "candidate-benchmark-report.md"
    assert report.is_file(), "iter_4/candidate-benchmark-report.md missing"
    text = _read(report)
    rows = [line for line in text.splitlines() if line.strip().startswith("|")]
    assert len(rows) >= 40, f"expected >=40 table rows, found {len(rows)}"
    assert "TODO" in text, "unscored rows must carry explicit TODO markers"


def test_proposal_v5_exists_with_draft_and_lit_watch() -> None:
    proposal = ITER5 / "proposal_v5.md"
    assert proposal.is_file(), "iter_5/proposal_v5.md missing"
    text = _read(proposal)
    assert "DRAFT" in text, "proposal_v5 must be marked DRAFT"
    assert "lit-watch" in text, "proposal_v5 must mention lit-watch"
