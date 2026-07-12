"""Home: the one-screen pitch. What SACRED is in three sentences, the hero
animation (predictable routing ambushed, calibrated mixing slipping through),
the two headline ladders, and four large entry buttons."""

from __future__ import annotations

import numpy as np
import yaml
from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from .. import theme
from ..sacred_bridge import oracle as oracle_bridge
from ..sacred_bridge.paths import DATA_DIR
from ..widgets.cards import Card, EraBadge
from ..widgets.charts import ChartWidget
from ..widgets.export import Exportable, export_widget_grab
from ..widgets.mapview import MapView
from ..workers import run_in_background

PITCH = (
    "<b>SACRED</b> routes convoys through cities where an adversary is waiting. "
    "A predictable route is an ambushed route, so the optimal defence is a calibrated "
    "MIXED strategy, and adversarially-trained reinforcement learning finds it on real "
    "road networks, scored against the game's computable optimum. "
    "This app lets you watch it, play against it, and trace every number to the "
    "project's ledgers.")


class HomeTab(QWidget, Exportable):
    export_name = "home"
    go_to = Signal(int)  # tab index

    def __init__(self, parent=None):
        super().__init__(parent)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        outer.addWidget(scroll)
        host = QWidget()
        lay = QVBoxLayout(host)
        lay.setContentsMargins(24, 12, 24, 18)
        lay.setSpacing(12)
        scroll.setWidget(host)

        title = QLabel("SACRED Mission Control")
        title.setProperty("h1", True)
        lay.addWidget(title)
        pitch = QLabel(PITCH)
        pitch.setWordWrap(True)
        pitch.setStyleSheet("font-size: 15px;")
        pitch.setTextInteractionFlags(Qt.TextSelectableByMouse)
        lay.addWidget(pitch)

        # hero: map animation + the two ladders beside it
        hero_row = QWidget()
        hl = QHBoxLayout(hero_row)
        hl.setContentsMargins(0, 0, 0, 0)
        hl.setSpacing(12)

        hero_card = Card()
        hero_title = QLabel("Predictability is ambushability")
        hero_title.setProperty("h3", True)
        hero_card.layout_().addWidget(hero_title)
        self.map = MapView()
        self.map.setMinimumSize(520, 400)
        hero_card.layout_().addWidget(self.map)
        self.hero_caption = QLabel("Loading the headline instance…")
        self.hero_caption.setWordWrap(True)
        self.hero_caption.setStyleSheet(f"color: {theme.INK_SECONDARY}; font-size: 11px;")
        hero_card.layout_().addWidget(self.hero_caption)
        hl.addWidget(hero_card, 5)

        ladders = QWidget()
        ll = QVBoxLayout(ladders)
        ll.setContentsMargins(0, 0, 0, 0)
        ll.setSpacing(12)
        data = yaml.safe_load((DATA_DIR / "exhibits.yaml").read_text())
        for key in ("multiconvoy", "singleconvoy"):
            ladder = data["headline_ladders"][key]
            card = Card()
            head = QWidget()
            hrow = QHBoxLayout(head)
            hrow.setContentsMargins(0, 0, 0, 0)
            t = QLabel(ladder["title"])
            t.setProperty("h3", True)
            hrow.addWidget(t, 1)
            hrow.addWidget(EraBadge(ladder["era"]))
            card.layout_().addWidget(head)
            chart = ChartWidget(title=f"home-ladder-{key}", height=2.1, width=4.6)
            ax = chart.axes()
            rows = ladder["rows"]
            vals = [r["value"] for r in rows]
            cols = [theme.STRATEGY_COLOURS.get(r["arm"], theme.BLUE) for r in rows]
            ax.barh(range(len(rows)), vals, color=cols, height=0.62)
            ax.set_yticks(range(len(rows)), [r["label"] for r in rows], fontsize=8)
            ax.invert_yaxis()
            for i, v in enumerate(vals):
                ax.text(v + 0.01, i, f"{v:.3f}", va="center", fontsize=8,
                        color=theme.INK_SECONDARY)
            ax.set_xlim(0, max(vals) * 1.2)
            ax.set_xlabel(ladder["unit"], fontsize=8)
            caption = f"ledger: {ladder['ledger']}"
            if key == "singleconvoy":
                caption += ("  ·  gen14's n=10 CI for the same cell: sacred 0.310 "
                            "[0.275, 0.345] (gen14_evidence.md)")
            chart.set_caption(caption, "ledger")
            card.layout_().addWidget(chart)
            ll.addWidget(card)
        hl.addWidget(ladders, 4)
        lay.addWidget(hero_row)

        # entry buttons (short subtitles so Home never forces horizontal scroll)
        grid = QGridLayout()
        grid.setSpacing(10)
        try:
            idx = yaml.safe_load((DATA_DIR / "narrative_index.yaml").read_text())
            n_gens = sum(1 for g in idx.get("generations", [])
                         if str(g.get("id", "")).startswith("gen"))
            history_sub = f"{n_gens} generations, 3 pivots"
        except Exception:
            history_sub = "The generations, 3 pivots"
        entries = [
            ("Playground", "Fly sorties, duel, ambush", 1),
            ("Objectives", "Six exhibits, live", 2),
            ("History", history_sub, 3),
            ("Documents", "Ledgers, searchable", 4),
        ]
        for col, (name, desc, idx) in enumerate(entries):
            btn = QPushButton(f"{name}\n{desc}")
            btn.setMinimumHeight(66)
            btn.setMinimumWidth(0)
            btn.setStyleSheet(
                f"QPushButton {{ text-align: left; padding: 10px 14px; font-size: 14px;"
                f"font-weight: 600; background: {theme.SURFACE}; }}")
            btn.clicked.connect(lambda _=False, i=idx: self.go_to.emit(i))
            grid.addWidget(btn, 0, col)
            grid.setColumnStretch(col, 1)
        lay.addLayout(grid)
        lay.addStretch(1)

        # hero animation state
        self._inst = None
        self._phase = 0.0
        self._dots = []
        self._routes = []
        self._flashed = []
        self._caught = []
        self._timer = QTimer(self)
        self._timer.setInterval(33)
        self._timer.timeout.connect(self._tick)
        self._rng = np.random.default_rng(0)
        run_in_background(
            oracle_bridge.build_instance, "kaliningrad", "33", "71", 1, 1, 8, None,
            on_done=self._hero_ready, on_fail=lambda tb: self.hero_caption.setText(
                "Hero animation unavailable (instance failed to solve)."))

    # ------------------------------------------------------------- hero loop

    def _hero_ready(self, inst) -> None:
        self._inst = inst
        self.map.set_city(inst.city_map)
        self.map.show_instance(inst.routes, inst.edge_vuln, inst.s, inst.t)
        self.map.set_route_mixture(list(inst.sc_defender))
        # committed attackers: BR to shortest (for the red convoy), BR to the mixture (blue)
        short = np.zeros(inst.n_routes)
        self._short_route = int(np.argmin(inst.route_costs))
        short[self._short_route] = 1.0
        j_red, self._red_loss = inst.exploitability_routes(short)
        j_blue, self._blue_loss = inst.exploitability_routes(inst.sc_defender)
        self._iset_red = inst.interdiction_sets[j_red]
        self._iset_blue = inst.interdiction_sets[j_blue]
        self.hero_caption.setText(
            f"Kaliningrad {inst.s}-{inst.t} (hard interception), computed live: the committed "
            f"interdictor intercepts the deterministic convoy with probability "
            f"{self._red_loss:.2f} and the calibrated mixture with {self._blue_loss:.2f} "
            f"(equilibrium {inst.sc_value:.3f}). Red flies the same route every sortie; "
            f"blue samples from the equilibrium mixture.")
        self._begin_cycle()
        self._timer.start()

    def _begin_cycle(self) -> None:
        inst = self._inst
        self.map.clear_convoys()
        self.map.clear_ambush()
        blue_route = int(self._rng.choice(inst.n_routes,
                                          p=inst.sc_defender / inst.sc_defender.sum()))
        self._routes = [self._short_route, blue_route]
        red_edges = [(tuple(e)[0], tuple(e)[-1]) for e in self._iset_red]
        self.map.show_ambush(red_edges, revealed=True)
        self._dots = [self.map.add_convoy(theme.STRATEGY_COLOURS["shortest_path"]),
                      self.map.add_convoy(theme.STRATEGY_COLOURS["sacred"])]
        # outcomes: red caught with prob red_loss on its BR edge; blue on its own BR iset
        self._caught = []
        for iset, route, ploss in ((self._iset_red, self._short_route, None),
                                   (self._iset_blue, blue_route, None)):
            hit = None
            nodes = self._inst.routes[route]
            for a, b in zip(nodes[:-1], nodes[1:]):
                e = frozenset({a, b})
                if e in iset and self._rng.random() < self._inst.edge_vuln.get(e, 1.0):
                    fe = self.map.fraction_of_edge(route, (a, b))
                    hit = fe if fe is not None else self._edge_frac(route, (a, b))
                    break
            self._caught.append(hit)
        self._flashed = [False, False]
        self._phase = 0.0

    def _edge_frac(self, route_idx: int, edge) -> float:
        nodes = self._inst.routes[route_idx]
        n_edges = max(1, len(nodes) - 1)
        for i, (a, b) in enumerate(zip(nodes[:-1], nodes[1:])):
            if tuple(sorted((a, b))) == tuple(sorted(edge)):
                return (i + 0.55) / n_edges
        return 1.0

    def _tick(self) -> None:
        if self._inst is None or not self._dots:
            return
        if not self.isVisible():
            return
        self._phase += 0.012
        frac = min(1.0, self._phase)
        for i, dot in enumerate(self._dots):
            stop = self._caught[i] if self._caught[i] is not None else 1.0
            self.map.place_on_route(dot, self._routes[i], min(frac, stop))
            if self._caught[i] is not None and frac >= stop and not self._flashed[i]:
                self._flashed[i] = True
                self.map.flash(dot)
                self.map.mark_lost(dot)
        if self._phase >= 1.35:
            self._begin_cycle()

    def export_view(self):
        return export_widget_grab(self, "home")
