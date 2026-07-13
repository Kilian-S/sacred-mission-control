"""The Playground: pick an instance, then play with it in four modes.

WATCH: strategy vs strategy, converging to solved values.
DUEL: the within-episode pattern-of-life game (you or the gen19 policy vs the
adaptive interdictor).
AMBUSH: you are the interdictor; discover why mixing beats you.
COMPARE: up to four protagonists (SACRED, the Block A controls, oracle arms)
side by side on the same instance as synchronised small multiples.

The instance picker (city, screened OD presets, N, K, threat band, objective)
is shared; each mode receives the solved OracleInstance. Space plays/pauses.
The objective selector exposes B3's three-regime law live; the duel stays
mission-only (the gen19 game is defined on the mission objective).
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
from .pg_compare import ComparePanel
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
        self.compare = ComparePanel()
        self.stack.addWidget(self.watch)
        self.stack.addWidget(self.duel)
        self.stack.addWidget(self.ambush)
        self.stack.addWidget(self.compare)
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
        self.mode_combo.addItem("Compare protagonists side by side", 3)
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

        self.k_warning = QLabel("K=3 enumerates ~80k interdiction sets; expect a ~20-30 s solve. "
                                "K=3 with N of 4 or more would need gigabytes and is refused.")
        self.k_warning.setWordWrap(True)
        self.k_warning.setStyleSheet(f"color: {theme.INK_MUTED}; font-size: 12px;")
        self.k_warning.hide()
        lay.addWidget(self.k_warning)

        lay.addWidget(heading("Objective"))
        self.objective_combo = QComboBox()
        self.objective_combo.addItem(
            "Mission: P(at least 1 lost) — the headline objective", ("mission", 1))
        self.objective_combo.addItem(
            "Threshold: P(at least 2 lost)", ("threshold", 2))
        self.objective_combo.addItem(
            "Risk-neutral: expected fraction lost", ("linear", 1))
        self.objective_combo.currentIndexChanged.connect(self._objective_changed)
        lay.addWidget(self.objective_combo)
        self.objective_label = QLabel("")
        self.objective_label.setWordWrap(True)
        self.objective_label.setStyleSheet(f"color: {theme.INK_MUTED}; font-size: 12px;")
        lay.addWidget(self.objective_label)
        self._update_objective_label()

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
        self.band_label.setStyleSheet(f"color: {theme.INK_MUTED}; font-size: 12px;")
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
        self.status.setStyleSheet(f"color: {theme.INK_MUTED}; font-size: 13px;")
        lay.addWidget(self.status)
        return side

    # ------------------------------------------------------------- helpers

    def _panel(self):
        return self.stack.currentWidget()

    def _objective(self) -> tuple[str, int]:
        data = self.objective_combo.currentData()
        return data if data else ("mission", 1)

    def _update_objective_label(self) -> None:
        obj, _m = self._objective()
        texts = {
            "mission": "the unique objective the deterministic planner cannot escape "
                       "by spreading (b3_b4_oracle.md)",
            "threshold": "B3's law: degenerate in favour of determinism while the fleet "
                         "fits disjoint routes (both values can be exactly 0); at N=5 it "
                         "re-enters.",
            "linear": "B3's law: a modest 1.3-1.8x gap deterministic spreading partly "
                      "closes.",
        }
        self.objective_label.setText(texts.get(obj, ""))

    def _objective_changed(self) -> None:
        obj, _m = self._objective()
        self._update_objective_label()
        # the gen19 duel game is defined on the mission objective only
        duel_item = self.mode_combo.model().item(1)
        if duel_item is not None:
            duel_item.setEnabled(obj == "mission")
        if obj != "mission" and self.mode_combo.currentData() == 1:
            self.mode_combo.setCurrentIndex(0)
            self.status.setText(
                "Duel mode needs the mission objective (the gen19 game is defined on it); "
                "switched to Watch.")
        self._schedule_rebuild()

    def _space(self) -> None:
        p = self._panel()
        if hasattr(p, "toggle_play"):
            p.toggle_play()

    def _mode_changed(self) -> None:
        for p in (self.watch, self.duel, self.compare):
            p.stop_play()
        self.stack.setCurrentIndex(self.mode_combo.currentData())
        if self._inst is not None:
            self._panel().set_instance(self._inst, self._preset_for_panel(),
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
        for panel in (self.watch, self.duel, self.compare):
            panel.stop_play()
        s, t = p["od"].split("-")
        K, N = self.k_spin.value(), self.n_spin.value()
        if K >= 3 and N >= 4:
            self._building = False
            self.status.setText(
                "K=3 with N>=4 would materialise a multi-gigabyte objective matrix "
                "(the measured oracle wall); lower K or N. The regime beyond the wall "
                "is the A4 greedy-BR story, told in History.")
            return
        band = None if self.hard_check.isChecked() else (
            self.band_lo.value() / 100, self.band_hi.value() / 100)
        obj, m = self._objective()
        self.status.setText(f"Solving {city} {s}-{t}  K={K} N={N} ({obj}) …")
        t0 = time.perf_counter()
        run_in_background(
            oracle_bridge.build_instance, city, s, t, K, N, int(p.get("k_extra", 8)), band,
            obj, m,
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
        note = ""
        if inst.objective != "mission":
            note = " · anchors hidden: banked at the mission objective"
        self.status.setText(
            f"{inst.n_routes} routes · {len(inst.interdiction_sets)} interdiction sets · "
            f"solved in {dt * 1000:.0f} ms{note}")
        self._panel().set_instance(inst, self._preset_for_panel(), self.seed_spin.value())

    def _preset_for_panel(self) -> dict | None:
        """Banked anchors are mission-objective ledger rows; off-mission they
        must not show at all (honesty over decoration)."""
        obj, _m = self._objective()
        return self.od_combo.currentData() if obj == "mission" else None

    # ------------------------------------------------------------- public API

    def load_custom_od(self, city: str, od: str) -> None:
        """Open a specific (city, od) instance, e.g. from the A8 prevalence
        screen. Falls back to inserting a clearly-labelled temporary preset
        when the OD is not a banked one; safe mid-build (debounced)."""
        if self.objective_combo.currentIndex() != 0:
            self.objective_combo.setCurrentIndex(0)  # anchors/presets are mission rows
        for i in range(self.city_combo.count()):
            if self.city_combo.itemData(i) == city:
                if self.city_combo.currentIndex() != i:
                    self.city_combo.setCurrentIndex(i)  # repopulates the OD combo
                break
        # drop any previous temporary entry
        for i in range(self.od_combo.count() - 1, -1, -1):
            data = self.od_combo.itemData(i)
            if isinstance(data, dict) and data.get("temp"):
                self.od_combo.removeItem(i)
        for i in range(self.od_combo.count()):
            data = self.od_combo.itemData(i)
            if isinstance(data, dict) and data.get("od") == od:
                self.od_combo.setCurrentIndex(i)
                self._schedule_rebuild()
                return
        self.od_combo.insertItem(
            0, f"{od} · from the prevalence screen (A8-sampled, not a banked preset)",
            {"od": od, "k_extra": 8, "N": 3, "K": 1, "temp": True})
        self.od_combo.setCurrentIndex(0)
        self._schedule_rebuild()

    def open_compare(self, contender_keys: list[str] | None = None) -> None:
        """Switch to the compare mode, optionally pre-ticking contenders."""
        if contender_keys:
            self.compare.set_contenders(contender_keys)
        idx = next((i for i in range(self.mode_combo.count())
                    if self.mode_combo.itemData(i) == 3), None)
        if idx is not None:
            self.mode_combo.setCurrentIndex(idx)

    # ------------------------------------------------------------- export

    def export_view(self):
        p = self._panel()
        if isinstance(p, Exportable):
            return p.export_view()
        return []
