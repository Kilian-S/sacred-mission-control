"""Playground mode 2: THE DUEL (within-episode pattern-of-life).

The interdictor softmax-best-responds to the defender's realised routes over a
trailing window (the gen19 game). Defenders: YOU (click routes on the map),
the gen19 history-aware policy, the history-blind equilibrium mixture, or the
best fixed route. Watching the history-aware policy dodge the adaptive
attacker down to the dynamic optimum is the gen19 headline, live."""

from __future__ import annotations

import numpy as np
from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
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

from .. import theme
from ..game import duel as duel_mod
from ..game.duel import DuelState, StackedGame
from ..sacred_bridge import oracle as oracle_bridge
from ..sacred_bridge import policies
from ..widgets.cards import Card, StateLabel
from ..widgets.charts import ChartWidget
from ..widgets.export import Exportable, export_widget_grab
from ..widgets.mapview import MapView
from ..workers import run_in_background


class DuelPanel(QWidget, Exportable):
    export_name = "playground-duel"

    def __init__(self, parent=None):
        super().__init__(parent)
        self._inst: oracle_bridge.OracleInstance | None = None
        self._game: StackedGame | None = None
        self._duel: DuelState | None = None
        self._policy: policies.LoadedPolicy | None = None
        self._policy_key = ""
        self._actor_refs = [r for r in policies.discover_actors() if r.kind == "history_aware"]
        self._playing = False
        self._pending_route: int | None = None
        self._anim = None
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
        bl.addWidget(QLabel("Attacker"))
        self.att_combo = QComboBox()
        self.att_combo.addItem("Pattern-of-life (softmax BR to your recent routes)", "pattern_of_life")
        self.att_combo.addItem("Committed BR to your cumulative play", "empirical_br")
        self.att_combo.currentIndexChanged.connect(self._reset_duel)
        bl.addWidget(self.att_combo)
        bl.addWidget(QLabel("window w"))
        self.w_spin = QSpinBox()
        self.w_spin.setRange(1, 3)
        self.w_spin.setValue(3)
        self.w_spin.valueChanged.connect(self._rebuild_game)
        bl.addWidget(self.w_spin)
        bl.addWidget(QLabel("tau"))
        self.tau_combo = QComboBox()
        self.tau_combo.addItems(["0.15", "0.05"])
        self.tau_combo.currentIndexChanged.connect(self._rebuild_game)
        bl.addWidget(self.tau_combo)
        bl.addStretch(1)
        self.play_btn = QPushButton("▶ Play (Space)")
        self.play_btn.setProperty("accent", True)
        self.play_btn.clicked.connect(self.toggle_play)
        bl.addWidget(self.play_btn)
        self.batch_btn = QPushButton("Run 300 instantly")
        self.batch_btn.clicked.connect(self._run_batch)
        bl.addWidget(self.batch_btn)
        self.reset_btn = QPushButton("Reset")
        self.reset_btn.clicked.connect(self._reset_duel)
        bl.addWidget(self.reset_btn)
        lay.addWidget(bar)

        split = QSplitter(Qt.Horizontal)
        self.map = MapView()
        self.map.route_clicked.connect(self._human_route)
        split.addWidget(self.map)
        split.addWidget(self._build_readouts())
        split.setSizes([780, 330])
        lay.addWidget(split, 1)

        self._timer = QTimer(self)
        self._timer.setInterval(33)
        self._timer.timeout.connect(self._tick)

    # ------------------------------------------------------------- readouts

    def _build_readouts(self) -> QWidget:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        host = QWidget()
        lay = QVBoxLayout(host)
        lay.setContentsMargins(0, 0, 4, 4)
        lay.setSpacing(8)

        self.anchor_card = Card()
        ah = QLabel("The dynamic game, solved live")
        ah.setProperty("h3", True)
        self.anchor_card.layout_().addWidget(ah)
        self.lbl_anchors = QLabel("…")
        self.lbl_anchors.setWordWrap(True)
        self.lbl_anchors.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.anchor_card.layout_().addWidget(self.lbl_anchors)
        cap = QLabel("computed live · exact value iteration over the window-state MDP")
        cap.setStyleSheet(f"color: {theme.LIVE_ACCENT}; font-size: 10px; font-weight: 600;")
        self.anchor_card.layout_().addWidget(cap)
        lay.addWidget(self.anchor_card)

        self.banked_card = Card()
        bh = QLabel("The banked gen19 record (35-159, w=3, tau=0.15)")
        bh.setProperty("h3", True)
        self.banked_card.layout_().addWidget(bh)
        bq = QLabel("static_det 0.613 > iid_eq/no-window 0.148 > **SACRED 0.050** ~ history_opt 0.049")
        bq.setTextFormat(Qt.MarkdownText)
        bq.setWordWrap(True)
        bq.setStyleSheet(
            f"font-size: 12px; background: {theme.PAGE}; border-left: 3px solid "
            f"{theme.BASELINE}; border-radius: 4px; padding: 5px 8px;")
        self.banked_card.layout_().addWidget(bq)
        src = QLabel("ledger: experiments/gen19_b1lite1.md")
        src.setStyleSheet(f"color: {theme.INK_MUTED}; font-size: 10px;")
        self.banked_card.layout_().addWidget(src)
        lay.addWidget(self.banked_card)

        self.run_card = Card()
        rh = QLabel("Running mean loss")
        rh.setProperty("h3", True)
        self.run_card.layout_().addWidget(rh)
        self.run_label = QLabel("No sorties yet.")
        self.run_label.setWordWrap(True)
        self.run_card.layout_().addWidget(self.run_label)
        self.run_chart = ChartWidget(title="duel-convergence", height=2.5, width=3.4)
        self.run_card.layout_().addWidget(self.run_chart)
        lay.addWidget(self.run_card)

        self.help_card = Card()
        hh = QLabel("How to read this")
        hh.setProperty("h3", True)
        self.help_card.layout_().addWidget(hh)
        ht = QLabel(
            "The interdictor watches your last w sorties and positions accordingly. "
            "A fixed route is destroyed (static_det); mixing blindly is safe but "
            "over-conservative (iid_eq); anticipating the anticipator (avoid your own "
            "recent pattern) reaches the dynamic optimum (history_opt). Click routes "
            "yourself to feel it, or let the gen19 policy play.")
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
        is_gen19_cell = (inst.city, inst.s, inst.t) == ("kaliningrad", "35", "159") \
            and inst.band == (0.15, 0.95)
        self.banked_card.setVisible(is_gen19_cell and self.w_spin.value() == 3
                                    and self.tau_combo.currentText() == "0.15")
        self._populate_defenders()
        self._rebuild_game()

    def _populate_defenders(self) -> None:
        self.def_combo.blockSignals(True)
        self.def_combo.clear()
        self.def_combo.addItem("YOU · click a route each sortie", "human")
        for r in self._actor_refs:
            self.def_combo.addItem(r.label, f"policy:{r.key}")
        self.def_combo.addItem("iid equilibrium mixture (history-blind)", "iid_eq")
        self.def_combo.addItem("Best fixed route (deterministic)", "static_det")
        self.def_combo.blockSignals(False)

    def _rebuild_game(self) -> None:
        if self._inst is None:
            return
        self.stop_play()
        w = self.w_spin.value()
        tau = float(self.tau_combo.currentText())
        self.lbl_anchors.setText("Solving the window-state MDP…")
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
            f"<b>static_det = {r['static_det']:.3f}</b> · a fixed route is destroyed<br>"
            f"<b>iid_eq = {r['iid_eq']:.3f}</b> · history-blind mixing (over-conservative "
            f"against this bounded adversary; single-shot minimax V_eq = {r['v_eq']:.3f})<br>"
            f"<b>history_opt = {r['history_opt']:.3f}</b> · the exact dynamic optimum "
            f"(anticipate the anticipator)")
        is_gen19_cell = (self._inst.city, self._inst.s, self._inst.t) == ("kaliningrad", "35", "159") \
            and self._inst.band == (0.15, 0.95)
        self.banked_card.setVisible(is_gen19_cell and game.w == 3 and abs(game.tau - 0.15) < 1e-9)
        self._reset_duel()
        self._defender_changed()

    def _defender_changed(self) -> None:
        key = self.def_combo.currentData()
        if key is None or self._inst is None:
            return
        if key and key.startswith("policy:") and key.split(":", 1)[1] != self._policy_key:
            ref = next((r for r in self._actor_refs if r.key == key.split(":", 1)[1]), None)
            if ref is not None:
                self.run_label.setText(f"Loading {ref.key}…")
                inst = self._inst
                run_in_background(
                    policies.load_policy, ref, inst,
                    on_done=self._policy_ready,
                    on_fail=lambda tb: self.run_label.setText(
                        "Policy load failed: " + tb.strip().splitlines()[-1]),
                )
        self._reset_duel()

    def _policy_ready(self, pol: policies.LoadedPolicy) -> None:
        self._policy = pol
        self._policy_key = pol.ref.key
        self.run_label.setText(f"{pol.ref.key} loaded ({pol.ref.provenance}).")
        self._show_mixture()

    def _reset_duel(self) -> None:
        if self._game is None:
            return
        self.stop_play()
        self._duel = DuelState(self._game, seed=self.seed)
        self.map.clear_convoys()
        self.map.clear_ambush()
        self._show_mixture()
        self._update_running()

    def set_seed(self, seed: int) -> None:
        self.seed = seed
        self._reset_duel()

    def _show_mixture(self) -> None:
        if self._game is None or self._duel is None:
            return
        key = self.def_combo.currentData()
        if key == "iid_eq":
            self.map.set_route_mixture(list(self._game.eq_mixture()))
        elif key == "static_det":
            d = np.zeros(self._game.R)
            d[int(np.argmin(np.max(self._game.L, axis=1)))] = 1.0
            self.map.set_route_mixture(list(d), theme.STRATEGY_COLOURS["static_det"])
        elif key and key.startswith("policy:") and self._policy is not None:
            d = self._policy.route_distribution(self._duel.window_freq())
            self.map.set_route_mixture(list(d))
        else:
            self.map.set_route_mixture([0.0] * self._game.R, theme.STRATEGY_COLOURS["human"])

    # ------------------------------------------------------------- play

    def _choose_route(self) -> int | None:
        """The automatic defender's route for the next sortie."""
        if self._game is None or self._duel is None:
            return None
        key = self.def_combo.currentData()
        rng = self._duel.rng
        if key == "iid_eq":
            eq = self._game.eq_mixture()
            return int(rng.choice(len(eq), p=eq / eq.sum()))
        if key == "static_det":
            return int(np.argmin(np.max(self._game.L, axis=1)))
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
        if self.def_combo.currentData() == "human":
            self.run_label.setText("You are the defender: click a route on the map to fly it.")
            return
        if self._game is None:
            return
        self._playing = True
        self.play_btn.setText("⏸ Pause (Space)")
        self._next_sortie()

    def stop_play(self) -> None:
        self._playing = False
        self._timer.stop()
        self.play_btn.setText("▶ Play (Space)")

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
        self._anim = {"route": route, "frac": 0.0, "res": res}
        self._timer.start()

    def _tick(self) -> None:
        if self._anim is None:
            return
        self._anim["frac"] += 0.014
        frac = min(1.0, self._anim["frac"])
        for i, dot in enumerate(self._dots):
            f = max(0.0, frac - 0.045 * i)  # convoys travel in file
            self.map.place_on_route(dot, self._anim["route"], f)
        if frac >= 1.0:
            res = self._anim["res"]
            self.map.reveal_ambush()
            if res["caught_sampled"]:
                for dot in self._dots:
                    self.map.flash(dot)
                    self.map.mark_lost(dot)
            self._anim = None
            self._timer.stop()
            self._show_mixture()
            self._update_running()
            if self._playing:
                QTimer.singleShot(260, self._next_sortie)

    def _run_batch(self) -> None:
        if self._game is None or self._duel is None:
            return
        self.stop_play()
        key = self.def_combo.currentData()
        if key == "human":
            self.run_label.setText("Batch mode needs an automatic defender.")
            return
        for _ in range(300):
            r = self._choose_route()
            if r is None:
                break
            self._duel.step(r, self.att_combo.currentData())
        self.map.clear_convoys()
        self.map.clear_ambush()
        self._update_running()

    def _update_running(self) -> None:
        if self._duel is None or self._game is None:
            return
        d = self._duel
        self.run_label.setText(
            f"<b>{d.mean_loss:.3f}</b> mean expected per-sortie mission failure over {d.n} "
            f"sorties (seed {d.seed}; the gen19 estimator: expected loss under each sortie's "
            f"committed ambush)" if d.n else "No sorties yet.")
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
            ax.annotate(f"{name} {val:.3f}", xy=(0.0, val),
                        xycoords=("axes fraction", "data"), fontsize=7.5, va="bottom",
                        color=colour)
        ax.set_ylim(-0.02, max(0.7, float(r["static_det"]) + 0.05))
        ax.set_xlabel("sortie")
        self.run_chart.set_caption(
            f"seed {self._duel.seed} · w={self._game.w} tau={self._game.tau}", "live")
        self.run_chart.redraw()

    def export_view(self):
        return export_widget_grab(self, "playground-duel")
