"""Document enumeration and full-text search over the sacred repo and the
thesis directory (both read-only)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from .paths import SACRED_ROOT, THESIS_ROOT, sacred_available, thesis_available

_EXCLUDE_DIRS = {".git", ".venv", "__pycache__", "node_modules", ".pytest_cache", "cache"}

# Reading-order hints: these float to the top of their directory listing.
_PRIORITY = [
    "HANDOVER.md",
    "THESIS_STORYLINE.md",
    "SACRED_PROGRESS.md",
    "NEXT_STEPS_11-07-26.md",
    "README.md",
]


@dataclass(frozen=True)
class DocRoot:
    label: str
    path: Path


def doc_roots() -> list[DocRoot]:
    roots = []
    if sacred_available():
        roots.append(DocRoot("sacred", SACRED_ROOT))
    if thesis_available():
        roots.append(DocRoot("thesis", THESIS_ROOT))
    return roots


def list_markdown(root: Path) -> list[Path]:
    """All .md files under root, excluding machinery directories."""
    found: list[Path] = []
    for p in sorted(root.rglob("*.md")):
        if any(part in _EXCLUDE_DIRS for part in p.relative_to(root).parts):
            continue
        found.append(p)

    def key(p: Path):
        rel = p.relative_to(root)
        prio = _PRIORITY.index(p.name) if (p.name in _PRIORITY and len(rel.parts) == 1) else 99
        return (len(rel.parts), prio, str(rel).lower())

    return sorted(found, key=key)


@dataclass(frozen=True)
class SearchHit:
    path: Path
    line_no: int
    line: str


def search_docs(query: str, limit: int = 300) -> list[SearchHit]:
    """Case-insensitive substring search across every markdown doc."""
    q = query.lower()
    if len(q) < 2:
        return []
    hits: list[SearchHit] = []
    for root in doc_roots():
        for p in list_markdown(root.path):
            try:
                text = p.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            for i, line in enumerate(text.splitlines(), start=1):
                if q in line.lower():
                    hits.append(SearchHit(p, i, line.strip()[:200]))
                    if len(hits) >= limit:
                        return hits
    return hits


def resolve_internal_link(current_doc: Path, target: str) -> Path | None:
    """Resolve a relative markdown link from one doc to another, if it exists."""
    target = target.split("#", 1)[0]
    if not target or target.startswith(("http://", "https://", "mailto:")):
        return None
    candidate = (current_doc.parent / target).resolve()
    if candidate.suffix.lower() != ".md":
        md_candidate = candidate.with_suffix(".md")
        candidate = md_candidate if md_candidate.is_file() else candidate
    return candidate if candidate.is_file() else None


_NUMBERISH = re.compile(r"\d")


def find_line_of(path: Path, needle: str) -> int:
    """First line number containing the needle (whitespace-collapsed), else 0."""
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return 0
    flat_needle = re.sub(r"\s+", " ", needle).strip().lower()
    probe = flat_needle[:60]
    for i, line in enumerate(text.splitlines(), start=1):
        if probe and probe[:30] in re.sub(r"\s+", " ", line).lower():
            return i
    return 0
