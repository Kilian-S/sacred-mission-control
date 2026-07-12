"""fraction_of_edge must place interceptions ON the ambush edge: fractions in
scene-length space, monotone along the route, None off the route."""

import os

import pytest

from smc.sacred_bridge.paths import SACRED_ROOT

pytestmark = pytest.mark.skipif(
    not (SACRED_ROOT / "experiments").is_dir(), reason="sacred repo not present"
)

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


@pytest.fixture(scope="module")
def mapview_with_instance():
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    from smc.sacred_bridge.oracle import build_instance
    from smc.widgets.mapview import MapView

    inst = build_instance("kaliningrad", "35", "159", K=1, N=3, k_extra=8, band=(0.15, 0.95))
    mv = MapView()
    mv.set_city(inst.city_map)
    mv.show_instance(inst.routes, inst.edge_vuln, inst.s, inst.t)
    return mv, inst


def test_fractions_valid_and_monotone_along_each_route(mapview_with_instance):
    mv, inst = mapview_with_instance
    for ri, nodes in enumerate(inst.routes):
        fracs = []
        for a, b in zip(nodes[:-1], nodes[1:]):
            f = mv.fraction_of_edge(ri, (a, b))
            if f is not None:
                assert 0.0 <= f <= 1.0
                fracs.append(f)
        assert fracs == sorted(fracs), f"route {ri}: fractions not monotone in route order"
        assert len(fracs) >= len(nodes) - 2, f"route {ri}: too few edges resolved"


def test_edge_off_route_returns_none(mapview_with_instance):
    mv, inst = mapview_with_instance
    r0_edges = {frozenset({a, b}) for a, b in zip(inst.routes[0][:-1], inst.routes[0][1:])}
    for a, b in zip(inst.routes[1][:-1], inst.routes[1][1:]):
        if frozenset({a, b}) not in r0_edges:
            assert mv.fraction_of_edge(0, (a, b)) is None
            return
    pytest.skip("routes 0 and 1 share every edge")
