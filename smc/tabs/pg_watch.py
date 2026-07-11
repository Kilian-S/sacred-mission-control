"""Playground mode 1: WATCH. Pick strategies for both sides and watch the
sortie loop converge to the exact solved values. Includes the trained roster
(post-fix actors, loaded lazily in workers)."""

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
from ..game.sortie import AttackerSpec, DefenderSpec, SortieEngine, SortieOutcome
from ..sacred_bridge import oracle as oracle_bridge
from ..sacred_bridge import policies
from ..widgets.cards import Card, EraBadge, StateLabel
from ..widgets.charts import ChartWidget
from ..widgets.export import Exportable, export_widget_grab
from ..widgets.mapview import MapView
from ..workers import run_in_background


class WatchPanel(QWidget, Exportable):
    export_name = "playground-watch"

    def __init__(self, parent=None):
        super().__init__(parent)
        self._inst: oracle_bridge.OracleInstance | None = None
        self._engine: SortieEngine | None = None
        self._defenders: list[DefenderSpec] = []
        self._attackers: list[AttackerSpec] = []
        self._city_loaded = ""
        self._playing = False
        self._anim_frac = 0.0
        self.speed = 1.0
        self._outcome: SortieOutcome | None = None
        self._dots = []
        self._alns_assignment: list[int] | None = None
        self._actor_refs = policies.discover_actors()
        self._loaded_policies: dict[str, np.ndarray] = {}  # ref.key -> occ_dist
        self._preset: dict | None = None
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
        self.def_combo.setMinimumWidth(240)
        self.def_combo.currentIndexChanged.connect(self._matchup_changed)
        bl.addWidget(self.def_combo)
        self.alns_btn = QPushButton("Compute ALNS")
        self.alns_btn.setToolTip("Run the classical metaheuristic on this instance (a few seconds)")
        self.alns_btn.clicked.connect(self._compute_alns)
        bl.addWidget(self.alns_btn)
        self.load_btn = QPushButton("Load trained SACRED…")
        self.load_btn.setToolTip("Load a post-fix actor checkpoint into the roster (lazy torch)")
        self.load_btn.clicked.connect(self._load_policy_clicked)
        bl.addWidget(self.load_btn)
        bl.addWidget(QLabel("Attacker"))
        self.att_combo = QComboBox()
        self.att_combo.setMinimumWidth(200)
        self.att_combo.currentIndexChanged.connect(self._matchup_changed)
        bl.addWidget(self.att_combo)
        bl.addStretch(1)
        self.play_btn = QPushButton("▶ Play (Space)")
        self.play_btn.setProperty("accent", True)
        self.play_btn.clicked.connect(self.toggle_play)
        bl.addWidget(self.play_btn)
        self.batch_btn = QPushButton("Run 500 instantly")
        self.batch_btn.clicked.connect(self._run_batch)
        bl.addWidget(self.batch_btn)
        lay.addWidget(bar)

        split = QSplitter(Qt.Horizontal)
        self.map = MapView()
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
        live_cap = QLabel("computed live · LP oracle on this instance")
        live_cap.setStyleSheet(f"color: {theme.LIVE_ACCENT}; font-size: 10px; font-weight: 600;")
        self.oracle_card.layout_().addWidget(live_cap)
        lay.addWidget(self.oracle_card)

        self.policy_card = Card()
        ph = QLabel("Trained policy on this instance")
        ph.setProperty("h3", True)
        self.policy_card.layout_().addWidget(ph)
        self.policy_body = QLabel("")
        self.policy_body.setWordWrap(True)
        self.policy_card.layout_().addWidget(self.policy_body)
        self.policy_card.hide()
        lay.addWidget(self.policy_card)

        self.banked_card = Card()
        bh = QLabel("The banked record for this instance")
        bh.setProperty("h3", True)
        self.banked_card.layout_().addWidget(bh)
        self.banked_host = QWidget()
        self.banked_body = QVBoxLayout(self.banked_host)
        self.banked_body.setContentsMargins(0, 0, 0, 0)
        self.banked_card.layout_().addWidget(self.banked_host)
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

    # ------------------------------------------------------------- instance

    def set_instance(self, inst: oracle_bridge.OracleInstance, preset: dict | None,
                     seed: int) -> None:
        self.stop_play()
        self._inst = inst
        self._preset = preset
        self.seed = seed
        self._alns_assignment = None
        self._loaded_policies = {}
        self._engine = SortieEngine(inst, seed=seed)
        if inst.city != self._city_loaded:
            self.map.set_city(inst.city_map)
            self._city_loaded = inst.city
        self.map.show_instance(inst.routes, inst.edge_vuln, inst.s, inst.t)
        self.alns_btn.setText("Compute ALNS")
        self.alns_btn.setEnabled(True)
        self._refresh_defenders()
        self._show_banked()

    def set_seed(self, seed: int) -> None:
        self.seed = seed
        if self._engine:
            self._engine.reseed(seed)
            self._update_running()

    def reset_stats(self) -> None:
        if self._engine:
            self._engine.reset_stats()
            self._update_running()

    # ------------------------------------------------------------- roster

    def _refresh_defenders(self) -> None:
        if self._engine is None or self._inst is None:
            return
        self._defenders = self._engine.defender_specs()
        if self._alns_assignment is not None:
            self._defenders.append(self._engine.alns_spec(self._alns_assignment))
        for key, occ in self._loaded_policies.items():
            ref = next((r for r in self._actor_refs if r.key == key), None)
            if ref is None:
                continue
            marg = self._engine._stacked_route_marginal(occ)
            self._defenders.append(DefenderSpec(
                f"policy:{key}", f"SACRED {ref.key} (trained, banked ensemble)",
                occ, marg))
        sel = self.def_combo.currentIndex()
        self.def_combo.blockSignals(True)
        self.def_combo.clear()
        for d in self._defenders:
            self.def_combo.addItem(d.label, d.key)
        default = next((i for i, d in enumerate(self._defenders) if d.key == "equilibrium"), 0)
        self.def_combo.setCurrentIndex(sel if 0 <= sel < len(self._defenders) else default)
        self.def_combo.blockSignals(False)
        self._matchup_changed()

    def _applicable_actors(self) -> list[policies.ActorRef]:
        inst = self._inst
        if inst is None or inst.band is None:
            return []  # trained actors observe the vulnerability column
        out = []
        for r in self._actor_refs:
            if r.kind == "specialist":
                if (inst.city, inst.s, inst.t, inst.N, inst.K) == ("kaliningrad", "35", "159", 3, 1) \
                        and inst.band == (0.15, 0.95) and inst.k_extra == 8:
                    out.append(r)
            elif r.kind == "generalist":
                out.append(r)
            # history-aware actors belong to the duel mode, not static watch
        return out

    def _load_policy_clicked(self) -> None:
        refs = self._applicable_actors()
        if not refs:
            self.policy_card.show()
            self.policy_body.setText(
                "No trained actor applies here. Specialists (gen13/gen14) load only on their "
                "trained cell (Kaliningrad 35-159, N=3, K=1, band 0.15-0.95); generalists need "
                "a soft threat band. Pre-fix actors are History material and never load live.")
            return
        from PySide6.QtWidgets import QInputDialog
        labels = [r.label for r in refs]
        label, ok = QInputDialog.getItem(self, "Load trained SACRED",
                                         "Checkpoint (banked TAP ensemble):", labels, 0, False)
        if not ok:
            return
        ref = refs[labels.index(label)]
        self.load_btn.setEnabled(False)
        self.load_btn.setText(f"Loading {ref.key}…")
        inst = self._inst
        run_in_background(
            self._load_policy_worker, ref, inst,
            on_done=self._policy_loaded,
            on_fail=self._policy_failed,
        )

    @staticmethod
    def _load_policy_worker(ref: policies.ActorRef, inst) -> tuple[str, np.ndarray, str]:
        pol = policies.load_policy(ref, inst)
        d = pol.route_distribution()
        occ = inst.route_dist_to_stacked_occ_dist(d)
        return ref.key, occ, ref.provenance

    def _policy_loaded(self, result) -> None:
        key, occ, provenance = result
        self.load_btn.setEnabled(True)
        self.load_btn.setText("Load trained SACRED…")
        if self._inst is None or self._engine is None:
            return
        self._loaded_policies[key] = occ
        _, e = self._inst.exploitability_occ(occ)
        self.policy_card.show()
        self.policy_body.setText(
            f"<b>{key}</b> loaded (actor checkpoints: {provenance}).<br>"
            f"Its route mixture's worst-case mission failure on THIS instance, computed live: "
            f"<b>{e:.3f}</b> (equilibrium {self._inst.mc_value:.3f}, "
            f"ALNS/loss_det {self._inst.mc_loss_det:.3f}).")
        self._refresh_defenders()
        idx = next((i for i, d in enumerate(self._defenders) if d.key == f"policy:{key}"), None)
        if idx is not None:
            self.def_combo.setCurrentIndex(idx)

    def _policy_failed(self, tb: str) -> None:
        self.load_btn.setEnabled(True)
        self.load_btn.setText("Load trained SACRED…")
        self.policy_card.show()
        self.policy_body.setText("Policy failed to load: " + tb.strip().splitlines()[-1])

    def _compute_alns(self) -> None:
        if self._inst is None:
            return
        self.alns_btn.setEnabled(False)
        self.alns_btn.setText("ALNS running…")
        run_in_background(
            oracle_bridge.alns_plan, self._inst,
            on_done=self._alns_done,
            on_fail=lambda tb: (self.alns_btn.setEnabled(True),
                                self.alns_btn.setText("Compute ALNS")),
        )

    def _alns_done(self, result) -> None:
        assignment, expl = result
        self._alns_assignment = assignment
        self.alns_btn.setEnabled(True)
        self.alns_btn.setText(f"ALNS ready ({expl:.3f})")
        self._refresh_defenders()
        idx = next((i for i, d in enumerate(self._defenders) if d.key == "alns"), None)
        if idx is not None:
            self.def_combo.setCurrentIndex(idx)

    # ------------------------------------------------------------- matchup

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
        keep = self.att_combo.currentIndex()
        self._attackers = self._engine.attacker_specs(d)
        self.att_combo.blockSignals(True)
        self.att_combo.clear()
        for a in self._attackers:
            self.att_combo.addItem(a.label, a.key)
        self.att_combo.setCurrentIndex(keep if 0 <= keep < len(self._attackers) else 0)
        self.att_combo.blockSignals(False)

        colour = theme.BLUE if d.key.startswith("policy:") or d.key == "equilibrium" else \
            theme.STRATEGY_COLOURS.get(d.key.split(":")[0], theme.BLUE)
        if d.route_dist is not None:
            self.map.set_route_mixture(list(d.route_dist), colour)
        else:
            marg = self._engine._stacked_route_marginal(d.occ_dist)
            self.map.set_route_mixture(list(marg), colour)
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
            "can do against a committed attacker (what ALNS converges to)")
        self.lbl_mixed.setText(
            f"<b>loss_mixed = {inst.mc_value:.3f}</b> · the minimax equilibrium value "
            "(calibrated MIXED strategy)")
        if d is not None:
            e = self._engine.exploitability(d)
            self.lbl_expl.setText(
                f"<b>{e:.3f}</b> · worst-case mission failure of “{d.label}” "
                "under the oracle best response")
        if d is not None and a is not None:
            ev = self._engine.expected_value(d, a)
            self.lbl_expected.setText(
                f"<b>{ev:.3f}</b> · exact expected mission failure of this matchup "
                "(the running estimate converges here)")

    def _show_banked(self) -> None:
        while self.banked_body.count():
            it = self.banked_body.takeAt(0)
            w = it.widget()
            if w:
                w.deleteLater()
        p = self._preset
        if not p or not p.get("banked"):
            self.banked_card.hide()
            return
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
                q.setTextFormat(Qt.MarkdownText)
                q.setWordWrap(True)
                q.setTextInteractionFlags(Qt.TextSelectableByMouse)
                q.setStyleSheet(
                    f"font-size: 12px; background: {theme.PAGE}; border-left: 3px solid "
                    f"{theme.BASELINE}; border-radius: 4px; padding: 5px 8px;")
                src = QLabel("ledger: " + item.get("ledger", bank["ledger"]))
                src.setStyleSheet(f"color: {theme.INK_MUTED}; font-size: 10px;")
                self.banked_body.addWidget(q)
                self.banked_body.addWidget(src)
        self.banked_card.show()

    # ------------------------------------------------------------- sortie loop

    def toggle_play(self) -> None:
        if self._playing:
            self.stop_play()
        else:
            if self._engine is None:
                return
            self._playing = True
            self.play_btn.setText("⏸ Pause (Space)")
            self._begin_sortie()
            self._timer.start()

    def stop_play(self) -> None:
        self._playing = False
        self._timer.stop()
        self.play_btn.setText("▶ Play (Space)")

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
        self._anim_frac += 0.011 * self.speed
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
                QTimer.singleShot(int(420 / self.speed), self._maybe_next)
            self._outcome = None

    def _maybe_next(self) -> None:
        if self._playing:
            self._begin_sortie()

    def _edge_frac(self, route_idx: int, edge: tuple[str, str]) -> float:
        if self._inst is None:
            return 1.0
        nodes = self._inst.routes[route_idx]
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
        self.stop_play()
        for _ in range(500):
            self._engine.play_sortie(d, a)
        self.map.clear_convoys()
        self.map.clear_ambush()
        self._update_running()

    def _update_running(self) -> None:
        if self._engine is None:
            return
        st = self._engine.stats
        d, a = self._current_defender(), self._current_attacker()
        ev = self._engine.expected_value(d, a) if (d and a) else float("nan")
        self.run_label.setText(
            f"<b>{st.rate:.3f}</b> mission-failure rate over {st.n} sorties "
            f"(seed {self._engine.seed}) · exact value {ev:.3f}")
        self._redraw_convergence()

    def _redraw_convergence(self) -> None:
        if self._engine is None or self._inst is None:
            return
        ax = self.run_chart.clear()
        st = self._engine.stats
        d, a = self._current_defender(), self._current_attacker()
        if st.history:
            ax.plot(range(1, len(st.history) + 1), st.history,
                    color=theme.STRATEGY_COLOURS["sacred"], linewidth=1.8)
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
        self.run_chart.set_caption(f"seed {self._engine.seed} · mission-failure per sortie", "live")
        self.run_chart.redraw()

    def export_view(self):
        return export_widget_grab(self, "playground-watch")
