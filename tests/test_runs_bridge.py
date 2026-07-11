"""Parsers against the real (read-only) run artefacts, tolerantly."""

from pathlib import Path

import pytest

from smc.sacred_bridge import gen_charts, runs
from smc.sacred_bridge.paths import RUNS_DIR

pytestmark = pytest.mark.skipif(not RUNS_DIR.is_dir(), reason="sacred repo not present")


def test_read_json_missing_is_typed():
    rf = runs.read_json(RUNS_DIR / "does_not_exist_ever.json")
    assert not rf.ok and rf.error == "missing"


def test_multiconvoy_history_shape():
    files = runs.list_family_jsons("gen13_lock")
    if not files:
        pytest.skip("gen13_lock not present")
    rf = runs.read_json(files[0])
    assert rf.ok
    result = runs.multiconvoy_result(rf.data)
    assert result is not None
    hs = runs.HistorySeries.from_rows(result["history"], runs.MULTICONVOY_HISTORY_FIELDS)
    assert len(hs.col("sortie")) == len(hs.col("expl_tap")) > 0
    assert all(isinstance(v, (int, float)) for v in hs.col("expl_tap"))


def test_generalist_history_shape():
    files = runs.list_family_jsons("gen16_multicity")
    if not files:
        pytest.skip("gen16_multicity not present")
    rf = runs.read_json(files[0])
    assert rf.ok
    assert rf.data.get("holdout_city") == "gdansk"
    hs = runs.HistorySeries.from_rows(rf.data["history"], runs.GENERALIST_HISTORY_FIELDS)
    assert len(hs.col("test_ratio")) > 0


def test_gen_chart_payloads():
    for gid in ("gen09", "gen13", "gen14", "gen15", "gen16", "gen19", "zst0", "gen08"):
        payload = gen_charts.load_gen_chart(gid)
        assert ("series" in payload) or ("error" in payload)
        if "series" in payload:
            assert payload["series"], gid


def test_checkpoints_listing_sorted():
    ckpts = runs.list_checkpoints("gen13_lock", "seed0")
    if not ckpts:
        pytest.skip("gen13_lock checkpoints not present")
    eps = [int(p.stem.split("actor_ep")[1]) for p in ckpts]
    assert eps == sorted(eps)
