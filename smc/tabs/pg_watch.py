"""Playground · Watch the game: pick a defender and an enemy, press play, and
watch the measured failure rate settle onto the predicted value. Plain words
lead; the formal terms live in fine print and the record drawer."""

from __future__ import annotations

import matplotlib.ticker as mtick
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

from .. import lexicon, theme
from ..game.sortie import AttackerSpec, DefenderSpec, SortieEngine, SortieOutcome
from ..sacred_bridge import oracle as oracle_bridge
from ..sacred_bridge import policies
from ..widgets.cards import Card, EraBadge
from ..widgets.charts import ChartWidget
from ..widgets.export import Exportable, export_widget_grab
from ..widgets.human import GoalpostBar, HeroNumber, MapLegend, OutcomeStrip, RecordDisclosure
from ..widgets.mapview import MapView
from ..workers import run_in_background

# trained-policy display names by run family (the lexicon is frozen; these are
# scenario-aware refinements of lexicon.strategy_name)
_POLICY_NAMES = {
    "gen13_lock": "SACRED (trained on this crossing)",
    "gen14_evidence": "SACRED (trained on this crossing)",
    "gen15_generalist": "SACRED (trained on this city's crossings)",
    "gen16_multicity": "SACRED (multi-city training)",
    "gen22_rotation": "SACRED (multi-city training, Istanbul held out)",
    "gen20_f2": "SACRED (trained against a learned enemy)",
    "gen24_distill": lexicon.strategy_name("distill"),
    "gen25_dr": lexicon.strategy_name("dr"),
    "gen21_vanilla": lexicon.strategy_name("vanilla"),
}


def _defender_display(d: DefenderSpec, refs: list[policies.ActorRef]) -> str:
    if d.key.startswith("policy:"):
        key = d.key.split(":", 1)[1]
        ref = next((r for r in refs if r.key == key), None)
        if ref is not None:
            base = _POLICY_NAMES.get(ref.family, "SACRED")
            seed = ref.key.rsplit("seed", 1)[-1]
            return f"{base} · run {int(seed) + 1}" if seed.isdigit() else base
        return "SACRED"
    return lexicon.strategy_name(d.key) or d.label


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
        self.def_combo.setMinimumWidth(250)
        self.def_combo.currentIndexChanged.connect(self._matchup_changed)
        bl.addWidget(self.def_combo)
        self.alns_btn = QPushButton("Ask the professional planner")
        self.alns_btn.setToolTip(
            "Compute the strongest industry plan for this scenario (a few seconds; "
            "the ALNS metaheuristic)")
        self.alns_btn.clicked.connect(self._compute_alns)
        bl.addWidget(self.alns_btn)
        self.load_btn = QPushButton("Add a trained AI…")
        self.load_btn.setToolTip(
            "Load a trained network from the project's record into the list")
        self.load_btn.clicked.connect(self._load_policy_clicked)
        bl.addWidget(self.load_btn)
        bl.addWidget(QLabel("Enemy"))
        self.att_combo = QComboBox()
        self.att_combo.setMinimumWidth(210)
        self.att_combo.currentIndexChanged.connect(self._matchup_changed)
        bl.addWidget(self.att_combo)
        bl.addStretch(1)
        self.play_btn = QPushButton("▶ Play (space)")
        self.play_btn.setProperty("accent", True)
        self.play_btn.clicked.connect(self.toggle_play)
        bl.addWidget(self.play_btn)
        self.batch_btn = QPushButton("Run 500 instantly")
        self.batch_btn.setProperty("quiet", True)
        self.batch_btn.clicked.connect(self._run_batch)
        bl.addWidget(self.batch_btn)
        lay.addWidget(bar)

        self.blurb_label = QLabel("")
        self.blurb_label.setProperty("fineprint", True)
        self.blurb_label.setWordWrap(True)
        lay.addWidget(self.blurb_label)

        split = QSplitter(Qt.Horizontal)
        map_col = QWidget()
        ml = QVBoxLayout(map_col)
        ml.setContentsMargins(0, 0, 0, 0)
        ml.setSpacing(2)
        self.map = MapView()
        ml.addWidget(self.map, 1)
        ml.addWidget(MapLegend())
        split.addWidget(map_col)
        split.addWidget(self._build_readouts())
        split.setSizes([760, 350])
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
        lay.setSpacing(10)

        self.hero_card = Card()
        self.hero = HeroNumber("chance the mission fails against this enemy")
        self.hero_card.layout_().addWidget(self.hero)
        live_cap = QLabel("computed live, on your machine, for this exact scenario")
        live_cap.setStyleSheet(
            f"color: {theme.LIVE_ACCENT}; font-size: 12px; font-weight: 600;")
        self.hero_card.layout_().addWidget(live_cap)

        gp_head = QLabel("How close to perfect?")
        gp_head.setProperty("h3", True)
        self.hero_card.layout_().addWidget(gp_head)
        gp_sub = QLabel(f"the dot is this defender, {lexicon.CONDITION}")
        gp_sub.setProperty("fineprint", True)
        gp_sub.setWordWrap(True)
        self.hero_card.layout_().addWidget(gp_sub)
        self.goalpost = GoalpostBar()
        self.hero_card.layout_().addWidget(self.goalpost)
        self.gap_line = QLabel("")
        self.gap_line.setProperty("fineprint", True)
        self.gap_line.setWordWrap(True)
        self.hero_card.layout_().addWidget(self.gap_line)
        lay.addWidget(self.hero_card)

        self.score_card = Card()
        sh = QLabel("The score so far")
        sh.setProperty("h3", True)
        self.score_card.layout_().addWidget(sh)
        self.strip = OutcomeStrip()
        self.score_card.layout_().addWidget(self.strip)
        self.run_label = QLabel("No runs yet. Press play.")
        self.run_label.setWordWrap(True)
        self.run_label.setProperty("fineprint", True)
        self.score_card.layout_().addWidget(self.run_label)
        lay.addWidget(self.score_card)

        # trained-policy note (shown after a load)
        self.policy_card = Card()
        ph = QLabel("Trained AI on this scenario")
        ph.setProperty("h3", True)
        self.policy_card.layout_().addWidget(ph)
        self.policy_body = QLabel("")
        self.policy_body.setWordWrap(True)
        self.policy_card.layout_().addWidget(self.policy_body)
        self.policy_card.hide()
        lay.addWidget(self.policy_card)

        # proof on demand
        self.record_host = QWidget()
        self.record_lay = QVBoxLayout(self.record_host)
        self.record_lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(self.record_host)

        # expert view
        self.detail_btn = QPushButton("More detail ▸")
        self.detail_btn.setProperty("quiet", True)
        self.detail_btn.setCheckable(True)
        self.detail_btn.toggled.connect(self._toggle_detail)
        lay.addWidget(self.detail_btn)

        self.detail_host = QWidget()
        dl = QVBoxLayout(self.detail_host)
        dl.setContentsMargins(0, 0, 0, 0)
        dl.setSpacing(10)
        self.mix_card = Card()
        mh = QLabel("How often each road gets used")
        mh.setProperty("h3", True)
        self.mix_card.layout_().addWidget(mh)
        self.mix_chart = ChartWidget(title="playground-mixture-compare",
                                     height=2.1, width=3.4)
        self.mix_card.layout_().addWidget(self.mix_chart)
        dl.addWidget(self.mix_card)
        self.run_card = Card()
        rh = QLabel("The measured rate homes in on the predicted value")
        rh.setProperty("h3", True)
        self.run_card.layout_().addWidget(rh)
        self.run_chart = ChartWidget(title="playground-convergence",
                                     height=2.3, width=3.4)
        self.run_card.layout_().addWidget(self.run_chart)
        dl.addWidget(self.run_card)
        self.detail_host.hide()
        lay.addWidget(self.detail_host)

        lay.addStretch(1)
        scroll.setWidget(host)
        return scroll

    def _toggle_detail(self, on: bool) -> None:
        self.detail_btn.setText("More detail ▾" if on else "More detail ▸")
        self.detail_host.setVisible(on)

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
        self.strip.reset()
        self.run_label.setText("No runs yet. Press play.")
        self.alns_btn.setText("Ask the professional planner")
        self.alns_btn.setEnabled(True)
        self._refresh_defenders()
        self._show_banked()

    def set_seed(self, seed: int) -> None:
        self.seed = seed
        if self._engine:
            self._engine.reseed(seed)
            self.strip.reset()
            self._update_running()

    def reset_stats(self) -> None:
        if self._engine:
            self._engine.reset_stats()
            self.strip.reset()
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
            self._defenders.append(DefenderSpec(f"policy:{key}", key, occ, marg))
        sel = self.def_combo.currentIndex()
        self.def_combo.blockSignals(True)
        self.def_combo.clear()
        for d in self._defenders:
            self.def_combo.addItem(_defender_display(d, self._actor_refs), d.key)
            self.def_combo.setItemData(
                self.def_combo.count() - 1,
                lexicon.strategy_blurb(d.key) or d.label, Qt.ToolTipRole)
        default = next((i for i, d in enumerate(self._defenders)
                        if d.key == "equilibrium"), 0)
        self.def_combo.setCurrentIndex(sel if 0 <= sel < len(self._defenders) else default)
        self.def_combo.blockSignals(False)
        self._matchup_changed()

    def _applicable_actors(self) -> list[policies.ActorRef]:
        inst = self._inst
        if inst is None or inst.band is None:
            return []  # trained actors observe the danger column
        out = []
        for r in self._actor_refs:
            if r.kind == "specialist":
                if (inst.city, inst.s, inst.t, inst.N, inst.K) == ("kaliningrad", "35", "159", 3, 1) \
                        and inst.band == (0.15, 0.95) and inst.k_extra == 8:
                    out.append(r)
            elif r.kind in ("generalist", "control"):
                out.append(r)
            # history-aware actors belong to the you-defend game
        return out

    def _load_policy_clicked(self) -> None:
        refs = self._applicable_actors()
        if not refs:
            self.policy_card.show()
            self.policy_body.setText(
                "No trained AI applies here. The record's crossing specialists only "
                "load on the crossing they trained on (The proving ground, three "
                "convoys, one ambush team); every trained AI needs the road-danger "
                "rule rather than every-ambush-lethal.")
            return
        from PySide6.QtWidgets import QInputDialog
        labels = [f"{_POLICY_NAMES.get(r.family, 'SACRED')} · {r.key}" for r in refs]
        label, ok = QInputDialog.getItem(
            self, "Add a trained AI",
            "Networks from the project record (banked checkpoints):", labels, 0, False)
        if not ok:
            return
        ref = refs[labels.index(label)]
        self.load_btn.setEnabled(False)
        self.load_btn.setText("Loading…")
        inst = self._inst
        run_in_background(
            self._load_policy_worker, ref, inst,
            on_done=lambda result, started_on=inst: self._policy_loaded(result, started_on),
            on_fail=self._policy_failed,
        )

    @staticmethod
    def _load_policy_worker(ref: policies.ActorRef, inst) -> tuple[str, np.ndarray, str]:
        pol = policies.load_policy(ref, inst)
        d = pol.route_distribution()
        occ = inst.route_dist_to_stacked_occ_dist(d)
        return ref.key, occ, ref.provenance

    def _policy_loaded(self, result, started_on=None) -> None:
        key, occ, provenance = result
        self.load_btn.setEnabled(True)
        self.load_btn.setText("Add a trained AI…")
        if self._inst is None or self._engine is None:
            return
        if started_on is not None and started_on is not self._inst:
            return  # the scenario changed while the policy was loading; discard
        self._loaded_policies[key] = occ
        _, e = self._inst.exploitability_occ(occ)
        ref = next((r for r in self._actor_refs if r.key == key), None)
        name = _POLICY_NAMES.get(ref.family, "SACRED") if ref else "SACRED"
        self.policy_card.show()
        self.policy_body.setText(
            f"<b>{name}</b> is in the defender list. Against an enemy who has "
            f"learned its habits it loses {lexicon.pct(e)} of missions here "
            f"(the proven optimum is {lexicon.pct(self._inst.mc_value)}; the best "
            f"predictable plan {lexicon.pct(self._inst.mc_loss_det)}).<br>"
            f"<span style='color:{theme.INK_MUTED}; font-size:12px;'>checkpoints: "
            f"{provenance} · computed live</span>")
        self._refresh_defenders()
        idx = next((i for i, d in enumerate(self._defenders)
                    if d.key == f"policy:{key}"), None)
        if idx is not None:
            self.def_combo.setCurrentIndex(idx)

    def _policy_failed(self, tb: str) -> None:
        self.load_btn.setEnabled(True)
        self.load_btn.setText("Add a trained AI…")
        self.policy_card.show()
        self.policy_body.setText("The AI failed to load: " + tb.strip().splitlines()[-1])

    def _compute_alns(self) -> None:
        if self._inst is None:
            return
        self.alns_btn.setEnabled(False)
        self.alns_btn.setText("Planning…")
        inst = self._inst
        run_in_background(
            oracle_bridge.alns_plan, inst,
            on_done=lambda result, started_on=inst: self._alns_done(result, started_on),
            on_fail=lambda tb: (self.alns_btn.setEnabled(True),
                                self.alns_btn.setText("Ask the professional planner")),
        )

    def _alns_done(self, result, started_on=None) -> None:
        assignment, expl = result
        self.alns_btn.setEnabled(True)
        if started_on is not None and started_on is not self._inst:
            self.alns_btn.setText("Ask the professional planner")
            return  # the scenario changed while the planner ran; discard
        self._alns_assignment = assignment
        self.alns_btn.setText(f"Planner ready (loses {lexicon.pct(expl)})")
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
            self.att_combo.addItem(lexicon.attacker_name(a.key) or a.label, a.key)
            self.att_combo.setItemData(
                self.att_combo.count() - 1,
                lexicon.ATTACKERS.get(a.key, ("", ""))[1], Qt.ToolTipRole)
        self.att_combo.setCurrentIndex(keep if 0 <= keep < len(self._attackers) else 0)
        self.att_combo.blockSignals(False)

        self._update_blurbs()

        colour = theme.BLUE if d.key.startswith("policy:") or d.key == "equilibrium" else \
            theme.STRATEGY_COLOURS.get(d.key.split(":")[0], theme.BLUE)
        if d.route_dist is not None:
            self.map.set_route_mixture(list(d.route_dist), colour)
        else:
            marg = self._engine._stacked_route_marginal(d.occ_dist)
            self.map.set_route_mixture(list(marg), colour)
        self._engine.reset_stats()
        self.strip.reset()
        self._update_readouts()
        self._redraw_mixture_compare(d, colour)
        self._redraw_convergence()

    def _update_blurbs(self) -> None:
        d = self._current_defender()
        a = self._current_attacker()
        parts = []
        if d is not None:
            blurb = lexicon.strategy_blurb(d.key)
            parts.append(f"Defender: {blurb or d.label}")
        if a is not None:
            parts.append(f"Enemy: {lexicon.ATTACKERS.get(a.key, ('', a.label))[1]}")
        self.blurb_label.setText("   ·   ".join(parts))

    def _redraw_mixture_compare(self, d: DefenderSpec, colour: str) -> None:
        """This defender's road usage beside the proven-optimal mix: when a
        trained SACRED mixture sits on the optimal bars, the claim is visible
        in one glance."""
        if self._engine is None or self._inst is None:
            return
        inst = self._inst
        ax = self.mix_chart.clear()
        eq_marg = self._engine._stacked_route_marginal(inst.mc_defender)
        cur = d.route_dist if d.route_dist is not None \
            else self._engine._stacked_route_marginal(d.occ_dist)
        x = np.arange(inst.n_routes)
        ax.bar(x - 0.19, cur, width=0.38, color=colour, label="this defender")
        ax.bar(x + 0.19, eq_marg, width=0.38,
               color=theme.STRATEGY_COLOURS["equilibrium"], alpha=0.85,
               label="the proven-optimal mix")
        ax.set_xticks(x)
        ax.set_xlabel("road choice", fontsize=10)
        ax.set_ylabel("share of runs", fontsize=10)
        ax.yaxis.set_major_formatter(mtick.PercentFormatter(1.0, decimals=0))
        ax.tick_params(labelsize=9)
        ax.legend(fontsize=9, loc="upper right")
        self.mix_chart.set_caption("how often each road gets used", "live")
        self.mix_chart.redraw()

    def _update_readouts(self) -> None:
        if self._engine is None or self._inst is None:
            return
        inst = self._inst
        d = self._current_defender()
        a = self._current_attacker()
        metric = lexicon.metric_phrase(inst.objective, inst.threshold_m)
        self.hero.set_caption(f"{metric} against this enemy")
        if d is not None and a is not None:
            ev = self._engine.expected_value(d, a)
            self.hero.set_value(ev)
            self.hero.set_fine_print(
                f"exact expected value of this matchup, {ev:.3f} · the running "
                f"score converges here · formal terms in the record drawer")
        self.goalpost.set_posts(inst.mc_value, inst.mc_loss_det)
        if d is not None:
            e = self._engine.exploitability(d)
            self.goalpost.set_value(e)
            headroom = inst.mc_loss_det - inst.mc_value
            if headroom > 1e-9:
                gc = (inst.mc_loss_det - e) / headroom
                self.gap_line.setText(
                    f"closes {gc:.0%} of the gap between the two goalposts "
                    f"(0% = no better than a predictable plan, 100% = perfect)")
            else:
                self.gap_line.setText(
                    "no gap between the goalposts on this scenario: predictable "
                    "play is already optimal here")

    def _show_banked(self) -> None:
        # rebuild the disclosure fresh each time (its body has no clear API)
        while self.record_lay.count():
            it = self.record_lay.takeAt(0)
            w = it.widget()
            if w:
                w.deleteLater()
        p = self._preset
        if not p or not p.get("banked"):
            return
        disc = RecordDisclosure()
        for bank in p["banked"]:
            disc.add_line(f"measured at {bank['cell']} · era: {bank.get('era', 'post-fix')}")
            for item in bank["items"]:
                disc.add_quote(item["quote"], item.get("ledger", bank["ledger"]))
        if self._inst is not None and p["banked"]:
            cell0 = p["banked"][0].get("cell", "")
            here = f"N={self._inst.N} K={self._inst.K}"
            if here not in cell0:
                disc.add_line(
                    f"⚠ the rules are currently {here}; these record numbers were "
                    f"measured at {cell0} and do not apply to the current rules")
        self.record_lay.addWidget(disc)

    # ------------------------------------------------------------- sortie loop

    def toggle_play(self) -> None:
        if self._playing:
            self.stop_play()
        else:
            if self._engine is None:
                return
            self._playing = True
            self.play_btn.setText("⏸ Pause (space)")
            self._begin_sortie()
            self._timer.start()

    def stop_play(self) -> None:
        self._playing = False
        self._timer.stop()
        self.play_btn.setText("▶ Play (space)")

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
                fe = self.map.fraction_of_edge(r, caught_e)
                stop_frac = fe if fe is not None else self._edge_frac(r, caught_e)
            f = min(frac, stop_frac)
            self.map.place_on_route(dot, r, f)
            if caught_e is not None and frac >= stop_frac and not self._flashed[ci]:
                self._flashed[ci] = True
                self.map.flash(dot)
                self.map.mark_lost(dot)
        if done:
            self.map.reveal_ambush()
            if not self._outcome.mission_failed and self._dots:
                self.map.celebrate(self._dots[-1])
            self.strip.push(self._outcome.mission_failed)
            self._update_running()
            if self._playing:
                QTimer.singleShot(int(420 / self.speed), self._maybe_next)
            self._outcome = None

    def _maybe_next(self) -> None:
        if self._playing:
            self._begin_sortie()

    def _edge_frac(self, route_idx: int, edge: tuple[str, str]) -> float:
        """Edge-count fallback for routes the map could not draw."""
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
        # in a worker: at three ambush teams a run samples from ~80k-entry
        # distributions and 500 of them would stall the interface
        self.batch_btn.setEnabled(False)
        self.play_btn.setEnabled(False)
        engine = self._engine

        def batch():
            for _ in range(500):
                engine.play_sortie(d, a)
            return engine

        run_in_background(batch, on_done=self._batch_done,
                          on_fail=lambda tb: self._batch_done(None))

    def _batch_done(self, engine) -> None:
        self.batch_btn.setEnabled(True)
        self.play_btn.setEnabled(True)
        if engine is None or engine is not self._engine:
            return  # scenario changed mid-batch; discard
        self.map.clear_convoys()
        self.map.clear_ambush()
        # the strip shows watched runs only; totals live in the label and chart
        self._update_running()

    def _update_running(self) -> None:
        if self._engine is None:
            return
        st = self._engine.stats
        d, a = self._current_defender(), self._current_attacker()
        ev = self._engine.expected_value(d, a) if (d and a) else float("nan")
        if st.n:
            self.run_label.setText(
                f"measured {lexicon.pct(st.rate, 1)} over {st.n} runs · predicted "
                f"{lexicon.pct(ev, 1)} · dice seed {self._engine.seed}")
        else:
            self.run_label.setText("No runs yet. Press play.")
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
            ax.annotate(f"predicted {lexicon.pct(ev, 1)}", xy=(1.0, ev),
                        xycoords=("axes fraction", "data"),
                        fontsize=10, ha="right", va="bottom", color=theme.INK)
        ax.axhline(self._inst.mc_loss_det, color=theme.STRATEGY_COLOURS["alns"],
                   linewidth=1.0, linestyle=":")
        ax.axhline(self._inst.mc_value, color=theme.STRATEGY_COLOURS["equilibrium"],
                   linewidth=1.0, linestyle=":")
        ax.annotate(f"best predictable plan {lexicon.pct(self._inst.mc_loss_det)}",
                    xy=(0.0, self._inst.mc_loss_det),
                    xycoords=("axes fraction", "data"), fontsize=9.5, va="bottom",
                    color=theme.STRATEGY_COLOURS["alns"])
        ax.annotate(f"proven optimum {lexicon.pct(self._inst.mc_value)}",
                    xy=(0.0, self._inst.mc_value),
                    xycoords=("axes fraction", "data"), fontsize=9.5, va="bottom",
                    color=theme.STRATEGY_COLOURS["equilibrium"])
        ax.set_ylim(-0.03, 1.03)
        ax.yaxis.set_major_formatter(mtick.PercentFormatter(1.0, decimals=0))
        ax.set_xlabel("run")
        self.run_chart.set_caption(
            f"dice seed {self._engine.seed} · share of missions failed", "live")
        self.run_chart.redraw()

    def export_view(self):
        return export_widget_grab(self, "playground-watch")
