"""The sortie sampler must converge to the exact LP values it displays
(brief §4.2: live simulations CONVERGE to citable numbers)."""

import numpy as np
import pytest

from smc.sacred_bridge.paths import SACRED_ROOT

pytestmark = pytest.mark.skipif(
    not (SACRED_ROOT / "experiments").is_dir(), reason="sacred repo not present"
)


@pytest.fixture(scope="module")
def engine():
    from smc.game.sortie import SortieEngine
    from smc.sacred_bridge.oracle import build_instance

    inst = build_instance("kaliningrad", "35", "159", K=1, N=3, k_extra=8, band=(0.15, 0.95))
    return SortieEngine(inst, seed=0)


def test_running_rate_converges_to_exact_value(engine):
    specs = {d.key: d for d in engine.defender_specs()}
    for dkey in ("equilibrium", "shortest", "uniform_stack"):
        d = specs[dkey]
        for a in engine.attacker_specs(d):
            engine.reset_stats()
            expected = engine.expected_value(d, a)
            for _ in range(4000):
                engine.play_sortie(d, a)
            got = engine.stats.rate
            assert abs(got - expected) < 0.035, (dkey, a.key, got, expected)


def test_equilibrium_exploitability_equals_game_value(engine):
    d = {x.key: x for x in engine.defender_specs()}["equilibrium"]
    e = engine.exploitability(d)
    assert abs(e - engine.inst.mc_value) < 1e-6


def test_occ_dists_are_distributions(engine):
    for d in engine.defender_specs():
        assert abs(float(np.sum(d.occ_dist)) - 1.0) < 1e-8, d.key
        assert float(np.min(d.occ_dist)) >= -1e-12, d.key
