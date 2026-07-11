"""The Playground: pick an instance, watch the security game live.

Left = instance picker (city, screened OD presets, N, K, threat band) and the
strategy roster. Centre = the map. Right = live oracle readouts, banked ledger
anchors where the cell matches, and the running sortie estimate converging to
the exact value. Space plays/pauses the sortie loop.
"""

from __future__ import annotations

import time

import numpy as np
from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSlider,
    QSpinBox,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

import yaml

from .. import theme
from ..game.sortie import AttackerSpec, DefenderSpec, SortieEngine, SortieOutcome
from ..sacred_bridge import maps as maps_bridge
from ..sacred_bridge import oracle as oracle_bridge
from ..sacred_bridge.paths import DATA_DIR
from ..widgets.cards import Card, EraBadge, StateLabel, hrule
from ..widgets.charts import ChartWidget
from ..widgets.export import Exportable, export_widget_grab
from ..workers import run_in_background


def _load_presets() -> dict:
    try:
        return yaml.safe_load((DATA_DIR / "od_presets.yaml").read_text())["presets"]
    except Exception:
        return {}


class PlaygroundTab(QWidget, Exportable):
    export_name = "playground"

    def __init__(self, parent=None):
        super().__init__(parent)
        self._presets = _load_presets()
        self._inst: oracle_bridge.OracleInstance | None = None
        self._engine: SortieEngine | None = None
        self._defenders: list[DefenderSpec] = []
        self._attackers: list[AttackerSpec] = []
        self._city_loaded: str = ""
        self._playing = False
        self._anim_frac = 0.0
        self._speed = 1.0
        self._outcome: SortieOutcome | None = None
        self._dots = []
        self._building = False
        self._rebuild_pending = False
        self._alns_assignment: list[int] | None = None

        lay = QHBoxLayout(self)
        lay.setContentsMargins(12, 8, 12, 12)
        split = QSplitter(Qt.Horizontal)
        lay.addWidget(split)

        split.addWidget(self._build_sidebar())

        from ..widgets.mapview import MapView
        self.map = MapView()
        split.addWidget(self.map)

        split.addWidget(self._build_readouts())
        split.setSizes([290, 760, 330])

        self._timer = QTimer(self)
        self._timer.setInterval(33)
        self._timer.timeout.connect(self._tick)

        QShortcut(QKeySequence(Qt.Key_Space), self, activated=self.toggle_play,
                  context=Qt.WidgetWithChildrenShortcut)

        self._populate_cities()
        QTimer.singleShot(50, self._rebuild_instance)

    # ================================================================ sidebar

    def _build_sidebar(self) -> QWidget:
        side = QWidget()
        lay = QVBoxLayout(side)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(8)

        def heading(text: str) -> QLabel:
            h = QLabel(text)
            h.setProperty("h3", True)
            return h

        lay.addWidget(heading("Instance"))
        self.city_combo = QComboBox()
        self.city_combo.currentIndexChanged.connect(self._city_changed)
        lay.addWidget(self.city_combo)

        self.od_combo = QComboBox()
        self.od_combo.currentIndexChanged.connect(self._od_changed)
        lay.addWidget(self.od_combo)

        grid = QWidget()
        g = QHBoxLayout(grid)
        g.setContentsMargins(0, 0, 0, 0)
        g.addWidget(QLabel("Convoys N"))
        self.n_spin = QSpinBox()
        self.n_spin.setRange(1, 5)
        self.n_spin.setValue(3)
        self.n_spin.valueChanged.connect(self._schedule_rebuild)
        g.addWidget(self.n_spin)
        g.addWidget(QLabel("Assets K"))
        self.k_spin = QSpinBox()
        self.k_spin.setRange(1, 3)
        self.k_spin.setValue(1)
        self.k_spin.valueChanged.connect(self._schedule_rebuild)
        g.addWidget(self.k_spin)
        lay.addWidget(grid)

        self.k_warning = QLabel("K=3 enumerates ~80k interdiction sets; the re-solve can take ~20-30 s.")
        self.k_warning.setWordWrap(True)
        self.k_warning.setStyleSheet(f"color: {theme.INK_MUTED}; font-size: 10px;")
        self.k_warning.hide()
        lay.addWidget(self.k_warning)

        lay.addWidget(heading("Threat band (edge vulnerability)"))
        from PySide6.QtWidgets import QCheckBox
        self.hard_check = QCheckBox("Hard interception (all-or-nothing)")
        self.hard_check.toggled.connect(self._hard_toggled)
        lay.addWidget(self.hard_check)
        band_row = QWidget()
        br = QHBoxLayout(band_row)
        br.setContentsMargins(0, 0, 0, 0)
        self.band_lo = QSlider(Qt.Horizontal)
        self.band_lo.setRange(5, 50)
        self.band_lo.setValue(15)
        self.band_hi = QSlider(Qt.Horizontal)
        self.band_hi.setRange(50, 99)
        self.band_hi.setValue(95)
        for s in (self.band_lo, self.band_hi):
            s.valueChanged.connect(self._band_changed)
            br.addWidget(s)
        lay.addWidget(band_row)
        self.band_label = QLabel("band 0.15 - 0.95 (the headline setting)")
        self.band_label.setStyleSheet(f"color: {theme.INK_MUTED}; font-size: 10px;")
        lay.addWidget(self.band_label)

        lay.addWidget(hrule())
        lay.addWidget(heading("Defender"))
        self.def_combo = QComboBox()
        self.def_combo.currentIndexChanged.connect(self._matchup_changed)
        lay.addWidget(self.def_combo)

        self.alns_btn = QPushButton("Compute ALNS plan (adds to roster)")
        self.alns_btn.clicked.connect(self._compute_alns)
        lay.addWidget(self.alns_btn)

        lay.addWidget(heading("Attacker"))
        self.att_combo = QComboBox()
        self.att_combo.currentIndexChanged.connect(self._matchup_changed)
        lay.addWidget(self.att_combo)

        lay.addWidget(hrule())
        lay.addWidget(heading("Sortie loop"))
        self.play_btn = QPushButton("▶ Play sorties (Space)")
        self.play_btn.setProperty("accent", True)
        self.play_btn.clicked.connect(self.toggle_play)
        lay.addWidget(self.play_btn)

        speed_row = QWidget()
        sr = QHBoxLayout(speed_row)
        sr.setContentsMargins(0, 0, 0, 0)
        self.speed_combo = QComboBox()
        self.speed_combo.addItems(["1x", "3x", "8x"])
        self.speed_combo.currentTextChanged.connect(
            lambda t: setattr(self, "_speed", float(t.rstrip("x"))))
        sr.addWidget(QLabel("Speed"))
        sr.addWidget(self.speed_combo)
        self.batch_btn = QPushButton("Run 500 instantly")
        self.batch_btn.clicked.connect(self._run_batch)
        sr.addWidget(self.batch_btn)
        lay.addWidget(speed_row)

        seed_row = QWidget()
        sd = QHBoxLayout(seed_row)
        sd.setContentsMargins(0, 0, 0, 0)
        sd.addWidget(QLabel("Seed"))
        self.seed_spin = QSpinBox()
        self.seed_spin.setRange(0, 9999)
        self.seed_spin.setValue(0)
        self.seed_spin.valueChanged.connect(self._reseed)
        sd.addWidget(self.seed_spin)
        self.reset_btn = QPushButton("Reset stats")
        self.reset_btn.clicked.connect(self._reset_stats)
        sd.addWidget(self.reset_btn)
        lay.addWidget(seed_row)

        lay.addStretch(1)
        self.status = QLabel("")
        self.status.setWordWrap(True)
        self.status.setStyleSheet(f"color: {theme.INK_MUTED}; font-size: 11px;")
        lay.addWidget(self.status)
        return side

    # ================================================================ readouts

    def _build_readouts(self) -> QWidget:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        host = QWidget()
        lay = QVBoxLayout(host)
        lay.setContentsMargins(0, 0, 4, 4)
        lay.setSpacing(8)

        self.oracle_card = Card()
        oh = QLabel("The game, solved live")
        oh.setProperty("h3", True)
        self.oracle_card.layout_().addWidget(oh)
        self.lbl_det = QLabel("…")
        self.lbl_mixed = QLabel("…")
        self.lbl_expl = QLabel("…")
        self.lbl_expected = QLabel("…")
        for lbl in (self.lbl_det, self.lbl_mixed, self.lbl_expl, self.lbl_expected):
            lbl.setWordWrap(True)
            lbl.setTextInteractionFlags(Qt.TextSelectableByMouse)
            self.oracle_card.layout_().addWidget(lbl)
        live_cap = QLabel("computed live · LP oracle, this instance, this second")
        live_cap.setStyleSheet(f"color: {theme.LIVE_ACCENT}; font-size: 10px; font-weight: 600;")
        self.oracle_card.layout_().addWidget(live_cap)
        lay.addWidget(self.oracle_card)

        self.banked_card = Card()
        bh = QLabel("The banked record for this instance")
        bh.setProperty("h3", True)
        self.banked_card.layout_().addWidget(bh)
        self.banked_body = QVBoxLayout()
        self.banked_card.layout_().addLayout(self.banked_body)
        self.banked_card.hide()
        lay.addWidget(self.banked_card)

        self.run_card = Card()
        rh = QLabel("Running estimate")
        rh.setProperty("h3", True)
        self.run_card.layout_().addWidget(rh)
        self.run_label = QLabel("No sorties yet. Press Space.")
        self.run_label.setWordWrap(True)
        self.run_card.layout_().addWidget(self.run_label)
        self.run_chart = ChartWidget(title="playground-convergence", height=2.3, width=3.4)
        self.run_card.layout_().addWidget(self.run_chart)
        lay.addWidget(self.run_card)

        lay.addStretch(1)
        scroll.setWidget(host)
        return scroll

    # ================================================================ pickers

    def _populate_cities(self) -> None:
        self.city_combo.blockSignals(True)
        self.city_combo.clear()
        for c in maps_bridge.available_cities():
            self.city_combo.addItem(maps_bridge.CITY_LABELS.get(c, c), c)
        self.city_combo.blockSignals(False)
        self._city_changed()

    def _city_changed(self) -> None:
        city = self.city_combo.currentData()
        self.od_combo.blockSignals(True)
        self.od_combo.clear()
        for p in self._presets.get(city, []):
            self.od_combo.addItem(p["label"], p)
        if self.od_combo.count() == 0:
            self.od_combo.addItem("no screened presets for this city", None)
        self.od_combo.blockSignals(False)
        self._od_changed()

    def _od_changed(self) -> None:
        p = self.od_combo.currentData()
        if p:
            self.n_spin.blockSignals(True)
            self.k_spin.blockSignals(True)
            self.hard_check.blockSignals(True)
            self.n_spin.setValue(int(p.get("N", 3)))
            self.k_spin.setValue(int(p.get("K", 1)))
            self.hard_check.setChecked(bool(p.get("hard", False)))
            self._hard_toggled(self.hard_check.isChecked(), rebuild=False)
            self.n_spin.blockSignals(False)
            self.k_spin.blockSignals(False)
            self.hard_check.blockSignals(False)
        self._schedule_rebuild()

    def _hard_toggled(self, on: bool, rebuild: bool = True) -> None:
        self.band_lo.setEnabled(not on)
        self.band_hi.setEnabled(not on)
        if rebuild:
            self._schedule_rebuild()

    def _band_changed(self) -> None:
        lo, hi = self.band_lo.value() / 100, self.band_hi.value() / 100
        self.band_label.setText(
            f"band {lo:.2f} - {hi:.2f}"
            + (" (the headline setting)" if (lo, hi) == (0.15, 0.95) else "")
        )
        self._schedule_rebuild()

    # ================================================================ rebuild

    def _schedule_rebuild(self) -> None:
        self.k_warning.setVisible(self.k_spin.value() >= 3)
        if not hasattr(self, "_debounce"):
            self._debounce = QTimer(self)
            self._debounce.setSingleShot(True)
            self._debounce.timeout.connect(self._rebuild_instance)
        self._debounce.start(350)

    def _rebuild_instance(self) -> None:
        p = self.od_combo.currentData()
        city = self.city_combo.currentData()
        if not city or not p:
            self.status.setText("Pick a city with screened presets.")
            return
        if self._building:
            self._rebuild_pending = True
            return
        self._building = True
        self._stop_play()
        s, t = p["od"].split("-")
        K, N = self.k_spin.value(), self.n_spin.value()
        band = None if self.hard_check.isChecked() else (
            self.band_lo.value() / 100, self.band_hi.value() / 100)
        self.status.setText(f"Solving {city} {s}-{t}  K={K} N={N} …")
        t0 = time.perf_counter()
        run_in_background(
            oracle_bridge.build_instance, city, s, t, K, N, int(p.get("k_extra", 8)), band,
            on_done=lambda inst: self._instance_ready(inst, time.perf_counter() - t0),
            on_fail=self._instance_failed,
        )

    def _instance_failed(self, tb: str) -> None:
        self._building = False
        self.status.setText("Instance failed to build. Last line:\n" + tb.strip().splitlines()[-1])

    def _instance_ready(self, inst: oracle_bridge.OracleInstance, dt: float) -> None:
        self._building = False
        if self._rebuild_pending:
            self._rebuild_pending = False
            self._rebuild_instance()
            return
        self._inst = inst
        self._alns_assignment = None
        self._engine = SortieEngine(inst, seed=self.seed_spin.value())
        if inst.city != self._city_loaded:
            self.map.set_city(inst.city_map)
            self._city_loaded = inst.city
        self.map.show_instance(inst.routes, inst.edge_vuln, inst.s, inst.t)
        self.status.setText(
            f"{inst.n_routes} routes · {len(inst.interdiction_sets)} interdiction sets · "
            f"solved in {dt * 1000:.0f} ms"
        )
        self._refresh_defenders()
        self._show_banked()

    def _refresh_defenders(self) -> None:
        if self._engine is None:
            return
        self._defenders = self._engine.defender_specs()
        if self._alns_assignment is not None:
            self._defenders.append(self._engine.alns_spec(self._alns_assignment))
        sel = self.def_combo.currentIndex()
        self.def_combo.blockSignals(True)
        self.def_combo.clear()
        for d in self._defenders:
            self.def_combo.addItem(d.label, d.key)
        default = next((i for i, d in enumerate(self._defenders) if d.key == "equilibrium"), 0)
        self.def_combo.setCurrentIndex(sel if 0 <= sel < len(self._defenders) else default)
        self.def_combo.blockSignals(False)
        self._matchup_changed()

    def _current_defender(self) -> DefenderSpec | None:
        i = self.def_combo.currentIndex()
        return self._defenders[i] if 0 <= i < len(self._defenders) else None

    def _current_attacker(self) -> AttackerSpec | None:
        i = self.att_combo.currentIndex()
        return self._attackers[i] if 0 <= i < len(self._attackers) else None

    def _matchup_changed(self) -> None:
        if self._engine is None or self._inst is None:
            return
        d = self._current_defender()
        if d is None:
            return
        # attacker list depends on the defender (BR re-aims)
        keep = self.att_combo.currentIndex()
        self._attackers = self._engine.attacker_specs(d)
        self.att_combo.blockSignals(True)
        self.att_combo.clear()
        for a in self._attackers:
            self.att_combo.addItem(a.label, a.key)
        self.att_combo.setCurrentIndex(keep if 0 <= keep < len(self._attackers) else 0)
        self.att_combo.blockSignals(False)

        if d.route_dist is not None:
            self.map.set_route_mixture(list(d.route_dist))
        else:
            marg = self._engine._stacked_route_marginal(d.occ_dist)
            self.map.set_route_mixture(list(marg))
        self._engine.reset_stats()
        self._update_readouts()
        self._redraw_convergence()

    def _update_readouts(self) -> None:
        if self._engine is None or self._inst is None:
            return
        inst = self._inst
        d = self._current_defender()
        a = self._current_attacker()
        self.lbl_det.setText(
            f"<b>loss_det = {inst.mc_loss_det:.3f}</b> · the best any DETERMINISTIC plan "
            "can do against a committed attacker (what ALNS converges to)"
        )
        self.lbl_mixed.setText(
            f"<b>loss_mixed = {inst.mc_value:.3f}</b> · the minimax equilibrium value "
            "(calibrated MIXED strategy)"
        )
        if d is not None:
            e = self._engine.exploitability(d)
            self.lbl_expl.setText(
                f"<b>{e:.3f}</b> · worst-case mission failure of “{d.label}” "
                "under the oracle best response"
            )
        if d is not None and a is not None:
            ev = self._engine.expected_value(d, a)
            self.lbl_expected.setText(
                f"<b>{ev:.3f}</b> · exact expected mission failure of this matchup "
                "(the running estimate below converges here)"
            )

    def _show_banked(self) -> None:
        # clear previous rows
        while self.banked_body.count():
            it = self.banked_body.takeAt(0)
            w = it.widget()
            if w:
                w.deleteLater()
        p = self.od_combo.currentData()
        if not p or not p.get("banked"):
            self.banked_card.hide()
            return
        shown = False
        for bank in p["banked"]:
            head = QWidget()
            hl = QHBoxLayout(head)
            hl.setContentsMargins(0, 0, 0, 0)
            hl.setSpacing(6)
            cell = QLabel(f"banked at {bank['cell']}")
            cell.setStyleSheet(f"color: {theme.INK_SECONDARY}; font-size: 11px; font-weight: 600;")
            hl.addWidget(cell)
            hl.addWidget(EraBadge(bank.get("era", "post-fix")))
            hl.addStretch(1)
            self.banked_body.addWidget(head)
            for item in bank["items"]:
                q = QLabel(item["quote"])
                q.setWordWrap(True)
                q.setTextInteractionFlags(Qt.TextSelectableByMouse)
                q.setStyleSheet(
                    f"font-size: 12px; background: {theme.PAGE}; border-left: 3px solid "
                    f"{theme.BASELINE}; border-radius: 4px; padding: 5px 8px;"
                )
                src = QLabel("ledger: " + item.get("ledger", bank["ledger"]))
                src.setStyleSheet(f"color: {theme.INK_MUTED}; font-size: 10px;")
                self.banked_body.addWidget(q)
                self.banked_body.addWidget(src)
            shown = True
        mismatch = ""
        if p.get("banked"):
            cell0 = p["banked"][0].get("cell", "")
            if f"N={self.n_spin.value()} K={self.k_spin.value()}" not in cell0:
                mismatch = ("Note: the picker is not at the banked cell; the anchors above "
                            "apply at " + cell0 + ".")
        if mismatch:
            m = QLabel(mismatch)
            m.setWordWrap(True)
            m.setStyleSheet(f"color: {theme.INK_MUTED}; font-size: 10px;")
            self.banked_body.addWidget(m)
        self.banked_card.setVisible(shown)

    # ================================================================ ALNS

    def _compute_alns(self) -> None:
        if self._inst is None:
            return
        self.alns_btn.setEnabled(False)
        self.alns_btn.setText("ALNS running…")
        run_in_background(
            oracle_bridge.alns_plan, self._inst,
            on_done=self._alns_done,
            on_fail=lambda tb: (self.alns_btn.setEnabled(True),
                                self.alns_btn.setText("Compute ALNS plan (adds to roster)")),
        )

    def _alns_done(self, result) -> None:
        assignment, expl = result
        self._alns_assignment = assignment
        self.alns_btn.setEnabled(True)
        self.alns_btn.setText(f"ALNS plan ready (worst case {expl:.3f})")
        self._refresh_defenders()
        idx = next((i for i, d in enumerate(self._defenders) if d.key == "alns"), None)
        if idx is not None:
            self.def_combo.setCurrentIndex(idx)

    # ================================================================ sortie loop

    def toggle_play(self) -> None:
        if self._playing:
            self._stop_play()
        else:
            if self._engine is None:
                return
            self._playing = True
            self.play_btn.setText("⏸ Pause (Space)")
            self._begin_sortie()
            self._timer.start()

    def _stop_play(self) -> None:
        self._playing = False
        self._timer.stop()
        self.play_btn.setText("▶ Play sorties (Space)")

    def _begin_sortie(self) -> None:
        if self._engine is None:
            return
        d, a = self._current_defender(), self._current_attacker()
        if d is None or a is None:
            return
        self._outcome = self._engine.play_sortie(d, a)
        self._anim_frac = 0.0
        self.map.clear_convoys()
        self.map.show_ambush(self._outcome.iset_edges, revealed=False)
        self._dots = []
        self._flashed = [False] * len(self._outcome.routes)
        for _r in self._outcome.routes:
            self._dots.append(self.map.add_convoy())

    def _tick(self) -> None:
        if self._outcome is None:
            return
        self._anim_frac += 0.011 * self._speed
        done = self._anim_frac >= 1.0
        frac = min(1.0, self._anim_frac)
        for ci, (r, dot) in enumerate(zip(self._outcome.routes, self._dots)):
            caught_e = self._outcome.caught_edge[ci]
            stop_frac = 1.0
            if caught_e is not None:
                stop_frac = self._edge_frac(r, caught_e)
            f = min(frac, stop_frac)
            self.map.place_on_route(dot, r, f)
            if caught_e is not None and frac >= stop_frac and not self._flashed[ci]:
                self._flashed[ci] = True
                self.map.flash(dot)
                self.map.mark_lost(dot)
        if done:
            self.map.reveal_ambush()
            self._update_running()
            if self._playing:
                QTimer.singleShot(int(420 / self._speed), self._maybe_next)
            self._outcome = None

    def _maybe_next(self) -> None:
        if self._playing:
            self._begin_sortie()

    def _edge_frac(self, route_idx: int, edge: tuple[str, str]) -> float:
        """Fraction along the route at which the given edge is exited (flash point)."""
        if self._inst is None:
            return 1.0
        nodes = self._inst.routes[route_idx]
        # cumulative cost fractions edge by edge (uniform per edge is fine visually)
        n_edges = max(1, len(nodes) - 1)
        for i, (a, b) in enumerate(zip(nodes[:-1], nodes[1:])):
            if tuple(sorted((a, b))) == tuple(sorted(edge)):
                return (i + 0.55) / n_edges
        return 1.0

    def _run_batch(self) -> None:
        if self._engine is None:
            return
        d, a = self._current_defender(), self._current_attacker()
        if d is None or a is None:
            return
        self._stop_play()
        for _ in range(500):
            self._engine.play_sortie(d, a)
        self.map.clear_convoys()
        self.map.clear_ambush()
        self._update_running()

    def _reseed(self) -> None:
        if self._engine is not None:
            self._engine.reseed(self.seed_spin.value())
            self._update_running()

    def _reset_stats(self) -> None:
        if self._engine is not None:
            self._engine.reset_stats()
            self._update_running()

    def _update_running(self) -> None:
        if self._engine is None:
            return
        st = self._engine.stats
        d, a = self._current_defender(), self._current_attacker()
        ev = self._engine.expected_value(d, a) if (d and a) else float("nan")
        self.run_label.setText(
            f"<b>{st.rate:.3f}</b> mission-failure rate over {st.n} sorties "
            f"(seed {self._engine.seed}) · exact value {ev:.3f}"
        )
        self._redraw_convergence()

    def _redraw_convergence(self) -> None:
        if self._engine is None or self._inst is None:
            return
        ax = self.run_chart.clear()
        st = self._engine.stats
        d, a = self._current_defender(), self._current_attacker()
        if st.history:
            ax.plot(range(1, len(st.history) + 1), st.history,
                    color=theme.STRATEGY_COLOURS["sacred"], linewidth=1.8,
                    label="running estimate")
        if d is not None and a is not None:
            ev = self._engine.expected_value(d, a)
            ax.axhline(ev, color=theme.INK, linewidth=1.1, linestyle="--")
            ax.annotate(f"exact {ev:.3f}", xy=(1.0, ev), xycoords=("axes fraction", "data"),
                        fontsize=8, ha="right", va="bottom", color=theme.INK)
        ax.axhline(self._inst.mc_loss_det, color=theme.STRATEGY_COLOURS["alns"],
                   linewidth=1.0, linestyle=":")
        ax.axhline(self._inst.mc_value, color=theme.STRATEGY_COLOURS["equilibrium"],
                   linewidth=1.0, linestyle=":")
        ax.annotate(f"loss_det {self._inst.mc_loss_det:.3f}", xy=(0.0, self._inst.mc_loss_det),
                    xycoords=("axes fraction", "data"), fontsize=7.5, va="bottom",
                    color=theme.STRATEGY_COLOURS["alns"])
        ax.annotate(f"equilibrium {self._inst.mc_value:.3f}", xy=(0.0, self._inst.mc_value),
                    xycoords=("axes fraction", "data"), fontsize=7.5, va="bottom",
                    color=theme.STRATEGY_COLOURS["equilibrium"])
        ax.set_ylim(-0.03, 1.03)
        ax.set_xlabel("sortie")
        self.run_chart.set_caption(
            f"seed {self._engine.seed} · mission-failure per sortie", "live")
        self.run_chart.redraw()

    # ================================================================ export

    def export_view(self):
        return export_widget_grab(self, "playground")
