"""The Objectives tab: six exhibits, each pairing the verbatim objective text
from the assessed literature review (quoted via THESIS_STORYLINE.md, provenance
tested) with an interactive demonstration of how the project met it."""

from __future__ import annotations

import numpy as np
import yaml
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QScrollArea,
    QSlider,
    QSplitter,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from .. import theme
from ..sacred_bridge import gen_charts
from ..sacred_bridge import maps as maps_bridge
from ..sacred_bridge import oracle as oracle_bridge
from ..sacred_bridge import policies
from ..sacred_bridge.paths import DATA_DIR, RUNS_DIR, SACRED_ROOT
from ..sacred_bridge.runs import (
    GENERALIST_HISTORY_FIELDS,
    MULTICONVOY_HISTORY_FIELDS,
    HistorySeries,
    multiconvoy_result,
    read_json,
)
from ..widgets.cards import Card, EraBadge, StateLabel
from ..widgets.charts import ChartWidget
from ..widgets.export import Exportable, export_widget_grab
from ..widgets.mapview import MapView
from ..workers import run_in_background


def _exhibit_data() -> dict:
    return yaml.safe_load((DATA_DIR / "exhibits.yaml").read_text())


class ExhibitBase(QWidget):
    """Scrollable exhibit page with the verbatim objective header."""

    def __init__(self, obj_quote: str, verdict: str, parent=None):
        super().__init__(parent)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        outer.addWidget(scroll)
        host = QWidget()
        self.lay = QVBoxLayout(host)
        self.lay.setContentsMargins(4, 0, 12, 12)
        self.lay.setSpacing(10)
        scroll.setWidget(host)

        head = Card()
        q = QLabel(obj_quote)
        q.setTextFormat(Qt.MarkdownText)
        q.setWordWrap(True)
        q.setStyleSheet(
            f"font-size: 14px; font-style: italic; background: {theme.PAGE};"
            f"border-left: 3px solid {theme.BLUE}; border-radius: 4px; padding: 8px 10px;")
        head.layout_().addWidget(q)
        src = QLabel("the promise, verbatim · THESIS_STORYLINE.md (literature review §2.2)")
        src.setStyleSheet(f"color: {theme.INK_MUTED}; font-size: 10px;")
        head.layout_().addWidget(src)
        v = QLabel(verdict)
        v.setWordWrap(True)
        v.setStyleSheet("font-weight: 600; font-size: 13px;")
        head.layout_().addWidget(v)
        self.lay.addWidget(head)
        self._built = False

    def build(self) -> None:  # lazy heavy work on first show
        pass

    def card(self, title: str = "") -> Card:
        c = Card()
        if title:
            t = QLabel(title)
            t.setProperty("h3", True)
            c.layout_().addWidget(t)
        self.lay.addWidget(c)
        return c

    def add_quote_cards(self, key: str) -> None:
        """Render this exhibit's provenance-tested ledger quote cards
        (data/exhibits.yaml `quote_cards`, verbatim-enforced by tests)."""
        for spec in _exhibit_data().get("quote_cards", {}).get(key, []):
            c = self.card(spec["title"])
            for item in spec["items"]:
                lab = QLabel(item["label"])
                lab.setStyleSheet(
                    f"color: {theme.INK_SECONDARY}; font-size: 11px; font-weight: 700;"
                    "text-transform: uppercase; letter-spacing: 0.04em;")
                body = QLabel(item["quote"])
                body.setTextFormat(Qt.MarkdownText)
                body.setWordWrap(True)
                body.setTextInteractionFlags(Qt.TextSelectableByMouse)
                body.setStyleSheet(
                    f"font-size: 13px; color: {theme.INK}; background: {theme.PAGE};"
                    f"border-left: 3px solid {theme.BASELINE}; border-radius: 4px;"
                    "padding: 8px 10px;")
                src = QLabel("ledger: " + item.get("ledger", spec["ledger"]))
                src.setStyleSheet(f"color: {theme.INK_MUTED}; font-size: 10px;")
                c.layout_().addWidget(lab)
                c.layout_().addWidget(body)
                c.layout_().addWidget(src)


# ===================================================================== Obj 1

class Obj1Exhibit(ExhibitBase):
    """The game made tangible: mixture slider vs live exploitability."""

    def build(self) -> None:
        if self._built:
            return
        self._built = True
        self._inst = None

        c = self.card("Slide from deterministic to calibrated mixing (33-71, hard interception)")
        self.slider = QSlider(Qt.Horizontal)
        self.slider.setRange(0, 200)
        self.slider.setValue(0)
        self.slider.valueChanged.connect(self._update)
        c.layout_().addWidget(self.slider)
        lab_row = QWidget()
        lr = QHBoxLayout(lab_row)
        lr.setContentsMargins(0, 0, 0, 0)
        for txt, align in (("deterministic (shortest path)", Qt.AlignLeft),
                           ("uniform noise", Qt.AlignCenter),
                           ("equilibrium (calibrated)", Qt.AlignRight)):
            l = QLabel(txt)
            l.setAlignment(align)
            l.setStyleSheet(f"color: {theme.INK_MUTED}; font-size: 10px;")
            lr.addWidget(l)
        c.layout_().addWidget(lab_row)
        self.readout = QLabel("Solving the game…")
        self.readout.setWordWrap(True)
        c.layout_().addWidget(self.readout)
        self.curve = ChartWidget(title="obj1-exploitability-curve", height=2.6, width=7.0)
        c.layout_().addWidget(self.curve)
        self.saddle = ChartWidget(title="obj1-attacker-options", height=2.6, width=7.0)
        c2 = self.card("The attacker's options against your mixture")
        c2.layout_().addWidget(self.saddle)
        note = QLabel(
            "At the equilibrium every attacker option on the support yields the same "
            "interception: the mixture makes the adversary indifferent. That saddle point "
            "is the solution concept every SACRED result is scored against.")
        note.setWordWrap(True)
        c2.layout_().addWidget(note)

        self.add_quote_cards("obj1")
        run_in_background(
            oracle_bridge.build_instance, "kaliningrad", "33", "71", 1, 1, 8, None,
            on_done=self._ready, on_fail=lambda tb: self.readout.setText("Solve failed."))

    def _ready(self, inst) -> None:
        self._inst = inst
        R = inst.n_routes
        short = np.zeros(R)
        short[int(np.argmin(inst.route_costs))] = 1.0
        self._d_short = short
        self._d_uniform = np.full(R, 1.0 / R)
        self._d_eq = inst.sc_defender
        # precompute the exploitability curve along the slider path
        xs, es = [], []
        for t in range(0, 201, 2):
            d = self._mix(t)
            _, e = inst.exploitability_routes(d)
            xs.append(t)
            es.append(e)
        self._curve = (xs, es)
        self._update()

    def _mix(self, t: int) -> np.ndarray:
        if t <= 100:
            a = t / 100.0
            d = (1 - a) * self._d_short + a * self._d_uniform
        else:
            a = (t - 100) / 100.0
            d = (1 - a) * self._d_uniform + a * self._d_eq
        return d / d.sum()

    def _update(self) -> None:
        if self._inst is None:
            return
        inst = self._inst
        t = self.slider.value()
        d = self._mix(t)
        j, e = inst.exploitability_routes(d)
        self.readout.setText(
            f"Your mixture's interception under the best response: <b>{e:.3f}</b> "
            f"(deterministic {inst.sc_loss_det:.3f}, equilibrium {inst.sc_value:.3f}) · computed live")
        ax = self.curve.clear()
        xs, es = self._curve
        ax.plot(xs, es, color=theme.BLUE, linewidth=2.0)
        ax.plot([t], [e], "o", color=theme.INK, markersize=7, zorder=5)
        ax.axhline(inst.sc_value, color=theme.STRATEGY_COLOURS["equilibrium"],
                   linestyle=":", linewidth=1.0)
        ax.annotate(f"equilibrium {inst.sc_value:.3f}", xy=(0.02, inst.sc_value),
                    xycoords=("axes fraction", "data"), fontsize=8,
                    color=theme.STRATEGY_COLOURS["equilibrium"], va="bottom")
        ax.set_xticks([0, 100, 200], ["deterministic", "uniform", "equilibrium"])
        ax.set_ylabel("exploitability")
        self.curve.set_caption("interception of your mixture under the oracle best response", "live")
        self.curve.redraw()

        ax2 = self.saddle.clear()
        yields = d @ inst.game.payoff
        cols = [theme.STRATEGY_COLOURS["attacker"] if k == j else theme.BASELINE
                for k in range(len(yields))]
        ax2.bar(range(len(yields)), yields, color=cols, width=0.8)
        ax2.axhline(inst.sc_value, color=theme.STRATEGY_COLOURS["equilibrium"],
                    linestyle=":", linewidth=1.0)
        ax2.set_xlabel("attacker option (interdiction set)")
        ax2.set_ylabel("expected interception")
        self.saddle.set_caption(
            "orange = the attacker's best response to your current mixture", "live")
        self.saddle.redraw()


# ===================================================================== Obj 2

class Obj2Exhibit(ExhibitBase):
    """The city pipeline and the environment itself."""

    def build(self) -> None:
        if self._built:
            return
        self._built = True
        c = self.card("Any city, its arterial extraction and intrinsic threat map")
        row = QWidget()
        rl = QHBoxLayout(row)
        rl.setContentsMargins(0, 0, 0, 0)
        self.city_combo = QComboBox()
        for city in maps_bridge.available_cities():
            self.city_combo.addItem(maps_bridge.CITY_LABELS.get(city, city), city)
        self.city_combo.currentIndexChanged.connect(self._load_city)
        rl.addWidget(self.city_combo)
        self.stats = QLabel("")
        self.stats.setStyleSheet(f"color: {theme.INK_SECONDARY};")
        rl.addWidget(self.stats, 1)
        c.layout_().addWidget(row)
        self.map = MapView()
        self.map.setMinimumHeight(420)
        c.layout_().addWidget(self.map)
        cap = QLabel("threat map computed live: edge length mapped into the band (0.15, 0.95), "
                     "normalised over the whole graph (the env's absolute_vuln_norm)")
        cap.setStyleSheet(f"color: {theme.LIVE_ACCENT}; font-size: 10px; font-weight: 600;")
        c.layout_().addWidget(cap)

        fig_card = self.card("The extraction pipeline (arterial filter + 30 m consolidation)")
        for f in ("assets/kaliningrad_filter_compare.png",
                  "assets/kaliningrad_consolidated_compare.png"):
            p = SACRED_ROOT / f
            if p.is_file():
                pl = QLabel()
                pm = QPixmap(str(p))
                if not pm.isNull():
                    pl.setPixmap(pm.scaledToWidth(820, Qt.SmoothTransformation))
                    fig_card.layout_().addWidget(pl)
                capf = QLabel(f"figure: {f}")
                capf.setStyleSheet(f"color: {theme.INK_MUTED}; font-size: 10px;")
                fig_card.layout_().addWidget(capf)
        self._load_city()

    def _load_city(self) -> None:
        city = self.city_combo.currentData()
        if not city:
            return
        self.stats.setText("loading…")
        run_in_background(self._city_worker, city,
                          on_done=self._city_ready,
                          on_fail=lambda tb: self.stats.setText("failed to load"))

    @staticmethod
    def _city_worker(city: str):
        cm = maps_bridge.load_city(city)
        G = cm.graph()
        from ..sacred_bridge.paths import ensure_sacred_importable
        ensure_sacred_importable()
        from src.baselines import interdiction_oracle as io
        all_edges = [frozenset({u, v}) for u, v in G.edges() if u != v]
        vuln = io.length_band_vulnerability(G, all_edges, band=(0.15, 0.95),
                                            weight="w", norm_edges=G.edges())
        return city, cm, vuln, G.number_of_nodes(), G.number_of_edges()

    def _city_ready(self, result) -> None:
        city, cm, vuln, n_nodes, n_edges = result
        if city != self.city_combo.currentData():
            return
        self.map.set_city(cm)
        self.map.show_instance([], vuln, "", "")
        self.map.fit_all()
        registered = city in maps_bridge.REGISTERED_CITIES
        self.stats.setText(
            f"{n_nodes} nodes · {n_edges} edges"
            + ("" if registered else " · not oracle-screened; no banked results"))


# ===================================================================== Obj 3

_OBJ3_FAMILIES = {
    "gen13_lock (the lock, 3 seeds)": ("gen13_lock", "seed*.json", "post-fix"),
    "gen14_evidence (n=10)": ("gen14_evidence", "mc_seed*.json", "post-fix"),
    "gen17_lastiterate (annealed tau, fails to hold)": ("gen17_lastiterate", "seed*.json", "post-fix"),
    "gen18_learnedfollower (the coordination boundary)": ("gen18_learnedfollower", "seed*.json", "post-fix"),
    "gen09_multiconvoy (the pre-fix lock)": ("gen09_multiconvoy", "headline_seed*.json", "pre-fix"),
}


class Obj3Exhibit(ExhibitBase):
    """Training dynamics replayed: TAP, drift, temperatures, FP cycling."""

    def build(self) -> None:
        if self._built:
            return
        self._built = True
        c = self.card("Training dynamics, replayed from the run artefacts")
        row = QWidget()
        rl = QHBoxLayout(row)
        rl.setContentsMargins(0, 0, 0, 0)
        self.family_combo = QComboBox()
        for label in _OBJ3_FAMILIES:
            self.family_combo.addItem(label)
        self.family_combo.currentIndexChanged.connect(self._load_family)
        rl.addWidget(self.family_combo)
        self.era_badge_host = QHBoxLayout()
        rl.addLayout(self.era_badge_host)
        rl.addStretch(1)
        c.layout_().addWidget(row)
        self.family_state = StateLabel("Loading run artefacts…", "loading")
        c.layout_().addWidget(self.family_state)
        self.traj = ChartWidget(title="obj3-tap", height=3.0, width=7.4)
        c.layout_().addWidget(self.traj)
        self.temps = ChartWidget(title="obj3-temperatures", height=2.4, width=7.4)
        c.layout_().addWidget(self.temps)

        anim_card = self.card("Fictitious-play cycling: the policy's occupancy distribution, eval by eval")
        bar_row = QWidget()
        brl = QHBoxLayout(bar_row)
        brl.setContentsMargins(0, 0, 0, 0)
        self.play_btn = QPushButton("▶ Replay drift (Space)")
        self.play_btn.clicked.connect(self.toggle_play)
        brl.addWidget(self.play_btn)
        self.anim_label = QLabel("")
        brl.addWidget(self.anim_label)
        brl.addStretch(1)
        anim_card.layout_().addWidget(bar_row)
        self.anim_chart = ChartWidget(title="obj3-fp-animation", height=2.8, width=7.4)
        anim_card.layout_().addWidget(self.anim_chart)

        erb_card = self.card("ERB bootstrapping, measured (gen23: seeded vs cold)")
        self.erb_state = StateLabel("Loading the gen23 run artefacts…", "loading")
        erb_card.layout_().addWidget(self.erb_state)
        self.erb_chart = ChartWidget(title="obj3-erb-gen23", height=2.8, width=7.4)
        erb_card.layout_().addWidget(self.erb_chart)
        self.add_quote_cards("obj3")
        run_in_background(gen_charts.load_gen_chart, "gen23",
                          on_done=self._erb_ready,
                          on_fail=lambda tb: self.erb_state.setText("gen23 artefacts failed to load."))

        self._pol_hist = None
        self._anim_i = 0
        self._timer = QTimer(self)
        self._timer.setInterval(600)
        self._timer.timeout.connect(self._anim_tick)
        self._load_family()

    def _erb_ready(self, payload: dict) -> None:
        if "error" in payload:
            self.erb_state.setText(f"Not available: {payload['error']}")
            return
        self.erb_state.hide()
        ax = self.erb_chart.clear()
        for s in payload["series"]:
            seeded = s.get("arm") == "seeded"
            colour = theme.STRATEGY_COLOURS["vanilla"] if seeded else theme.STRATEGY_COLOURS["sacred"]
            ax.plot(s["x"], s["y"], color=colour, linewidth=1.6, alpha=0.8,
                    label=s["label"] if s["label"].endswith("seed 0") else None)
        refs = payload.get("refs", {})
        if "competence bar" in refs:
            ax.axhline(refs["competence bar"], color=theme.INK_MUTED, linestyle="--", linewidth=1.1)
            ax.annotate(f"competence bar {refs['competence bar']:.2f}",
                        xy=(1.0, refs["competence bar"]), xycoords=("axes fraction", "data"),
                        fontsize=8, ha="right", va="bottom", color=theme.INK_MUTED)
        if "equilibrium" in refs:
            ax.axhline(refs["equilibrium"], color=theme.STRATEGY_COLOURS["equilibrium"],
                       linestyle=":", linewidth=1.0)
            ax.annotate(f"equilibrium {refs['equilibrium']:.3f}", xy=(0.0, refs["equilibrium"]),
                        xycoords=("axes fraction", "data"), fontsize=8, va="bottom",
                        color=theme.STRATEGY_COLOURS["equilibrium"])
        ax.set_xlabel("sortie")
        ax.set_ylabel("exploitability (TAP)")
        ax.legend(fontsize=8.5)
        self.erb_chart.set_caption(
            "yellow = ERB-seeded (ALNS demonstrations), blue = cold: the cold arms dive under "
            "the bar, the seeded arms never do · source: models/runs/gen23_c1 "
            "(gen23_c1_erb.md)", "ledger")
        self.erb_chart.redraw()

    def _load_family(self) -> None:
        label = self.family_combo.currentText()
        family, glob, era = _OBJ3_FAMILIES[label]
        while self.era_badge_host.count():
            w = self.era_badge_host.takeAt(0).widget()
            if w:
                w.deleteLater()
        self.era_badge_host.addWidget(EraBadge(era))
        self._timer.stop()
        # the previous family's curves must not linger under the new era badge
        for chart in (self.traj, self.temps, self.anim_chart):
            chart.clear()
            chart.redraw()
        self.family_state.setText("Loading run artefacts…")
        self.family_state.show()
        run_in_background(self._family_worker, family, glob,
                          on_done=lambda result, wanted=label: self._family_ready(result, wanted),
                          on_fail=lambda tb, wanted=label: self._family_failed(wanted))

    def _family_failed(self, wanted: str) -> None:
        if wanted == self.family_combo.currentText():
            self.family_state.setText("Run artefacts failed to load for this family.")
            self.family_state.show()

    @staticmethod
    def _family_worker(family: str, glob: str):
        out = []
        pol_hist = None
        d = RUNS_DIR / family
        for p in sorted(d.glob(glob)):
            rf = read_json(p)
            if not rf.ok:
                continue
            res = multiconvoy_result(rf.data)
            if not res:
                continue
            hs = HistorySeries.from_rows(res["history"], MULTICONVOY_HISTORY_FIELDS)
            out.append({
                "label": p.stem,
                "sortie": hs.col("sortie"),
                "expl_tap": hs.col("expl_tap"),
                "expl": hs.col("expl"),
                "alpha_leader": hs.col("alpha_leader"),
                "alpha_foll": hs.col("alpha_foll"),
                "stack": hs.col("stack_rate"),
                "follow": hs.col("follow_rate"),
                "best": res.get("best_tap"),
                "best_at": res.get("best_tap_sortie"),
            })
            if pol_hist is None and res.get("pol_hist"):
                pol_hist = res["pol_hist"]
        refs = {}
        rf = read_json(next(iter(sorted(d.glob(glob))), d / "none"))
        if rf.ok and isinstance(rf.data.get("loss_mixed"), (int, float)):
            refs["equilibrium"] = rf.data["loss_mixed"]
        return family, out, pol_hist, refs

    def _family_ready(self, result, wanted: str = "") -> None:
        family, series, pol_hist, refs = result
        if wanted and wanted != self.family_combo.currentText():
            return  # the combo moved on; a pre-fix payload must not sit under a post-fix badge
        if not series:
            self.family_state.setText("No run artefacts found for this family.")
            self.family_state.show()
            return
        self.family_state.hide()
        self._pol_hist = pol_hist
        self._anim_i = 0
        palette = theme.CATEGORICAL
        ax = self.traj.clear()
        many = len(series) > 6
        for i, s in enumerate(series):
            colour = theme.BLUE if many else palette[i % len(palette)]
            ax.plot(s["sortie"], s["expl_tap"], color=colour, alpha=0.55 if many else 1.0,
                    linewidth=1.5, label=None if many else s["label"])
            if s["best"] is not None and s["best_at"] is not None:
                ax.plot([s["best_at"]], [s["best"]], "o", color=colour, markersize=6,
                        markeredgecolor="white", zorder=5)
        if "equilibrium" in refs:
            ax.axhline(refs["equilibrium"], color=theme.STRATEGY_COLOURS["equilibrium"],
                       linestyle=":", linewidth=1.0)
        ax.set_xlabel("sortie")
        ax.set_ylabel("exploitability (TAP)")
        if not many:
            ax.legend(fontsize=8)
        self.traj.set_caption(
            f"dots = best checkpoints (the deployable object); the later drift toward uniform "
            f"is the disclosed last-iterate FP cycling · source: models/runs/{family}", "ledger")
        self.traj.redraw()

        ax2 = self.temps.clear()
        for i, s in enumerate(series[:6]):
            colour = palette[i % len(palette)]
            ax2.plot(s["sortie"], s["alpha_leader"], color=colour, linewidth=1.4)
            if any(v for v in s["alpha_foll"]):
                ax2.plot(s["sortie"], s["alpha_foll"], color=colour, linewidth=1.1,
                         linestyle="--", alpha=0.7)
        ax2.set_xlabel("sortie")
        ax2.set_ylabel("SAC temperature α")
        self.temps.set_caption("solid = leader alpha, dashed = follower alpha", "ledger")
        self.temps.redraw()
        self._draw_anim_frame()

    def toggle_play(self) -> None:
        if self._timer.isActive():
            self._timer.stop()
            self.play_btn.setText("▶ Replay drift (Space)")
        else:
            if not self._pol_hist:
                self.anim_label.setText("no pol_hist saved for this family")
                return
            self._timer.start()
            self.play_btn.setText("⏸ Pause (Space)")

    def _anim_tick(self) -> None:
        if not self._pol_hist:
            return
        self._anim_i = (self._anim_i + 1) % len(self._pol_hist)
        self._draw_anim_frame()

    def _draw_anim_frame(self) -> None:
        if not self._pol_hist:
            self.anim_label.setText("no pol_hist saved for this family")
            return
        dist = np.asarray(self._pol_hist[self._anim_i], dtype=float)
        ax = self.anim_chart.clear()
        ax.bar(range(len(dist)), dist, color=theme.BLUE, width=1.0)
        ax.set_xlabel("occupancy (joint fleet placement)")
        ax.set_ylabel("probability")
        ax.set_ylim(0, max(0.35, float(dist.max()) * 1.15))
        self.anim_label.setText(f"eval {self._anim_i}/{len(self._pol_hist) - 1} (seed 0)")
        self.anim_chart.set_caption(
            "the policy's mixed strategy over occupancies, per eval: concentrate onto the "
            "hedge, then over-train toward uniform", "ledger")
        self.anim_chart.redraw()


# ===================================================================== Obj 4

class Obj4Exhibit(ExhibitBase):
    """The design-space explorer + the live acquisition race."""

    def build(self) -> None:
        if self._built:
            return
        self._built = True
        data = _exhibit_data()

        c = self.card("The surrogate: predicted vs true design quality (F3, 450 designs)")
        self.scatter = ChartWidget(title="obj4-surrogate-scatter", height=3.2, width=7.2)
        c.layout_().addWidget(self.scatter)
        self.design_label = QLabel("Click a point to see that design as a game on the map below.")
        self.design_label.setWordWrap(True)
        c.layout_().addWidget(self.design_label)
        self.design_map = MapView()
        self.design_map.setMinimumHeight(360)
        self.design_map.hide()  # appears with the first clicked design
        c.layout_().addWidget(self.design_map)
        self.design_caption = QLabel("")
        self.design_caption.setWordWrap(True)
        self.design_caption.setStyleSheet(
            f"color: {theme.LIVE_ACCENT}; font-size: 10px; font-weight: 600;")
        c.layout_().addWidget(self.design_caption)
        self._design_seq = 0
        self._design_city_loaded = False

        c2 = self.card("The acquisition loop, raced live against random search")
        row = QWidget()
        rl = QHBoxLayout(row)
        rl.setContentsMargins(0, 0, 0, 0)
        self.race_btn = QPushButton("Run the loop live")
        self.race_btn.setProperty("accent", True)
        self.race_btn.clicked.connect(self._run_race)
        rl.addWidget(self.race_btn)
        self.race_label = QLabel("Press “Run the loop live” to race the surrogate against random search.")
        rl.addWidget(self.race_label, 1)
        c2.layout_().addWidget(row)
        self.race_chart = ChartWidget(title="obj4-acquisition-race", height=3.0, width=7.2)
        c2.layout_().addWidget(self.race_chart)

        c3 = self.card("D1 (banked) and D3 (the composite)")
        self.banked_chart = ChartWidget(title="obj4-d1-banked", height=2.6, width=7.2)
        c3.layout_().addWidget(self.banked_chart)
        d3_label = QLabel(
            "D3, the composite over the TRAINED generalist: held-out Spearman <b>0.959</b>; "
            "policy-target vs oracle-target rank correlation <b>0.768</b>: designing against "
            "the deployed policy differs measurably from designing against the equilibrium "
            "abstraction, and only the RL + surrogate loop can do the former.")
        d3_label.setWordWrap(True)
        c3.layout_().addWidget(d3_label)
        d3_src = QLabel("ledger: experiments/d3_composite.md · artefact: models/runs/d3_composite.json")
        d3_src.setStyleSheet(f"color: {theme.INK_MUTED}; font-size: 10px;")
        c3.layout_().addWidget(d3_src)
        self.add_quote_cards("obj4")

        run_in_background(self._load_worker, on_done=self._loaded,
                          on_fail=lambda tb: self.design_label.setText("artefacts unavailable"))

    @staticmethod
    def _load_worker():
        f3 = read_json(RUNS_DIR / "sbo_placement_demo.json")
        d1 = read_json(RUNS_DIR / "d1_sbo_loop.json")
        return f3.data, d1.data

    def _loaded(self, result) -> None:
        f3, d1 = result
        self._f3 = f3
        if f3:
            rows = f3["test_rows"]
            true = [r["true"] for r in rows]
            pred = [r["pred"] for r in rows]
            ax = self.scatter.clear()
            self._sc = ax.scatter(true, pred, s=26, c=theme.BLUE, alpha=0.7, picker=5)
            lim = [min(true + pred), max(true + pred)]
            ax.plot(lim, lim, color=theme.BASELINE, linewidth=1.0, linestyle="--")
            ax.set_xlabel("true equilibrium exploitability of the design")
            ax.set_ylabel("surrogate prediction")
            self.scatter.set_caption(
                "held-out designs · banked: RMSE 0.0222, Spearman 0.894, argmin regret 0.0000 "
                "(f3_sbo_demonstrator.md; artefact sbo_placement_demo.json)", "ledger")
            self.scatter.canvas.mpl_connect("pick_event", self._picked)
            self.scatter.redraw()
            self._test_rows = rows
        if d1:
            ax = self.banked_chart.clear()
            sbo = np.median(np.asarray(d1["sbo_curves"]), axis=0)
            rnd = np.median(np.asarray(d1["random_curves"]), axis=0)
            x = range(1, len(sbo) + 1)
            ax.plot(x, sbo, color=theme.BLUE, linewidth=2.0, label="SBO (banked, D1)")
            ax.plot(x, rnd, color=theme.STRATEGY_COLOURS["uniform"], linewidth=2.0,
                    label="random search (banked)")
            ax.axhline(d1["true_opt"], color=theme.STRATEGY_COLOURS["equilibrium"],
                       linestyle=":", linewidth=1.0)
            ax.annotate(f"true optimum {d1['true_opt']:.3f}", xy=(0.02, d1["true_opt"]),
                        xycoords=("axes fraction", "data"), fontsize=8, va="bottom",
                        color=theme.STRATEGY_COLOURS["equilibrium"])
            ax.set_xlabel("evaluations")
            ax.set_ylabel("best design found")
            ax.legend(fontsize=8.5)
            self.banked_chart.set_caption(
                "banked D1 medians over 20 repeats: median 32.5 evaluations to the optimum vs "
                "random never (d1_sbo_loop.md; artefact d1_sbo_loop.json)", "ledger")
            self.banked_chart.redraw()

    def _picked(self, event) -> None:
        if not hasattr(self, "_test_rows"):
            return
        i = int(event.ind[0])
        r = self._test_rows[i]
        self.design_label.setText(
            f"Design: OD <b>{r['od']}</b>, fleet N={r['N']} · true {r['true']:.3f}, "
            f"predicted {r['pred']:.3f} · a placement is an (origin base, destination FOB) "
            f"pair; the design objective is the equilibrium mission-failure of the resulting game.")
        self._design_seq += 1
        seq = self._design_seq
        self.design_caption.setText(f"solving the design {r['od']} N={r['N']} live…")
        s, t = str(r["od"]).split("-")
        run_in_background(
            oracle_bridge.build_instance, "kaliningrad", s, t, 1, int(r["N"]), 8, (0.15, 0.95),
            on_done=lambda inst, my=seq: self._design_ready(inst, my),
            on_fail=lambda tb, my=seq: (self.design_caption.setText("design solve failed")
                                        if my == self._design_seq else None))

    def _design_ready(self, inst, seq: int) -> None:
        if seq != self._design_seq:
            return  # another design was clicked meanwhile
        self.design_map.show()
        if not self._design_city_loaded:
            self.design_map.set_city(inst.city_map)
            self._design_city_loaded = True
        self.design_map.show_instance(inst.routes, inst.edge_vuln, inst.s, inst.t)
        marg = np.zeros(inst.n_routes)
        for i, occ in enumerate(inst.occupancies):
            p = inst.mc_defender[i]
            if p > 0:
                for ri, c in enumerate(occ):
                    marg[ri] += p * c / inst.N
        self.design_map.set_route_mixture(list(marg))
        # the map may have been hidden until now; refit once the layout has run
        QTimer.singleShot(0, self.design_map.fit_routes)
        self.design_caption.setText(
            f"computed live · the design {inst.s}-{inst.t} (N={inst.N}) as a game: equilibrium "
            f"mixture drawn; loss_mixed {inst.mc_value:.3f}, loss_det {inst.mc_loss_det:.3f}")

    def _run_race(self) -> None:
        if not getattr(self, "_f3", None):
            return
        self.race_btn.setEnabled(False)
        self.race_label.setText("racing…")
        rows = self._f3["rows"]
        run_in_background(self._race_worker, rows,
                          on_done=self._race_done,
                          on_fail=lambda tb: (self.race_btn.setEnabled(True),
                                              self.race_label.setText("race failed")))

    @staticmethod
    def _race_worker(rows: list, repeats: int = 12, n0: int = 8, budget: int = 60):
        """A live LCB acquisition race over the banked F3 design table.

        Surrogate = ridge regression on the design features (simplified: the
        banked run used a neural surrogate); the 'oracle' values are the
        table's banked true exploitabilities."""
        X = np.array([r["x"] for r in rows], dtype=float)
        y = np.array([r["y"] for r in rows], dtype=float)
        X = (X - X.mean(0)) / (X.std(0) + 1e-9)
        X = np.concatenate([X, np.ones((len(X), 1))], axis=1)
        n = len(y)
        sbo_curves, rnd_curves = [], []
        for rep in range(repeats):
            rng = np.random.default_rng(rep)
            seen = list(rng.choice(n, size=n0, replace=False))
            best = [float(y[seen].min())]
            for _ in range(budget):
                A = X[seen]
                w = np.linalg.solve(A.T @ A + 1e-2 * np.eye(A.shape[1]), A.T @ y[seen])
                mu = X @ w
                resid = float(np.std(y[seen] - A @ w) + 1e-6)
                lcb = mu - 1.0 * resid
                lcb[seen] = np.inf
                pick = int(np.argmin(lcb))
                seen.append(pick)
                best.append(min(best[-1], float(y[pick])))
            sbo_curves.append(best)
            rng2 = np.random.default_rng(1000 + rep)
            order = rng2.permutation(n)
            rbest, cur = [], np.inf
            for i in range(n0 + budget):
                cur = min(cur, float(y[order[i]]))
                if i >= n0 - 1:
                    rbest.append(cur)
            rnd_curves.append(rbest)
        return (np.median(np.asarray(sbo_curves), axis=0),
                np.median(np.asarray(rnd_curves), axis=0),
                float(y.min()))

    def _race_done(self, result) -> None:
        sbo, rnd, opt = result
        self.race_btn.setEnabled(True)
        self.race_label.setText("done (12 repeats, seeds 0-11)")
        n0 = 8  # both methods start after the same 8 seed evaluations
        ax = self.race_chart.clear()
        ax.plot(range(n0, n0 + len(sbo)), sbo, color=theme.BLUE, linewidth=2.0,
                label="surrogate-guided (live)")
        ax.plot(range(n0, n0 + len(rnd)), rnd, color=theme.STRATEGY_COLOURS["uniform"],
                linewidth=2.0, label="random search (live)")
        ax.axhline(opt, color=theme.STRATEGY_COLOURS["equilibrium"], linestyle=":", linewidth=1.0)
        ax.annotate(f"table optimum {opt:.3f}", xy=(0.02, opt),
                    xycoords=("axes fraction", "data"), fontsize=8, va="bottom",
                    color=theme.STRATEGY_COLOURS["equilibrium"])
        ax.set_xlabel("evaluations")
        ax.set_ylabel("best design found (median of 12 repeats)")
        ax.legend(fontsize=8.5)
        self.race_chart.set_caption(
            "ridge surrogate re-fitted live over the banked F3 design table "
            "(simplified surrogate; the banked D1 loop below used the neural one)", "live")
        self.race_chart.redraw()


# ===================================================================== Obj 5

class Obj5Exhibit(ExhibitBase):
    """The ladder raced live + the gen12 disruption sweep curves."""

    def build(self) -> None:
        if self._built:
            return
        self._built = True
        self._engines = {}
        self._racing = False

        c = self.card("The ladder, raced on the headline instance (35-159, N=3, K=1)")
        row = QWidget()
        rl = QHBoxLayout(row)
        rl.setContentsMargins(0, 0, 0, 0)
        self.race_btn = QPushButton("▶ Race the strategies (Space)")
        self.race_btn.setProperty("accent", True)
        self.race_btn.clicked.connect(self.toggle_play)
        rl.addWidget(self.race_btn)
        self.race_label = QLabel("Preparing strategies (LP + ALNS + SACRED checkpoints)…")
        rl.addWidget(self.race_label, 1)
        c.layout_().addWidget(row)
        self.race_chart = ChartWidget(title="obj5-ladder-race", height=3.4, width=7.4)
        c.layout_().addWidget(self.race_chart)

        c2 = self.card("Varied disruption: the gen12 K and N sweep")
        self.sweep_chart = ChartWidget(title="obj5-gen12-sweeps", height=3.0, width=7.4)
        c2.layout_().addWidget(self.sweep_chart)
        self._draw_sweeps()

        self._timer = QTimer(self)
        self._timer.setInterval(60)
        self._timer.timeout.connect(self._race_tick)
        run_in_background(self._prepare_worker, on_done=self._prepared,
                          on_fail=lambda tb: self.race_label.setText(
                              "preparation failed: " + tb.strip().splitlines()[-1]))

    @staticmethod
    def _prepare_worker():
        from ..game.sortie import SortieEngine
        inst = oracle_bridge.build_instance("kaliningrad", "35", "159", 1, 3, 8, (0.15, 0.95))
        engine = SortieEngine(inst, seed=0)
        specs = {d.key: d for d in engine.defender_specs()}
        assignment, _ = oracle_bridge.alns_plan(inst)
        alns = engine.alns_spec(assignment)
        refs = policies.discover_actors()
        sacred_spec = None
        g14 = [r for r in refs if r.family == "gen14_evidence"]
        if g14:
            pol = policies.load_policy(g14[0], inst)
            occ = inst.route_dist_to_stacked_occ_dist(pol.route_distribution())
            from ..game.sortie import DefenderSpec
            sacred_spec = DefenderSpec("sacred", "SACRED (gen14 banked ensemble)", occ)
        contenders = [("shortest_path", specs["shortest"]), ("alns", alns)]
        if sacred_spec is not None:
            contenders.append(("sacred", sacred_spec))
        contenders.append(("equilibrium", specs["equilibrium"]))
        return inst, engine, contenders

    def _prepared(self, result) -> None:
        self._inst, self._engine, self._contenders = result
        self._stats = {k: {"n": 0, "fail": 0, "hist": []} for k, _ in self._contenders}
        from ..game.sortie import SortieEngine
        self._per_engine = {k: SortieEngine(self._inst, seed=7 + i)
                            for i, (k, _) in enumerate(self._contenders)}
        self.race_label.setText("Ready. Each strategy flies its own sorties against its own "
                                "best-response interdictor; ledger rows shown for the arms "
                                "that cannot be re-flown live.")
        self._draw_race()

    def toggle_play(self) -> None:
        if not hasattr(self, "_contenders"):
            return
        self._racing = not self._racing
        self.race_btn.setText("⏸ Pause (Space)" if self._racing else "▶ Race the strategies (Space)")
        if self._racing:
            self._timer.start()
        else:
            self._timer.stop()

    def _race_tick(self) -> None:
        for key, spec in self._contenders:
            eng = self._per_engine[key]
            att = eng.attacker_specs(spec)[0]  # oracle BR
            for _ in range(4):
                eng.play_sortie(spec, att)
            st = self._stats[key]
            st["n"] = eng.stats.n
            st["hist"] = eng.stats.history
        self._draw_race()
        if self._stats[self._contenders[0][0]]["n"] >= 600:
            self.toggle_play()

    def _draw_race(self) -> None:
        ax = self.race_chart.clear()
        for key, spec in self._contenders:
            colour = theme.STRATEGY_COLOURS.get(key, theme.BLUE)
            hist = self._stats[key]["hist"]
            if hist:
                ax.plot(range(1, len(hist) + 1), hist, color=colour, linewidth=1.8, label=None)
            exact = self._per_engine[key].exploitability(spec)
            ax.axhline(exact, color=colour, linestyle=":", linewidth=1.0, alpha=0.85)
            ax.annotate(f"{key} {exact:.3f}", xy=(1.0, exact),
                        xycoords=("axes fraction", "data"), fontsize=8, ha="right",
                        va="bottom", color=colour)
        # ledger rows that cannot be re-flown live
        rows = _exhibit_data()["headline_ladders"]["multiconvoy"]["rows"]
        van = next((r for r in rows if r["arm"] == "vanilla"), None)
        if van:
            ax.axhline(van["value"], color=theme.STRATEGY_COLOURS["vanilla"], linestyle="--",
                       linewidth=1.2, alpha=0.9)
            ax.annotate(f"vanilla {van['value']} (ledger row, gen14: no checkpoint on disk)",
                        xy=(0.0, van["value"]), xycoords=("axes fraction", "data"), fontsize=8,
                        va="bottom", color=theme.STRATEGY_COLOURS["vanilla"])
        banked = next((r for r in rows if r["arm"] == "sacred"), None)
        if banked:
            ax.annotate(
                f"banked SACRED best-ckpt TAP {banked['value']} [0.246, 0.266] (gen14_evidence.md)",
                xy=(0.0, banked["value"]), xycoords=("axes fraction", "data"), fontsize=8,
                va="top", color=theme.STRATEGY_COLOURS["sacred"])
        ax.set_xlabel("sortie")
        ax.set_ylabel("running mission-failure rate")
        ax.set_ylim(-0.03, 1.03)
        seeds = ", ".join(f"{k} seed {self._per_engine[k].seed}" for k, _ in self._contenders)
        self.race_chart.set_caption(
            "solid = live running estimates; dotted = exact values computed live; dashed = "
            f"the ledger's vanilla row (gen14_evidence.md) · seeds: {seeds}", "live")
        self.race_chart.redraw()

    def _draw_sweeps(self) -> None:
        data = _exhibit_data()["gen12_sweeps"]
        cells_order = ["N=2 K=1", "N=3 K=1", "N=3 K=2", "N=3 K=3", "N=5 K=1"]
        ax = self.sweep_chart.clear()
        for od, marker in (("62-97", "o"), ("35-159", "s")):
            xs, sac, alns, eq = [], [], [], []
            for cname in cells_order:
                cell = next((c for c in data["cells"] if c["od"] == od and c["cell"] == cname), None)
                if cell:
                    xs.append(cname)
                    sac.append(cell["sacred"])
                    alns.append(cell["alns"])
                    eq.append(cell["eq"])
            x = range(len(xs))
            ax.plot(x, sac, marker=marker, color=theme.STRATEGY_COLOURS["sacred"],
                    linewidth=1.8, label=f"SACRED {od}")
            ax.plot(x, alns, marker=marker, color=theme.STRATEGY_COLOURS["alns"],
                    linewidth=1.6, label=f"ALNS {od}")
            ax.plot(x, eq, marker=marker, color=theme.STRATEGY_COLOURS["equilibrium"],
                    linewidth=1.4, label=f"equilibrium {od}")
        ax.set_xticks(range(len(cells_order)), cells_order)
        ax.set_ylabel("best-checkpoint exploitability")
        ax.legend(fontsize=8, ncols=2)
        self.sweep_chart.set_caption(
            "SACRED < ALNS in all 10 cells; every value from the gen12 ledger table "
            "(gen12_sweeps.md; circles 62-97, squares 35-159; single-seed curve points "
            "except 62-97 N=3 K=1)", "ledger")
        self.sweep_chart.redraw()


# ===================================================================== ZST

class ZstExhibit(ExhibitBase):
    """Zero-shot transfer: the frozen generalist routes a city it never saw."""

    def build(self) -> None:
        if self._built:
            return
        self._built = True

        c = self.card("Route a never-seen city, zero-shot")
        row = QWidget()
        rl = QHBoxLayout(row)
        rl.setContentsMargins(0, 0, 0, 0)
        self.od_combo = QComboBox()
        for od in ("249-95", "106-173", "351-210", "146-296", "275-72", "193-278"):
            self.od_combo.addItem(f"Gdansk {od} (gen16 held-out)", ("gdansk", od))
        rl.addWidget(self.od_combo)
        self.eval_btn = QPushButton("Evaluate zero-shot")
        self.eval_btn.setProperty("accent", True)
        self.eval_btn.clicked.connect(self._evaluate)
        rl.addWidget(self.eval_btn)
        self.zst_label = QLabel("")
        rl.addWidget(self.zst_label, 1)
        c.layout_().addWidget(row)

        maps_row = QSplitter(Qt.Horizontal)
        left_box = QWidget()
        ll = QVBoxLayout(left_box)
        ll.setContentsMargins(0, 0, 0, 0)
        lt = QLabel("gen16 multi-city generalist (frozen, never trained here)")
        lt.setProperty("h3", True)
        ll.addWidget(lt)
        self.map_gen = MapView()
        self.map_gen.setMinimumHeight(340)
        ll.addWidget(self.map_gen)
        maps_row.addWidget(left_box)
        right_box = QWidget()
        rr = QVBoxLayout(right_box)
        rr.setContentsMargins(0, 0, 0, 0)
        rt = QLabel("random-init network (same architecture, untrained)")
        rt.setProperty("h3", True)
        rr.addWidget(rt)
        self.map_rnd = MapView()
        self.map_rnd.setMinimumHeight(340)
        rr.addWidget(self.map_rnd)
        maps_row.addWidget(right_box)
        c.layout_().addWidget(maps_row)
        self.result_label = QLabel(
            "Press “Evaluate zero-shot”: both networks route the chosen Gdansk instance; "
            "the maps and ratios appear here.")
        self.result_label.setWordWrap(True)
        c.layout_().addWidget(self.result_label)

        c2 = self.card("The transfer-difficulty ladder")
        self.ladder_chart = ChartWidget(title="zst-transfer-ladder", height=3.0, width=7.2)
        c2.layout_().addWidget(self.ladder_chart)
        self._draw_ladder()
        self.add_quote_cards("zst")

    def _draw_ladder(self) -> None:
        rungs = _exhibit_data()["transfer_ladder"]["rungs"]
        ax = self.ladder_chart.clear()
        labels = [r["label"] for r in rungs]
        vals = [r["value"] for r in rungs]
        cols = [theme.STRATEGY_COLOURS["random_init"] if r.get("kind") == "boundary"
                else theme.BLUE for r in rungs]
        ax.barh(range(len(rungs)), vals, color=cols, height=0.6)
        ax.set_yticks(range(len(rungs)), labels, fontsize=8)
        ax.invert_yaxis()
        ax.axvline(1.0, color=theme.STRATEGY_COLOURS["equilibrium"], linestyle=":", linewidth=1.0)
        for i, v in enumerate(vals):
            ax.text(v + 0.03, i, f"{v:.2f}x", va="center", fontsize=9,
                    color=theme.INK_SECONDARY)
        ax.set_xlabel("mean ratio to each instance's own equilibrium (1.0 = optimal)")
        self.ladder_chart.set_caption(
            "gen15_generalist.md · gen16_multicity.md · gen22_rotation.md · "
            "a2_graph_transfer.md (multi-graph training is what removes the A2 boundary: "
            "gen16's A2-rescue row scores 1.90 vs random 2.43 on the A2 graph)", "ledger")
        self.ladder_chart.redraw()

    def _evaluate(self) -> None:
        city, od = self.od_combo.currentData()
        self.eval_btn.setEnabled(False)
        self.od_combo.setEnabled(False)
        self.zst_label.setText("loading the frozen generalist…")
        run_in_background(self._eval_worker, city, od,
                          on_done=self._eval_done,
                          on_fail=lambda tb: (self.eval_btn.setEnabled(True),
                                              self.od_combo.setEnabled(True),
                                              self.zst_label.setText(
                                                  "failed: " + tb.strip().splitlines()[-1])))

    @staticmethod
    def _eval_worker(city: str, od: str):
        s, t = od.split("-")
        inst = oracle_bridge.build_instance(city, s, t, 1, 3, 8, (0.15, 0.95))
        refs = [r for r in policies.discover_actors() if r.family == "gen16_multicity"]
        if not refs:
            raise RuntimeError("no gen16 checkpoints on disk")
        pol = policies.load_policy(refs[0], inst)
        d_gen = pol.route_distribution()
        d_rnd = policies.random_init_distribution(inst, seed=0)
        occ_gen = inst.route_dist_to_stacked_occ_dist(d_gen)
        occ_rnd = inst.route_dist_to_stacked_occ_dist(d_rnd)
        _, e_gen = inst.exploitability_occ(occ_gen)
        _, e_rnd = inst.exploitability_occ(occ_rnd)
        return inst, d_gen, d_rnd, e_gen, e_rnd, refs[0]

    def _eval_done(self, result) -> None:
        inst, d_gen, d_rnd, e_gen, e_rnd, ref = result
        self.eval_btn.setEnabled(True)
        self.od_combo.setEnabled(True)
        self.zst_label.setText("")
        for mv, dist in ((self.map_gen, d_gen), (self.map_rnd, d_rnd)):
            mv.set_city(inst.city_map)
            mv.show_instance(inst.routes, inst.edge_vuln, inst.s, inst.t)
            mv.set_route_mixture(list(dist),
                                 theme.BLUE if mv is self.map_gen else theme.INK_MUTED)
        self.result_label.setText(
            f"<b>Gdansk {inst.s}-{inst.t} · Generalist: {e_gen:.3f} = "
            f"{e_gen / inst.mc_value:.2f}x equilibrium</b> vs random-init {e_rnd:.3f} = "
            f"{e_rnd / inst.mc_value:.2f}x · this instance's equilibrium {inst.mc_value:.3f}, "
            f"deterministic optimum {inst.mc_loss_det:.3f} (all computed live; policy = "
            f"{ref.provenance}). The generalist was trained on Kaliningrad, East London and "
            f"Istanbul; it has never seen this graph.")


# ===================================================================== tab

class ObjectivesTab(QWidget, Exportable):
    export_name = "objectives"

    def __init__(self, parent=None):
        super().__init__(parent)
        data = _exhibit_data()
        quotes = {i["id"]: i["quote"] for i in data["objectives_verbatim"]["items"]}

        lay = QHBoxLayout(self)
        lay.setContentsMargins(12, 8, 12, 12)
        split = QSplitter(Qt.Horizontal)
        lay.addWidget(split)

        self.sidebar = QListWidget()
        self.sidebar.setWordWrap(True)
        split.addWidget(self.sidebar)
        self.stack = QStackedWidget()
        split.addWidget(self.stack)
        split.setSizes([270, 1000])

        self._exhibits = [
            ("Obj 1 · The zero-sum game", Obj1Exhibit(
                quotes["obj1"],
                "Met more deeply than promised: formulated, characterised (when it fails), "
                "solved against its own computable equilibrium, and closed with a LEARNED "
                "antagonist agent (gen20: 0.81x oracle strength).")),
            ("Obj 2 · The simulation environment", Obj2Exhibit(
                quotes["obj2"],
                "Met and strengthened: the multi-city extraction pipeline, the interdiction game "
                "layer, and this application are all Obj-2 artefacts.")),
            ("Obj 3 · SAC + ATLA + ERB", Obj3Exhibit(
                quotes["obj3"],
                "Met and closed verbatim: SAC entropy IS the mixed strategy; ATLA realised as "
                "smooth fictitious play vs the oracle best response; and gen23 measured ERB "
                "bootstrapping from the ALNS population (it hurts: deterministic demonstrations "
                "fight the mixed-strategy optimum).")),
            ("Obj 4 · Surrogate-based optimisation", Obj4Exhibit(
                quotes["obj4"],
                "Met, now arguably the most complete objective: F3 regression, D1 acquisition "
                "loop, D2 hardening tier, D3 composite over the trained policy, and D3-on-Gdansk "
                "(the composite holds on a never-trained city).")),
            ("Obj 5 · Evaluation vs baselines", Obj5Exhibit(
                quotes["obj5"],
                "Met strongly: both headline ladders on corrected code with n=10 CIs; disruption "
                "curves in 10/10 cells; fairness rows pre-empting the natural attacks; and the "
                "transfer-level vanilla control (gen21) making the adversarial claim causal.")),
            ("ZST · The aim's promise", ZstExhibit(
                quotes["zst"],
                "Realised at the held-out-CITY level (gen16), rotated to the hardest hold-out "
                "(Istanbul, gen22), extended to whole-city Kyiv scale, with the honest boundary "
                "(A2) measured and then removed by multi-graph training.")),
        ]
        for label, widget in self._exhibits:
            item = QListWidgetItem(label)
            self.sidebar.addItem(item)
            self.stack.addWidget(widget)
        self.sidebar.currentRowChanged.connect(self._select)
        self.sidebar.setCurrentRow(0)

        from PySide6.QtGui import QKeySequence, QShortcut
        QShortcut(QKeySequence(Qt.Key_Space), self, activated=self._space,
                  context=Qt.WidgetWithChildrenShortcut)

    def _space(self) -> None:
        w = self.stack.currentWidget()
        if hasattr(w, "toggle_play"):
            w.toggle_play()

    def _select(self, row: int) -> None:
        if 0 <= row < self.stack.count():
            self.stack.setCurrentIndex(row)
            w = self.stack.currentWidget()
            if isinstance(w, ExhibitBase):
                w.build()
            self.export_name = f"objectives-{row + 1}"

    def select_exhibit(self, idx: int) -> None:
        self.sidebar.setCurrentRow(idx)

    def export_view(self):
        return export_widget_grab(self.stack.currentWidget(), self.export_name)
