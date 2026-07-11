"""The Playground: pick an instance, then play with it in three modes.

WATCH: strategy vs strategy, converging to solved values.
DUEL: the within-episode pattern-of-life game (you or the gen19 policy vs the
adaptive interdictor).
AMBUSH: you are the interdictor; discover why mixing beats you.

The instance picker (city, screened OD presets, N, K, threat band) is shared;
each mode receives the solved OracleInstance. Space plays/pauses.
"""

from __future__ import annotations

import time

import yaml
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSlider,
    QSpinBox,
    QSplitter,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from .. import theme
from ..sacred_bridge import maps as maps_bridge
from ..sacred_bridge import oracle as oracle_bridge
from ..sacred_bridge.paths import DATA_DIR
from ..widgets.cards import hrule
from ..widgets.export import Exportable
from ..workers import run_in_background
from .pg_ambush import AmbushPanel
from .pg_duel import DuelPanel
from .pg_watch import WatchPanel


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
        self._building = False
        self._rebuild_pending = False

        lay = QHBoxLayout(self)
        lay.setContentsMargins(12, 8, 12, 12)
        split = QSplitter(Qt.Horizontal)
        lay.addWidget(split)

        split.addWidget(self._build_sidebar())

        self.stack = QStackedWidget()
        self.watch = WatchPanel()
        self.duel = DuelPanel()
        self.ambush = AmbushPanel()
        self.stack.addWidget(self.watch)
        self.stack.addWidget(self.duel)
        self.stack.addWidget(self.ambush)
        split.addWidget(self.stack)
        split.setSizes([280, 1080])

        QShortcut(QKeySequence(Qt.Key_Space), self, activated=self._space,
                  context=Qt.WidgetWithChildrenShortcut)

        self._populate_cities()
        QTimer.singleShot(50, self._rebuild_instance)

    # ------------------------------------------------------------- sidebar

    def _build_sidebar(self) -> QWidget:
        side = QWidget()
        lay = QVBoxLayout(side)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(8)

        def heading(text: str) -> QLabel:
            h = QLabel(text)
            h.setProperty("h3", True)
            return h

        lay.addWidget(heading("Mode"))
        self.mode_combo = QComboBox()
        self.mode_combo.addItem("Watch strategies play", 0)
        self.mode_combo.addItem("Pattern-of-life duel (you can play)", 1)
        self.mode_combo.addItem("You place the ambush", 2)
        self.mode_combo.currentIndexChanged.connect(self._mode_changed)
        lay.addWidget(self.mode_combo)

        lay.addWidget(hrule())
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

        self.k_warning = QLabel("K=3 enumerates ~80k interdiction sets; expect a ~20-30 s solve.")
        self.k_warning.setWordWrap(True)
        self.k_warning.setStyleSheet(f"color: {theme.INK_MUTED}; font-size: 10px;")
        self.k_warning.hide()
        lay.addWidget(self.k_warning)

        lay.addWidget(heading("Threat band"))
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
        seed_row = QWidget()
        sd = QHBoxLayout(seed_row)
        sd.setContentsMargins(0, 0, 0, 0)
        sd.addWidget(QLabel("Seed"))
        self.seed_spin = QSpinBox()
        self.seed_spin.setRange(0, 9999)
        self.seed_spin.setValue(0)
        self.seed_spin.valueChanged.connect(self._seed_changed)
        sd.addWidget(self.seed_spin)
        self.reset_btn = QPushButton("Reset stats")
        self.reset_btn.clicked.connect(lambda: self._panel().reset_stats()
                                       if hasattr(self._panel(), "reset_stats") else None)
        sd.addWidget(self.reset_btn)
        lay.addWidget(seed_row)

        lay.addStretch(1)
        self.status = QLabel("")
        self.status.setWordWrap(True)
        self.status.setStyleSheet(f"color: {theme.INK_MUTED}; font-size: 11px;")
        lay.addWidget(self.status)
        return side

    # ------------------------------------------------------------- helpers

    def _panel(self):
        return self.stack.currentWidget()

    def _space(self) -> None:
        p = self._panel()
        if hasattr(p, "toggle_play"):
            p.toggle_play()

    def _mode_changed(self) -> None:
        for p in (self.watch, self.duel):
            p.stop_play()
        self.stack.setCurrentIndex(self.mode_combo.currentData())
        if self._inst is not None:
            self._panel().set_instance(self._inst, self.od_combo.currentData(),
                                       self.seed_spin.value())

    def _seed_changed(self) -> None:
        p = self._panel()
        if hasattr(p, "set_seed"):
            p.set_seed(self.seed_spin.value())

    # ------------------------------------------------------------- pickers

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
            + (" (the headline setting)" if (lo, hi) == (0.15, 0.95) else ""))
        self._schedule_rebuild()

    # ------------------------------------------------------------- rebuild

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
        for panel in (self.watch, self.duel):
            panel.stop_play()
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
        self.status.setText(
            f"{inst.n_routes} routes · {len(inst.interdiction_sets)} interdiction sets · "
            f"solved in {dt * 1000:.0f} ms")
        self._panel().set_instance(inst, self.od_combo.currentData(), self.seed_spin.value())

    # ------------------------------------------------------------- export

    def export_view(self):
        p = self._panel()
        if isinstance(p, Exportable):
            return p.export_view()
        return []
