"""The Objectives tab: six promises, six demonstrations.

Story first (REDESIGN.md §3.3): each exhibit opens with a plain headline and a
plain verdict; the verbatim promise and every ledger quote sit one click away
in "From the record" disclosures. All maths stays exactly as verified; only the
language and presentation changed.
"""

from __future__ import annotations

import numpy as np
import yaml
from matplotlib.ticker import PercentFormatter
from PySide6.QtCore import Qt, QTimer, Signal
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

from .. import lexicon, theme
from ..sacred_bridge import gen_charts
from ..sacred_bridge import maps as maps_bridge
from ..sacred_bridge import oracle as oracle_bridge
from ..sacred_bridge import policies
from ..sacred_bridge.paths import DATA_DIR, RUNS_DIR, SACRED_ROOT
from ..sacred_bridge.runs import (
    MULTICONVOY_HISTORY_FIELDS,
    HistorySeries,
    multiconvoy_result,
    read_json,
)
from ..widgets.cards import Card, EraBadge, StateLabel
from ..widgets.charts import ChartWidget
from ..widgets.export import Exportable, export_widget_grab
from ..widgets.human import HeroNumber, RecordDisclosure
from ..widgets.mapview import MapView
from ..workers import run_in_background


def _exhibit_data() -> dict:
    return yaml.safe_load((DATA_DIR / "exhibits.yaml").read_text())


def _pct_axis(ax, axis: str = "y") -> None:
    fmt = PercentFormatter(xmax=1.0, decimals=0)
    (ax.yaxis if axis == "y" else ax.xaxis).set_major_formatter(fmt)


class _Disclosure(RecordDisclosure):
    """A RecordDisclosure with a custom collapsed title (e.g. the promise)."""

    def __init__(self, title: str, parent=None):
        self._title = title
        super().__init__(parent)
        self.toggle.setText(f"{title} ▸")

    def _toggled(self, on: bool) -> None:
        self.toggle.setText(f"{self._title} {'▾' if on else '▸'}")
        self.body.setVisible(on)


class ExhibitBase(QWidget):
    """Scrollable exhibit page: plain headline, plain verdict, promise-on-demand."""

    def __init__(self, headline: str, promise_quote: str, verdict: str, parent=None):
        super().__init__(parent)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        outer.addWidget(scroll)
        host = QWidget()
        self.lay = QVBoxLayout(host)
        self.lay.setContentsMargins(4, 0, 12, 12)
        self.lay.setSpacing(12)
        scroll.setWidget(host)

        head = Card()
        h = QLabel(headline)
        h.setProperty("h2", True)
        h.setWordWrap(True)
        head.layout_().addWidget(h)
        v = QLabel(verdict)
        v.setWordWrap(True)
        v.setStyleSheet("font-size: 15px;")
        head.layout_().addWidget(v)
        promise = _Disclosure("The promise, in the project's own words")
        promise.add_quote(promise_quote,
                          "THESIS_STORYLINE.md (the assessed literature review, §2.2)")
        head.layout_().addWidget(promise)
        self.lay.addWidget(head)
        self._built = False

    def build(self) -> None:  # lazy heavy work on first show
        pass

    def card(self, title: str = "") -> Card:
        c = Card()
        if title:
            t = QLabel(title)
            t.setProperty("h3", True)
            t.setWordWrap(True)
            c.layout_().addWidget(t)
        self.lay.addWidget(c)
        return c

    def add_quote_cards(self, key: str) -> None:
        """Plain sentence first; the verbatim ledger quotes one click away."""
        for spec in _exhibit_data().get("quote_cards", {}).get(key, []):
            c = self.card(spec["title"])
            plain = spec.get("plain", "")
            if plain:
                lead = QLabel(plain)
                lead.setWordWrap(True)
                lead.setStyleSheet("font-size: 15px;")
                c.layout_().addWidget(lead)
            rd = RecordDisclosure()
            for item in spec["items"]:
                rd.add_line(item["label"])
                rd.add_quote(item["quote"], item.get("ledger", spec["ledger"]))
            c.layout_().addWidget(rd)


# ===================================================================== Obj 1

class Obj1Exhibit(ExhibitBase):
    """The game made tangible: mixing slider vs live catch-chance."""

    def build(self) -> None:
        if self._built:
            return
        self._built = True
        self._inst = None

        c = self.card("How does the convoy pick its road?")
        intro = QLabel(
            "Drag the slider. The enemy watches long enough to learn whatever habit "
            "you settle into, then places its ambush accordingly.")
        intro.setWordWrap(True)
        c.layout_().addWidget(intro)
        self.slider = QSlider(Qt.Horizontal)
        self.slider.setRange(0, 200)
        self.slider.setValue(0)
        self.slider.valueChanged.connect(self._update)
        c.layout_().addWidget(self.slider)
        lab_row = QWidget()
        lr = QHBoxLayout(lab_row)
        lr.setContentsMargins(0, 0, 0, 0)
        for txt, align in (("always the same road", Qt.AlignLeft),
                           ("coin flip", Qt.AlignCenter),
                           ("the proven mix", Qt.AlignRight)):
            l = QLabel(txt)
            l.setAlignment(align)
            l.setStyleSheet(f"color: {theme.INK_MUTED}; font-size: 12px;")
            lr.addWidget(l)
        c.layout_().addWidget(lab_row)
        self.hero = HeroNumber(
            "chance of being caught · once the enemy learns your habits",
            "computed live · the lone-convoy run, Kaliningrad")
        c.layout_().addWidget(self.hero)
        self.curve = ChartWidget(title="obj1-catch-curve", height=2.6, width=7.0)
        c.layout_().addWidget(self.curve)

        c2 = self.card("Every ambush option pays the enemy the same — "
                       "that is why the mix cannot be beaten")
        self.saddle = ChartWidget(title="obj1-ambush-options", height=2.6, width=7.0)
        c2.layout_().addWidget(self.saddle)
        note = QLabel(
            "At the proven mix, every ambush the enemy could pick would catch exactly "
            "the same share of convoys. There is nothing left to exploit: that balance "
            "point is what every SACRED result in this app is measured against.")
        note.setWordWrap(True)
        c2.layout_().addWidget(note)

        self.add_quote_cards("obj1")
        run_in_background(
            oracle_bridge.build_instance, "kaliningrad", "33", "71", 1, 1, 8, None,
            on_done=self._ready,
            on_fail=lambda tb: self.hero.set_caption("The live solve failed."))

    def _ready(self, inst) -> None:
        self._inst = inst
        R = inst.n_routes
        short = np.zeros(R)
        short[int(np.argmin(inst.route_costs))] = 1.0
        self._d_short = short
        self._d_uniform = np.full(R, 1.0 / R)
        self._d_eq = inst.sc_defender
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
        self.hero.set_value(e)

        ax = self.curve.clear()
        xs, es = self._curve
        ax.plot(xs, es, color=theme.BLUE, linewidth=2.0)
        ax.plot([t], [e], "o", color=theme.INK, markersize=7, zorder=5)
        ax.axhline(inst.sc_value, color=theme.STRATEGY_COLOURS["equilibrium"],
                   linestyle=":", linewidth=1.0)
        ax.annotate(f"{lexicon.GOALPOST_LEFT} · {lexicon.pct(inst.sc_value)}",
                    xy=(0.02, inst.sc_value), xycoords=("axes fraction", "data"),
                    fontsize=10, color=theme.STRATEGY_COLOURS["equilibrium"], va="bottom")
        ax.set_xticks([0, 100, 200],
                      ["always the\nsame road", "coin flip", "the proven mix"])
        ax.set_ylabel("chance of being caught")
        _pct_axis(ax)
        self.curve.set_caption("your habit, and what it costs you", "live")
        self.curve.redraw()

        ax2 = self.saddle.clear()
        yields = d @ inst.game.payoff
        cols = [theme.STRATEGY_COLOURS["attacker"] if k == j else theme.BASELINE
                for k in range(len(yields))]
        ax2.bar(range(len(yields)), yields, color=cols, width=0.8)
        ax2.axhline(inst.sc_value, color=theme.STRATEGY_COLOURS["equilibrium"],
                    linestyle=":", linewidth=1.0)
        ax2.set_xlabel("each possible ambush")
        ax2.set_ylabel("what it would catch")
        _pct_axis(ax2)
        self.saddle.set_caption(
            "orange = the ambush the enemy would actually pick against your current habit",
            "live")
        self.saddle.redraw()


# ===================================================================== Obj 2

class Obj2Exhibit(ExhibitBase):
    """Any city becomes a game board."""

    def build(self) -> None:
        if self._built:
            return
        self._built = True
        c = self.card("Pick any city — see its roads and their danger")
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
        cap = QLabel("computed live · how dangerous each road is, worked out "
                     "from road lengths the moment you pick the city")
        cap.setStyleSheet(f"color: {theme.LIVE_ACCENT}; font-size: 12px; font-weight: 600;")
        c.layout_().addWidget(cap)

        fig_card = self.card("From map data to game board: keep the main roads, "
                             "then simplify the junctions")
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
                capf.setProperty("fineprint", True)
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
            f"{n_nodes} junctions · {n_edges} road segments"
            + ("" if registered else " · no measured results on this map yet"))


# ===================================================================== Obj 3

# plain names for the training-run families (technical id, glob, era kept as data)
_OBJ3_FAMILIES = {
    "The proving ground — the final three runs":
        ("gen13_lock", "seed*.json", "post-fix"),
    "The proving ground — the ten-run evidence set":
        ("gen14_evidence", "mc_seed*.json", "post-fix"),
    "Trying to hold the final version steady (it would not)":
        ("gen17_lastiterate", "seed*.json", "post-fix"),
    "Teaching convoys to follow each other (it did not take)":
        ("gen18_learnedfollower", "seed*.json", "post-fix"),
    "The old proving ground (before the bug fix)":
        ("gen09_multiconvoy", "headline_seed*.json", "pre-fix"),
}


class Obj3Exhibit(ExhibitBase):
    """One story chart by default; the machinery behind an expert view."""

    def build(self) -> None:
        if self._built:
            return
        self._built = True
        c = self.card("Watch it learn — and watch us keep the best version")
        intro = QLabel(
            "Each line is one training run. The chance of mission failure falls as the "
            "AI practises against the enemy; train too long and it over-trains, so the "
            "project always keeps the best version, never the last one.")
        intro.setWordWrap(True)
        c.layout_().addWidget(intro)
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
        self.family_state = StateLabel("Loading the training record…", "loading")
        c.layout_().addWidget(self.family_state)
        self.traj = ChartWidget(title="obj3-learning", height=3.2, width=7.4)
        c.layout_().addWidget(self.traj)

        # ---- everything technical lives behind the expert view
        expert_card = self.card("")
        self.expert = _Disclosure("Expert view — temperatures, the strategy replay, "
                                  "and the expert-examples experiment")
        expert_card.layout_().addWidget(self.expert)

        self.temps = ChartWidget(title="obj3-temperatures", height=2.4, width=7.2)
        self.expert.body_lay.addWidget(self.temps)

        bar_row = QWidget()
        brl = QHBoxLayout(bar_row)
        brl.setContentsMargins(0, 0, 0, 0)
        self.play_btn = QPushButton("▶ Replay how its strategy shifts (Space)")
        self.play_btn.clicked.connect(self.toggle_play)
        brl.addWidget(self.play_btn)
        self.anim_label = QLabel("")
        brl.addWidget(self.anim_label)
        brl.addStretch(1)
        self.expert.body_lay.addWidget(bar_row)
        self.anim_chart = ChartWidget(title="obj3-strategy-replay", height=2.8, width=7.2)
        self.expert.body_lay.addWidget(self.anim_chart)

        erb_head = QLabel("The expert-examples experiment, run by run")
        erb_head.setProperty("h3", True)
        self.expert.body_lay.addWidget(erb_head)
        self.erb_state = StateLabel("Loading the experiment record…", "loading")
        self.expert.body_lay.addWidget(self.erb_state)
        self.erb_chart = ChartWidget(title="obj3-expert-examples", height=2.8, width=7.2)
        self.expert.body_lay.addWidget(self.erb_chart)

        self.add_quote_cards("obj3")
        run_in_background(gen_charts.load_gen_chart, "gen23",
                          on_done=self._erb_ready,
                          on_fail=lambda tb: self.erb_state.setText(
                              "The experiment record failed to load."))

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
        run_no = {"cold": 0, "seeded": 0}
        for s in payload["series"]:
            seeded = s.get("arm") == "seeded"
            key = "seeded" if seeded else "cold"
            run_no[key] += 1
            colour = theme.STRATEGY_COLOURS["vanilla"] if seeded else theme.STRATEGY_COLOURS["sacred"]
            label = None
            if run_no[key] == 1:
                label = "shown expert examples first" if seeded else "fresh start"
            ax.plot(s["x"], s["y"], color=colour, linewidth=1.6, alpha=0.8, label=label)
        refs = payload.get("refs", {})
        if "equilibrium" in refs:
            ax.axhline(refs["equilibrium"], color=theme.STRATEGY_COLOURS["equilibrium"],
                       linestyle=":", linewidth=1.0)
            ax.annotate(f"{lexicon.GOALPOST_LEFT} · {lexicon.pct(refs['equilibrium'])}",
                        xy=(0.0, refs["equilibrium"]), xycoords=("axes fraction", "data"),
                        fontsize=10, va="bottom",
                        color=theme.STRATEGY_COLOURS["equilibrium"])
        ax.set_xlabel("practice runs")
        ax.set_ylabel("chance the mission fails")
        _pct_axis(ax)
        ax.legend(fontsize=10.5)
        self.erb_chart.set_caption(
            "three runs each way · blue = fresh start, yellow = shown the professional "
            "planner's examples first · source: models/runs/gen23_c1 (gen23_c1_erb.md)",
            "ledger")
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
        for chart in (self.traj, self.temps, self.anim_chart):
            chart.clear()
            chart.redraw()
        self.family_state.setText("Loading the training record…")
        self.family_state.show()
        run_in_background(self._family_worker, family, glob,
                          on_done=lambda result, wanted=label: self._family_ready(result, wanted),
                          on_fail=lambda tb, wanted=label: self._family_failed(wanted))

    def _family_failed(self, wanted: str) -> None:
        if wanted == self.family_combo.currentText():
            self.family_state.setText("The training record failed to load.")
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
                "alpha_leader": hs.col("alpha_leader"),
                "alpha_foll": hs.col("alpha_foll"),
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
            return  # the combo moved on; wrong-era curves must not linger
        if not series:
            self.family_state.setText("No training record found for this family.")
            self.family_state.show()
            return
        self.family_state.hide()
        self._pol_hist = pol_hist
        self._anim_i = 0
        palette = theme.CATEGORICAL
        ax = self.traj.clear()
        many = len(series) > 6
        best_marked = False
        for i, s in enumerate(series):
            colour = theme.BLUE if many else palette[i % len(palette)]
            ax.plot(s["sortie"], s["expl_tap"], color=colour, alpha=0.55 if many else 1.0,
                    linewidth=1.5, label=None if many else f"run {i + 1}")
            if s["best"] is not None and s["best_at"] is not None:
                ax.plot([s["best_at"]], [s["best"]], "o", color=colour, markersize=6,
                        markeredgecolor="white", zorder=5)
                if not best_marked:
                    ax.annotate("the version we keep", xy=(s["best_at"], s["best"]),
                                xytext=(10, -16), textcoords="offset points",
                                fontsize=10.5, color=theme.INK,
                                arrowprops=dict(arrowstyle="-", color=theme.INK_MUTED,
                                                lw=0.8))
                    best_marked = True
        # one annotation for the drift, placed at the end of the first run
        s0 = series[0]
        if s0["sortie"]:
            ax.annotate("over-training — discarded", xy=(s0["sortie"][-1], s0["expl_tap"][-1]),
                        xytext=(-10, 12), textcoords="offset points", ha="right",
                        fontsize=10.5, color=theme.INK_MUTED)
        if "equilibrium" in refs:
            ax.axhline(refs["equilibrium"], color=theme.STRATEGY_COLOURS["equilibrium"],
                       linestyle=":", linewidth=1.0)
            ax.annotate(f"{lexicon.GOALPOST_LEFT} · {lexicon.pct(refs['equilibrium'])}",
                        xy=(0.0, refs["equilibrium"]), xycoords=("axes fraction", "data"),
                        fontsize=10, va="bottom",
                        color=theme.STRATEGY_COLOURS["equilibrium"])
        ax.set_xlabel("practice runs")
        ax.set_ylabel("chance the mission fails")
        _pct_axis(ax)
        if not many:
            ax.legend(fontsize=10)
        self.traj.set_caption(
            f"dots = the versions the project keeps · source: models/runs/{family}",
            "ledger")
        self.traj.redraw()

        ax2 = self.temps.clear()
        for i, s in enumerate(series[:6]):
            colour = palette[i % len(palette)]
            ax2.plot(s["sortie"], s["alpha_leader"], color=colour, linewidth=1.4)
            if any(v for v in s["alpha_foll"]):
                ax2.plot(s["sortie"], s["alpha_foll"], color=colour, linewidth=1.1,
                         linestyle="--", alpha=0.7)
        ax2.set_xlabel("practice runs")
        ax2.set_ylabel("SAC temperature α")
        self.temps.set_caption(
            "how much the AI explores over time (solid = leader, dashed = follower)",
            "ledger")
        self.temps.redraw()
        self._draw_anim_frame()

    def toggle_play(self) -> None:
        if not self.expert.toggle.isChecked():
            return  # the replay lives in the expert view
        if self._timer.isActive():
            self._timer.stop()
            self.play_btn.setText("▶ Replay how its strategy shifts (Space)")
        else:
            if not self._pol_hist:
                self.anim_label.setText("no strategy snapshots saved for this family")
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
            self.anim_label.setText("no strategy snapshots saved for this family")
            return
        dist = np.asarray(self._pol_hist[self._anim_i], dtype=float)
        ax = self.anim_chart.clear()
        ax.bar(range(len(dist)), dist, color=theme.BLUE, width=1.0)
        ax.set_xlabel("every possible way to place the fleet")
        ax.set_ylabel("how often it is played")
        _pct_axis(ax)
        ax.set_ylim(0, max(0.35, float(dist.max()) * 1.15))
        self.anim_label.setText(
            f"snapshot {self._anim_i} of {len(self._pol_hist) - 1} (run 1)")
        self.anim_chart.set_caption(
            "the AI's strategy over training: it concentrates on the smart hedge, "
            "then over-trains toward pure randomness — which is why we keep the best "
            "version, not the last", "ledger")
        self.anim_chart.redraw()


# ===================================================================== Obj 4

class Obj4Exhibit(ExhibitBase):
    """Where should the base go? Told as three steps on the map."""

    def build(self) -> None:
        if self._built:
            return
        self._built = True

        # ---- step 1: the design space on the map
        c = self.card("Step 1 · Every possible base site, scored by the game")
        intro = QLabel(
            "Each dot is a possible base location in Kaliningrad. Its colour is the "
            "mission-failure chance the game assigns to basing there: darker means "
            "riskier. Finding the best dot is the design problem.")
        intro.setWordWrap(True)
        c.layout_().addWidget(intro)
        self.sites_chart = ChartWidget(title="obj4-base-sites", height=4.4, width=7.2)
        c.layout_().addWidget(self.sites_chart)
        self.sites_state = StateLabel("Drawing the design space…", "loading")
        c.layout_().addWidget(self.sites_state)

        scatter_head = QLabel("The shortcut model that scores sites instantly — "
                              "click any point to see that site as a live game")
        scatter_head.setProperty("h3", True)
        c.layout_().addWidget(scatter_head)
        self.scatter = ChartWidget(title="obj4-shortcut-model", height=3.0, width=7.2)
        c.layout_().addWidget(self.scatter)
        self.design_label = QLabel("")
        self.design_label.setWordWrap(True)
        c.layout_().addWidget(self.design_label)
        self.design_map = MapView()
        self.design_map.setMinimumHeight(360)
        self.design_map.hide()
        c.layout_().addWidget(self.design_map)
        self.design_caption = QLabel("")
        self.design_caption.setWordWrap(True)
        self.design_caption.setStyleSheet(
            f"color: {theme.LIVE_ACCENT}; font-size: 12px; font-weight: 600;")
        c.layout_().addWidget(self.design_caption)
        self._design_seq = 0
        self._design_city_loaded = False

        # ---- step 2: the search
        c2 = self.card("Step 2 · Smart search vs blind search: the best site "
                       "in a few dozen tries")
        row = QWidget()
        rl = QHBoxLayout(row)
        rl.setContentsMargins(0, 0, 0, 0)
        self.race_btn = QPushButton("Run the search live")
        self.race_btn.setProperty("accent", True)
        self.race_btn.clicked.connect(self._run_race)
        rl.addWidget(self.race_btn)
        self.race_label = QLabel("Press the button: the smart search races blind luck, "
                                 "right now, on this machine.")
        rl.addWidget(self.race_label, 1)
        c2.layout_().addWidget(row)
        self.race_chart = ChartWidget(title="obj4-search-race", height=3.0, width=7.2)
        c2.layout_().addWidget(self.race_chart)
        self.banked_chart = ChartWidget(title="obj4-recorded-race", height=2.6, width=7.2)
        c2.layout_().addWidget(self.banked_chart)

        # ---- step 3: together vs one-at-a-time (B1)
        c3 = self.card("Step 3 · Decide everything together, or one thing at a time?")
        b1_intro = QLabel(
            "A real base decision is three decisions at once: where to put it, how many "
            "convoys to run, and which roads to reinforce. Deciding them together never "
            "did worse than the classical one-at-a-time approach — and for one of the "
            "two trained AIs, one-at-a-time left 19% of the achievable safety on the table.")
        b1_intro.setWordWrap(True)
        c3.layout_().addWidget(b1_intro)
        self.b1_chart = ChartWidget(title="obj4-together-vs-sequential", height=2.6, width=7.2)
        c3.layout_().addWidget(self.b1_chart)
        b1_note = QLabel(
            "Shown as numbers rather than map sites: the project artefact records the "
            "outcomes of each search, not the coordinates of the chosen designs.")
        b1_note.setProperty("fineprint", True)
        b1_note.setWordWrap(True)
        c3.layout_().addWidget(b1_note)

        # ---- pricing designs against the deployed AI (D3, plain)
        c4 = self.card("And the part no equation-solver can do")
        d3_label = QLabel(
            "The same shortcut-model trick can score every design against the AI you "
            "will actually deploy, rather than against the abstract mathematics. The "
            "two scorecards agree closely where the AI trained, and disagree enough to "
            "matter in a never-seen city — which is exactly where you would want to "
            "design against the real deployed player.")
        d3_label.setWordWrap(True)
        c4.layout_().addWidget(d3_label)
        d3_rd = RecordDisclosure()
        d3_rd.add_line("the in-distribution composite (D3)")
        d3_rd.add_quote(
            "**Surrogate over the TRAINED generalist's operational exploitability: "
            "held-out Spearman 0.959.**", "experiments/d3_composite.md")
        d3_rd.add_quote(
            "**policy-target vs oracle-target rank correlation across designs: 0.768** "
            "- designing against the DEPLOYED policy is strongly but NOT perfectly "
            "aligned with designing against the equilibrium abstraction",
            "experiments/d3_composite.md")
        d3_rd.add_line("on the never-seen city, per-seed (the A5 rule)")
        d3_rd.add_quote("**0.109 (seed 0) / 0.443 (seed 1) / 0.433 (seed 2)**",
                        "experiments/d3_gdansk.md")
        c4.layout_().addWidget(d3_rd)

        self.add_quote_cards("obj4")

        run_in_background(self._load_worker, on_done=self._loaded,
                          on_fail=lambda tb: self.sites_state.setText(
                              "The design-space artefacts are unavailable."))

    @staticmethod
    def _load_worker():
        f3 = read_json(RUNS_DIR / "sbo_placement_demo.json")
        d1 = read_json(RUNS_DIR / "d1_sbo_loop.json")
        b1 = read_json(RUNS_DIR / "b1_integration_gap.json")
        cm = maps_bridge.load_city("kaliningrad")
        pos = cm.projected()
        segments = []
        for u, v, _l in cm.edges:
            pu, pv = pos.get(u), pos.get(v)
            if pu and pv:
                segments.append([pu, pv])
        return f3.data, d1.data, b1.data, pos, segments

    def _loaded(self, result) -> None:
        f3, d1, b1, pos, segments = result
        self._f3 = f3

        # ---- step 1 map of base sites
        if f3 and segments:
            self.sites_state.hide()
            from matplotlib.collections import LineCollection
            ax = self.sites_chart.clear()
            ax.add_collection(LineCollection(segments, colors=theme.GRID,
                                             linewidths=0.7, zorder=1))
            best_by_base: dict[str, float] = {}
            for r in f3.get("rows", []):
                s = str(r["od"]).split("-")[0]
                y = float(r["y"])
                if s not in best_by_base or y < best_by_base[s]:
                    best_by_base[s] = y
            xs, ys, vals = [], [], []
            for s, y in best_by_base.items():
                p = pos.get(s)
                if p:
                    xs.append(p[0])
                    ys.append(p[1])
                    vals.append(y)
            if vals:
                v = np.asarray(vals)
                ranks = np.argsort(np.argsort(v)) / max(1, len(v) - 1)
                colours = [theme.VULN_RAMP[min(len(theme.VULN_RAMP) - 1,
                                               int(q * len(theme.VULN_RAMP)))]
                           for q in ranks]
                order = np.argsort(-v)  # draw riskiest first so safe sites sit on top
                ax.scatter(np.asarray(xs)[order], np.asarray(ys)[order],
                           s=44, c=[colours[i] for i in order],
                           edgecolors="white", linewidths=0.7, zorder=3)
                i_best = int(np.argmin(v))
                ax.annotate("the best site", xy=(xs[i_best], ys[i_best]),
                            xytext=(12, -14), textcoords="offset points",
                            fontsize=10.5, color=theme.INK,
                            arrowprops=dict(arrowstyle="-", color=theme.INK_MUTED, lw=0.8))
            ax.set_aspect("equal")
            ax.invert_yaxis()
            ax.set_xticks([])
            ax.set_yticks([])
            ax.grid(False)
            for spine in ax.spines.values():
                spine.set_visible(False)
            self.sites_chart.set_caption(
                "each dot = a possible base site (its best fleet size), darker = riskier · "
                "150 sites scored by the game "
                "(f3_sbo_demonstrator.md; artefact sbo_placement_demo.json)", "ledger")
            self.sites_chart.redraw()

        # ---- the shortcut-model scatter (click to open a design)
        if f3:
            rows = f3["test_rows"]
            true = [r["true"] for r in rows]
            pred = [r["pred"] for r in rows]
            ax = self.scatter.clear()
            ax.scatter(true, pred, s=26, c=theme.BLUE, alpha=0.7, picker=5)
            lim = [min(true + pred), max(true + pred)]
            ax.plot(lim, lim, color=theme.BASELINE, linewidth=1.0, linestyle="--")
            ax.set_xlabel("what the game actually says about a site")
            ax.set_ylabel("what the shortcut model guessed")
            _pct_axis(ax)
            _pct_axis(ax, "x")
            self.scatter.set_caption(
                "sites the model never saw · from the record: guesses within about two "
                "percentage points, and it named the single best site correctly "
                "(f3_sbo_demonstrator.md; artefact sbo_placement_demo.json)", "ledger")
            self.scatter.canvas.mpl_connect("pick_event", self._picked)
            self.scatter.redraw()
            self._test_rows = rows

        # ---- the recorded race (D1)
        if d1:
            ax = self.banked_chart.clear()
            sbo = np.median(np.asarray(d1["sbo_curves"]), axis=0)
            rnd = np.median(np.asarray(d1["random_curves"]), axis=0)
            x = range(1, len(sbo) + 1)
            ax.plot(x, sbo, color=theme.BLUE, linewidth=2.0, label="smart search")
            ax.plot(x, rnd, color=theme.STRATEGY_COLOURS["uniform"], linewidth=2.0,
                    label="blind search")
            ax.axhline(d1["true_opt"], color=theme.STRATEGY_COLOURS["equilibrium"],
                       linestyle=":", linewidth=1.0)
            ax.annotate(f"the best site · {lexicon.pct(d1['true_opt'])}",
                        xy=(0.02, d1["true_opt"]), xycoords=("axes fraction", "data"),
                        fontsize=10, va="bottom",
                        color=theme.STRATEGY_COLOURS["equilibrium"])
            ax.set_xlabel("designs tried")
            ax.set_ylabel("best risk found so far")
            _pct_axis(ax)
            ax.legend(fontsize=10.5)
            self.banked_chart.set_caption(
                "the project's recorded run of this race: the smart search reached the "
                "best site in about 33 tries; blind search never did within 60 "
                "(d1_sbo_loop.md; artefact d1_sbo_loop.json)", "ledger")
            self.banked_chart.redraw()

        # ---- step 3 (B1)
        if b1:
            ax = self.b1_chart.clear()
            labels = ["first trained AI", "second trained AI"]
            together = [b1["actor0"]["joint_median"], b1["actor1"]["joint_median"]]
            oneat = [b1["actor0"]["seq_median"], b1["actor1"]["seq_median"]]
            xpos = np.arange(2)
            width = 0.34
            ax.bar(xpos - width / 2, together, width, color=theme.BLUE,
                   label="decided together")
            ax.bar(xpos + width / 2, oneat, width,
                   color=theme.STRATEGY_COLOURS["uniform"], label="one at a time")
            for x, v in list(zip(xpos - width / 2, together)) + \
                    list(zip(xpos + width / 2, oneat)):
                ax.text(x, v + 0.004, lexicon.pct(v), ha="center", fontsize=10,
                        color=theme.INK_SECONDARY)
            ax.set_xticks(xpos, labels)
            ax.set_ylabel("risk of the chosen design")
            _pct_axis(ax)
            ax.legend(fontsize=10.5)
            self.b1_chart.set_caption(
                "the same search budget both ways, measured with two independently "
                "trained AIs (b1_integration_gap.md; artefact "
                "models/runs/b1_integration_gap.json)", "ledger")
            self.b1_chart.redraw()

    def _picked(self, event) -> None:
        if not hasattr(self, "_test_rows"):
            return
        i = int(event.ind[0])
        r = self._test_rows[i]
        self.design_label.setText(
            f"This site: convoys would run {r['od'].split('-')[0]} → "
            f"{r['od'].split('-')[1]} with a fleet of {r['N']}. The game says "
            f"{lexicon.pct(r['true'])} risk; the shortcut model guessed "
            f"{lexicon.pct(r['pred'])}. Solving it live below…")
        self._design_seq += 1
        seq = self._design_seq
        s, t = str(r["od"]).split("-")
        run_in_background(
            oracle_bridge.build_instance, "kaliningrad", s, t, 1, int(r["N"]), 8, (0.15, 0.95),
            on_done=lambda inst, my=seq: self._design_ready(inst, my),
            on_fail=lambda tb, my=seq: (self.design_caption.setText("the live solve failed")
                                        if my == self._design_seq else None))

    def _design_ready(self, inst, seq: int) -> None:
        if seq != self._design_seq:
            return
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
        QTimer.singleShot(0, self.design_map.fit_routes)
        self.design_caption.setText(
            f"computed live · this site as a game, with the proven-optimal mix drawn: "
            f"best possible risk {lexicon.pct(inst.mc_value)}, best predictable plan "
            f"{lexicon.pct(inst.mc_loss_det)}")

    def _run_race(self) -> None:
        if not getattr(self, "_f3", None):
            return
        self.race_btn.setEnabled(False)
        self.race_label.setText("racing…")
        rows = self._f3["rows"]
        run_in_background(self._race_worker, rows,
                          on_done=self._race_done,
                          on_fail=lambda tb: (self.race_btn.setEnabled(True),
                                              self.race_label.setText("the race failed")))

    @staticmethod
    def _race_worker(rows: list, repeats: int = 12, n0: int = 8, budget: int = 60):
        """A live LCB acquisition race over the banked F3 design table
        (simplified linear shortcut model; the project's recorded run used the
        neural one)."""
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
        self.race_label.setText("done — twelve repeats, fixed seeds 0-11")
        n0 = 8
        ax = self.race_chart.clear()
        ax.plot(range(n0, n0 + len(sbo)), sbo, color=theme.BLUE, linewidth=2.0,
                label="smart search (live)")
        ax.plot(range(n0, n0 + len(rnd)), rnd, color=theme.STRATEGY_COLOURS["uniform"],
                linewidth=2.0, label="blind search (live)")
        ax.axhline(opt, color=theme.STRATEGY_COLOURS["equilibrium"], linestyle=":",
                   linewidth=1.0)
        ax.annotate(f"the best site · {lexicon.pct(opt)}", xy=(0.02, opt),
                    xycoords=("axes fraction", "data"), fontsize=10, va="bottom",
                    color=theme.STRATEGY_COLOURS["equilibrium"])
        ax.set_xlabel("designs tried")
        ax.set_ylabel("best risk found so far")
        _pct_axis(ax)
        ax.legend(fontsize=10.5)
        self.race_chart.set_caption(
            "both searches start from the same eight random tries · simplified shortcut "
            "model, re-fitted live over the recorded design table", "live")
        self.race_chart.redraw()


# ===================================================================== Obj 5

class Obj5Exhibit(ExhibitBase):
    """The race, the harder fights, and the not-cherry-picked proof."""

    open_od_requested = Signal(str, str)  # (city, od)

    def build(self) -> None:
        if self._built:
            return
        self._built = True
        self._engines = {}
        self._racing = False

        c = self.card("The race: four ways to run convoys, each against an enemy "
                      "who knows its habits")
        row = QWidget()
        rl = QHBoxLayout(row)
        rl.setContentsMargins(0, 0, 0, 0)
        self.race_btn = QPushButton("▶ Race them (Space)")
        self.race_btn.setProperty("accent", True)
        self.race_btn.clicked.connect(self.toggle_play)
        rl.addWidget(self.race_btn)
        self.race_label = QLabel("Getting the contenders ready…")
        rl.addWidget(self.race_label, 1)
        c.layout_().addWidget(row)
        self.race_chart = ChartWidget(title="obj5-the-race", height=3.4, width=7.4)
        c.layout_().addWidget(self.race_chart)

        c2 = self.card("Does it still win when the enemy grows stronger "
                       "and the fleet grows bigger?")
        self.sweep_chart = ChartWidget(title="obj5-harder-fights", height=3.0, width=7.4)
        c2.layout_().addWidget(self.sweep_chart)
        self._draw_sweeps()

        self._build_prevalence()
        self.add_quote_cards("obj5")

        self._timer = QTimer(self)
        self._timer.setInterval(60)
        self._timer.timeout.connect(self._race_tick)
        run_in_background(self._prepare_worker, on_done=self._prepared,
                          on_fail=lambda tb: self.race_label.setText(
                              "preparation failed: " + tb.strip().splitlines()[-1]))

    # ------------------------------------------------------- prevalence (A8)

    def _build_prevalence(self) -> None:
        c = self.card("Were these maps cherry-picked?")
        lead = QLabel(
            "No — the opposite. Across 160 crossings in four cities, predictable habits "
            "are expensive on most of them; the proving grounds were deliberately chosen "
            "among the hardest. Click any dot to open that crossing in the Playground.")
        lead.setWordWrap(True)
        c.layout_().addWidget(lead)
        self.prev_chart = ChartWidget(title="obj5-every-crossing", height=3.4, width=7.4)
        c.layout_().addWidget(self.prev_chart)
        self.prev_label = QLabel("Loading the survey…")
        self.prev_label.setWordWrap(True)
        c.layout_().addWidget(self.prev_label)
        run_in_background(self._prevalence_worker, on_done=self._prevalence_ready,
                          on_fail=lambda tb: self.prev_label.setText(
                              "survey artefact unavailable: models/runs/a8_prevalence.json"))

    @staticmethod
    def _prevalence_worker():
        rf = read_json(RUNS_DIR / "a8_prevalence.json")
        if not rf.ok:
            raise RuntimeError("a8_prevalence.json unavailable")
        return rf.data

    def _prevalence_ready(self, data) -> None:
        rows = data.get("rows", [])
        heads = data.get("headlines", {})
        if not rows:
            self.prev_label.setText("survey artefact empty")
            return
        self._prev_rows = rows
        ax = self.prev_chart.clear()
        city_colours = {"kaliningrad": theme.BLUE, "gdansk": theme.AQUA,
                        "east_london": theme.VIOLET, "istanbul": theme.MAGENTA}
        city_names = {"kaliningrad": "Kaliningrad", "gdansk": "Gdansk",
                      "east_london": "East London", "istanbul": "Istanbul"}
        for city, colour in city_colours.items():
            xs = [r["det_eq"] for r in rows if r["city"] == city]
            ys = [r["unif_eq"] for r in rows if r["city"] == city]
            ax.scatter(xs, ys, s=22, c=colour, alpha=0.65,
                       label=city_names[city], picker=5)
        for od, h in heads.items():
            ax.plot([h["det_eq"]], [h["unif_eq"]], "*", markersize=16,
                    color=theme.STRATEGY_COLOURS["shortest_path"],
                    markeredgecolor="white", zorder=5)
            ax.annotate("a proving ground", xy=(h["det_eq"], h["unif_eq"]),
                        xytext=(6, 6), textcoords="offset points", fontsize=10,
                        color=theme.INK)
        ax.axvline(2.0, color=theme.BASELINE, linestyle=":", linewidth=1.0)
        ax.annotate("habits cost double, to the right", xy=(2.0, 0.03),
                    xycoords=("data", "axes fraction"), fontsize=9.5,
                    color=theme.INK_MUTED, rotation=90, va="bottom", ha="right")
        ax.set_xlabel("how much habits cost here (higher = worse for predictable plans)")
        ax.set_ylabel("how much naive randomness costs")
        ax.legend(fontsize=9)
        self.prev_chart.set_caption(
            "160 crossings, 40 per city · click a dot to open that crossing in the "
            "Playground · artefact models/runs/a8_prevalence.json "
            "(a6_a7_a8_completions.md; figure assets/prevalence.png)", "ledger")
        self.prev_chart.canvas.mpl_connect("pick_event", self._prevalence_picked)
        self.prev_chart.redraw()
        self.prev_label.setText(
            "The stars are the two proving grounds: hard on purpose, picked by rules "
            "written down before any training.")

    def _prevalence_picked(self, event) -> None:
        offsets = event.artist.get_offsets()
        i = int(event.ind[0])
        x, y = float(offsets[i][0]), float(offsets[i][1])
        best = min(self._prev_rows,
                   key=lambda r: (r["det_eq"] - x) ** 2 + (r["unif_eq"] - y) ** 2)
        self.prev_label.setText(
            f"Selected a {best['city'].replace('_', ' ').title()} crossing where habits "
            f"cost {best['det_eq']:.1f}× the optimum · opening it in the Playground…")
        self.open_od_requested.emit(best["city"], best["od"])

    # ------------------------------------------------------- the live race

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
            sacred_spec = DefenderSpec("sacred", "SACRED", occ)
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
        self.race_label.setText(
            "Ready. Each plan flies its own missions against an enemy tuned to its own "
            "habits — press play.")
        self._draw_race()

    def toggle_play(self) -> None:
        if not hasattr(self, "_contenders"):
            return
        self._racing = not self._racing
        self.race_btn.setText("⏸ Pause (Space)" if self._racing else "▶ Race them (Space)")
        if self._racing:
            self._timer.start()
        else:
            self._timer.stop()

    def _race_tick(self) -> None:
        for key, spec in self._contenders:
            eng = self._per_engine[key]
            att = eng.attacker_specs(spec)[0]  # the worst-case enemy
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
                ax.plot(range(1, len(hist) + 1), hist, color=colour, linewidth=1.8)
            exact = self._per_engine[key].exploitability(spec)
            ax.axhline(exact, color=colour, linestyle=":", linewidth=1.0, alpha=0.85)
            ax.annotate(f"{lexicon.strategy_name(key)} · {lexicon.pct(exact)}",
                        xy=(1.0, exact), xycoords=("axes fraction", "data"),
                        fontsize=10, ha="right", va="bottom", color=colour)
        rows = _exhibit_data()["headline_ladders"]["multiconvoy"]["rows"]
        van = next((r for r in rows if r["arm"] == "vanilla"), None)
        if van:
            ax.axhline(van["value"], color=theme.STRATEGY_COLOURS["vanilla"],
                       linestyle="--", linewidth=1.2, alpha=0.9)
            ax.annotate(
                f"{lexicon.strategy_name('vanilla')} · {lexicon.pct(van['value'])} "
                "(from the record; cannot be re-flown)",
                xy=(0.0, van["value"]), xycoords=("axes fraction", "data"), fontsize=10,
                va="bottom", color=theme.STRATEGY_COLOURS["vanilla"])
        ax.set_xlabel("missions flown")
        ax.set_ylabel("share of missions failed so far")
        _pct_axis(ax)
        ax.set_ylim(-0.03, 1.03)
        self.race_chart.set_caption(
            "solid lines = missions being flown right now; dotted = each "
            "plan's exact worst case; SACRED's recorded result was 25.6% "
            "(gen14_evidence.md) · fixed seeds per plan", "live")
        self.race_chart.redraw()

    def _draw_sweeps(self) -> None:
        data = _exhibit_data()["gen12_sweeps"]
        cells_order = ["N=2 K=1", "N=3 K=1", "N=3 K=2", "N=3 K=3", "N=5 K=1"]
        cell_labels = ["2 convoys\n1 ambush team", "3 convoys\n1 team",
                       "3 convoys\n2 teams", "3 convoys\n3 teams",
                       "5 convoys\n1 team"]
        ground = {"62-97": "old proving ground", "35-159": "proving ground"}
        ax = self.sweep_chart.clear()
        for od, marker in (("62-97", "o"), ("35-159", "s")):
            xs, sac, alns, eq = [], [], [], []
            for cname in cells_order:
                cell = next((c for c in data["cells"]
                             if c["od"] == od and c["cell"] == cname), None)
                if cell:
                    xs.append(cname)
                    sac.append(cell["sacred"])
                    alns.append(cell["alns"])
                    eq.append(cell["eq"])
            x = range(len(xs))
            ax.plot(x, sac, marker=marker, color=theme.STRATEGY_COLOURS["sacred"],
                    linewidth=1.8, label=f"SACRED · {ground[od]}")
            ax.plot(x, alns, marker=marker, color=theme.STRATEGY_COLOURS["alns"],
                    linewidth=1.6, label=f"{lexicon.strategy_name('alns')} · {ground[od]}")
            ax.plot(x, eq, marker=marker, color=theme.STRATEGY_COLOURS["equilibrium"],
                    linewidth=1.4, label=f"{lexicon.GOALPOST_LEFT} · {ground[od]}")
        ax.set_xticks(range(len(cell_labels)), cell_labels, fontsize=9.5)
        ax.set_ylabel("chance the mission fails (worst case)")
        _pct_axis(ax)
        ax.legend(fontsize=9.5, ncols=2)
        self.sweep_chart.set_caption(
            "SACRED stays below the professional planner in all ten fights "
            "(gen12_sweeps.md; circles = the old proving ground, squares = the "
            "proving ground)", "ledger")
        self.sweep_chart.redraw()


# ===================================================================== ZST

class ZstExhibit(ExhibitBase):
    """Drop it somewhere it has never been — in three beats."""

    open_compare_requested = Signal()

    def build(self) -> None:
        if self._built:
            return
        self._built = True
        self._pol = None
        self._inst_zst = None
        self._intel_points = {}
        self._rnd_ratio = None

        # ---- beat 1: the drop
        c = self.card("Trained in three cities. Dropped into Gdansk.")
        row = QWidget()
        rl = QHBoxLayout(row)
        rl.setContentsMargins(0, 0, 0, 0)
        self.od_combo = QComboBox()
        for i, od in enumerate(("249-95", "106-173", "351-210",
                                "146-296", "275-72", "193-278")):
            self.od_combo.addItem(f"Gdansk crossing {i + 1}", ("gdansk", od))
            self.od_combo.setItemData(self.od_combo.count() - 1,
                                      f"crossing {od} · never seen in training",
                                      Qt.ToolTipRole)
        rl.addWidget(self.od_combo)
        self.eval_btn = QPushButton("Drop them into Gdansk")
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
        lt = QLabel("SACRED — first time in this city")
        lt.setProperty("h3", True)
        ll.addWidget(lt)
        self.map_gen = MapView()
        self.map_gen.setMinimumHeight(320)
        ll.addWidget(self.map_gen)
        self.hero_gen = HeroNumber("above the proven optimum · lower is better")
        ll.addWidget(self.hero_gen)
        maps_row.addWidget(left_box)
        right_box = QWidget()
        rr = QVBoxLayout(right_box)
        rr.setContentsMargins(0, 0, 0, 0)
        rt = QLabel("An untrained AI")
        rt.setProperty("h3", True)
        rr.addWidget(rt)
        self.map_rnd = MapView()
        self.map_rnd.setMinimumHeight(320)
        rr.addWidget(self.map_rnd)
        self.hero_rnd = HeroNumber("above the proven optimum")
        rr.addWidget(self.hero_rnd)
        maps_row.addWidget(right_box)
        c.layout_().addWidget(maps_row)
        self.result_label = QLabel(
            "Pick a crossing and press the button: both AIs plan their route mixes for "
            "a city neither has ever seen, and both are scored right here, right now.")
        self.result_label.setWordWrap(True)
        c.layout_().addWidget(self.result_label)
        self.result_fine = QLabel("")
        self.result_fine.setProperty("fineprint", True)
        self.result_fine.setWordWrap(True)
        c.layout_().addWidget(self.result_fine)

        # ---- beat 2: who else can do this?
        c3 = self.card("Who else can do this?")
        lead = QLabel(
            "The methods that match SACRED here all need the maths answer key for every "
            "training map. SACRED needs nothing — and past a certain problem size, "
            "answer keys stop existing.")
        lead.setWordWrap(True)
        c3.layout_().addWidget(lead)
        self.amort_chart = ChartWidget(title="zst-who-else", height=3.2, width=7.2)
        c3.layout_().addWidget(self.amort_chart)
        cmp_row = QWidget()
        crl = QHBoxLayout(cmp_row)
        crl.setContentsMargins(0, 0, 0, 0)
        self.compare_btn = QPushButton("See them fly, side by side")
        self.compare_btn.setProperty("accent", True)
        self.compare_btn.clicked.connect(self.open_compare_requested.emit)
        crl.addWidget(self.compare_btn)
        crl.addStretch(1)
        c3.layout_().addWidget(cmp_row)
        self._draw_amortiser()

        # the old transfer-difficulty ladder stays, one click away
        ladder_rd = _Disclosure("The transfer ladder, in the record's own units")
        self.ladder_chart = ChartWidget(title="zst-transfer-ladder", height=3.0, width=7.0)
        ladder_rd.body_lay.addWidget(self.ladder_chart)
        c3.layout_().addWidget(ladder_rd)
        self._draw_ladder()

        # ---- beat 3: how far does it stretch?
        c4 = self.card("How far does it stretch?")
        stretch_lead = QLabel(
            "Think of it as a battery: how much of the possible protection is left as "
            "the AI gets further from home. Near home, most of it. In a giant city it "
            "has never seen, almost none — it still beats an untrained AI there, but "
            "that far out the protection is randomness, not cleverness.")
        stretch_lead.setWordWrap(True)
        c4.layout_().addWidget(stretch_lead)
        self.gap_chart = ChartWidget(title="zst-how-far", height=2.9, width=7.2)
        c4.layout_().addWidget(self.gap_chart)
        gap_rd = RecordDisclosure()
        gap_rd.add_quote(_exhibit_data()["gap_closure_ladder"]["shared_quote"],
                         "experiments/a6_a7_a8_completions.md")
        c4.layout_().addWidget(gap_rd)
        self._draw_gap_closure()

        # ---- the intel-error demo
        c5 = self.card("Feed it a completely wrong danger map — it barely cares")
        intel_row = QWidget()
        irl = QHBoxLayout(intel_row)
        irl.setContentsMargins(0, 0, 0, 0)
        irl.addWidget(QLabel("How wrong is the map it sees?"))
        self.intel_slider = QSlider(Qt.Horizontal)
        self.intel_slider.setRange(0, 100)
        self.intel_slider.setValue(0)
        self.intel_slider.setEnabled(False)
        self.intel_slider.sliderReleased.connect(self._intel_run)
        irl.addWidget(self.intel_slider, 1)
        self.intel_btn = QPushButton("Corrupt the map and re-test")
        self.intel_btn.setEnabled(False)
        self.intel_btn.clicked.connect(self._intel_run)
        irl.addWidget(self.intel_btn)
        c5.layout_().addWidget(intel_row)
        self.intel_label = QLabel(
            "Drop the AIs into Gdansk above first. Then scramble the danger map the AI "
            "is shown — the real dangers stay where they are, and the real game does "
            "the scoring.")
        self.intel_label.setWordWrap(True)
        c5.layout_().addWidget(self.intel_label)
        self.intel_chart = ChartWidget(title="zst-wrong-map", height=2.6, width=7.2)
        c5.layout_().addWidget(self.intel_chart)
        intel_note = QLabel(
            "This is two findings at once: the protection survives bad intelligence, "
            "and the AI is not reading the map road by road — its protection comes "
            "from road geometry it learned across cities.")
        intel_note.setWordWrap(True)
        c5.layout_().addWidget(intel_note)

        self.add_quote_cards("zst")

    # ---------------------------------------------------- beat 2 + 3 charts

    def _draw_amortiser(self) -> None:
        ladder = _exhibit_data()["amortiser_ladder"]
        rows = [r for r in ladder["rows"] if r["arm"] != "equilibrium"]
        ax = self.amort_chart.clear()
        vals = [r["value"] - 1.0 for r in rows]     # distance above the optimum
        cols = [theme.STRATEGY_COLOURS.get(r["arm"], theme.BLUE) for r in rows]
        labels = [lexicon.strategy_name(r["arm"])
                  + ("  ·  needs the answer key" if r.get("labelled") else "")
                  for r in rows]
        ax.barh(range(len(rows)), vals, color=cols, height=0.62)
        ax.set_yticks(range(len(rows)), labels, fontsize=10)
        ax.invert_yaxis()
        for i, v in enumerate(vals):
            ax.text(v + 0.015, i, f"+{lexicon.pct(v)}", va="center", fontsize=10,
                    color=theme.INK_SECONDARY)
        ax.set_xlim(0, max(vals) * 1.18)
        ax.set_xlabel("how far above the proven optimum each one plays, in Gdansk")
        _pct_axis(ax, "x")
        self.amort_chart.set_caption(
            "every contender scored on the same six never-seen crossings · from the "
            "record: gen25_dr_control.md (equilibrium row: a6_a7_a8_completions.md)",
            "ledger")
        self.amort_chart.redraw()

    def _draw_gap_closure(self) -> None:
        g = _exhibit_data()["gap_closure_ladder"]
        rungs = g["rungs"]
        plain = ["At home — three convoys", "At home — one convoy",
                 "A new crossing, same city", "Gdansk — a new city",
                 "Istanbul — the hardest new city", "Kyiv — new, and huge"]
        ax = self.gap_chart.clear()
        y = np.arange(len(rungs))
        ax.barh(y, [1.0] * len(rungs), color=theme.GRID, height=0.6, zorder=1)
        vals = [max(0.0, r["value"]) for r in rungs]
        ax.barh(y, vals, color=theme.BLUE, height=0.6, zorder=2)
        labels = [plain[i] if i < len(plain) else r["label"]
                  for i, r in enumerate(rungs)]
        ax.set_yticks(y, labels, fontsize=10)
        ax.invert_yaxis()
        for i, r in enumerate(rungs):
            ax.text(1.015, i, lexicon.pct(max(0.0, r["value"])), va="center",
                    fontsize=10, color=theme.INK_SECONDARY)
        ax.set_xlim(0, 1.12)
        ax.set_xticks([])
        ax.grid(False)
        ax.set_xlabel("share of the possible protection it delivers")
        self.gap_chart.set_caption(
            "100% = plays like the proven optimum; 0% = no better than the best "
            "predictable plan (a6_a7_a8_completions.md; figure "
            "assets/transfer_gap_closure.png)", "ledger")
        self.gap_chart.redraw()

    def _draw_ladder(self) -> None:
        rungs = _exhibit_data()["transfer_ladder"]["rungs"]
        ax = self.ladder_chart.clear()
        labels = [r["label"] for r in rungs]
        vals = [r["value"] for r in rungs]
        cols = [theme.STRATEGY_COLOURS["random_init"] if r.get("kind") == "boundary"
                else theme.BLUE for r in rungs]
        ax.barh(range(len(rungs)), vals, color=cols, height=0.6)
        ax.set_yticks(range(len(rungs)), labels, fontsize=10)
        ax.invert_yaxis()
        ax.axvline(1.0, color=theme.STRATEGY_COLOURS["equilibrium"], linestyle=":",
                   linewidth=1.0)
        for i, v in enumerate(vals):
            ax.text(v + 0.03, i, f"{v:.2f}x", va="center", fontsize=11,
                    color=theme.INK_SECONDARY)
        ax.set_xlabel("mean ratio to each instance's own equilibrium (1.0 = optimal)")
        self.ladder_chart.set_caption(
            "gen15_generalist.md · gen16_multicity.md · gen22_rotation.md · "
            "a2_graph_transfer.md (multi-graph training is what removes the A2 boundary: "
            "gen16's A2-rescue row scores 1.90 vs random 2.43 on the A2 graph)", "ledger")
        self.ladder_chart.redraw()

    # ---------------------------------------------------- the drop (beat 1)

    def _evaluate(self) -> None:
        city, od = self.od_combo.currentData()
        self.eval_btn.setEnabled(False)
        self.od_combo.setEnabled(False)
        self.zst_label.setText("waking the AIs…")
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
        return inst, d_gen, d_rnd, e_gen, e_rnd, refs[0], pol

    def _eval_done(self, result) -> None:
        inst, d_gen, d_rnd, e_gen, e_rnd, ref, pol = result
        self.eval_btn.setEnabled(True)
        self.od_combo.setEnabled(True)
        self.zst_label.setText("")
        for mv, dist in ((self.map_gen, d_gen), (self.map_rnd, d_rnd)):
            mv.set_city(inst.city_map)
            mv.show_instance(inst.routes, inst.edge_vuln, inst.s, inst.t)
            mv.set_route_mixture(list(dist),
                                 theme.BLUE if mv is self.map_gen else theme.INK_MUTED)
        r_gen = e_gen / inst.mc_value
        r_rnd = e_rnd / inst.mc_value
        self.hero_gen.set_text(f"+{lexicon.pct(r_gen - 1)}")
        self.hero_rnd.set_text(f"+{lexicon.pct(r_rnd - 1)}")
        self.result_label.setText(
            f"On this crossing SACRED plays {lexicon.pct(r_gen - 1)} above the proven "
            f"optimum; the untrained AI plays {lexicon.pct(r_rnd - 1)} above it. "
            f"Closer to perfect play, in a city it has never seen — measured right now, "
            f"on this machine.")
        self.result_fine.setText(
            f"computed live · mission-failure {e_gen:.3f} vs untrained {e_rnd:.3f} · "
            f"this crossing's proven optimum {inst.mc_value:.3f}, best predictable plan "
            f"{inst.mc_loss_det:.3f} · policy: {ref.provenance}")
        # arm the wrong-map demo on this crossing/policy
        self._pol = pol
        self._inst_zst = inst
        self._intel_points = {0.0: r_gen}
        self._rnd_ratio = r_rnd
        self.intel_slider.setEnabled(True)
        self.intel_btn.setEnabled(True)
        self.intel_label.setText(
            f"Armed on this crossing: with the true map it plays "
            f"+{lexicon.pct(r_gen - 1)} above the optimum. Now scramble what it sees.")

    # ---------------------------------------------------- the wrong map

    def _intel_run(self) -> None:
        if self._pol is None or self._inst_zst is None:
            self.intel_label.setText("Drop the AIs into Gdansk above first.")
            return
        frac = self.intel_slider.value() / 100.0
        self.intel_btn.setEnabled(False)
        pol, inst = self._pol, self._inst_zst
        run_in_background(self._intel_worker, pol, inst, frac,
                          on_done=lambda res: self._intel_done(res, pol),
                          on_fail=lambda tb: (self.intel_btn.setEnabled(True),
                                              self.intel_label.setText(
                                                  "failed: " + tb.strip().splitlines()[-1])))

    @staticmethod
    def _intel_worker(pol, inst, frac: float, seed: int = 0):
        rng = np.random.default_rng(seed)
        edges = list(inst.edge_vuln.keys())
        vals = np.array([inst.edge_vuln[e] for e in edges])
        k = int(round(frac * len(edges)))
        override = {}
        if k >= 2:
            idx = rng.choice(len(edges), size=k, replace=False)
            perm = rng.permutation(idx)
            for i_from, i_to in zip(idx, perm):
                override[edges[i_to]] = float(vals[i_from])
        d = pol.route_distribution_observed(override) if override else pol.route_distribution()
        occ = inst.route_dist_to_stacked_occ_dist(d)
        _, e = inst.exploitability_occ(occ)   # scored under the TRUE game
        return frac, e / inst.mc_value, seed

    def _intel_done(self, res, pol) -> None:
        self.intel_btn.setEnabled(True)
        if pol is not self._pol:
            return  # a new crossing was evaluated meanwhile
        frac, ratio, seed = res
        self._intel_points[frac] = ratio
        ax = self.intel_chart.clear()
        xs = sorted(self._intel_points)
        ys = [self._intel_points[x] - 1.0 for x in xs]
        ax.plot([x * 100 for x in xs], ys, "o-", color=theme.BLUE, linewidth=1.8,
                markersize=7, markeredgecolor="white")
        if self._rnd_ratio is not None:
            ax.axhline(self._rnd_ratio - 1.0,
                       color=theme.STRATEGY_COLOURS["random_init"],
                       linestyle="--", linewidth=1.2)
            ax.annotate(
                f"{lexicon.strategy_name('random_init')} · "
                f"+{lexicon.pct(self._rnd_ratio - 1)}",
                xy=(1.0, self._rnd_ratio - 1.0), xycoords=("axes fraction", "data"),
                fontsize=9, ha="right", va="bottom",
                color=theme.STRATEGY_COLOURS["random_init"])
        ax.axhline(0.0, color=theme.STRATEGY_COLOURS["equilibrium"], linestyle=":",
                   linewidth=1.0)
        ax.set_xlabel("share of the danger map scrambled (the real dangers stay put)")
        ax.set_ylabel("above the proven optimum")
        _pct_axis(ax)
        ax.set_ylim(-0.06, max(1.3, (self._rnd_ratio or 2.0) - 1.0 + 0.2))
        self.intel_chart.set_caption(
            f"computed live · seed {seed} · SACRED on this Gdansk crossing, shown an "
            "increasingly wrong map while the real dangers stay fixed", "live")
        self.intel_chart.redraw()
        self.intel_label.setText(
            f"With {frac:.0%} of the map scrambled it plays +{lexicon.pct(ratio - 1)} "
            "above the optimum — the same banked version of the AI in every test.")


# ===================================================================== tab

class ObjectivesTab(QWidget, Exportable):
    export_name = "objectives"
    open_compare = Signal()        # ZST exhibit -> Playground compare mode
    open_od = Signal(str, str)     # prevalence explorer -> Playground (city, od)

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
            ("1 · The game, won", Obj1Exhibit(
                "Make the routing problem a game — and win it",
                quotes["obj1"],
                "Delivered, and more: the game was formulated, solved against its own "
                "provable optimum, and finally played against a learned enemy — which "
                "SACRED still beat.")),
            ("2 · A city becomes a game board", Obj2Exhibit(
                "A real city becomes a game board in seconds",
                quotes["obj2"],
                "Delivered: any city's road map turns into a playable game, and this "
                "application is itself part of the promise.")),
            ("3 · The AI that teaches itself", Obj3Exhibit(
                "The AI teaches itself — and knows when to stop",
                quotes["obj3"],
                "Delivered: it trains against a thinking enemy, the project keeps the "
                "best version of it, and we measured that expert examples actually "
                "hurt it.")),
            ("4 · Where should the base go?", Obj4Exhibit(
                "Where should the base go? Let the game decide",
                quotes["obj4"],
                "Delivered in its honest form: a fast shortcut model scores every "
                "design, a smart search finds the best in a few dozen tries, and "
                "deciding everything together is the safe default.")),
            ("5 · Beating the old world", Obj5Exhibit(
                "Beat the best of the old world — then keep beating it as the "
                "fight gets harder",
                quotes["obj5"],
                "Delivered strongly: SACRED beats the professional planner in every "
                "fight we measured, keeps winning as the enemy grows stronger, and the "
                "maps were chosen hard on purpose.")),
            ("6 · A city it has never seen", ZstExhibit(
                "Drop it somewhere it has never been",
                quotes["zst"],
                "Delivered, then honestly re-scoped: simple methods that use the maths "
                "answer key travel just as well — SACRED's distinction is that it needs "
                "no answer key, stops its own training, and shrugs off bad "
                "intelligence.")),
        ]
        for label, widget in self._exhibits:
            item = QListWidgetItem(label)
            self.sidebar.addItem(item)
            self.stack.addWidget(widget)
            if isinstance(widget, Obj5Exhibit):
                widget.open_od_requested.connect(self.open_od)
            if isinstance(widget, ZstExhibit):
                widget.open_compare_requested.connect(self.open_compare)
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
