"""Trained-policy loading (torch): the LIVE roster.

Implements sacred's own loading recipes exactly (train_generalist.exact_ratio,
train_b1lite1 main(), fleet_cost_probe): construct ProtagonistSAC with widths
inferred from the checkpoint, attach menu/head attributes BEFORE
load_state_dict, slice features with _clip_x/_clip_ea, index nodes with
node_index_map (post-fix convention).

POLICY: only POST-FIX artefacts are loadable here (gen13/gen14 headline actors,
gen15/gen16 generalists, gen19); pre-fix checkpoints are History material and
this module refuses them by construction (no legacy indexing path).

torch and the sacred env are imported lazily; call everything here from worker
threads only.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from .maps import _KNOWN_FILES
from .oracle import OracleInstance
from .paths import MAPS_DIR, RUNS_DIR, SACRED_ROOT, ensure_sacred_importable
from .runs import read_json


def _torch_mods():
    ensure_sacred_importable()
    import torch  # noqa: PLC0415
    from src.agents.sac import (  # noqa: PLC0415
        ProtagonistSAC,
        _clip_ea,
        _clip_x,
        infer_edge_in_dim,
        infer_node_in_dim,
    )
    from src.agents.networks import featurize_state, node_index_map  # noqa: PLC0415
    from src.envs.multiconvoy_interdiction import make_multiconvoy_env  # noqa: PLC0415
    return locals()


@dataclass(frozen=True)
class ActorRef:
    """One loadable checkpoint from the post-fix live roster."""
    key: str            # e.g. "gen14_seed1"
    family: str         # gen13_lock | gen14_evidence | gen15_generalist | gen16_multicity | gen19_b1lite1
    label: str
    ckpt: Path
    kind: str           # specialist | generalist | history_aware
    provenance: str     # short ledger pointer for captions


def _best_ckpt_of_multiconvoy(family: str, stem: str) -> tuple[Path, int] | None:
    rf = read_json(RUNS_DIR / family / f"{stem}.json")
    if not rf.ok:
        return None
    res = None
    for key in ("fleet_route", "sacred"):
        if isinstance(rf.data.get(key), dict):
            res = rf.data[key]
            break
    if not res or res.get("best_tap_sortie") is None:
        return None
    ep = int(res["best_tap_sortie"])
    p = RUNS_DIR / family / f"{stem}_ckpts" / f"actor_ep{ep}.pt"
    return (p, ep) if p.is_file() else None


def _best_ckpt_of_generalist(family: str, stem: str) -> tuple[Path, int] | None:
    rf = read_json(RUNS_DIR / family / f"{stem}.json")
    if not rf.ok or rf.data.get("best_at") is None:
        return None
    ep = int(rf.data["best_at"])
    p = RUNS_DIR / family / f"{stem}_ckpts" / f"actor_ep{ep}.pt"
    return (p, ep) if p.is_file() else None


def _best_ckpt_of_b1lite(stem: str) -> tuple[Path, int] | None:
    rf = read_json(RUNS_DIR / "gen19_b1lite1" / f"{stem}.json")
    if not rf.ok or not rf.data.get("history"):
        return None
    hist = rf.data["history"]
    k_best = min(hist, key=lambda row: row[1])[0]
    p = RUNS_DIR / "gen19_b1lite1" / f"{stem}_ckpts" / f"actor_ep{int(k_best)}.pt"
    if p.is_file():
        return (p, int(k_best))
    # fall back to the nearest saved checkpoint
    d = RUNS_DIR / "gen19_b1lite1" / f"{stem}_ckpts"
    cands = sorted(d.glob("actor_ep*.pt"),
                   key=lambda q: abs(int(q.stem.split("actor_ep")[1]) - int(k_best)))
    return (cands[0], int(cands[0].stem.split("actor_ep")[1])) if cands else None


def discover_actors() -> list[ActorRef]:
    """Enumerate the post-fix live roster present on disk (no torch needed)."""
    out: list[ActorRef] = []
    for seed in range(3):
        hit = _best_ckpt_of_multiconvoy("gen13_lock", f"seed{seed}")
        if hit:
            out.append(ActorRef(
                f"gen13_seed{seed}", "gen13_lock",
                f"SACRED gen13 seed {seed} (35-159 headline actor)",
                hit[0], "specialist",
                f"gen13_lock.md best checkpoint @ sortie {hit[1]}"))
    for seed in range(10):
        hit = _best_ckpt_of_multiconvoy("gen14_evidence", f"mc_seed{seed}")
        if hit:
            out.append(ActorRef(
                f"gen14_seed{seed}", "gen14_evidence",
                f"SACRED gen14 seed {seed} (35-159, n=10 evidence run)",
                hit[0], "specialist",
                f"gen14_evidence.md best checkpoint @ sortie {hit[1]}"))
    for seed in range(3):
        hit = _best_ckpt_of_generalist("gen15_generalist", f"seed{seed}")
        if hit:
            out.append(ActorRef(
                f"gen15_seed{seed}", "gen15_generalist",
                f"Generalist gen15 seed {seed} (Kaliningrad, zero-shot across ODs)",
                hit[0], "generalist",
                f"gen15_generalist.md best checkpoint @ sortie {hit[1]}"))
        hit = _best_ckpt_of_generalist("gen16_multicity", f"seed{seed}")
        if hit:
            out.append(ActorRef(
                f"gen16_seed{seed}", "gen16_multicity",
                f"Multi-city generalist gen16 seed {seed} (zero-shot across cities)",
                hit[0], "generalist",
                f"gen16_multicity.md best checkpoint @ sortie {hit[1]}"))
    for seed in range(3):
        hit = _best_ckpt_of_b1lite(f"seed{seed}")
        if hit:
            out.append(ActorRef(
                f"gen19_seed{seed}", "gen19_b1lite1",
                f"History-aware gen19 seed {seed} (pattern-of-life defender)",
                hit[0], "history_aware",
                f"gen19_b1lite1.md best checkpoint @ sortie {hit[1]}"))
    return out


class LoadedPolicy:
    """A loaded post-fix actor bound to one instance's route menu.

    route_distribution(window_freq) -> np.ndarray [R]; window_freq is only
    used by history-aware (gen19-style) actors and may be None otherwise.
    """

    def __init__(self, ref: ActorRef, inst: OracleInstance):
        self.ref = ref
        self.inst = inst
        m = _torch_mods()
        torch = m["torch"]

        state = torch.load(ref.ckpt, map_location="cpu", weights_only=True)
        node_dim = m["infer_node_in_dim"](state, 14)
        edge_dim = m["infer_edge_in_dim"](state, 4)

        # sacred env for the SAME instance (menus + observation)
        nfile, efile = _KNOWN_FILES[inst.city]
        env = m["make_multiconvoy_env"](
            od=(inst.s, inst.t), N=inst.N, K=inst.K,
            k_extra_routes=inst.k_extra,
            edge_vuln_band=inst.band, absolute_vuln_norm=True,
            menu_select=True, seed=0,
            nodes_path=str(MAPS_DIR / nfile), edges_path=str(MAPS_DIR / efile),
        )
        env.reset()
        obs = env.observe()

        # menu identity check: env routes must match the oracle instance's routes
        env_routes = [list(r) for r in env.game.routes]
        if env_routes != inst.routes:
            raise RuntimeError(
                "route menu mismatch between the oracle instance and the sacred env; "
                "refusing to score the policy on a different game")

        prot = m["ProtagonistSAC"](
            node_in_dim=node_dim, edge_in_dim=edge_dim, hidden_dim=64,
            num_layers=2, heads=4, device="cpu")
        menu_idx = [torch.tensor(r, dtype=torch.long) for r in env.menu_route_node_idx()]
        actor = prot.actor
        actor.menu_routes = menu_idx
        if any(k == "follow_w" for k in state):
            actor.follow_w = torch.nn.Parameter(torch.tensor(1.0))
        self._feat_cols = 0
        if any(k == "route_feat_w" for k in state):
            width = int(state["route_feat_w"].shape[0])
            self._feat_cols = width
            actor.route_feat_w = torch.nn.Parameter(torch.zeros(width))
            actor.route_feats = None
        if any(k == "route_bias" for k in state):
            actor.route_bias = torch.nn.Parameter(torch.zeros(env.game.n_routes))
        actor.load_state_dict(state)
        actor.eval()

        self._torch = torch
        self._actor = actor
        self._prot = prot
        self._clip_x = m["_clip_x"]
        self._clip_ea = m["_clip_ea"]
        self._env = env
        self._obs = obs
        pyg = m["featurize_state"](obs, 0)
        pyg.x = self._clip_x(pyg.x, node_dim)
        pyg.edge_attr = self._clip_ea(pyg.edge_attr, edge_dim)
        self._pyg = pyg
        n2i = m["node_index_map"](obs)
        self._active_idx = n2i[obs["trucks"][0]["current_node"]]
        self._R = env.game.n_routes

        # static route features (min-max cost, worst vulnerability), per the recipes
        c = np.asarray(env.game.travel_cost, dtype=float)
        v = env.game.payoff.max(axis=1)

        def mm(x: np.ndarray) -> np.ndarray:
            return (x - x.min()) / (x.max() - x.min()) if x.max() > x.min() else np.zeros_like(x)

        self._static_feats = np.stack([mm(c), mm(v)], axis=1)

    def route_distribution(self, window_freq: np.ndarray | None = None) -> np.ndarray:
        torch = self._torch
        if self._feat_cols == 2:
            feats = torch.tensor(self._static_feats, dtype=torch.float32)
            self._actor.route_feats = feats
        elif self._feat_cols == 3:
            wf = np.zeros(self._R) if window_freq is None else np.asarray(window_freq, float)
            feats = np.concatenate([self._static_feats, wf.reshape(-1, 1)], axis=1)
            self._actor.route_feats = torch.tensor(feats, dtype=torch.float32)
        with torch.no_grad():
            probs, _ = self._actor(self._pyg, self._active_idx, list(range(self._R)),
                                   torch.zeros(self._R))
        d = probs.detach().cpu().numpy().astype(float).reshape(-1)
        s = d.sum()
        return d / s if s > 0 else np.full(self._R, 1.0 / self._R)

    @property
    def is_history_aware(self) -> bool:
        return self._feat_cols == 3


def load_policy(ref: ActorRef, inst: OracleInstance) -> LoadedPolicy:
    return LoadedPolicy(ref, inst)
