"""The narrative index: curated per-generation metadata with ledger provenance.

The YAML is authored by hand from reading the ledgers; every `quote` string
must occur verbatim (modulo hard line-wrapping) in the document it cites.
`verify_quote` implements exactly the check the unit tests enforce, and the
History tab calls it at load so a stale quote degrades to a visible warning
rather than a silently wrong number.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

import yaml

from .paths import DATA_DIR, SACRED_ROOT


@dataclass(frozen=True)
class Quote:
    label: str
    quote: str
    verified: bool
    source: str = ""  # ledger path the quote is verified against (defaults to the entry's)


@dataclass(frozen=True)
class Generation:
    id: str
    chapter: str
    era: str  # campaign | pre-fix | post-fix
    title: str
    dates: str
    status: str
    question: str
    ledger: str  # path relative to SACRED_ROOT
    quotes: tuple[Quote, ...]
    plain: str = ""   # one-sentence "in plain words" summary of the quotes
    lesson: str = ""
    demo: str = "text"  # live | chart | text
    runs_dir: str = ""
    artefact: str = ""
    instance: str = ""
    sha: str = ""
    tb_runs: tuple[str, ...] = field(default_factory=tuple)
    figures: tuple[str, ...] = field(default_factory=tuple)

    @property
    def ledger_path(self) -> Path:
        return SACRED_ROOT / self.ledger


@dataclass(frozen=True)
class Chapter:
    id: str
    title: str
    subtitle: str


@dataclass(frozen=True)
class EraDivider:
    after: str
    title: str
    text: str
    source: str


def _normalise(text: str) -> str:
    """Collapse whitespace runs and strip blockquote markers so hard
    line-wrapping (the ledgers wrap at ~100 chars, often inside `> ` blocks)
    does not defeat matching. Content characters are never altered."""
    text = re.sub(r"(?m)^\s*(?:>\s*)+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


@lru_cache(maxsize=64)
def _normalised_doc(path: str) -> str | None:
    p = Path(path)
    try:
        return _normalise(p.read_text(encoding="utf-8"))
    except OSError:
        return None


def verify_quote(quote: str, ledger_path: Path) -> bool:
    doc = _normalised_doc(str(ledger_path))
    if doc is None:
        return False
    return _normalise(quote) in doc


def load_narrative_index(
    yaml_path: Path | None = None,
) -> tuple[list[Chapter], list[Generation], EraDivider | None]:
    path = yaml_path or (DATA_DIR / "narrative_index.yaml")
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))

    chapters = [Chapter(**c) for c in raw.get("chapters", [])]

    div = None
    if raw.get("era_divider"):
        div = EraDivider(**raw["era_divider"])

    gens: list[Generation] = []
    for g in raw.get("generations", []):
        ledger_rel = g["ledger"]
        quotes = tuple(
            Quote(
                label=q["label"],
                quote=q["quote"],
                verified=verify_quote(q["quote"],
                                      SACRED_ROOT / q.get("ledger", ledger_rel)),
                source=q.get("ledger", ledger_rel),
            )
            for q in g.get("quotes", [])
        )
        gens.append(
            Generation(
                id=g["id"],
                chapter=g["chapter"],
                era=g["era"],
                title=g["title"],
                dates=g.get("dates", ""),
                status=str(g.get("status", "")),
                question=g.get("question", "").strip(),
                ledger=ledger_rel,
                quotes=quotes,
                plain=g.get("plain", "").strip(),
                lesson=g.get("lesson", "").strip(),
                demo=g.get("demo", "text"),
                runs_dir=g.get("runs_dir", ""),
                artefact=g.get("artefact", ""),
                instance=g.get("instance", ""),
                sha=g.get("sha", ""),
                tb_runs=tuple(g.get("tb_runs", [])),
                figures=tuple(g.get("figures", [])),
            )
        )
    return chapters, gens, div
