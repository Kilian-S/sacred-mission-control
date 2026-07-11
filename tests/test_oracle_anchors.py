"""The professor-proof regression: the app's live oracle pipeline must reproduce
the ledgers' banked oracle anchors EXACTLY on the four canonical instances.
If this fails, live numbers and ledger numbers would disagree on screen."""

import pytest

from smc.sacred_bridge.paths import SACRED_ROOT

pytestmark = pytest.mark.skipif(
    not (SACRED_ROOT / "experiments").is_dir(), reason="sacred repo not present"
)


@pytest.mark.parametrize(
    "od,N,band,exp_det,exp_eq,which",
    [
        (("35", "159"), 3, (0.15, 0.95), 0.699, 0.206, "mc"),   # gen13_lock.md ladder
        (("62", "97"), 3, (0.15, 0.95), 0.699, 0.216, "mc"),    # gen09_multiconvoy.md ladder
        (("33", "71"), 1, None, 1.000, 0.167, "sc"),            # gen08/gen10 ladder (hard)
        (("110", "135"), 1, None, 1.000, 0.333, "sc"),          # zst_step0.md anchors (hard)
    ],
)
def test_live_oracle_matches_ledger_anchor(od, N, band, exp_det, exp_eq, which):
    from smc.sacred_bridge.oracle import build_instance

    inst = build_instance("kaliningrad", od[0], od[1], K=1, N=N, k_extra=8, band=band)
    det = inst.mc_loss_det if which == "mc" else inst.sc_loss_det
    eq = inst.mc_value if which == "mc" else inst.sc_value
    assert round(det, 3) == pytest.approx(exp_det, abs=5e-4)
    assert round(eq, 3) == pytest.approx(exp_eq, abs=5e-4)
