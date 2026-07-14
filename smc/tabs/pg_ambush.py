"""Playground · You attack: place the ambush yourself and learn why the
proven-optimal mix cannot be beaten by any single placement."""

from __future__ import annotations

import matplotlib.ticker as mtick
import numpy as np
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from .. import lexicon, theme
from ..game.sortie import DefenderSpec, SortieEngine
from ..sacred_bridge import oracle as oracle_bridge
from ..widgets.cards import Card
from ..widgets.charts import ChartWidget
from ..widgets.export import Exportable, export_widget_grab
from ..widgets.human import MapLegend
from ..widgets.mapview import MapView


class AmbushPanel(QWidget, Exportable):
    export_name = "playground-ambush"

    def __init__(self, parent=None):
        super().__init__(parent)
        self._inst: oracle_bridge.OracleInstance | None = None
        self._engine: SortieEngine | None = None
        self._defenders: list[DefenderSpec] = []
        self._my_edge: tuple[str, str] | None = None
        self._my_iset: int | None = None
        self.seed = 0

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(6)

        bar = QWidget()
        bl = QHBoxLayout(bar)
        bl.setContentsMargins(0, 0, 0, 0)
        bl.setSpacing(8)
        bl.addWidget(QLabel("Defender"))
        self.def_combo = QComboBox()
        self.def_combo.currentIndexChanged.connect(self._defender_changed)
        bl.addWidget(self.def_combo)
        self.hint = QLabel("Pick where to lie in wait: click any coloured road.")
        self.hint.setStyleSheet(f"color: {theme.INK_SECONDARY};")
        bl.addWidget(self.hint)
        bl.addStretch(1)
        self.clear_btn = QPushButton("Clear the ambush")
        self.clear_btn.setProperty("quiet", True)
        self.clear_btn.clicked.connect(self._clear_ambush)
        bl.addWidget(self.clear_btn)
        lay.addWidget(bar)

        split = QSplitter(Qt.Horizontal)
        map_col = QWidget()
        ml = QVBoxLayout(map_col)
        ml.setContentsMargins(0, 0, 0, 0)
        ml.setSpacing(2)
        self.map = MapView()
        self.map.edge_clicked.connect(self._edge_clicked)
        ml.addWidget(self.map, 1)
        ml.addWidget(MapLegend())
        split.addWidget(map_col)
        split.addWidget(self._build_readouts())
        split.setSizes([760, 350])
        lay.addWidget(split, 1)

    def _build_readouts(self) -> QWidget:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        host = QWidget()
        lay = QVBoxLayout(host)
        lay.setContentsMargins(0, 0, 4, 4)
        lay.setSpacing(10)

        self.score_card = Card()
        sh = QLabel("Your ambush against the best possible one")
        sh.setProperty("h3", True)
        self.score_card.layout_().addWidget(sh)
        self.score_label = QLabel(
            "The defender's driving habits are on the map: thicker roads are "
            "used more often. Your ambush pays off when a convoy drives through "
            "it. Place one to score it.")
        self.score_label.setWordWrap(True)
        self.score_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.score_card.layout_().addWidget(self.score_label)
        self.score_chart = ChartWidget(title="ambush-score", height=2.2, width=3.4)
        self.score_card.layout_().addWidget(self.score_chart)
        cap = QLabel("computed live · exact expected values, no dice")
        cap.setStyleSheet(
            f"color: {theme.LIVE_ACCENT}; font-size: 12px; font-weight: 600;")
        self.score_card.layout_().addWidget(cap)
        lay.addWidget(self.score_card)

        self.lesson_card = Card()
        lh = QLabel("Why you cannot win here")
        lh.setProperty("h3", True)
        self.lesson_card.layout_().addWidget(lh)
        lt = QLabel(
            "Against a predictable defender there is always a perfect ambush — "
            "find it. Against the proven-optimal mix, every spot you can pick "
            "pays exactly the same, and no spot pays more than the game's "
            "proven floor. That built-in indifference is the whole idea, and it "
            "is what SACRED learns to play.")
        lt.setWordWrap(True)
        self.lesson_card.layout_().addWidget(lt)
        lay.addWidget(self.lesson_card)

        lay.addStretch(1)
        scroll.setWidget(host)
        return scroll

    # ------------------------------------------------------------- instance

    def set_instance(self, inst: oracle_bridge.OracleInstance, preset: dict | None,
                     seed: int) -> None:
        self._inst = inst
        self.seed = seed
        self._engine = SortieEngine(inst, seed=seed)
        self._my_edge = None
        self._my_iset = None
        self.map.set_city(inst.city_map)
        self.map.show_instance(inst.routes, inst.edge_vuln, inst.s, inst.t)
        self.map.set_edge_click_mode(True)
        if inst.K != 1:
            self.hint.setText(
                "This game places a single ambush; set ambush teams to 1 in the rules.")
        else:
            self.hint.setText("Pick where to lie in wait: click any coloured road.")
        self._populate_defenders()

    def _populate_defenders(self) -> None:
        if self._engine is None:
            return
        self._defenders = self._engine.defender_specs()
        self.def_combo.blockSignals(True)
        self.def_combo.clear()
        for d in self._defenders:
            self.def_combo.addItem(lexicon.strategy_name(d.key) or d.label, d.key)
            self.def_combo.setItemData(
                self.def_combo.count() - 1,
                lexicon.strategy_blurb(d.key) or d.label, Qt.ToolTipRole)
        # start with the predictable defender: the player should first WIN
        idx = next((i for i, d in enumerate(self._defenders) if d.key == "shortest"), 0)
        self.def_combo.setCurrentIndex(idx)
        self.def_combo.blockSignals(False)
        self._defender_changed()

    def _current_defender(self) -> DefenderSpec | None:
        i = self.def_combo.currentIndex()
        return self._defenders[i] if 0 <= i < len(self._defenders) else None

    def _defender_changed(self) -> None:
        d = self._current_defender()
        if d is None or self._engine is None:
            return
        if d.route_dist is not None:
            self.map.set_route_mixture(list(d.route_dist))
        else:
            self.map.set_route_mixture(list(self._engine._stacked_route_marginal(d.occ_dist)))
        self._rescore()

    # ------------------------------------------------------------- ambush

    def _edge_clicked(self, u: str, v: str) -> None:
        if self._inst is None or self._inst.K != 1:
            return
        target = frozenset({u, v})
        iset_idx = None
        for j, iset in enumerate(self._inst.interdiction_sets):
            if len(iset) == 1 and iset[0] == target:
                iset_idx = j
                break
        if iset_idx is None:
            self.hint.setText("That road is never used by the defender; pick a coloured one.")
            return
        self._my_edge = (u, v)
        self._my_iset = iset_idx
        self.map.show_ambush([(u, v)], revealed=True)
        self._rescore()

    def _clear_ambush(self) -> None:
        self._my_edge = None
        self._my_iset = None
        self.map.clear_ambush()
        self._rescore()

    def _rescore(self) -> None:
        if self._inst is None:
            return
        d = self._current_defender()
        if d is None:
            return
        inst = self._inst
        if inst.K != 1:
            self.score_chart.clear()
            self.score_chart.redraw()
            self.score_label.setText(
                "This game places a single ambush; set ambush teams to 1 in the rules.")
            return
        name = lexicon.strategy_name(d.key) or d.label
        br_j, br_val = inst.exploitability_occ(d.occ_dist)
        ax = self.score_chart.clear()
        bars = [("The best possible ambush", br_val, theme.STRATEGY_COLOURS["attacker"]),
                ("The game's proven floor", inst.mc_value,
                 theme.STRATEGY_COLOURS["equilibrium"])]
        if self._my_iset is not None:
            mine = float(d.occ_dist @ inst.obj_matrix[:, self._my_iset])
            bars.insert(0, ("Your ambush", mine, theme.STRATEGY_COLOURS["human"]))
            share = 100.0 * mine / br_val if br_val > 0 else 0.0
            self.score_label.setText(
                f"Your ambush catches the mission <b>{lexicon.pct(mine)}</b> of the "
                f"time against “{name}”. The best possible ambush gets "
                f"{lexicon.pct(br_val)} — you are at {share:.0f}% of perfect play."
                + ("<br><b>Notice every road pays you almost the same: the mix has "
                   "made you indifferent. That is the point.</b>"
                   if d.key == "equilibrium" else ""))
        else:
            self.score_label.setText(
                f"Against “{name}” the best possible ambush catches the mission "
                f"{lexicon.pct(br_val)} of the time; the proven floor is "
                f"{lexicon.pct(inst.mc_value)}. Place yours.")
        labels = [b[0] for b in bars]
        vals = [b[1] for b in bars]
        cols = [b[2] for b in bars]
        ax.barh(range(len(bars)), vals, color=cols, height=0.6)
        ax.set_yticks(range(len(bars)), labels)
        ax.invert_yaxis()
        for i, v in enumerate(vals):
            ax.text(v + 0.01, i, lexicon.pct(v), va="center", fontsize=11,
                    color=theme.INK_SECONDARY)
        ax.set_xlim(0, max(vals) * 1.25 + 0.05)
        ax.xaxis.set_major_formatter(mtick.PercentFormatter(1.0, decimals=0))
        ax.set_xlabel("share of missions caught")
        self.score_chart.set_caption("chance the mission fails, per ambush spot", "live")
        self.score_chart.redraw()

    def export_view(self):
        return export_widget_grab(self, "playground-ambush")
