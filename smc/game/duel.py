"""The stacked (fleet-route) dynamic game: within-episode pattern-of-life play,
human-in-the-loop routing, and ambush placement. Reuses sacred's own gen19 game
logic (stacked_L, softmax_br, oracle_refs) imported from scripts/train_b1lite1.py
so live numbers are the project's numbers.
"""

from __future__ import annotations

import importlib.util
from collections import deque
from dataclasses import dataclass, field

import numpy as np

from ..sacred_bridge.oracle import OracleInstance
from ..sacred_bridge.paths import SACRED_ROOT, ensure_sacred_importable

_b1 = None


def _b1lite():
    """Import sacred's gen19 module (torch import cost; call in workers first)."""
    global _b1
    if _b1 is None:
        ensure_sacred_importable()
        spec = importlib.util.spec_from_file_location(
            "sacred_train_b1lite1", SACRED_ROOT / "scripts" / "train_b1lite1.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        _b1 = mod
    return _b1


@dataclass
class StackedGame:
    """The reduced game when the fleet stacks on one route per sortie."""
    inst: OracleInstance
    L: np.ndarray                    # [R, n_isets] mission loss per stacked route
    refs: dict[str, object]         # v_eq, eq (mixture), iid_eq, static_det, history_opt
    w: int
    tau: float

    @property
    def R(self) -> int:
        return self.L.shape[0]

    def eq_mixture(self) -> np.ndarray:
        return np.asarray(self.refs["eq"], dtype=float)


def build_stacked_game(inst: OracleInstance, w: int = 3, tau: float = 0.15) -> StackedGame:
    b1 = _b1lite()
    L = np.asarray(b1.stacked_L(inst.game, inst.N), dtype=float)
    refs = b1.oracle_refs(L, tau, w)
    return StackedGame(inst=inst, L=L, refs=refs, w=w, tau=tau)


def softmax_br_dist(game: StackedGame, window_counts: np.ndarray) -> np.ndarray:
    """The pattern-of-life attacker: softmax BR to the recent-window counts."""
    b1 = _b1lite()
    return np.asarray(b1.softmax_br(np.asarray(window_counts, float), game.L, game.tau), float)


@dataclass
class DuelState:
    """One running within-episode duel (defender vs adaptive attacker)."""
    game: StackedGame
    seed: int = 0
    rng: np.random.Generator = field(init=False)
    window: deque = field(init=False)
    n: int = 0
    total_loss: float = 0.0
    route_counts: np.ndarray = field(init=False)
    history: list[float] = field(default_factory=list)

    def __post_init__(self):
        self.rng = np.random.default_rng(self.seed)
        self.window = deque(maxlen=self.game.w)
        self.route_counts = np.zeros(self.game.R)

    def window_counts(self) -> np.ndarray:
        c = np.zeros(self.game.R)
        for r in self.window:
            c[r] += 1
        return c

    def window_freq(self) -> np.ndarray:
        c = self.window_counts()
        s = c.sum()
        return c / s if s > 0 else c

    @property
    def mean_loss(self) -> float:
        return self.total_loss / self.n if self.n else 0.0

    def empirical_route_dist(self) -> np.ndarray:
        s = self.route_counts.sum()
        return self.route_counts / s if s > 0 else np.full(self.game.R, 1.0 / self.game.R)

    def step(self, route: int, attacker: str = "pattern_of_life",
             fixed_attacker_dist: np.ndarray | None = None) -> dict:
        """Play one sortie: the attacker commits against the CURRENT window
        (before seeing this sortie's route), then the fleet stacks on `route`."""
        g = self.game
        if attacker == "pattern_of_life":
            a = softmax_br_dist(g, self.window_counts())
        elif attacker == "empirical_br":
            # oracle BR to the defender's cumulative realised play (punishes predictability)
            d = self.empirical_route_dist()
            j = int(np.argmax(d @ g.L))
            a = np.zeros(g.L.shape[1])
            a[j] = 1.0
        elif attacker == "fixed" and fixed_attacker_dist is not None:
            a = fixed_attacker_dist
        else:
            raise ValueError(f"unknown attacker {attacker}")

        j = int(self.rng.choice(len(a), p=a / a.sum()))
        expected = float(g.L[route, j])
        caught = bool(self.rng.random() < expected)

        self.window.append(route)
        self.route_counts[route] += 1
        self.n += 1
        self.total_loss += expected  # expected per-sortie loss (the gen19 metric)
        self.history.append(self.mean_loss)
        return {
            "iset_index": j,
            "expected_loss": expected,
            "caught_sampled": caught,
            "mean_loss": self.mean_loss,
        }
