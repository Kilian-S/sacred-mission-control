"""Chart data for History-tab generation cards, loaded from run JSONs in a
worker thread. Returns plain dicts so the UI thread only plots."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from . import runs
from .paths import TB_DIR
from .runs import (
    B1LITE_HISTORY_FIELDS,
    C1_HISTORY_FIELDS,
    F2_HISTORY_FIELDS,
    GENERALIST_HISTORY_FIELDS,
    INTERDICTION_HISTORY_FIELDS,
    MULTICONVOY_HISTORY_FIELDS,
    HistorySeries,
    RUNS_DIR,
    multiconvoy_result,
    read_json,
)

# Which JSON stems make the canonical trajectory chart per generation id.
_FAMILY_SPECS: dict[str, dict[str, Any]] = {
    "gen08": {"family": "gen08_interdiction_I3", "glob": "B2P3_seed*.json", "kind": "interdiction",
              "note": "B2-P3, the banked single-convoy run (pre-fix era)"},
    "gen09": {"family": "gen09_multiconvoy", "glob": "headline_seed*.json", "kind": "multiconvoy",
              "note": "gen09-HEADLINE: best checkpoint ~sortie 400-500, then the disclosed drift"},
    "gen10": {"family": "gen10_postfix", "glob": "B2P3_seed*.json", "kind": "interdiction",
              "note": "gen10-SC re-run (post-fix): the single-convoy primary replicates"},
    "gen11": {"family": "gen11_menuhead", "glob": "*_seed*.json", "kind": "multiconvoy_arms",
              "note": "six arms x three seeds; no arm beats the plateau"},
    "gen12": {"family": "gen12_sweeps", "glob": "hl_N3K1_seed*.json", "kind": "multiconvoy",
              "note": "headline cell 62-97 N=3 K=1 (three seeds); sweep curves live in Objectives"},
    "gen13": {"family": "gen13_lock", "glob": "seed*.json", "kind": "multiconvoy",
              "note": "the lock on 35-159: tight best checkpoints, drift disclosed"},
    "gen14": {"family": "gen14_evidence", "glob": "mc_seed*.json", "kind": "multiconvoy",
              "note": "n=10 seeds on 35-159 (the citable CI)"},
    "gen15": {"family": "gen15_generalist", "glob": "seed*.json", "kind": "generalist",
              "note": "held-out ratio (solid) vs train ratio (dashed) per seed"},
    "gen16": {"family": "gen16_multicity", "glob": "seed*.json", "kind": "generalist",
              "note": "held-out CITY (Gdansk) ratio (solid) vs train ratio (dashed)"},
    "gen17": {"family": "gen17_lastiterate", "glob": "seed*.json", "kind": "multiconvoy",
              "note": "annealed tau does not hold the tail; best checkpoints in the gen14 band"},
    "gen18": {"family": "gen18_learnedfollower", "glob": "seed*.json", "kind": "multiconvoy",
              "note": "learned followers: exploitability of the partially-coordinated fleet"},
    "gen19": {"family": "gen19_b1lite1", "glob": "seed*.json", "kind": "b1lite",
              "note": "per-sortie mission-failure vs the pattern-of-life adversary"},
    "gen20": {"family": "gen20_f2", "glob": "seed*.json", "kind": "f2",
              "note": "solid = defender exploitability under the ORACLE BR; dashed = the learned "
                      "antagonist's own exploitation (it reaches 0.81x the oracle)"},
    "gen21": {"family": "gen21_vanilla", "glob": "seed*.json", "kind": "generalist",
              "note": "the vanilla (travel-objective) generalist: held-out Gdansk ratio (solid) "
                      "never approaches the adversarial 1.68; the transfer control"},
    "gen22": {"family": "gen22_rotation", "glob": "seed*.json", "kind": "generalist",
              "note": "held-out ISTANBUL ratio (solid) vs train ratio (dashed): transfer holds "
                      "to the hardest hold-out city"},
    "gen24": {"family": "gen24_distill", "glob": "seed*.json", "kind": "generalist",
              "note": "the overfitting signature: train ratio (dashed) keeps falling while "
                      "held-out (solid) degrades past ~step 100-300; adversarial training "
                      "never shows this shape"},
    "gen25": {"family": "gen25_dr", "glob": "[dv]*_seed?.json", "kind": "generalist",
              "note": "the controls: cost-trained vanilla (2 seeds) and domain randomisation, "
                      "held-out ratio (solid) vs train (dashed); both sit at or above "
                      "random-init level throughout"},
    "gen23": {"family": "gen23_c1", "glob": "*_seed*.json", "kind": "c1",
              "note": "ERB-seeded (ALNS demonstrations) vs cold arms: the seeding HURTS; "
                      "deterministic demos bias a mixed-strategy learner"},
}


def has_chart(gen_id: str) -> bool:
    return gen_id in _FAMILY_SPECS or gen_id == "zst0"


def load_gen_chart(gen_id: str) -> dict[str, Any]:
    """Returns {kind, note, series: [...], refs: {...}, sources: [paths]} or {error}."""
    if gen_id == "zst0":
        return _load_zst0()
    spec = _FAMILY_SPECS.get(gen_id)
    if spec is None:
        return {"error": "no chart specification"}
    d = RUNS_DIR / spec["family"]
    files = sorted(d.glob(spec["glob"])) if d.is_dir() else []
    if not files:
        return {"error": f"no run JSONs found under models/runs/{spec['family']}"}

    kind = spec["kind"]
    series: list[dict[str, Any]] = []
    refs: dict[str, float] = {}
    sources: list[str] = []

    for path in files:
        rf = read_json(path)
        if not rf.ok:
            continue
        data = rf.data
        sources.append(str(path.relative_to(RUNS_DIR)))
        label = path.stem

        if kind in ("multiconvoy", "multiconvoy_arms"):
            result = multiconvoy_result(data)
            if not result:
                continue
            hs = HistorySeries.from_rows(result["history"], MULTICONVOY_HISTORY_FIELDS)
            series.append({
                "label": label,
                "x": hs.col("sortie"),
                "y": hs.col("expl_tap"),
                "best": result.get("best_tap"),
                "best_at": result.get("best_tap_sortie"),
                "arm": label.split("_seed")[0] if kind == "multiconvoy_arms" else "",
            })
            if "loss_mixed" in data:
                refs["equilibrium"] = data["loss_mixed"]
            if isinstance(data.get("baselines"), dict):
                refs.update({k: v for k, v in data["baselines"].items() if isinstance(v, (int, float))})

        elif kind == "interdiction":
            arms = data.get("arms", {})
            for arm_name in ("vanilla", "sacred"):
                arm = arms.get(arm_name)
                if not isinstance(arm, dict) or "history" not in arm:
                    continue
                hs = HistorySeries.from_rows(arm["history"], INTERDICTION_HISTORY_FIELDS)
                series.append({
                    "label": f"{arm_name} {label.split('_')[-1]}",
                    "x": hs.col("sortie"),
                    "y": hs.col("expl_tap"),
                    "arm": arm_name,
                })
            refs.setdefault("equilibrium", data.get("loss_mixed"))
            if isinstance(arms.get("shortest_path"), dict):
                refs.setdefault("shortest_path", arms["shortest_path"].get("expl_tap"))
            if isinstance(arms.get("uniform"), dict):
                refs.setdefault("uniform", arms["uniform"].get("expl_tap"))

        elif kind == "generalist":
            hs = HistorySeries.from_rows(data["history"], GENERALIST_HISTORY_FIELDS)
            series.append({
                "label": label,
                "x": hs.col("sortie"),
                "y": hs.col("test_ratio"),
                "y2": hs.col("train_ratio"),
                "best": data.get("best_test_ratio"),
            })

        elif kind == "f2":
            hs = HistorySeries.from_rows(data["history"], F2_HISTORY_FIELDS)
            series.append({
                "label": label,
                "x": hs.col("sortie"),
                "y": hs.col("defender_expl_oracle"),
                "y2": hs.col("learned_antag_exploit"),
                "best": data.get("best_defender_expl"),
                "best_at": data.get("best_at"),
            })
            for name, key in (("equilibrium", "eq"), ("alns", "alns"),
                              ("gen14 headline", "oracle_trained_ref")):
                v = data.get(key)
                if isinstance(v, (int, float)):
                    refs.setdefault(name, v)

        elif kind == "c1":
            hs = HistorySeries.from_rows(data["history"], C1_HISTORY_FIELDS)
            arm = "seeded" if data.get("erb") else "cold"
            series.append({
                "label": f"{arm} seed {data.get('seed', '?')}",
                "x": hs.col("sortie"),
                "y": hs.col("tap"),
                "best": data.get("best_tap"),
                "arm": arm,
            })
            if isinstance(data.get("eq"), (int, float)):
                refs.setdefault("equilibrium", data["eq"])
            if isinstance(data.get("bar"), (int, float)):
                refs.setdefault("competence bar", data["bar"])

        elif kind == "b1lite":
            hs = HistorySeries.from_rows(data["history"], B1LITE_HISTORY_FIELDS)
            series.append({
                "label": label,
                "x": hs.col("sortie"),
                "y": hs.col("eval_loss"),
                "best": data.get("best"),
            })
            for k in ("static_det", "iid_eq", "history_opt"):
                v = (data.get("refs") or {}).get(k)
                if isinstance(v, (int, float)):
                    refs[k] = v

    refs = {k: v for k, v in refs.items() if isinstance(v, (int, float))}
    if not series:
        return {"error": "run JSONs present but unreadable (possibly mid-write); try again"}
    return {"kind": kind, "note": spec["note"], "series": series, "refs": refs, "sources": sources}


# the campaign story tags, in preference order: the flat delivery-rate plateau
# is the chapter's central evidence; Q-spread collapse and reward are fallbacks
_TB_PREFERRED_TAGS = (
    "Episode/Delivery_Rate",
    "Value/Protagonist_Q_Spread",
    "Episode/Protagonist_Reward",
)


def _short_tb_label(rel: str) -> str:
    return rel if len(rel) <= 34 else rel[:18] + "…" + rel[-13:]


def load_tb_chart(gen_id: str, tb_runs: tuple[str, ...]) -> dict[str, Any]:
    """Campaign-era TensorBoard scalars, read lazily in a worker.

    One comparable tag per chart (the first preferred tag found); every
    events file under each listed run directory becomes one series."""
    try:
        from tensorboard.backend.event_processing.event_accumulator import (  # noqa: PLC0415
            EventAccumulator,
        )
    except ImportError:
        return {"error": "tensorboard reader not installed in this venv"}

    series: list[dict[str, Any]] = []
    sources: list[str] = []
    used_tag: str | None = None
    for run in tb_runs:
        d = TB_DIR / run
        if not d.is_dir():
            continue
        for ev in sorted(d.rglob("events.out.tfevents.*"))[:4]:
            try:
                acc = EventAccumulator(str(ev.parent), size_guidance={"scalars": 0})
                acc.Reload()
                tags = acc.Tags().get("scalars", [])
                tag = next((t for t in _TB_PREFERRED_TAGS if t in tags), None)
                if tag is None or (used_tag is not None and tag != used_tag):
                    continue
                used_tag = tag
                sc = acc.Scalars(tag)
                rel = str(ev.parent.relative_to(TB_DIR))
                series.append({
                    "label": _short_tb_label(rel),
                    "x": [p.step for p in sc],
                    "y": [p.value for p in sc],
                })
                sources.append(rel)
                if len(series) >= 6:
                    break
            except Exception:
                continue  # unreadable events file: skip, never crash the card
        if len(series) >= 6:
            break
    if not series:
        return {"error": "no readable tfevents with a known scalar tag under logs/tb_runs"}
    return {
        "kind": "tb",
        "tag": used_tag,
        "note": f"TensorBoard scalar {used_tag} per training run (bold = rolling mean, faint = raw)",
        "series": series,
        "refs": {},
        "sources": sources,
        "source_root": "logs/tb_runs/",
    }


def _load_zst0() -> dict[str, Any]:
    rf = read_json(RUNS_DIR / "zst_step0.json")
    if not rf.ok:
        return {"error": "models/runs/zst_step0.json unavailable"}
    d = rf.data
    tr = d.get("transfer", {})
    ri = d.get("random_init_reference", {})
    bars = [
        ("shortest (anchor)", tr.get("shortest")),
        ("uniform (anchor)", tr.get("uniform")),
        ("transferred policy", tr.get("expl")),
        ("random-init net", ri.get("expl")),
        ("equilibrium (anchor)", tr.get("equilibrium")),
    ]
    bars = [(k, v) for k, v in bars if isinstance(v, (int, float))]
    return {
        "kind": "bars",
        "note": "held-out OD 110-135: the transferred policy loses to an untrained net",
        "series": [{"label": k, "y": v} for k, v in bars],
        "refs": {},
        "sources": ["zst_step0.json"],
    }
