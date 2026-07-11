"""The sortie loop at oracle level: sample defender routes, sample/commit the
attacker, resolve interceptions, accumulate the running mission-failure rate.

All randomness is seeded and the seed is exposed (brief §4.6). The exact
expected value of the current matchup is computed alongside the running
estimate so agreement is visible (brief §4.2).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np

from ..sacred_bridge.oracle import OracleInstance


@dataclass
class DefenderSpec:
    key: str            # shortest | alns | forced_stack | uniform_stack |
                        # cost_mixture | equilibrium | independent_uniform | custom_occ
    label: str
    occ_dist: np.ndarray                 # exact occupancy distribution [n_occ]
    route_dist: np.ndarray | None = None  # stacked route mixture where meaningful
    live: bool = True                    # every oracle-level strategy is computed live


@dataclass
class AttackerSpec:
    key: str            # oracle_br | equilibrium
    label: str
    dist: np.ndarray    # distribution over isets (one-hot for the committed BR)


@dataclass
class SortieOutcome:
    routes: list[int]                    # route index per convoy
    iset_edges: list[tuple[str, str]]    # interdicted edges (u, v)
    caught: list[bool]
    caught_edge: list[tuple[str, str] | None]
    mission_failed: bool


@dataclass
class RunningStats:
    n: int = 0
    failures: int = 0
    caught_convoys: int = 0
    convoys: int = 0
    history: list[float] = field(default_factory=list)  # running rate after each sortie

    @property
    def rate(self) -> float:
        return self.failures / self.n if self.n else 0.0


class SortieEngine:
    def __init__(self, inst: OracleInstance, seed: int = 0):
        self.inst = inst
        self.seed = seed
        self.rng = np.random.default_rng(seed)
        self.stats = RunningStats()

    def reseed(self, seed: int) -> None:
        self.seed = seed
        self.rng = np.random.default_rng(seed)
        self.reset_stats()

    def reset_stats(self) -> None:
        self.stats = RunningStats()

    # ------------------------------------------------------------- strategies

    def defender_specs(self) -> list[DefenderSpec]:
        inst = self.inst
        specs: list[DefenderSpec] = []

        r_short = int(np.argmin(inst.route_costs))
        d = np.zeros(len(inst.occupancies))
        d[inst.stacked_occ_index(r_short)] = 1.0
        rd = np.zeros(inst.n_routes)
        rd[r_short] = 1.0
        specs.append(DefenderSpec("shortest", "Shortest path (deterministic stack)", d, rd))

        rd_u = np.full(inst.n_routes, 1.0 / inst.n_routes)
        specs.append(DefenderSpec(
            "uniform_stack", "Uniform mixture (uncalibrated noise)",
            inst.route_dist_to_stacked_occ_dist(rd_u), rd_u))

        if inst.N > 1:
            specs.append(DefenderSpec(
                "independent_uniform", "Independent uniform (convoys do not coordinate)",
                self._independent_uniform_occ(), None))

        cd, _, temp = inst.best_cost_mixture()
        specs.append(DefenderSpec(
            "cost_mixture", f"Best cost-calibrated mixture (softmax T={temp:.2f})",
            inst.route_dist_to_stacked_occ_dist(cd), cd))

        specs.append(DefenderSpec(
            "equilibrium", "Equilibrium mixture (LP minimax)",
            inst.mc_defender.copy(),
            self._stacked_route_marginal(inst.mc_defender)))
        return specs

    def alns_spec(self, assignment: list[int]) -> DefenderSpec:
        return DefenderSpec(
            "alns", "ALNS plan (deterministic coordinator)",
            self.inst.occ_dist_of_fixed_assignment(assignment), None)

    def forced_stack_spec(self, route_idx: int) -> DefenderSpec:
        d = np.zeros(len(self.inst.occupancies))
        d[self.inst.stacked_occ_index(route_idx)] = 1.0
        rd = np.zeros(self.inst.n_routes)
        rd[route_idx] = 1.0
        return DefenderSpec("forced_stack", "ALNS forced to stack (fairness row)", d, rd)

    def _independent_uniform_occ(self) -> np.ndarray:
        inst = self.inst
        R, N = inst.n_routes, inst.N
        d = np.zeros(len(inst.occupancies))
        for i, occ in enumerate(inst.occupancies):
            coeff = math.factorial(N)
            for c in occ:
                coeff //= math.factorial(c)
            d[i] = coeff / (R ** N)
        return d

    def _stacked_route_marginal(self, occ_dist: np.ndarray) -> np.ndarray:
        """Expected per-route share of convoys (for map mixture display)."""
        inst = self.inst
        marg = np.zeros(inst.n_routes)
        for i, occ in enumerate(inst.occupancies):
            p = occ_dist[i]
            if p > 0:
                for r, c in enumerate(occ):
                    marg[r] += p * c / inst.N
        return marg

    def attacker_specs(self, defender: DefenderSpec) -> list[AttackerSpec]:
        inst = self.inst
        j, _ = inst.exploitability_occ(defender.occ_dist)
        br = np.zeros(len(inst.interdiction_sets))
        br[j] = 1.0
        return [
            AttackerSpec("oracle_br", "Oracle best response (commits vs your pattern)", br),
            AttackerSpec("equilibrium", "Equilibrium attacker (mixes optimally)", inst.mc_attacker.copy()),
        ]

    # ------------------------------------------------------------- exact values

    def expected_value(self, defender: DefenderSpec, attacker: AttackerSpec) -> float:
        """Exact expected mission-failure of this matchup (computed live)."""
        return float(defender.occ_dist @ self.inst.obj_matrix @ attacker.dist)

    def exploitability(self, defender: DefenderSpec) -> float:
        _, e = self.inst.exploitability_occ(defender.occ_dist)
        return e

    # ------------------------------------------------------------- sampling

    def _sample_occ(self, defender: DefenderSpec) -> tuple[int, ...]:
        i = int(self.rng.choice(len(defender.occ_dist), p=_norm(defender.occ_dist)))
        return self.inst.occupancies[i]

    def play_sortie(self, defender: DefenderSpec, attacker: AttackerSpec) -> SortieOutcome:
        inst = self.inst
        occ = self._sample_occ(defender)
        routes: list[int] = []
        for r, c in enumerate(occ):
            routes.extend([r] * c)

        j = int(self.rng.choice(len(attacker.dist), p=_norm(attacker.dist)))
        iset = inst.interdiction_sets[j]
        iset_keys = [tuple(sorted(e)) for e in iset]

        caught: list[bool] = []
        caught_edge: list[tuple[str, str] | None] = []
        for r in routes:
            route_nodes = inst.routes[r]
            hit = None
            for a, b in zip(route_nodes[:-1], route_nodes[1:]):
                e = frozenset({a, b})
                if e in iset:
                    p = inst.edge_vuln.get(e, 1.0)
                    if self.rng.random() < p:
                        hit = tuple(sorted((a, b)))
                        break
            caught.append(hit is not None)
            caught_edge.append(hit)  # type: ignore[arg-type]

        failed = any(caught)
        self.stats.n += 1
        self.stats.failures += int(failed)
        self.stats.caught_convoys += sum(caught)
        self.stats.convoys += len(routes)
        self.stats.history.append(self.stats.rate)

        return SortieOutcome(
            routes=routes,
            iset_edges=[(tuple(e)[0], tuple(e)[1]) if len(tuple(e)) == 2 else (tuple(e)[0], tuple(e)[0]) for e in iset],
            caught=caught,
            caught_edge=caught_edge,
            mission_failed=failed,
        )


def _norm(d: np.ndarray) -> np.ndarray:
    s = d.sum()
    if s <= 0:
        return np.full(len(d), 1.0 / len(d))
    return d / s
