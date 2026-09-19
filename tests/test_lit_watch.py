"""Keyless structure tests for the T8 lit-watch intake queue."""

import importlib.util
import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
WATCH = REPO / "docs" / "lit-review" / "lit-watch"
SEEN = WATCH / "seen.txt"
CRON = WATCH / "cron-prompt.md"
WATCH_README = WATCH / "README.md"
DIGEST_DIR = WATCH / "daily-files"
CHECK_SEEN = WATCH / "check_seen.py"
SEED_BIBS = [
    REPO / "docs" / "lit-review" / "iter_1" / "seed.bib",
    REPO / "docs" / "lit-review" / "references.bib",
]

EPRINT_RE = re.compile(r"eprint\s*=\s*\{([^}]+)\}")
DOI_RE = re.compile(r"doi\s*=\s*\{([^}]+)\}", re.IGNORECASE)


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _seed_ids() -> set[str]:
    ids: set[str] = set()
    for bib in SEED_BIBS:
        text = _read(bib)
        ids.update(m.group(1).strip().lower() for m in EPRINT_RE.finditer(text))
        ids.update(
            m.group(1).strip().lower().rstrip(".,);]") for m in DOI_RE.finditer(text)
        )
    return ids


def _load_check_seen():
    spec = importlib.util.spec_from_file_location("lit_watch_check_seen", CHECK_SEEN)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_seen_txt_exists_sorted_and_covers_seed():
    assert SEEN.is_file(), "lit-watch/seen.txt missing"
    lines = [
        ln.strip()
        for ln in _read(SEEN).splitlines()
        if ln.strip() and not ln.strip().startswith("#")
    ]
    assert len(lines) >= 10, f"seen.txt must list >=10 IDs, found {len(lines)}"
    assert lines == sorted(lines), "seen.txt identifiers must be sorted one per line"
    seen = {ln.lower() for ln in lines}
    seed = _seed_ids()
    assert len(seed) >= 10, "seed bibs must yield >=10 IDs"
    assert seed.issubset(seen), f"seen.txt missing seed IDs: {sorted(seed - seen)[:5]}"


def test_check_seen_detects_duplicate_vs_new(tmp_path):
    mod = _load_check_seen()
    seen = mod.load_seen(SEEN)
    assert len(seen) >= 10
    dup_file = tmp_path / "dup.md"
    dup_file.write_text(
        "Known work arXiv:2609.02459 https://doi.org/10.1126/science.ade9097\n",
        encoding="utf-8",
    )
    dup_result = mod.check([dup_file], seen)
    assert dup_result, "expected IDs extracted from dup fixture"
    assert all(status == "DUPLICATE" for status in dup_result.values()), (
        f"seed IDs must be DUPLICATE: {dup_result}"
    )
    new_file = tmp_path / "new.md"
    new_file.write_text(
        "Fresh find arXiv:9999.99999 https://doi.org/10.9999/fresh.2026.001\n",
        encoding="utf-8",
    )
    new_result = mod.check([new_file], seen)
    assert any(status == "NEW" for status in new_result.values()), (
        "novel IDs must be NEW"
    )
    extracted = mod.extract_ids("see arXiv:2609.02459 and 10.1126/science.ade9097")
    assert "2609.02459" in extracted
    assert "10.1126/science.ade9097" in extracted


def test_daily_files_dir_exists_and_holds_no_samples():
    assert DIGEST_DIR.is_dir(), "lit-watch/daily-files/ missing"
    for digest in DIGEST_DIR.glob("*.md"):
        text = _read(digest)
        assert "SAMPLE" not in text, (
            f"{digest.name} is a placeholder: no unearned digests"
        )


def test_cron_prompt_has_process_and_scoped_add():
    assert CRON.is_file(), "lit-watch/cron-prompt.md missing"
    text = _read(CRON)
    for keyword in ("DISCOVER", "VERIFY", "DEDUP", "RECORD", "DIGEST"):
        assert keyword in text, f"cron-prompt must contain {keyword}"
    assert "git add docs/lit-review/lit-watch/" in text, (
        "cron-prompt must carry the scoped-add rule"
    )
    assert "git add -A" in text, "cron-prompt must forbid git add -A"


def test_watch_readme_mentions_idempotent():
    assert WATCH_README.is_file(), "lit-watch/README.md missing"
    text = _read(WATCH_README).lower()
    assert "idempotent" in text, "lit-watch README must mention idempotency rule"
    assert "keyless" in text, "lit-watch README must note keyless CI"
