"""Character encoding hygiene check — emoji, controls, confusables, UTF-8.

Pure and stdlib-only; ``check_char_encoding`` returns violation strings
(empty list = clean).  Reads file type and exclusion config from
``[tool.openfrontbench.char-encoding]`` in ``pyproject.toml``.

Detected hazards:

* UTF-8 BOM at file start; bytes that are not valid UTF-8.
* Characters in flagged Unicode General Categories (default: So, Cf, Co,
  Cn, Cs, Zs) — emoji, format chars, private use, unassigned, surrogates,
  and space separators such as NBSP.
* Dangerous control characters: every Cc except tab/LF/CR, i.e. NUL, ESC,
  DEL, C1 controls, and the Unicode line/paragraph separators that
  ``str.splitlines`` hides.
* ASCII-confusable lookalikes: Cyrillic homoglyph letters and the
  fullwidth forms block (U+FF01-U+FF5E, which maps to ASCII 0x21-0x7E by
  subtracting 0xFEE0).  Greek letters are deliberately exempt — alpha,
  kappa, rho and tau are legitimate scientific notation.

The Unicode Box Drawing block (U+2500-U+257F) is allowlisted.  Extensionless
files (Dockerfiles, Makefiles, LICENSE) are scanned by exact name or glob.
"""

from __future__ import annotations

import fnmatch
import os
import re
import tomllib
import unicodedata
from collections.abc import Iterator
from pathlib import Path

_BOM_UTF8 = b"\xef\xbb\xbf"
_NON_ASCII_RE = re.compile(r"[^\x00-\x7f]")
_ASCII_LIMIT = 128

_DANGEROUS_CONTROLS_RE = re.compile(
    r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f\u0080-\u009f\u2028\u2029]"
)

_CONFUSABLE_ASCII: dict[str, str] = {
    "\u0430": "a",
    "\u0435": "e",
    "\u043e": "o",
    "\u0440": "p",
    "\u0441": "c",
    "\u0443": "y",
    "\u0445": "x",
    "\u0456": "i",
    "\u0458": "j",
    "\u04bb": "h",
    "\u0501": "d",
    "\u0410": "A",
    "\u0412": "B",
    "\u0415": "E",
    "\u041a": "K",
    "\u041c": "M",
    "\u041d": "H",
    "\u041e": "O",
    "\u0420": "P",
    "\u0421": "C",
    "\u0422": "T",
    "\u0423": "Y",
    "\u0425": "X",
}
_FULLWIDTH_START = 0xFF01
_FULLWIDTH_END = 0xFF5E
_FULLWIDTH_OFFSET = 0xFEE0

_DEFAULT_EXTENSIONS: frozenset[str] = frozenset(
    {
        ".py",
        ".md",
        ".toml",
        ".yaml",
        ".yml",
        ".json",
        ".jsonl",
        ".sh",
        ".txt",
        ".bib",
        ".tex",
        ".ts",
        ".js",
    }
)
_DEFAULT_INCLUDE_FILES: tuple[str, ...] = (
    "Dockerfile*",
    "Makefile",
    "makefile",
    "GNUmakefile",
    "LICENSE",
    "LICENCE",
)
_DEFAULT_EXCLUDE_DIRS: frozenset[str] = frozenset(
    {
        ".agent",
        ".hermes",
        "tmp",
    }
)
_DEFAULT_FLAGGED: frozenset[str] = frozenset({"So", "Cf", "Co", "Cn", "Cs", "Zs"})
_DEFAULT_ALLOWED_CHARS: frozenset[str] = frozenset(
    chr(c) for c in range(0x2500, 0x2580)
)

_SKIPPED_DIRS: frozenset[str] = frozenset(
    {
        ".git",
        ".venv",
        "node_modules",
        "__pycache__",
        ".worktrees",
        ".ruff_cache",
        ".ty_cache",
        ".pytest_cache",
        "runs",
        "dist",
        "logs",
        "vendor",
        "cycles",
        "raw",
        "skills-available",
    }
)


def _default_config() -> tuple[
    frozenset[str], frozenset[str], frozenset[str], frozenset[str], tuple[str, ...]
]:
    return (
        _DEFAULT_EXTENSIONS,
        _DEFAULT_EXCLUDE_DIRS,
        _DEFAULT_FLAGGED,
        _DEFAULT_ALLOWED_CHARS,
        _DEFAULT_INCLUDE_FILES,
    )


def _load_config(
    repo_root: Path,
) -> tuple[
    frozenset[str], frozenset[str], frozenset[str], frozenset[str], tuple[str, ...]
]:
    """Load config from pyproject.toml; fall back to defaults."""
    pyproject = repo_root / "pyproject.toml"
    if not pyproject.exists():
        return _default_config()
    try:
        with pyproject.open("rb") as f:
            data = tomllib.load(f)
    except (tomllib.TOMLDecodeError, OSError):
        return _default_config()

    section = data.get("tool", {}).get("openfrontbench", {}).get("char-encoding", {})
    extensions = frozenset(section.get("extensions", _DEFAULT_EXTENSIONS))
    exclude_dirs = frozenset(section.get("exclude-dirs", _DEFAULT_EXCLUDE_DIRS))
    flagged = frozenset(section.get("flagged-categories", _DEFAULT_FLAGGED))
    allowed = frozenset(section.get("allowed-chars", _DEFAULT_ALLOWED_CHARS))
    include_files = tuple(section.get("include-files", _DEFAULT_INCLUDE_FILES))
    return extensions, exclude_dirs, flagged, allowed, include_files


def _check_bom(path: Path) -> list[str]:
    """Return a violation if file starts with UTF-8 BOM."""
    try:
        with path.open("rb") as fb:
            head = fb.read(3)
        if head == _BOM_UTF8:
            return [f"{path}: UTF-8 BOM detected"]
    except OSError:
        return [f"{path}: cannot read"]
    return []


def _flagged_char(
    ch: str, flagged: frozenset[str], allowed: frozenset[str]
) -> str | None:
    """Return a violation descriptor if ch is flagged, else None."""
    code = ord(ch)
    if code < _ASCII_LIMIT or ch in allowed:
        return None
    twin = _CONFUSABLE_ASCII.get(ch)
    if twin is None and _FULLWIDTH_START <= code <= _FULLWIDTH_END:
        twin = chr(code - _FULLWIDTH_OFFSET)
    if twin is not None:
        return f"U+{code:04X} (confusable with ASCII {twin!r})"
    cat = unicodedata.category(ch)
    if cat in flagged:
        return f"U+{code:04X} (category {cat})"
    return None


def _scan_chars(
    text: str, path: Path, flagged: frozenset[str], allowed: frozenset[str]
) -> list[str]:
    """Scan decoded text for flagged Unicode categories."""
    violations: list[str] = []
    for line_no, line in enumerate(text.splitlines(), start=1):
        if not _NON_ASCII_RE.search(line):
            continue
        for col, ch in enumerate(line, start=1):
            info = _flagged_char(ch, flagged, allowed)
            if info:
                violations.append(f"{path}:{line_no}:{col}: flagged character {info}")
    return violations


def _scan_controls(text: str, path: Path) -> list[str]:
    """Scan raw decoded text for dangerous control characters.

    Operates on the unsplit text: ``str.splitlines`` silently consumes
    several of these (form feed, NEL, U+2028/U+2029), which would hide
    them from the line-based scan.
    """
    violations: list[str] = []
    for match in _DANGEROUS_CONTROLS_RE.finditer(text):
        idx = match.start()
        line_no = text.count("\n", 0, idx) + 1
        col = idx - (text.rfind("\n", 0, idx) + 1) + 1
        cat = unicodedata.category(match.group())
        violations.append(
            f"{path}:{line_no}:{col}: flagged character U+{ord(match.group()):04X} (category {cat})"
        )
    return violations


def _scan_file(
    path: Path, flagged: frozenset[str], allowed: frozenset[str]
) -> list[str]:
    """Check one file for encoding violations."""
    bom_violations = _check_bom(path)
    if bom_violations and "cannot read" in bom_violations[0]:
        return bom_violations

    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        return [f"{path}: not valid UTF-8 - {exc.reason} at byte {exc.start}"]

    return (
        bom_violations
        + _scan_controls(text, path)
        + _scan_chars(text, path, flagged, allowed)
    )


def _should_skip(path: Path, exclude_dirs: frozenset[str], repo_root: Path) -> bool:
    """Return True if any repo-relative path component is an excluded directory.

    Matching is on repo-relative parts only: a checkout path whose
    ancestors happen to carry an excluded name (e.g. a parent ``tmp/``)
    must not suppress the whole scan.
    """
    all_skipped = _SKIPPED_DIRS | exclude_dirs
    try:
        rel = path.resolve().relative_to(repo_root.resolve())
    except ValueError:
        rel = path
    return any(part in all_skipped for part in rel.parts)


def _iter_repo_files(repo_root: Path) -> Iterator[Path]:
    """Yield every file under repo_root, pruning skipped dirs during walk."""
    for dirpath, dirnames, filenames in os.walk(repo_root):
        dirnames[:] = [d for d in dirnames if d not in _SKIPPED_DIRS]
        for name in filenames:
            yield Path(dirpath) / name


def _candidate_paths(
    repo_root: Path,
    extensions: frozenset[str],
    include_files: tuple[str, ...],
) -> set[Path]:
    """Collect scan candidates in a single walk.

    Extension match is case-insensitive (covers .py and .PY); include
    patterns are fnmatch'd case-sensitively against the file name.
    """
    exts = {ext.lower() for ext in extensions}
    candidates: set[Path] = set()
    for path in _iter_repo_files(repo_root):
        if path.suffix.lower() in exts:
            candidates.add(path)
            continue
        if any(fnmatch.fnmatchcase(path.name, pat) for pat in include_files):
            candidates.add(path)
    return candidates


def check_char_encoding(repo_root: Path) -> list[str]:
    """Return violation strings for *repo_root* (empty list = clean).

    Scans text files matching configured extensions (upper- and lowercase)
    plus configured extensionless names (Dockerfiles, Makefiles, LICENSE)
    under *repo_root*, skipping configured exclude directories.
    """
    extensions, exclude_dirs, flagged, allowed, include_files = _load_config(repo_root)

    violations: list[str] = []
    for path in sorted(_candidate_paths(repo_root, extensions, include_files)):
        if _should_skip(path, exclude_dirs, repo_root):
            continue
        violations.extend(_scan_file(path, flagged, allowed))
    return violations
