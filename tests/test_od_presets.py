"""Provenance for the Playground's banked anchors, same bar as the narrative index."""

from pathlib import Path

import pytest
import yaml

from smc.sacred_bridge.ledgers import verify_quote
from smc.sacred_bridge.paths import DATA_DIR, SACRED_ROOT

pytestmark = pytest.mark.skipif(
    not (SACRED_ROOT / "experiments").is_dir(), reason="sacred repo not present"
)


def _load():
    return yaml.safe_load((DATA_DIR / "od_presets.yaml").read_text())


def test_banked_anchor_quotes_verbatim():
    raw = _load()
    failures = []
    for city, presets in raw["presets"].items():
        for p in presets:
            for bank in p.get("banked", []):
                default_ledger = bank["ledger"]
                for item in bank["items"]:
                    ledger = item.get("ledger", default_ledger)
                    if not verify_quote(item["quote"], SACRED_ROOT / ledger):
                        failures.append(f"{city} {p['od']}: {item['label']}")
    assert not failures, "\n".join(failures)


def test_preset_ods_exist_in_their_graphs():
    from smc.sacred_bridge import maps

    raw = _load()
    for city, presets in raw["presets"].items():
        cm = maps.load_city(city)
        for p in presets:
            s, t = p["od"].split("-")
            assert s in cm.nodes, f"{city} {p['od']}: source node missing"
            assert t in cm.nodes, f"{city} {p['od']}: target node missing"
