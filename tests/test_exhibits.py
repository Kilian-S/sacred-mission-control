"""Provenance for exhibit data: every quote verbatim in its ledger; every
plotted value must appear inside its own quote (so a chart can never drift
from the ledger silently)."""

import re

import pytest
import yaml

from smc.sacred_bridge.ledgers import verify_quote
from smc.sacred_bridge.paths import DATA_DIR, SACRED_ROOT

pytestmark = pytest.mark.skipif(
    not (SACRED_ROOT / "experiments").is_dir(), reason="sacred repo not present"
)


@pytest.fixture(scope="module")
def data():
    return yaml.safe_load((DATA_DIR / "exhibits.yaml").read_text())


def _value_in_quote(value: float, quote: str) -> bool:
    """The plotted value must literally appear in the quote (e.g. 0.483)."""
    patterns = [f"{value:.3f}", f"{value:.2f}", f"{value:.1f}",
                f"{value:.3f}".rstrip("0"), str(value)]
    return any(p and p in quote for p in patterns)


def test_headline_ladders(data):
    for ladder in data["headline_ladders"].values():
        ledger = SACRED_ROOT / ladder["ledger"]
        shared = ladder.get("shared_quote")
        if shared:
            assert verify_quote(shared, ledger), shared[:60]
        for row in ladder["rows"]:
            quote = row.get("quote", shared)
            assert quote, row
            if "quote" in row:
                assert verify_quote(row["quote"], ledger), row["quote"][:60]
            assert _value_in_quote(row["value"], quote), (row["arm"], row["value"], quote)


def test_gen12_cells(data):
    ledger = SACRED_ROOT / data["gen12_sweeps"]["ledger"]
    for cell in data["gen12_sweeps"]["cells"]:
        assert verify_quote(cell["quote"], ledger), cell["quote"]
        for key in ("sacred", "alns", "eq"):
            assert _value_in_quote(cell[key], cell["quote"]), (cell["cell"], key)


def test_transfer_ladder(data):
    for rung in data["transfer_ladder"]["rungs"]:
        assert verify_quote(rung["quote"], SACRED_ROOT / rung["ledger"]), rung["label"]


def test_gen19_ladder(data):
    g = data["gen19_ladder"]
    assert verify_quote(g["quote"], SACRED_ROOT / g["ledger"])
    for row in g["rows"]:
        assert _value_in_quote(row["value"], g["quote"]), row


def test_amortiser_ladder(data):
    ladder = data["amortiser_ladder"]
    default_ledger = SACRED_ROOT / ladder["ledger"]
    shared = ladder["shared_quote"]
    assert verify_quote(shared, default_ledger), "amortiser shared quote"
    for row in ladder["rows"]:
        quote = row.get("quote", shared)
        ledger = SACRED_ROOT / row.get("ledger", ladder["ledger"])
        if "quote" in row:
            assert verify_quote(row["quote"], ledger), row["label"]
        assert _value_in_quote(row["value"], quote), (row["arm"], row["value"])


def test_gap_closure_ladder(data):
    g = data["gap_closure_ladder"]
    assert verify_quote(g["shared_quote"], SACRED_ROOT / g["ledger"])
    for rung in g["rungs"]:
        assert _value_in_quote(rung["value"], g["shared_quote"]), rung["label"]


def test_quote_cards(data):
    """Every Objectives quote card is verbatim in the ledger it cites."""
    for exhibit, cards in data.get("quote_cards", {}).items():
        for card in cards:
            default = card["ledger"]
            for item in card["items"]:
                ledger = SACRED_ROOT / item.get("ledger", default)
                assert verify_quote(item["quote"], ledger), (exhibit, item["label"])


def test_objectives_verbatim(data):
    src = SACRED_ROOT / data["objectives_verbatim"]["source"]
    for item in data["objectives_verbatim"]["items"]:
        assert verify_quote(item["quote"], src), item["id"]
    assert verify_quote(data["objectives_verbatim"]["aim"], src)
