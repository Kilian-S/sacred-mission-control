"""Home: the pitch, the argument, the doors in.

The hero IS the argument (REDESIGN.md §3.1): ALNS on the
left, SACRED on the right, both crossing the proving ground against an enemy
who has learned their habits. The planner's habit never changes, so it keeps
dying in the same place; SACRED has no habit to learn.
"""

from __future__ import annotations

import numpy as np
import yaml
from matplotlib.ticker import FuncFormatter
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

from .. import lexicon, theme
from ..game.sortie import DefenderSpec, SortieEngine
from ..sacred_bridge import oracle as oracle_bridge
from ..sacred_bridge import policies
from ..sacred_bridge.paths import DATA_DIR
from ..widgets.cards import Card, EraBadge, StateLabel
from ..widgets.charts import ChartWidget
from ..widgets.export import Exportable, export_widget_grab
from ..widgets.human import HeroNumber, MapLegend, OutcomeStrip, RecordDisclosure
from ..widgets.mapview import MapView
from ..workers import run_in_background

PITCH = (
    "Convoys that always take the fastest road get ambushed, because habits can be "
    "learned. SACRED is an AI that learns to mix its routes so cleverly that even an "
    "enemy watching every move cannot profit from watching. Everything on these "
    "screens is measured: either live on this machine as you watch, or quoted "
    "word for word from the project's written record.")

_HERO_SEEDS = {"planner": 11, "sacred": 12}


class _HeroPanel(QWidget):
    """One side of the hero duel: a map, a legend, a tally and a hero number."""

    def __init__(self, name: str, colour: str, gloss: str = "", parent=None):
        super().__init__(parent)
        self.colour = colour
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(6)

        head = QWidget()
        hl = QHBoxLayout(head)
        hl.setContentsMargins(0, 0, 0, 0)
        hl.setSpacing(8)
        chip = QLabel()
        chip.setFixedSize(14, 14)
        chip.setStyleSheet(f"background: {colour}; border-radius: 7px;")
        title = QLabel(name)
        title.setProperty("h3", True)
        hl.addWidget(chip)
        hl.addWidget(title)
        if gloss:
            g = QLabel(f"— {gloss}")
            g.setStyleSheet(f"color: {theme.INK_MUTED}; font-size: 13px;")
            hl.addWidget(g)
        hl.addStretch(1)
        lay.addWidget(head)

        self.map = MapView()
        self.map.setMinimumSize(380, 300)
        lay.addWidget(self.map, 1)
        lay.addWidget(MapLegend(show_ambush=True))

        stats_row = QWidget()
        sl = QHBoxLayout(stats_row)
        sl.setContentsMargins(0, 0, 0, 0)
        sl.setSpacing(16)
        self.hero = HeroNumber("chance the mission fails — measured so far")
        self.strip = OutcomeStrip()
        sl.addWidget(self.hero, 1)
        sl.addWidget(self.strip, 1)
        lay.addWidget(stats_row)

        self.placeholder = StateLabel("Preparing the duel…", "loading")
        lay.addWidget(self.placeholder)

    def ready(self) -> None:
        self.placeholder.hide()


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
        lay.setContentsMargins(28, 16, 28, 20)
        lay.setSpacing(14)
        scroll.setWidget(host)

        title = QLabel("SACRED")
        title.setProperty("h1", True)
        lay.addWidget(title)
        subtitle = QLabel("Convoy routing that cannot be ambushed by habit.")
        subtitle.setProperty("h2", True)
        subtitle.setStyleSheet(f"color: {theme.INK_SECONDARY}; font-weight: 500;")
        lay.addWidget(subtitle)
        pitch = QLabel(PITCH)
        pitch.setWordWrap(True)
        pitch.setStyleSheet("font-size: 16px;")
        pitch.setTextInteractionFlags(Qt.TextSelectableByMouse)
        lay.addWidget(pitch)

        # the provenance legend: teach the colour language once, up front.
        # a single wrapping rich-text line, so it never forces horizontal scroll.
        legend = QLabel(
            f"<b>How to read every number:</b> &nbsp;"
            f"<span style='color:{theme.LIVE_ACCENT};'><b>green</b></span> "
            f"= measured live on this machine as you watch. &nbsp; "
            f"<span style='color:{theme.INK_MUTED};'>grey “from the record”</span> "
            f"= quoted word for word from the project's written record. &nbsp; "
            f"Results from before and after the 9 July fix are never mixed.")
        legend.setWordWrap(True)
        legend.setStyleSheet(f"color: {theme.INK_SECONDARY}; font-size: 13px;")
        legend.setToolTip(lexicon.ERA_TOOLTIP)
        lay.addWidget(legend)

        # ------------------------------------------------------------- hero
        hero_card = Card()
        hero_title = QLabel("Same city, same enemy, one difference: a habit")
        hero_title.setProperty("h2", True)
        hero_card.layout_().addWidget(hero_title)
        hero_sub = QLabel(
            "Three convoys cross Kaliningrad. The enemy has watched both sides long "
            "enough to know exactly how each behaves, and places its ambush accordingly.")
        hero_sub.setWordWrap(True)
        hero_sub.setStyleSheet(f"color: {theme.INK_SECONDARY}; font-size: 14px;")
        hero_card.layout_().addWidget(hero_sub)

        duel_row = QWidget()
        dl = QHBoxLayout(duel_row)
        dl.setContentsMargins(0, 0, 0, 0)
        dl.setSpacing(16)
        self.left = _HeroPanel("ALNS", theme.STRATEGY_COLOURS["alns"],
                               gloss="the industry-standard route planner")
        self.right = _HeroPanel("SACRED", theme.STRATEGY_COLOURS["sacred"],
                                gloss="our adversarially-trained AI")
        dl.addWidget(self.left, 1)
        dl.addWidget(self.right, 1)
        hero_card.layout_().addWidget(duel_row)

        verdict = QLabel(
            "Both sides face an enemy who has learned their habits. "
            "The planner's habit never changes; SACRED has none.")
        verdict.setWordWrap(True)
        verdict.setStyleSheet("font-size: 15px; font-weight: 600;")
        hero_card.layout_().addWidget(verdict)

        self.hero_record = RecordDisclosure()
        self.hero_record.add_quote(
            "| **SACRED (adversarial, n=10)** | **0.256 [0.246, 0.266]** | the headline |",
            "experiments/gen14_evidence.md")
        hero_card.layout_().addWidget(self.hero_record)
        lay.addWidget(hero_card)

        # ------------------------------------------------------------ ladders
        ladders_row = QWidget()
        lr = QHBoxLayout(ladders_row)
        lr.setContentsMargins(0, 0, 0, 0)
        lr.setSpacing(14)
        data = yaml.safe_load((DATA_DIR / "exhibits.yaml").read_text())
        titles = {
            "multiconvoy": "Three convoys through Kaliningrad: how often does the mission fail?",
            "singleconvoy": "A single convoy through Kaliningrad",
        }
        for key in ("multiconvoy", "singleconvoy"):
            ladder = data["headline_ladders"][key]
            card = Card()
            head = QWidget()
            hrow = QHBoxLayout(head)
            hrow.setContentsMargins(0, 0, 0, 0)
            t = QLabel(titles[key])
            t.setProperty("h3", True)
            t.setWordWrap(True)
            hrow.addWidget(t, 1)
            badge = EraBadge(ladder["era"])
            badge.setToolTip(lexicon.ERA_TOOLTIP)
            hrow.addWidget(badge)
            card.layout_().addWidget(head)
            chart = ChartWidget(title=f"home-ladder-{key}", height=2.3, width=4.8)
            ax = chart.axes()
            rows = ladder["rows"]
            vals = [r["value"] for r in rows]
            cols = [theme.STRATEGY_COLOURS.get(r["arm"], theme.BLUE) for r in rows]
            labels = []
            for r in rows:
                name = lexicon.strategy_name(r["arm"])
                if r["arm"] == "sacred":
                    name += " (trained here)"
                labels.append(name)
            ax.barh(range(len(rows)), vals, color=cols, height=0.62)
            ax.set_yticks(range(len(rows)), labels, fontsize=10)
            ax.invert_yaxis()
            for i, v in enumerate(vals):
                pct_label = lexicon.pct(v, 1) if (v * 100) % 1 else lexicon.pct(v)
                ax.text(v + 0.015, i, pct_label, va="center", fontsize=10,
                        color=theme.INK_SECONDARY)
            ax.set_xlim(0, max(vals) * 1.22)
            ax.xaxis.set_major_formatter(FuncFormatter(lambda x, _: f"{x * 100:.0f}%"))
            ax.set_xlabel(f"{lexicon.metric_phrase()} · {lexicon.CONDITION}",
                          fontsize=10)
            chart.set_caption(f"ledger: {ladder['ledger']}", "ledger")
            card.layout_().addWidget(chart)
            lr.addWidget(card, 1)
        lay.addWidget(ladders_row)

        # ------------------------------------------------------- entry doors
        grid = QGridLayout()
        grid.setSpacing(12)
        entries = [
            ("Watch the game", "Live duels on real city maps", 1),
            ("See the promises kept", "Six promises, each demonstrated", 2),
            ("Read the story", "From first failure to final result", 3),
            ("Check the sources", "Every document, searchable", 4),
        ]
        for col, (name, desc, idx) in enumerate(entries):
            btn = QPushButton(f"{name}\n{desc}")
            btn.setMinimumHeight(70)
            btn.setMinimumWidth(0)
            btn.setStyleSheet(
                f"QPushButton {{ text-align: left; padding: 12px 16px; font-size: 15px;"
                f"font-weight: 600; background: {theme.SURFACE}; }}")
            btn.clicked.connect(lambda _=False, i=idx: self.go_to.emit(i))
            grid.addWidget(btn, 0, col)
            grid.setColumnStretch(col, 1)
        lay.addLayout(grid)
        lay.addStretch(1)

        # ----------------------------------------------------- hero mechanics
        self._inst = None
        self._arms: dict[str, dict] = {}
        self._sortie_live = False
        self._anim_frac = 0.0
        self._timer = QTimer(self)
        self._timer.setInterval(33)
        self._timer.timeout.connect(self._tick)
        run_in_background(
            self._hero_worker,
            on_done=self._hero_ready,
            on_fail=lambda tb: (self.left.placeholder.setText(
                "The duel could not start: " + tb.strip().splitlines()[-1]),
                self.right.placeholder.setText("")))

    # ------------------------------------------------------------- hero loop

    @staticmethod
    def _hero_worker():
        inst = oracle_bridge.build_instance(
            "kaliningrad", "35", "159", 1, 3, 8, (0.15, 0.95))
        assignment, _ = oracle_bridge.alns_plan(inst)
        sacred_occ = None
        provenance = ""
        try:
            refs = [r for r in policies.discover_actors()
                    if r.family == "gen14_evidence"]
            if refs:
                pol = policies.load_policy(refs[0], inst)
                sacred_occ = inst.route_dist_to_stacked_occ_dist(
                    pol.route_distribution())
                provenance = refs[0].provenance
        except Exception:
            sacred_occ = None
        return inst, assignment, sacred_occ, provenance

    def _hero_ready(self, result) -> None:
        inst, assignment, sacred_occ, provenance = result
        self._inst = inst

        engines = {
            "planner": SortieEngine(inst, seed=_HERO_SEEDS["planner"]),
            "sacred": SortieEngine(inst, seed=_HERO_SEEDS["sacred"]),
        }
        planner_spec = engines["planner"].alns_spec(assignment)
        if sacred_occ is not None:
            sacred_spec = DefenderSpec("sacred", "SACRED", sacred_occ)
            sacred_note = provenance
        else:
            eq = {d.key: d for d in engines["sacred"].defender_specs()}["equilibrium"]
            sacred_spec = eq
            sacred_note = ("banked SACRED checkpoints unavailable; showing the "
                           "proven-optimal mix instead")

        for key, panel, spec in (("planner", self.left, planner_spec),
                                 ("sacred", self.right, sacred_spec)):
            engine = engines[key]
            attacker = engine.attacker_specs(spec)[0]
            exact = engine.exploitability(spec)
            panel.map.set_city(inst.city_map)
            panel.map.show_instance(inst.routes, inst.edge_vuln, inst.s, inst.t)
            marg = (spec.route_dist if spec.route_dist is not None
                    else engine._stacked_route_marginal(spec.occ_dist))
            panel.map.set_route_mixture(list(marg), panel.colour)
            panel.hero.set_fine_print(
                f"worst case, computed live: {lexicon.pct(exact)} · "
                f"seed {engine.seed}")
            panel.ready()
            self._arms[key] = {
                "engine": engine, "spec": spec, "attacker": attacker,
                "panel": panel, "outcome": None, "dots": [], "flashed": [],
                "exact": exact,
            }

        live_line = (
            f"computed live: the planner's worst case is "
            f"{lexicon.pct(self._arms['planner']['exact'])}, SACRED's is "
            f"{lexicon.pct(self._arms['sacred']['exact'])} · both against their own "
            f"fully-informed ambusher · seeds {_HERO_SEEDS['planner']} and "
            f"{_HERO_SEEDS['sacred']}")
        self.hero_record.add_line(live_line)
        if sacred_note:
            self.hero_record.add_line(sacred_note)

        # the panels are placeholder-sized when the instance lands; re-fit once
        # the grid has settled (and again on first show), or the view is cropped
        QTimer.singleShot(150, self._refit_maps)
        QTimer.singleShot(600, self._refit_maps)
        QTimer.singleShot(400, self._begin_cycle)
        self._timer.start()

    def _refit_maps(self) -> None:
        for panel in (self.left, self.right):
            panel.map.fit_routes()

    def showEvent(self, event):
        super().showEvent(event)
        if self._arms:
            QTimer.singleShot(80, self._refit_maps)

    def _begin_cycle(self) -> None:
        if not self._arms:
            return
        self._anim_frac = 0.0
        self._sortie_live = True
        for arm in self._arms.values():
            outcome = arm["engine"].play_sortie(arm["spec"], arm["attacker"])
            arm["outcome"] = outcome
            panel = arm["panel"]
            panel.map.clear_convoys()
            panel.map.show_ambush(outcome.iset_edges, revealed=False)
            arm["dots"] = [panel.map.add_convoy(panel.colour)
                           for _ in outcome.routes]
            arm["flashed"] = [False] * len(outcome.routes)

    def _tick(self) -> None:
        if not self._sortie_live or not self._arms:
            return
        if not self.isVisible():
            return
        self._anim_frac += 0.013
        done = self._anim_frac >= 1.0
        frac = min(1.0, self._anim_frac)
        for arm in self._arms.values():
            outcome = arm["outcome"]
            if outcome is None:
                continue
            panel = arm["panel"]
            for ci, (r, dot) in enumerate(zip(outcome.routes, arm["dots"])):
                caught_e = outcome.caught_edge[ci]
                stop_frac = 1.0
                if caught_e is not None:
                    fe = panel.map.fraction_of_edge(r, caught_e)
                    stop_frac = fe if fe is not None else 1.0
                f = min(frac, stop_frac)
                panel.map.place_on_route(dot, r, f)
                if caught_e is not None and frac >= stop_frac and not arm["flashed"][ci]:
                    arm["flashed"][ci] = True
                    panel.map.flash(dot)
                    panel.map.mark_lost(dot)
        if done:
            self._sortie_live = False
            for arm in self._arms.values():
                outcome = arm["outcome"]
                if outcome is None:
                    continue
                panel = arm["panel"]
                panel.map.reveal_ambush()
                if not outcome.mission_failed and arm["dots"]:
                    panel.map.celebrate(arm["dots"][0])
                panel.strip.push(outcome.mission_failed)
                panel.hero.set_value(arm["engine"].stats.rate)
                arm["outcome"] = None
            QTimer.singleShot(500, self._maybe_next)

    def _maybe_next(self) -> None:
        if self._arms:
            self._begin_cycle()

    def export_view(self):
        return export_widget_grab(self, "home")
