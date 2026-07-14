"""Playground · You defend: fly the convoy against an enemy that studies your
recent runs (the gen19 game). Click a road, or let a trained SACRED play, and
try to stay below what blind mixing achieves."""

from __future__ import annotations

import matplotlib.ticker as mtick
import numpy as np
from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from .. import lexicon, theme
from ..game import duel as duel_mod
from ..game.duel import DuelState, StackedGame
from ..sacred_bridge import oracle as oracle_bridge
from ..sacred_bridge import policies
from ..widgets.cards import Card
from ..widgets.charts import ChartWidget
from ..widgets.export import Exportable, export_widget_grab
from ..widgets.human import HeroNumber, MapLegend, OutcomeStrip, RecordDisclosure
from ..widgets.mapview import MapView
from ..workers import run_in_background

# plain names for the duel's three reference lines (chart annotations)
_ANCHOR_NAMES = {
    "static_det": "a fixed habit",
    "iid_eq": "the blind proven mix",
    "history_opt": "the perfect adaptive play",
}


class DuelPanel(QWidget, Exportable):
    export_name = "playground-duel"

    def __init__(self, parent=None):
        super().__init__(parent)
        self._inst: oracle_bridge.OracleInstance | None = None
        self._game: StackedGame | None = None
        self._duel: DuelState | None = None
        self._policy: policies.LoadedPolicy | None = None
        self._policy_key = ""
        self._actor_refs = [r for r in policies.discover_actors()
                            if r.kind == "history_aware"]
        self._playing = False
        self._pending_route: int | None = None
        self._anim = None
        self._loading = False
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
        bl.addWidget(QLabel("Enemy"))
        self.att_combo = QComboBox()
        self.att_combo.addItem(lexicon.attacker_name("pattern_of_life"), "pattern_of_life")
        self.att_combo.addItem(lexicon.attacker_name("empirical_br"), "empirical_br")
        for i, key in enumerate(("pattern_of_life", "empirical_br")):
            self.att_combo.setItemData(i, lexicon.ATTACKERS[key][1], Qt.ToolTipRole)
        self.att_combo.currentIndexChanged.connect(self._reset_duel)
        bl.addWidget(self.att_combo)

        self.enemy_btn = QPushButton("Enemy settings ▸")
        self.enemy_btn.setProperty("quiet", True)
        self.enemy_btn.setCheckable(True)
        self.enemy_btn.toggled.connect(self._toggle_enemy_settings)
        bl.addWidget(self.enemy_btn)

        self.attention_check = QCheckBox("Show where the enemy is looking")
        self.attention_check.setChecked(True)
        self.attention_check.setToolTip(
            "The orange glow marks the roads the enemy currently expects you "
            "on, updated after every run (computed live)")
        self.attention_check.toggled.connect(self._update_attention)
        bl.addWidget(self.attention_check)
        bl.addStretch(1)
        self.play_btn = QPushButton("▶ Play (space)")
        self.play_btn.setProperty("accent", True)
        self.play_btn.clicked.connect(self.toggle_play)
        bl.addWidget(self.play_btn)
        self.batch_btn = QPushButton("Run 300 instantly")
        self.batch_btn.setProperty("quiet", True)
        self.batch_btn.clicked.connect(self._run_batch)
        bl.addWidget(self.batch_btn)
        self.reset_btn = QPushButton("Start over")
        self.reset_btn.setProperty("quiet", True)
        self.reset_btn.clicked.connect(self._reset_duel)
        bl.addWidget(self.reset_btn)
        lay.addWidget(bar)

        self.enemy_row = QWidget()
        er = QHBoxLayout(self.enemy_row)
        er.setContentsMargins(8, 0, 0, 0)
        er.setSpacing(8)
        er.addWidget(QLabel("Enemy memory (runs)"))
        self.w_spin = QSpinBox()
        self.w_spin.setRange(1, 3)
        self.w_spin.setValue(3)
        self.w_spin.setToolTip("How many of your recent runs the enemy studies")
        self.w_spin.valueChanged.connect(self._rebuild_game)
        er.addWidget(self.w_spin)
        er.addWidget(QLabel("Enemy sharpness"))
        self.tau_combo = QComboBox()
        self.tau_combo.addItem("Standard", "0.15")
        self.tau_combo.addItem("Razor-sharp", "0.05")
        self.tau_combo.setToolTip(
            "How decisively the enemy commits to its best guess (the record "
            "was measured at Standard)")
        self.tau_combo.currentIndexChanged.connect(self._rebuild_game)
        er.addWidget(self.tau_combo)
        er.addStretch(1)
        self.enemy_row.hide()
        lay.addWidget(self.enemy_row)

        split = QSplitter(Qt.Horizontal)
        map_col = QWidget()
        ml = QVBoxLayout(map_col)
        ml.setContentsMargins(0, 0, 0, 0)
        ml.setSpacing(2)
        self.map = MapView()
        self.map.route_clicked.connect(self._human_route)
        ml.addWidget(self.map, 1)
        ml.addWidget(MapLegend(show_glow=True))
        split.addWidget(map_col)
        split.addWidget(self._build_readouts())
        split.setSizes([760, 350])
        lay.addWidget(split, 1)

        self._timer = QTimer(self)
        self._timer.setInterval(33)
        self._timer.timeout.connect(self._tick)

    def _toggle_enemy_settings(self, on: bool) -> None:
        self.enemy_btn.setText("Enemy settings ▾" if on else "Enemy settings ▸")
        self.enemy_row.setVisible(on)

    def _tau(self) -> float:
        return float(self.tau_combo.currentData() or "0.15")

    # ------------------------------------------------------------- readouts

    def _build_readouts(self) -> QWidget:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        host = QWidget()
        lay = QVBoxLayout(host)
        lay.setContentsMargins(0, 0, 4, 4)
        lay.setSpacing(10)

        self.hero_card = Card()
        self.hero = HeroNumber("of missions lost so far, on average")
        self.hero_card.layout_().addWidget(self.hero)
        self.lbl_anchors = QLabel("Solving this game…")
        self.lbl_anchors.setWordWrap(True)
        self.lbl_anchors.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.hero_card.layout_().addWidget(self.lbl_anchors)
        cap = QLabel("computed live · the exact optimal plays for this scenario")
        cap.setStyleSheet(
            f"color: {theme.LIVE_ACCENT}; font-size: 12px; font-weight: 600;")
        self.hero_card.layout_().addWidget(cap)
        lay.addWidget(self.hero_card)

        self.score_card = Card()
        sh = QLabel("The score so far")
        sh.setProperty("h3", True)
        self.score_card.layout_().addWidget(sh)
        self.strip = OutcomeStrip()
        self.score_card.layout_().addWidget(self.strip)
        self.run_label = QLabel("No runs yet.")
        self.run_label.setWordWrap(True)
        self.run_label.setProperty("fineprint", True)
        self.score_card.layout_().addWidget(self.run_label)
        self.run_chart = ChartWidget(title="duel-convergence", height=2.5, width=3.4)
        self.score_card.layout_().addWidget(self.run_chart)
        lay.addWidget(self.score_card)

        self.record_disc = RecordDisclosure()
        self.record_disc.add_line(
            "measured on The proving ground (three convoys, one ambush team, "
            "enemy memory 3, standard sharpness) · era: post-fix")
        self.record_disc.add_quote(
            "static_det 0.613 > iid_eq/no-window 0.148 > **SACRED 0.050** ~ "
            "history_opt 0.049", "experiments/gen19_b1lite1.md")
        lay.addWidget(self.record_disc)

        self.help_card = Card()
        hh = QLabel("How to play")
        hh.setProperty("h3", True)
        self.help_card.layout_().addWidget(hh)
        ht = QLabel(
            "Click any road to fly the convoy down it; the enemy has already "
            "placed its ambush based on your recent runs. Fly where the orange "
            "glow is not, and never settle into a pattern.")
        ht.setWordWrap(True)
        self.help_card.layout_().addWidget(ht)
        lay.addWidget(self.help_card)

        lay.addStretch(1)
        scroll.setWidget(host)
        return scroll

    # ------------------------------------------------------------- instance

    def set_instance(self, inst: oracle_bridge.OracleInstance, preset: dict | None,
                     seed: int) -> None:
        self.stop_play()
        self._inst = inst
        self.seed = seed
        self._policy = None
        self._policy_key = ""
        self.map.set_city(inst.city_map)
        self.map.show_instance(inst.routes, inst.edge_vuln, inst.s, inst.t)
        self.map.set_route_click_mode(True)
        self._update_record_visibility()
        self._populate_defenders()
        self._rebuild_game()

    def _update_record_visibility(self) -> None:
        if self._inst is None:
            self.record_disc.hide()
            return
        inst = self._inst
        is_gen19_cell = (inst.city, inst.s, inst.t, inst.N, inst.K) \
            == ("kaliningrad", "35", "159", 3, 1) and inst.band == (0.15, 0.95)
        self.record_disc.setVisible(
            is_gen19_cell and self.w_spin.value() == 3
            and abs(self._tau() - 0.15) < 1e-9)

    def _populate_defenders(self) -> None:
        self.def_combo.blockSignals(True)
        self.def_combo.clear()
        self.def_combo.addItem("You — click a road each run", "human")
        for r in self._actor_refs:
            seed = r.key.rsplit("seed", 1)[-1]
            run = f" · run {int(seed) + 1}" if seed.isdigit() else ""
            self.def_combo.addItem(
                lexicon.strategy_name("history_aware") + run, f"policy:{r.key}")
            self.def_combo.setItemData(
                self.def_combo.count() - 1,
                lexicon.strategy_blurb("history_aware"), Qt.ToolTipRole)
        self.def_combo.addItem(lexicon.strategy_name("iid_eq"), "iid_eq")
        self.def_combo.addItem(lexicon.strategy_name("static_det"), "static_det")
        self.def_combo.blockSignals(False)

    def _rebuild_game(self) -> None:
        if self._inst is None:
            return
        self.stop_play()
        w = self.w_spin.value()
        tau = self._tau()
        self.lbl_anchors.setText("Solving this game…")
        inst = self._inst
        run_in_background(
            duel_mod.build_stacked_game, inst, w, tau,
            on_done=self._game_ready,
            on_fail=lambda tb: self.lbl_anchors.setText(
                "Solve failed: " + tb.strip().splitlines()[-1]),
        )

    def _game_ready(self, game: StackedGame) -> None:
        if self._inst is None or game.inst is not self._inst:
            return
        self._game = game
        r = game.refs
        self.lbl_anchors.setText(
            f"A fixed habit loses <b>{lexicon.pct(r['static_det'])}</b> of missions. "
            f"Blind mixing (ignore the enemy, play the proven mix): "
            f"<b>{lexicon.pct(r['iid_eq'])}</b>. The perfect adaptive play gets down "
            f"to <b>{lexicon.pct(r['history_opt'])}</b> — dodge where the enemy "
            f"expects you.")
        self._update_record_visibility()
        self._reset_duel()
        self._defender_changed()

    def _defender_changed(self) -> None:
        key = self.def_combo.currentData()
        if key is None or self._inst is None:
            return
        if key and key.startswith("policy:") and key.split(":", 1)[1] != self._policy_key:
            ref = next((r for r in self._actor_refs if r.key == key.split(":", 1)[1]), None)
            if ref is not None:
                self._policy = None
                self._policy_key = ""
                self._set_loading(True, ref.key)
                inst = self._inst
                run_in_background(
                    policies.load_policy, ref, inst,
                    on_done=lambda pol, started_on=inst: self._policy_ready(pol, started_on),
                    on_fail=lambda tb: (self._set_loading(False),
                                        self.run_label.setText(
                                            "The AI failed to load: "
                                            + tb.strip().splitlines()[-1])),
                )
        self._reset_duel()

    def _set_loading(self, on: bool, key: str = "") -> None:
        """While the AI loads, the play controls are disabled, not silently dead."""
        self._loading = on
        for btn in (self.play_btn, self.batch_btn):
            btn.setEnabled(not on)
        self.def_combo.setEnabled(not on)
        if on:
            self.run_label.setText("Loading the trained AI (a few seconds)…")

    def _policy_ready(self, pol: policies.LoadedPolicy, started_on=None) -> None:
        self._set_loading(False)
        if started_on is not None and started_on is not self._inst:
            return  # scenario changed while loading; the list will reload on demand
        want = str(self.def_combo.currentData() or "")
        if want != f"policy:{pol.ref.key}":
            return  # a different defender was picked meanwhile
        self._policy = pol
        self._policy_key = pol.ref.key
        self.run_label.setText(
            f"Trained AI ready · <span style='color:{theme.INK_MUTED}'>"
            f"checkpoints: {pol.ref.provenance}</span>")
        self._show_mixture()

    def _reset_duel(self) -> None:
        if self._game is None:
            return
        self.stop_play()
        self._duel = DuelState(self._game, seed=self.seed)
        self.map.clear_convoys()
        self.map.clear_ambush()
        self.strip.reset()
        self._show_mixture()
        self._update_running()
        self._update_attention()

    def _update_attention(self, *_args) -> None:
        """Show where the enemy is looking for the NEXT run, given your recent
        pattern: the whole game made visible."""
        if self._game is None or self._duel is None or self._inst is None:
            return
        if not self.attention_check.isChecked():
            self.map.clear_attention()
            return
        g, duel = self._game, self._duel
        attacker = self.att_combo.currentData()
        if attacker == "pattern_of_life":
            a = duel_mod.softmax_br_dist(g, duel.window_counts())
        elif attacker == "empirical_br":
            dist = duel.empirical_route_dist()
            j = int(np.argmax(dist @ g.L))
            a = np.zeros(g.L.shape[1])
            a[j] = 1.0
        else:
            self.map.clear_attention()
            return
        weights: dict[tuple[str, str], float] = {}
        for j, p in enumerate(a):
            if p <= 1e-9:
                continue
            for e in self._inst.interdiction_sets[j]:
                uv = tuple(e)
                key = (uv[0], uv[-1])
                weights[key] = weights.get(key, 0.0) + float(p)
        self.map.show_attention(weights)

    def set_seed(self, seed: int) -> None:
        self.seed = seed
        self._reset_duel()

    def reset_stats(self) -> None:
        self._reset_duel()

    def _show_mixture(self) -> None:
        if self._game is None or self._duel is None:
            return
        key = self.def_combo.currentData()
        if key == "iid_eq":
            self.map.set_route_mixture(list(self._game.eq_mixture()))
        elif key == "static_det":
            d = np.zeros(self._game.R)
            d[self._static_det_route()] = 1.0
            self.map.set_route_mixture(list(d), theme.STRATEGY_COLOURS["static_det"])
        elif key and key.startswith("policy:") and self._policy is not None:
            d = self._policy.route_distribution(self._duel.window_freq())
            self.map.set_route_mixture(list(d))
        else:
            self.map.set_route_mixture([0.0] * self._game.R,
                                       theme.STRATEGY_COLOURS["human"])

    # ------------------------------------------------------------- play

    def _static_det_route(self) -> int:
        """The best FIXED route against this adversary: playing r forever fills
        the window with r, so the stationary loss is L[r] @ softmax_br(w*e_r).
        This matches sacred's static_det anchor exactly."""
        g = self._game
        best_r, best_v = 0, float("inf")
        for r in range(g.R):
            counts = np.zeros(g.R)
            counts[r] = g.w
            a = duel_mod.softmax_br_dist(g, counts)
            v = float(g.L[r] @ a)
            if v < best_v:
                best_r, best_v = r, v
        return best_r

    def _choose_route(self) -> int | None:
        """The automatic defender's route for the next run."""
        if self._game is None or self._duel is None:
            return None
        key = self.def_combo.currentData()
        rng = self._duel.rng
        if key == "iid_eq":
            eq = self._game.eq_mixture()
            return int(rng.choice(len(eq), p=eq / eq.sum()))
        if key == "static_det":
            return self._static_det_route()
        if key and key.startswith("policy:"):
            if self._policy is None:
                return None
            d = self._policy.route_distribution(self._duel.window_freq())
            return int(rng.choice(len(d), p=d / d.sum()))
        return None  # human

    def toggle_play(self) -> None:
        if self._playing:
            self.stop_play()
            return
        if self._loading:
            self.run_label.setText("The AI is still loading; one moment.")
            return
        key = self.def_combo.currentData()
        if key == "human":
            self.run_label.setText("You are the defender: click a road on the map to fly it.")
            return
        if key and str(key).startswith("policy:") and self._policy is None:
            self.run_label.setText("The AI is still loading; one moment.")
            return
        if self._game is None:
            return
        self._playing = True
        self.play_btn.setText("⏸ Pause (space)")
        self._next_sortie()

    def stop_play(self) -> None:
        self._playing = False
        self._timer.stop()
        self.play_btn.setText("▶ Play (space)")

    def _human_route(self, route_idx: int) -> None:
        if self.def_combo.currentData() != "human" or self._anim is not None:
            return
        self._play_route(route_idx)

    def _next_sortie(self) -> None:
        r = self._choose_route()
        if r is not None:
            self._play_route(r)

    def _play_route(self, route: int) -> None:
        if self._game is None or self._duel is None or self._inst is None:
            return
        attacker = self.att_combo.currentData()
        res = self._duel.step(route, attacker)
        iset = self._inst.interdiction_sets[res["iset_index"]]
        iset_edges = [(tuple(e)[0], tuple(e)[-1]) for e in iset]
        self.map.clear_convoys()
        self.map.show_ambush(iset_edges, revealed=False)
        self._dots = [self.map.add_convoy(
            theme.STRATEGY_COLOURS["human"] if self.def_combo.currentData() == "human"
            else theme.STRATEGY_COLOURS["sacred"]) for _ in range(self._inst.N)]
        # if caught, the fleet dies AT the ambush: stop at the first route edge
        # in the committed interdiction set, not at the destination
        stop = 1.0
        if res["caught_sampled"]:
            nodes = self._inst.routes[route]
            iset_set = set(iset)
            for a, b in zip(nodes[:-1], nodes[1:]):
                if frozenset({a, b}) in iset_set:
                    fe = self.map.fraction_of_edge(route, (a, b))
                    if fe is not None:
                        stop = fe
                    break
        self._anim = {"route": route, "frac": 0.0, "res": res,
                      "stop": stop, "sprung": False}
        self._timer.start()

    def _tick(self) -> None:
        if self._anim is None:
            return
        anim = self._anim
        anim["frac"] += 0.014
        frac = min(1.0, anim["frac"])
        res = anim["res"]
        caught = res["caught_sampled"]
        stop = anim["stop"] if caught else 1.0
        for i, dot in enumerate(self._dots):
            # convoys travel in file; on interception the column halts behind the lead
            f = max(0.0, min(frac - 0.045 * i, max(0.0, stop - 0.03 * i)))
            self.map.place_on_route(dot, anim["route"], f)
        if caught and not anim["sprung"] and frac >= stop:
            # the ambush springs the moment the lead convoy reaches it
            anim["sprung"] = True
            self.map.reveal_ambush()
            for dot in self._dots:
                self.map.flash(dot)
                self.map.mark_lost(dot)
            # a short dwell so the loss reads, then the run ends
            anim["frac"] = max(anim["frac"], 1.0 - 0.014 * 16)
        if frac >= 1.0:
            if not caught:
                self.map.reveal_ambush()
                if self._dots:
                    self.map.celebrate(self._dots[0])
            self.strip.push(bool(caught))
            self._anim = None
            self._timer.stop()
            self._show_mixture()
            self._update_running()
            self._update_attention()
            if self._playing:
                QTimer.singleShot(260, self._next_sortie)

    def _run_batch(self) -> None:
        if self._game is None or self._duel is None or self._loading:
            return
        self.stop_play()
        key = self.def_combo.currentData()
        if key == "human":
            self.run_label.setText("Instant runs need an automatic defender.")
            return
        if key and key.startswith("policy:") and self._policy is None:
            self.run_label.setText("The AI is still loading; one moment.")
            return
        self.batch_btn.setEnabled(False)
        self.play_btn.setEnabled(False)
        duel, attacker = self._duel, self.att_combo.currentData()

        def batch():
            for _ in range(300):
                r = self._choose_route()
                if r is None:
                    break
                duel.step(r, attacker)
            return duel

        run_in_background(
            batch,
            on_done=lambda d: self._batch_done(d),
            on_fail=lambda tb: self._batch_done(None),
        )

    def _batch_done(self, duel) -> None:
        self.batch_btn.setEnabled(True)
        self.play_btn.setEnabled(True)
        if duel is not self._duel:
            return  # a reset happened mid-batch; discard
        self.map.clear_convoys()
        self.map.clear_ambush()
        self._update_running()
        self._update_attention()

    def _update_running(self) -> None:
        if self._duel is None or self._game is None:
            return
        d = self._duel
        if d.n:
            self.hero.set_value(d.mean_loss, 1)
            self.run_label.setText(
                f"{d.n} runs · dice seed {d.seed} · the score is the expected "
                f"loss under each run's committed ambush (the record's estimator)")
        else:
            self.hero.set_text("—")
            self.run_label.setText("No runs yet.")
        ax = self.run_chart.clear()
        if d.history:
            ax.plot(range(1, len(d.history) + 1), d.history,
                    color=theme.STRATEGY_COLOURS["human"]
                    if self.def_combo.currentData() == "human"
                    else theme.STRATEGY_COLOURS["sacred"], linewidth=1.8)
        r = self._game.refs
        for name, val, colour in (
            ("static_det", r["static_det"], theme.STRATEGY_COLOURS["static_det"]),
            ("iid_eq", r["iid_eq"], theme.STRATEGY_COLOURS["iid_eq"]),
            ("history_opt", r["history_opt"], theme.STRATEGY_COLOURS["history_opt"]),
        ):
            ax.axhline(val, linewidth=1.0, linestyle=":", color=colour)
            ax.annotate(f"{_ANCHOR_NAMES[name]} {lexicon.pct(val)}", xy=(0.0, val),
                        xycoords=("axes fraction", "data"), fontsize=9.5, va="bottom",
                        color=colour)
        ax.set_ylim(-0.02, max(0.7, float(r["static_det"]) + 0.05))
        ax.yaxis.set_major_formatter(mtick.PercentFormatter(1.0, decimals=0))
        ax.set_xlabel("run")
        self.run_chart.set_caption(
            f"dice seed {self._duel.seed} · enemy memory {self._game.w}, "
            f"sharpness {self._game.tau}", "live")
        self.run_chart.redraw()

    def export_view(self):
        return export_widget_grab(self, "playground-duel")
