"""Playground mode 3: PLACE THE AMBUSH. You are the interdictor: pick a
defender, click a candidate edge to commit your ambush, and discover why a
calibrated mixed strategy cannot be beaten by any single placement."""

from __future__ import annotations

import numpy as np
from PySide6.QtCore import Qt, QTimer
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

from .. import theme
from ..game.sortie import DefenderSpec, SortieEngine
from ..sacred_bridge import oracle as oracle_bridge
from ..widgets.cards import Card, StateLabel
from ..widgets.charts import ChartWidget
from ..widgets.export import Exportable, export_widget_grab
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
        self.hint = QLabel("Click a heat-coloured edge to place your ambush (K=1).")
        self.hint.setStyleSheet(f"color: {theme.INK_SECONDARY};")
        bl.addWidget(self.hint)
        bl.addStretch(1)
        self.clear_btn = QPushButton("Clear ambush")
        self.clear_btn.clicked.connect(self._clear_ambush)
        bl.addWidget(self.clear_btn)
        lay.addWidget(bar)

        split = QSplitter(Qt.Horizontal)
        self.map = MapView()
        self.map.edge_clicked.connect(self._edge_clicked)
        split.addWidget(self.map)
        split.addWidget(self._build_readouts())
        split.setSizes([780, 330])
        lay.addWidget(split, 1)

    def _build_readouts(self) -> QWidget:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        host = QWidget()
        lay = QVBoxLayout(host)
        lay.setContentsMargins(0, 0, 4, 4)
        lay.setSpacing(8)

        self.score_card = Card()
        sh = QLabel("Your ambush vs the optimum")
        sh.setProperty("h3", True)
        self.score_card.layout_().addWidget(sh)
        self.score_label = QLabel("Place an ambush to score it.")
        self.score_label.setWordWrap(True)
        self.score_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.score_card.layout_().addWidget(self.score_label)
        self.score_chart = ChartWidget(title="ambush-score", height=2.2, width=3.4)
        self.score_card.layout_().addWidget(self.score_chart)
        cap = QLabel("computed live · exact expected values, no sampling")
        cap.setStyleSheet(f"color: {theme.LIVE_ACCENT}; font-size: 12px; font-weight: 600;")
        self.score_card.layout_().addWidget(cap)
        lay.addWidget(self.score_card)

        self.lesson_card = Card()
        lh = QLabel("Why you cannot win here")
        lh.setProperty("h3", True)
        self.lesson_card.layout_().addWidget(lh)
        lt = QLabel(
            "Against a DETERMINISTIC defender there is always a perfect ambush (find it!). "
            "Against the calibrated equilibrium mixture, every candidate edge yields at most "
            "the game value: the mixture makes all your options equally mediocre. That "
            "indifference IS the security-game equilibrium, and it is what SACRED learns.")
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
            self.hint.setText("Ambush placement is a K=1 exercise; set Assets K to 1.")
        else:
            self.hint.setText("Click a heat-coloured edge to place your ambush (K=1).")
        self._populate_defenders()

    def _populate_defenders(self) -> None:
        if self._engine is None:
            return
        self._defenders = self._engine.defender_specs()
        self.def_combo.blockSignals(True)
        self.def_combo.clear()
        for d in self._defenders:
            self.def_combo.addItem(d.label, d.key)
        # start with the deterministic defender: the player should first WIN
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
            self.hint.setText("That edge is not on any candidate route; pick a heat-coloured one.")
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
                "This exercise places a single asset; set Assets K to 1 in the sidebar.")
            return
        br_j, br_val = inst.exploitability_occ(d.occ_dist)
        ax = self.score_chart.clear()
        bars = [("best possible ambush", br_val, theme.STRATEGY_COLOURS["attacker"]),
                ("game value (loss_mixed)", inst.mc_value, theme.STRATEGY_COLOURS["equilibrium"])]
        if self._my_iset is not None:
            mine = float(d.occ_dist @ inst.obj_matrix[:, self._my_iset])
            bars.insert(0, ("YOUR ambush", mine, theme.STRATEGY_COLOURS["human"]))
            pct = 100.0 * mine / br_val if br_val > 0 else 0.0
            self.score_label.setText(
                f"Your ambush on edge {self._my_edge[0]}-{self._my_edge[1]} nets an expected "
                f"mission-failure of <b>{mine:.3f}</b> against “{d.label}”. The best possible "
                f"single ambush nets {br_val:.3f} ({pct:.0f}% of optimal play)."
                + ("<br><b>Note how close every edge is to the game value: the mixture has "
                   "made you indifferent.</b>" if d.key == "equilibrium" else ""))
        else:
            self.score_label.setText(
                f"“{d.label}”: the best possible single ambush nets {br_val:.3f}; "
                f"the game value is {inst.mc_value:.3f}. Place yours.")
        labels = [b[0] for b in bars]
        vals = [b[1] for b in bars]
        cols = [b[2] for b in bars]
        ax.barh(range(len(bars)), vals, color=cols, height=0.6)
        ax.set_yticks(range(len(bars)), labels)
        ax.invert_yaxis()
        for i, v in enumerate(vals):
            ax.text(v + 0.01, i, f"{v:.3f}", va="center", fontsize=11,
                    color=theme.INK_SECONDARY)
        ax.set_xlim(0, max(vals) * 1.25 + 0.05)
        self.score_chart.set_caption("expected mission failure per sortie", "live")
        self.score_chart.redraw()

    def export_view(self):
        return export_widget_grab(self, "playground-ambush")
