"""Live game-theory layer: thin wrappers over sacred's oracle modules.

Everything here is oracle-level (no torch, LP solves in milliseconds at
K=1-2). Called from worker threads; returns plain dataclasses the UI can
render. All numbers produced here are "computed live" in the provenance
scheme, never confusable with ledger numbers.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np

from .maps import CityMap, load_city
from .paths import ensure_sacred_importable


def _oracle_mods():
    ensure_sacred_importable()
    from src.baselines import interdiction_oracle as io  # noqa: PLC0415
    from src.baselines import multiconvoy_oracle as mo  # noqa: PLC0415
    from src.baselines import multiconvoy_planners as mp  # noqa: PLC0415
    return io, mo, mp


@dataclass
class OracleInstance:
    """One solved contested-routing instance, ready for display and sorties."""
    city: str
    s: str
    t: str
    K: int
    N: int
    k_extra: int
    band: tuple[float, float] | None
    routes: list[list[str]]                 # node-id paths
    route_costs: np.ndarray                 # [R]
    route_vuln_worst: np.ndarray            # [R] worst edge vulnerability per route
    edge_vuln: dict[frozenset, float]       # candidate edge -> p
    # single-convoy solve
    sc_value: float                         # loss_mixed
    sc_loss_det: float
    sc_defender: np.ndarray                 # [R] equilibrium route mixture
    sc_attacker: np.ndarray                 # [n_isets]
    # multi-convoy solve (N as configured; present even at N=1 for uniformity)
    occupancies: list[tuple[int, ...]]
    obj_matrix: np.ndarray                  # [n_occ, n_isets]
    mc_value: float
    mc_loss_det: float
    mc_defender: np.ndarray                 # [n_occ]
    mc_attacker: np.ndarray
    interdiction_sets: list[tuple[frozenset, ...]]
    game: Any                               # the InterdictionGame (opaque to UI)
    city_map: CityMap

    @property
    def n_routes(self) -> int:
        return len(self.routes)

    # ------------------------------------------------------------ strategies

    def stacked_occ_index(self, route_idx: int) -> int:
        occ = tuple(self.N if i == route_idx else 0 for i in range(self.n_routes))
        return self._occ_index[occ]

    def route_dist_to_stacked_occ_dist(self, route_dist: np.ndarray) -> np.ndarray:
        d = np.zeros(len(self.occupancies))
        for r, p in enumerate(route_dist):
            if p > 0:
                d[self.stacked_occ_index(r)] += p
        return d

    def occ_dist_of_fixed_assignment(self, assignment: list[int]) -> np.ndarray:
        occ = [0] * self.n_routes
        for r in assignment:
            occ[r] += 1
        d = np.zeros(len(self.occupancies))
        d[self._occ_index[tuple(occ)]] = 1.0
        return d

    def exploitability_occ(self, occ_dist: np.ndarray) -> tuple[int, float]:
        """(best-response iset index, mission-failure exploitability)."""
        io, mo, mp = _oracle_mods()
        j, loss = mo.best_response_attacker_multi(self.obj_matrix, occ_dist)
        return int(j), float(loss)

    def exploitability_routes(self, route_dist: np.ndarray) -> tuple[int, float]:
        io, mo, mp = _oracle_mods()
        j, loss = io.best_response_attacker(self.game, route_dist)
        return int(j), float(loss)

    def best_cost_mixture(self) -> tuple[np.ndarray, float, float]:
        """The best cost-calibrated softmax mixture (oracle scan over T).

        Returns (route_dist, exploitability, temperature)."""
        costs = self.route_costs
        best = (None, np.inf, 0.0)
        for T in np.geomspace(0.05, 50.0, 40):
            d = np.exp(-costs / T)
            d = d / d.sum()
            _, e = self.exploitability_routes(d)
            if e < best[1]:
                best = (d, e, float(T))
        return best  # type: ignore[return-value]


def build_instance(
    city: str,
    s: str,
    t: str,
    K: int = 1,
    N: int = 3,
    k_extra: int = 8,
    band: tuple[float, float] | None = (0.15, 0.95),
    objective: str = "mission",
) -> OracleInstance:
    io, mo, mp = _oracle_mods()
    cm = load_city(city)
    G = cm.graph()
    s, t = str(s), str(t)
    if s not in G or t not in G:
        raise ValueError(f"OD {s}-{t} not in the {city} graph")

    routes = io.build_route_set(G, s, t, k_extra=k_extra, weight="w")
    cand = set().union(*(io.edges_of_route(r) for r in routes))
    if band is not None:
        # exactly what the sacred env does under absolute_vuln_norm=True
        vuln = io.length_band_vulnerability(G, cand, band=band, weight="w", norm_edges=G.edges())
        intercept_fn = io.survival_intercept_fn(vuln)
    else:
        vuln = {e: 1.0 for e in cand}
        intercept_fn = None
    game = io.build_interdiction_game(G, s, t, K, k_extra=k_extra, weight="w",
                                      intercept_fn=intercept_fn)
    sol = io.solve(game)
    msol = mo.solve_multiconvoy(game, N, objective)
    occs, obj_m = mo.objective_matrix(game, N, objective)

    route_vuln_worst = np.array([
        max((vuln.get(e, 0.0) for e in re), default=0.0) for re in game.route_edges
    ])

    inst = OracleInstance(
        city=city, s=s, t=t, K=K, N=N, k_extra=k_extra, band=band,
        routes=[list(r) for r in game.routes],
        route_costs=np.asarray(game.travel_cost, dtype=float),
        route_vuln_worst=route_vuln_worst,
        edge_vuln=dict(vuln),
        sc_value=float(sol.value),
        sc_loss_det=float(sol.loss_det),
        sc_defender=np.asarray(sol.defender_strategy, dtype=float),
        sc_attacker=np.asarray(sol.attacker_strategy, dtype=float),
        occupancies=[tuple(int(x) for x in o) for o in occs],
        obj_matrix=np.asarray(obj_m, dtype=float),
        mc_value=float(msol.loss_mixed),
        mc_loss_det=float(msol.loss_det),
        mc_defender=np.asarray(msol.defender_strategy, dtype=float),
        mc_attacker=np.asarray(msol.attacker_strategy, dtype=float),
        interdiction_sets=[tuple(iset) for iset in game.interdiction_sets],
        game=game,
        city_map=cm,
    )
    inst._occ_index = {tuple(int(x) for x in o): i for i, o in enumerate(occs)}  # type: ignore[attr-defined]
    return inst


def alns_plan(inst: OracleInstance, seed: int = 0) -> tuple[list[int], float]:
    """ALNS fleet plan for the instance: (assignment, worst-case exploitability)."""
    io, mo, mp = _oracle_mods()
    plan = mp.alns_fleet_planner(inst.game, inst.N, "mission", seed=seed)
    return list(plan.assignment), float(plan.exploitability)


def forced_stack_alns(inst: OracleInstance) -> tuple[int, float]:
    """Best single stacked route for a deterministic planner (the fairness row)."""
    best_r, best_e = 0, np.inf
    for r in range(inst.n_routes):
        d = np.zeros(len(inst.occupancies))
        d[inst.stacked_occ_index(r)] = 1.0
        _, e = inst.exploitability_occ(d)
        if e < best_e:
            best_r, best_e = r, e
    return best_r, float(best_e)
