"""The strongest guarantee in the app: a LOADED actor's live exploitability
must reproduce the ledger's banked value. Loads torch, so opt in with
SMC_SLOW_TESTS=1 (documented in README)."""

import os

import pytest

from smc.sacred_bridge.paths import SACRED_ROOT

pytestmark = [
    pytest.mark.skipif(not (SACRED_ROOT / "experiments").is_dir(),
                       reason="sacred repo not present"),
    pytest.mark.skipif(os.environ.get("SMC_SLOW_TESTS") != "1",
                       reason="set SMC_SLOW_TESTS=1 to run the torch-loading anchor test"),
]

# gen14_evidence.md, "Per-seed: 0.238, 0.244, 0.248, 0.248, 0.251, 0.255,
# 0.260, 0.264, 0.267, 0.285." (order in the ledger is not stated to be seed
# order, so seed 0 is pinned to the SET). gen20_f2_learned.md's table IS
# per-seed: seed 0 -> 0.355.
GEN14_PER_SEED = {0.238, 0.244, 0.248, 0.251, 0.255, 0.260, 0.264, 0.267, 0.285}
GEN20_SEED0 = 0.355


@pytest.fixture(scope="module")
def instance():
    from smc.sacred_bridge.oracle import build_instance

    return build_instance("kaliningrad", "35", "159", K=1, N=3, k_extra=8, band=(0.15, 0.95))


def _live_expl(ref, inst) -> float:
    from smc.sacred_bridge import policies

    pol = policies.load_policy(ref, inst)
    occ = inst.route_dist_to_stacked_occ_dist(pol.route_distribution())
    _, e = inst.exploitability_occ(occ)
    return round(float(e), 3)


def test_gen14_seed0_tap_matches_a_banked_per_seed_value(instance):
    from smc.sacred_bridge import policies

    ref = next(r for r in policies.discover_actors() if r.key == "gen14_seed0")
    assert _live_expl(ref, instance) in GEN14_PER_SEED


def test_gen20_seed0_matches_its_banked_row_exactly(instance):
    from smc.sacred_bridge import policies

    ref = next(r for r in policies.discover_actors() if r.key == "gen20_seed0")
    assert _live_expl(ref, instance) == GEN20_SEED0
