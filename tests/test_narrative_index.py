"""Provenance enforcement: every quote in the narrative index must occur verbatim
(whitespace-normalised) in the sacred document it cites. A failure here means a
number shown in the History tab cannot be traced to its ledger, which the brief
treats as a hard error."""

from pathlib import Path

import pytest

from smc.sacred_bridge.ledgers import load_narrative_index
from smc.sacred_bridge.paths import SACRED_ROOT

pytestmark = pytest.mark.skipif(
    not (SACRED_ROOT / "experiments").is_dir(),
    reason="sacred repo not present",
)


def test_index_loads():
    chapters, gens, div = load_narrative_index()
    assert len(chapters) >= 5
    assert len(gens) >= 25
    assert div is not None


def test_every_quote_verbatim_in_cited_document():
    _, gens, _ = load_narrative_index()
    failures = []
    for g in gens:
        if not g.ledger_path.is_file():
            failures.append(f"{g.id}: cited document missing: {g.ledger}")
            continue
        for q in g.quotes:
            if not q.verified:
                failures.append(f"{g.id}: quote not found in {g.ledger}: {q.quote[:80]!r}")
    assert not failures, "\n".join(failures)


def test_eras_are_legal():
    _, gens, _ = load_narrative_index()
    for g in gens:
        assert g.era in ("campaign", "pre-fix", "post-fix"), g.id


def test_live_demos_are_post_fix_only():
    """Brief §3: pre-fix material is History-tab content, never a live demo."""
    _, gens, _ = load_narrative_index()
    for g in gens:
        if g.demo == "live":
            assert g.era == "post-fix", f"{g.id} is {g.era} but marked live-demoable"
