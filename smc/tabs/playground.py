"""The Playground: pick a scenario, then explore it one game at a time.

A landing chooser offers four games (watch / you defend / you attack /
compare). Every game shares one scenario bar: a human-named scenario picker
and a "Change the rules" drawer holding everything advanced (convoys, ambush
teams, road danger, the objective rule, the dice seed). Space plays/pauses.

Under the hood nothing changed: the LP re-solves live per scenario, banked
anchors stay mission-only, the duel game stays on the headline rule, and the
two public APIs (load_custom_od, open_compare) are unchanged.
"""

from __future__ import annotations

import time

import yaml
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSlider,
    QSpinBox,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from .. import lexicon, theme
from ..sacred_bridge import maps as maps_bridge
from ..sacred_bridge import oracle as oracle_bridge
from ..sacred_bridge.paths import DATA_DIR
from ..widgets.coach import CoachOverlay
from ..widgets.export import Exportable
from ..workers import run_in_background
from .pg_ambush import AmbushPanel
from .pg_compare import ComparePanel
from .pg_duel import DuelPanel
from .pg_watch import WatchPanel

_MODES = {"watch": 1, "defend": 2, "attack": 3, "compare": 4}

_COACH_STEPS = {
    "watch": [
        "Pick a scenario at the top. Each one is a real city crossing with a "
        "hidden ambusher waiting.",
        "Choose a defender and an enemy, then press the blue Play button. "
        "Convoys that make it flash green; ambushed ones flash red.",
        "Read the score on the right: the big number is the chance the mission "
        "fails, and the dot shows how close this defender gets to perfect play.",
    ],
    "defend": [
        "You fly the convoy. Click any road on the map to run it.",
        "The enemy studies your last few runs and waits where you have been — "
        "the orange glow shows where it expects you right now.",
        "Keep your score low by never settling into a pattern. The dotted "
        "lines show what fixed habits, blind mixing and perfect play achieve.",
    ],
    "attack": [
        "You are the ambusher. The defender's driving habits are drawn on the "
        "map: thicker roads are used more often.",
        "Click a coloured road to place your ambush there.",
        "Try to beat the best possible ambush. Against the proven-optimal mix "
        "you will find every spot pays the same — that is the whole point.",
    ],
    "compare": [
        "Up to four strategies drive the same scenario side by side, each "
        "against an enemy that knows its habits.",
        "Press Race, or Run 300 instantly, and watch the failure rates settle "
        "onto their predicted values in the shared chart below.",
        "Use the Contenders button to swap in different strategies, including "
        "the control AIs.",
    ],
}


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

        root = QVBoxLayout(self)
        root.setContentsMargins(16, 10, 16, 14)
        root.setSpacing(8)

        self.scenario_bar = self._build_scenario_bar()
        root.addWidget(self.scenario_bar)

        self.stack = QStackedWidget()
        self.landing = self._build_landing()
        self.watch = WatchPanel()
        self.duel = DuelPanel()
        self.ambush = AmbushPanel()
        self.compare = ComparePanel()
        for w in (self.landing, self.watch, self.duel, self.ambush, self.compare):
            self.stack.addWidget(w)
        root.addWidget(self.stack, 1)

        QShortcut(QKeySequence(Qt.Key_Space), self, activated=self._space,
                  context=Qt.WidgetWithChildrenShortcut)

        self._populate_scenarios()
        self.scenario_bar.hide()  # landing first
        QTimer.singleShot(50, self._rebuild_instance)

    # ------------------------------------------------------------- landing

    def _build_landing(self) -> QWidget:
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(24, 18, 24, 18)
        lay.setSpacing(14)

        title = QLabel("What do you want to see?")
        title.setProperty("h1", True)
        lay.addWidget(title)
        sub = QLabel("Four ways into the same game: a city, some convoys, and an "
                     "enemy that learns your habits.")
        sub.setStyleSheet(f"color: {theme.INK_SECONDARY}; font-size: 15px;")
        sub.setWordWrap(True)
        lay.addWidget(sub)

        grid = QGridLayout()
        grid.setSpacing(14)
        cards = [
            ("Watch the game", "See defenders and enemies play each other, and "
             "watch the score settle onto the predicted value.", "watch"),
            ("You defend", "Click the convoy's road each run and try to dodge an "
             "enemy that studies your pattern.", "defend"),
            ("You attack", "Place the ambush yourself and learn why the "
             "proven-optimal mix cannot be beaten.", "attack"),
            ("Compare policies", "Four strategies on the same map, side by side, "
             "with one shared scoreboard.", "compare"),
        ]
        self._landing_cards: dict[str, QPushButton] = {}
        for i, (name, desc, key) in enumerate(cards):
            btn = QPushButton(f"{name}\n{desc}")
            btn.setMinimumHeight(104)
            btn.setStyleSheet(
                f"QPushButton {{ text-align: left; padding: 16px 18px; font-size: 16px;"
                f"font-weight: 600; background: {theme.SURFACE}; border-radius: 12px; }}"
                f"QPushButton:hover {{ border-color: {theme.BLUE}; }}")
            btn.clicked.connect(lambda _=False, k=key: self.open_mode(k))
            grid.addWidget(btn, i // 2, i % 2)
            self._landing_cards[key] = btn
        lay.addLayout(grid)
        lay.addStretch(1)
        return page

    # ------------------------------------------------------------- scenario bar

    def _build_scenario_bar(self) -> QWidget:
        bar = QWidget()
        outer = QVBoxLayout(bar)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(4)

        row1 = QWidget()
        r1 = QHBoxLayout(row1)
        r1.setContentsMargins(0, 0, 0, 0)
        r1.setSpacing(10)
        self.back_btn = QPushButton("← All games")
        self.back_btn.setProperty("quiet", True)
        self.back_btn.clicked.connect(lambda: self.open_mode(None))
        r1.addWidget(self.back_btn)
        r1.addWidget(QLabel("Scenario:"))
        self.scenario_combo = QComboBox()
        self.scenario_combo.setMinimumWidth(340)
        self.scenario_combo.currentIndexChanged.connect(self._scenario_changed)
        r1.addWidget(self.scenario_combo)
        self.rules_btn = QPushButton("Change the rules ▸")
        self.rules_btn.setProperty("quiet", True)
        self.rules_btn.setCheckable(True)
        self.rules_btn.toggled.connect(self._toggle_rules)
        r1.addWidget(self.rules_btn)
        self.coach_btn = QPushButton("?")
        self.coach_btn.setProperty("quiet", True)
        self.coach_btn.setFixedWidth(30)
        self.coach_btn.setToolTip("Show the three-step guide for this game again")
        self.coach_btn.clicked.connect(self._replay_coach)
        r1.addWidget(self.coach_btn)
        r1.addStretch(1)
        self.status = QLabel("")
        self.status.setProperty("fineprint", True)
        self.status.setWordWrap(True)
        r1.addWidget(self.status)
        outer.addWidget(row1)

        self.story_label = QLabel("")
        self.story_label.setProperty("fineprint", True)
        self.story_label.setWordWrap(True)
        outer.addWidget(self.story_label)

        self.rules_drawer = self._build_rules_drawer()
        self.rules_drawer.hide()
        outer.addWidget(self.rules_drawer)
        return bar

    def _build_rules_drawer(self) -> QWidget:
        drawer = QWidget()
        lay = QVBoxLayout(drawer)
        lay.setContentsMargins(8, 4, 8, 6)
        lay.setSpacing(6)

        row = QWidget()
        rl = QHBoxLayout(row)
        rl.setContentsMargins(0, 0, 0, 0)
        rl.setSpacing(12)

        rl.addWidget(QLabel("Convoys"))
        self.n_spin = QSpinBox()
        self.n_spin.setRange(1, 5)
        self.n_spin.setValue(3)
        self.n_spin.valueChanged.connect(self._schedule_rebuild)
        rl.addWidget(self.n_spin)

        rl.addWidget(QLabel("Ambush teams"))
        self.k_spin = QSpinBox()
        self.k_spin.setRange(1, 3)
        self.k_spin.setValue(1)
        self.k_spin.valueChanged.connect(self._schedule_rebuild)
        rl.addWidget(self.k_spin)

        rl.addWidget(QLabel("Road danger"))
        self.danger_slider = QSlider(Qt.Horizontal)
        self.danger_slider.setRange(50, 99)
        self.danger_slider.setValue(95)
        self.danger_slider.setFixedWidth(140)
        self.danger_slider.setToolTip(
            "How dangerous the most exposed roads are. The safest roads stay "
            "at 15% per ambush; this sets the top of the range.")
        self.danger_slider.valueChanged.connect(self._danger_changed)
        rl.addWidget(self.danger_slider)
        self.danger_label = QLabel("up to 95%")
        self.danger_label.setProperty("fineprint", True)
        rl.addWidget(self.danger_label)

        self.hard_check = QCheckBox("Every ambush is lethal")
        self.hard_check.setToolTip(
            "All-or-nothing: driving through an ambush always destroys the "
            "convoy (the single-convoy record was measured this way)")
        self.hard_check.toggled.connect(self._hard_toggled)
        rl.addWidget(self.hard_check)
        rl.addStretch(1)
        lay.addWidget(row)

        row2 = QWidget()
        r2 = QHBoxLayout(row2)
        r2.setContentsMargins(0, 0, 0, 0)
        r2.setSpacing(12)
        r2.addWidget(QLabel("What counts as failure?"))
        self.objective_combo = QComboBox()
        for key in ("mission", "threshold", "linear"):
            name, blurb = lexicon.OBJECTIVES[key]
            m = 2 if key == "threshold" else 1
            self.objective_combo.addItem(name, (key, m))
            self.objective_combo.setItemData(
                self.objective_combo.count() - 1, blurb, Qt.ToolTipRole)
        self.objective_combo.currentIndexChanged.connect(self._objective_changed)
        r2.addWidget(self.objective_combo)
        self.objective_label = QLabel("")
        self.objective_label.setProperty("fineprint", True)
        self.objective_label.setWordWrap(True)
        r2.addWidget(self.objective_label, 1)

        r2.addWidget(QLabel("Dice seed"))
        self.seed_spin = QSpinBox()
        self.seed_spin.setRange(0, 9999)
        self.seed_spin.setValue(0)
        self.seed_spin.setToolTip(
            "Every random draw is reproducible; the same seed replays the same runs")
        self.seed_spin.valueChanged.connect(self._seed_changed)
        r2.addWidget(self.seed_spin)
        self.reset_btn = QPushButton("Reset the score")
        self.reset_btn.clicked.connect(lambda: self._panel().reset_stats()
                                       if hasattr(self._panel(), "reset_stats") else None)
        r2.addWidget(self.reset_btn)
        lay.addWidget(row2)

        self.k_warning = QLabel(
            "Three ambush teams take twenty to thirty seconds to solve. Three "
            "teams against four or more convoys is beyond this machine and is "
            "refused.")
        self.k_warning.setWordWrap(True)
        self.k_warning.setProperty("fineprint", True)
        self.k_warning.hide()
        lay.addWidget(self.k_warning)
        return drawer

    def _toggle_rules(self, on: bool) -> None:
        self.rules_btn.setText("Change the rules ▾" if on else "Change the rules ▸")
        self.rules_drawer.setVisible(on)

    # ------------------------------------------------------------- helpers

    def _panel(self):
        return self.stack.currentWidget()

    def _mode_key(self) -> str | None:
        idx = self.stack.currentIndex()
        for k, v in _MODES.items():
            if v == idx:
                return k
        return None

    def _objective(self) -> tuple[str, int]:
        data = self.objective_combo.currentData()
        return data if data else ("mission", 1)

    def _update_objective_label(self) -> None:
        obj, _m = self._objective()
        _name, blurb = lexicon.OBJECTIVES.get(obj, ("", ""))
        self.objective_label.setText(blurb)

    def _objective_changed(self) -> None:
        obj, _m = self._objective()
        self._update_objective_label()
        # the you-defend game (gen19) is defined on the headline rule
        defend_card = self._landing_cards.get("defend")
        if defend_card is not None:
            defend_card.setEnabled(obj == "mission")
            defend_card.setToolTip(
                "" if obj == "mission" else
                "The you-defend game is defined on the headline rule (any loss "
                "means failure). Change the rule back to play it.")
        if obj != "mission" and self._mode_key() == "defend":
            self.open_mode("watch")
            self.status.setText(
                "You-defend uses the headline rule (any loss means failure); "
                "switched to Watch.")
        self._schedule_rebuild()

    def _space(self) -> None:
        p = self._panel()
        if hasattr(p, "toggle_play"):
            p.toggle_play()

    # ------------------------------------------------------------- modes

    def open_mode(self, key: str | None) -> None:
        """Switch to a game (or back to the landing chooser with None)."""
        for p in (self.watch, self.duel, self.compare):
            p.stop_play()
        # a coach from the mode we are leaving must not linger over the new one
        if getattr(self, "_coach", None) is not None:
            self._coach.dismiss()
            self._coach = None
        if key is None:
            self.stack.setCurrentIndex(0)
            self.scenario_bar.hide()
            self.export_name = "playground"
            return
        if key == "defend" and self._objective()[0] != "mission":
            self.objective_combo.setCurrentIndex(0)
            self.status.setText(
                "You-defend uses the headline rule; the rule was switched back.")
        self.stack.setCurrentIndex(_MODES[key])
        self.scenario_bar.show()
        self.export_name = f"playground-{key}"
        if self._inst is not None:
            self._panel().set_instance(self._inst, self._preset_for_panel(),
                                       self.seed_spin.value())
        self._coach = CoachOverlay.maybe_show(self, f"playground-{key}", _COACH_STEPS[key])

    def _replay_coach(self) -> None:
        key = self._mode_key()
        if key:
            if getattr(self, "_coach", None) is not None:
                self._coach.dismiss()
            self._coach = CoachOverlay.maybe_show(
                self, f"playground-{key}", _COACH_STEPS[key], force=True)

    def _seed_changed(self) -> None:
        p = self._panel()
        if hasattr(p, "set_seed"):
            p.set_seed(self.seed_spin.value())

    # ------------------------------------------------------------- scenarios

    def _populate_scenarios(self) -> None:
        """One combo, human names first, grouped by city order."""
        self.scenario_combo.blockSignals(True)
        self.scenario_combo.clear()
        for city in maps_bridge.available_cities():
            city_label = maps_bridge.CITY_LABELS.get(city, city).split(" (")[0]
            for p in self._presets.get(city, []):
                human = p.get("human") or p.get("label", p.get("od", "?"))
                self.scenario_combo.addItem(f"{human} — {city_label}",
                                            {"city": city, "preset": p})
                self.scenario_combo.setItemData(
                    self.scenario_combo.count() - 1,
                    p.get("story", ""), Qt.ToolTipRole)
        self.scenario_combo.blockSignals(False)
        self._scenario_changed()

    def _current_scenario(self) -> tuple[str | None, dict | None]:
        data = self.scenario_combo.currentData()
        if not data:
            return None, None
        return data["city"], data["preset"]

    def _scenario_changed(self) -> None:
        _city, p = self._current_scenario()
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
            self._update_story(p)
        self._schedule_rebuild()

    def _update_story(self, p: dict) -> None:
        story = p.get("story", "")
        band = "every ambush lethal" if self.hard_check.isChecked() else \
            f"road danger 15-{self.danger_slider.value()}%"
        code = (f"{p.get('od', '?')} · convoys {self.n_spin.value()} · "
                f"ambush teams {self.k_spin.value()} · {band}")
        self.story_label.setText(f"{story}   ·   {code}")

    def _hard_toggled(self, on: bool, rebuild: bool = True) -> None:
        self.danger_slider.setEnabled(not on)
        if rebuild:
            self._schedule_rebuild()

    def _danger_changed(self) -> None:
        self.danger_label.setText(f"up to {self.danger_slider.value()}%")
        self._schedule_rebuild()

    # ------------------------------------------------------------- rebuild

    def _schedule_rebuild(self) -> None:
        self.k_warning.setVisible(self.k_spin.value() >= 3)
        _city, p = self._current_scenario()
        if p:
            self._update_story(p)
        if not hasattr(self, "_debounce"):
            self._debounce = QTimer(self)
            self._debounce.setSingleShot(True)
            self._debounce.timeout.connect(self._rebuild_instance)
        self._debounce.start(350)

    def _rebuild_instance(self) -> None:
        city, p = self._current_scenario()
        if not city or not p:
            self.status.setText("Pick a scenario.")
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
                "Three ambush teams against four or more convoys is beyond this "
                "machine (the measured wall); lower one of them.")
            return
        band = None if self.hard_check.isChecked() else (
            0.15, self.danger_slider.value() / 100)
        obj, m = self._objective()
        self.status.setText("Solving this scenario…")
        t0 = time.perf_counter()
        run_in_background(
            oracle_bridge.build_instance, city, s, t, K, N, int(p.get("k_extra", 8)),
            band, obj, m,
            on_done=lambda inst: self._instance_ready(inst, time.perf_counter() - t0),
            on_fail=self._instance_failed,
        )

    def _instance_failed(self, tb: str) -> None:
        self._building = False
        self.status.setText("This scenario failed to solve. Last line:\n"
                            + tb.strip().splitlines()[-1])

    def _instance_ready(self, inst: oracle_bridge.OracleInstance, dt: float) -> None:
        self._building = False
        if self._rebuild_pending:
            self._rebuild_pending = False
            self._rebuild_instance()
            return
        self._inst = inst
        note = ""
        if inst.objective != "mission":
            note = " · record numbers hidden: they were banked under the headline rule"
        self.status.setText(f"solved in {dt * 1000:.0f} ms{note}")
        if self.stack.currentIndex() != 0:
            self._panel().set_instance(inst, self._preset_for_panel(),
                                       self.seed_spin.value())

    def _preset_for_panel(self) -> dict | None:
        """Banked anchors are mission-rule ledger rows; off-mission they must
        not show at all (honesty over decoration)."""
        obj, _m = self._objective()
        _city, p = self._current_scenario()
        return p if obj == "mission" else None

    # ------------------------------------------------------------- public API

    def load_custom_od(self, city: str, od: str) -> None:
        """Open a specific (city, od) scenario, e.g. from the prevalence map.
        Inserts a clearly-labelled temporary scenario when the crossing is not
        a banked one; safe mid-build (debounced)."""
        if self.objective_combo.currentIndex() != 0:
            self.objective_combo.setCurrentIndex(0)  # records are headline-rule rows
        # drop any previous temporary entry
        for i in range(self.scenario_combo.count() - 1, -1, -1):
            data = self.scenario_combo.itemData(i)
            if isinstance(data, dict) and data.get("preset", {}).get("temp"):
                self.scenario_combo.removeItem(i)
        # existing scenario?
        for i in range(self.scenario_combo.count()):
            data = self.scenario_combo.itemData(i)
            if (isinstance(data, dict) and data.get("city") == city
                    and data.get("preset", {}).get("od") == od):
                self.scenario_combo.setCurrentIndex(i)
                if self.stack.currentIndex() == 0:
                    self.open_mode("watch")
                return
        city_label = maps_bridge.CITY_LABELS.get(city, city).split(" (")[0]
        preset = {"od": od, "k_extra": 8, "N": 3, "K": 1, "temp": True,
                  "human": f"Crossing {od}",
                  "story": "Picked from the prevalence map; a screened crossing, "
                           "not one of the named scenarios."}
        self.scenario_combo.insertItem(0, f"Crossing {od} — {city_label}",
                                       {"city": city, "preset": preset})
        self.scenario_combo.setCurrentIndex(0)
        if self.stack.currentIndex() == 0:
            self.open_mode("watch")

    def open_compare(self, contender_keys: list[str] | None = None) -> None:
        """Switch to the compare game, optionally pre-ticking contenders."""
        if contender_keys:
            self.compare.set_contenders(contender_keys)
        self.open_mode("compare")

    # ------------------------------------------------------------- export

    def export_view(self):
        p = self._panel()
        if isinstance(p, Exportable):
            return p.export_view()
        from ..widgets.export import export_widget_grab
        return export_widget_grab(self, self.export_name)
