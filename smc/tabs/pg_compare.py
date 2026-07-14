"""Playground mode 4: COMPARE. The same instance, up to four protagonists side
by side as synchronised small multiples: SACRED, the Block A control actors,
and the oracle-level arms, each flying the same sortie index against its own
best-response interdictor, with one shared convergence chart.

Identity is carried three ways at once (panel position, header label + colour
chip, mixture colour); overlaying mixtures on one map would be illegible since
the routes share edges, hence small multiples."""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMenu,
    QPushButton,
    QStackedLayout,
    QVBoxLayout,
    QWidget,
)

from .. import theme
from ..game.sortie import AttackerSpec, DefenderSpec, SortieEngine, SortieOutcome
from ..sacred_bridge import oracle as oracle_bridge
from ..sacred_bridge import policies
from ..widgets.cards import StateLabel
from ..widgets.charts import ChartWidget
from ..widgets.export import Exportable, export_widget_grab
from ..widgets.mapview import MapView
from ..workers import run_in_background

# The master contender list: (key, lexicon key for the display name,
# STRATEGY_COLOURS key). Colour follows the entity across the whole app; the
# list position doubles as the per-arm seed offset so each arm's sortie stream
# is independent and reproducible from the base seed.
from .. import lexicon  # noqa: E402  (grouped with the other first-party imports)

_CONTENDERS: list[tuple[str, str, str]] = [
    ("equilibrium", lexicon.strategy_name("equilibrium"), "equilibrium"),
    ("shortest", lexicon.strategy_name("shortest"), "shortest_path"),
    ("uniform", lexicon.strategy_name("uniform"), "uniform"),
    ("alns", lexicon.strategy_name("alns"), "alns"),
    ("sacred", lexicon.strategy_name("sacred"), "sacred"),
    ("distill", lexicon.strategy_name("distill"), "distill"),
    ("dr", lexicon.strategy_name("dr"), "dr"),
    ("vanilla", lexicon.strategy_name("vanilla"), "vanilla"),
    ("random", lexicon.strategy_name("random_init"), "random_init"),
]
_BLURBS = {
    "equilibrium": lexicon.strategy_blurb("equilibrium"),
    "shortest": lexicon.strategy_blurb("shortest"),
    "uniform": lexicon.strategy_blurb("uniform"),
    "alns": lexicon.strategy_blurb("alns"),
    "sacred": lexicon.strategy_blurb("sacred"),
    "distill": "needs the maths answer key for every training map",
    "dr": lexicon.strategy_blurb("dr"),
    "vanilla": lexicon.strategy_blurb("vanilla"),
    "random": lexicon.strategy_blurb("random_init"),
}
_DEFAULT_TICKED = ("equilibrium", "sacred", "distill", "dr")
_MAX_PANELS = 4


@dataclass
class ArmState:
    key: str
    label: str
    colour: str
    seed: int
    spec: DefenderSpec | None = None
    attacker: AttackerSpec | None = None
    engine: SortieEngine | None = None
    status: str = "loading"          # loading | ready | unavailable
    detail: str = ""
    outcome: SortieOutcome | None = None
    dots: list = field(default_factory=list)
    flashed: list = field(default_factory=list)


class _ArmPanel(QWidget):
    """One small-multiple: colour chip + label + live value + map (or an
    honest unavailability note)."""

    def __init__(self, arm: ArmState, parent=None):
        super().__init__(parent)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(2)

        head = QWidget()
        hl = QHBoxLayout(head)
        hl.setContentsMargins(2, 0, 2, 0)
        hl.setSpacing(6)
        chip = QLabel()
        chip.setFixedSize(14, 14)
        chip.setStyleSheet(f"background: {arm.colour}; border-radius: 3px;")
        hl.addWidget(chip)
        name = QLabel(arm.label)
        name.setStyleSheet("font-weight: 600; font-size: 13px;")
        name.setWordWrap(True)
        hl.addWidget(name, 1)
        self.value = QLabel("…")
        self.value.setStyleSheet(
            f"color: {theme.INK}; font-size: 19px; font-weight: 700;")
        self.value.setToolTip("chance the mission fails, against an enemy who has "
                              "learned this strategy's habits (computed live)")
        hl.addWidget(self.value)
        self.run_line = QLabel("")
        self.run_line.setStyleSheet(
            f"color: {theme.LIVE_ACCENT}; font-size: 11px; font-weight: 600;")
        hl.addWidget(self.run_line)
        lay.addWidget(head)

        self.body = QStackedLayout()
        self.map = MapView()
        self.map.setMinimumHeight(250)
        holder = QWidget()
        holder.setLayout(self.body)
        map_host = QWidget()
        mh = QVBoxLayout(map_host)
        mh.setContentsMargins(0, 0, 0, 0)
        mh.addWidget(self.map)
        self.body.addWidget(map_host)
        self.state = StateLabel("Loading…", "loading")
        self.body.addWidget(self.state)
        lay.addWidget(holder, 1)

    def show_map(self) -> None:
        self.body.setCurrentIndex(0)

    def show_state(self, text: str, kind: str = "empty") -> None:
        self.state.setText(text)
        self.body.setCurrentIndex(1)


class ComparePanel(QWidget, Exportable):
    export_name = "playground-compare"

    def __init__(self, parent=None):
        super().__init__(parent)
        self._inst: oracle_bridge.OracleInstance | None = None
        self._arms: dict[str, ArmState] = {}
        self._panels: dict[str, _ArmPanel] = {}
        self._ticked: list[str] = list(_DEFAULT_TICKED)
        self._actor_refs = policies.discover_actors()
        self._alns_assignment: list[int] | None = None
        self._playing = False
        self._anim_frac = 0.0
        self._sortie_live = False
        self.seed = 0

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(6)

        bar = QWidget()
        bl = QHBoxLayout(bar)
        bl.setContentsMargins(0, 0, 0, 0)
        bl.setSpacing(8)
        self.contenders_btn = QPushButton("Contenders…")
        self.contenders_btn.setToolTip("Pick 2-4 protagonists to race on this instance")
        self._menu = QMenu(self)
        self._menu_actions: dict[str, QAction] = {}
        for key, label, _colour in _CONTENDERS:
            act = QAction(label, self._menu)
            act.setCheckable(True)
            act.setChecked(key in self._ticked)
            act.setToolTip(_BLURBS.get(key, ""))
            act.toggled.connect(lambda on, k=key: self._contender_toggled(k, on))
            self._menu.addAction(act)
            self._menu_actions[key] = act
        self._menu.setToolTipsVisible(True)
        self.contenders_btn.setMenu(self._menu)
        bl.addWidget(self.contenders_btn)
        self.status = QLabel("")
        self.status.setWordWrap(True)
        self.status.setStyleSheet(f"color: {theme.INK_MUTED}; font-size: 12px;")
        bl.addWidget(self.status, 1)
        self.play_btn = QPushButton("▶ Race (Space)")
        self.play_btn.setProperty("accent", True)
        self.play_btn.clicked.connect(self.toggle_play)
        bl.addWidget(self.play_btn)
        self.batch_btn = QPushButton("Run 300 instantly")
        self.batch_btn.clicked.connect(self._run_batch)
        bl.addWidget(self.batch_btn)
        lay.addWidget(bar)

        self.grid_host = QWidget()
        self.grid = QGridLayout(self.grid_host)
        self.grid.setContentsMargins(0, 0, 0, 0)
        self.grid.setSpacing(8)
        lay.addWidget(self.grid_host, 3)

        self.chart = ChartWidget(title="compare-convergence", height=2.6, width=9.0)
        lay.addWidget(self.chart, 1)

        self._timer = QTimer(self)
        self._timer.setInterval(33)
        self._timer.timeout.connect(self._tick)

    # ------------------------------------------------------------- contenders

    def set_contenders(self, keys: list[str]) -> None:
        """Programmatic contender selection (used by the Objectives tab).
        Accepts arm keys or their STRATEGY_COLOURS aliases; caps at 4. The
        arms rebuild on the next set_instance."""
        aliases = {"random_init": "random", "shortest_path": "shortest",
                   "uniform_stack": "uniform"}
        wanted = []
        valid = {c[0] for c in _CONTENDERS}
        for k in keys:
            k = aliases.get(k, k)
            if k in valid and k not in wanted:
                wanted.append(k)
        if len(wanted) < 2:
            return
        self._ticked = wanted[:_MAX_PANELS]
        full = len(self._ticked) >= _MAX_PANELS
        for k, act in self._menu_actions.items():
            act.blockSignals(True)
            act.setChecked(k in self._ticked)
            act.setEnabled(k in self._ticked or not full)
            act.blockSignals(False)
        if self._inst is not None:
            self._rebuild_arms()

    def _contender_toggled(self, key: str, on: bool) -> None:
        if on and key not in self._ticked:
            self._ticked.append(key)
        if not on and key in self._ticked:
            self._ticked.remove(key)
        full = len(self._ticked) >= _MAX_PANELS
        for k, act in self._menu_actions.items():
            if not act.isChecked():
                act.setEnabled(not full)
        if self._inst is not None:
            self._rebuild_arms()

    # ------------------------------------------------------------- instance

    def set_instance(self, inst: oracle_bridge.OracleInstance, preset: dict | None,
                     seed: int) -> None:
        self.stop_play()
        self._inst = inst
        self.seed = seed
        self._alns_assignment = None
        self._rebuild_arms()

    def set_seed(self, seed: int) -> None:
        self.seed = seed
        if self._inst is not None:
            self._rebuild_arms()

    def reset_stats(self) -> None:
        for arm in self._arms.values():
            if arm.engine is not None:
                arm.engine.reset_stats()
        self._update_values()
        self._redraw_chart()

    # ------------------------------------------------------------- arms

    def _seed_of(self, key: str) -> int:
        offset = next(i for i, (k, _l, _c) in enumerate(_CONTENDERS) if k == key)
        return self.seed + offset

    def _rebuild_arms(self) -> None:
        assert self._inst is not None
        inst = self._inst
        self.stop_play()
        self._arms = {}
        # clear the grid
        while self.grid.count():
            it = self.grid.takeAt(0)
            w = it.widget()
            if w:
                w.deleteLater()
        self._panels = {}

        ticked = [k for k in self._ticked if k in {c[0] for c in _CONTENDERS}][:_MAX_PANELS]
        base_engine = SortieEngine(inst, seed=0)
        oracle_specs = {d.key: d for d in base_engine.defender_specs()}

        for i, key in enumerate(ticked):
            label = next(l for k, l, _c in _CONTENDERS if k == key)
            colour = theme.STRATEGY_COLOURS[next(c for k, _l, c in _CONTENDERS if k == key)]
            arm = ArmState(key=key, label=label, colour=colour, seed=self._seed_of(key))
            arm.engine = SortieEngine(inst, seed=arm.seed)
            self._arms[key] = arm
            panel = _ArmPanel(arm)
            self._panels[key] = panel
            self.grid.addWidget(panel, i // 2, i % 2)
            panel.map.set_city(inst.city_map)
            panel.map.show_instance(inst.routes, inst.edge_vuln, inst.s, inst.t)
            self._resolve_arm(arm, oracle_specs)
        self._update_status()
        self._redraw_chart()
        # the maps were fitted before the grid gave the panels their real
        # sizes; re-fit once the layout has settled
        QTimer.singleShot(120, self._refit_maps)

    def _refit_maps(self) -> None:
        for panel in self._panels.values():
            panel.map.fit_routes()

    def _resolve_arm(self, arm: ArmState, oracle_specs: dict) -> None:
        inst = self._inst
        key = arm.key
        if key in ("equilibrium", "shortest"):
            spec = oracle_specs["equilibrium" if key == "equilibrium" else "shortest"]
            self._arm_ready(arm, spec)
        elif key == "uniform":
            self._arm_ready(arm, oracle_specs["uniform_stack"])
        elif key == "alns":
            self._panels[key].show_state("ALNS running…", "loading")
            run_in_background(
                oracle_bridge.alns_plan, inst,
                on_done=lambda res, started_on=inst: self._alns_ready(res, started_on),
                on_fail=lambda tb: self._arm_unavailable("alns", "ALNS failed to run"),
            )
        elif key == "random":
            self._panels[key].show_state("Building the untrained reference…", "loading")
            run_in_background(
                self._random_worker, inst,
                on_done=lambda occ, started_on=inst: self._dist_ready("random", occ, started_on),
                on_fail=lambda tb: self._arm_unavailable(
                    "random", "random-init net needs the sacred env (soft band only)"),
            )
        else:  # trained arms
            ref = self._trained_ref(key)
            if inst.band is None:
                self._arm_unavailable(key, "needs a soft threat band (trained actors observe "
                                           "the vulnerability column)")
                return
            if ref is None:
                self._arm_unavailable(key, "checkpoints not on disk")
                return
            self._panels[key].show_state(f"Loading {ref.key}…", "loading")
            run_in_background(
                self._policy_worker, ref, inst,
                on_done=lambda occ, k=key, started_on=inst: self._dist_ready(k, occ, started_on),
                on_fail=lambda tb, k=key: self._arm_unavailable(
                    k, "policy failed to load: " + tb.strip().splitlines()[-1][:80]),
            )

    def _trained_ref(self, key: str) -> policies.ActorRef | None:
        inst = self._inst
        by_key = {r.key: r for r in self._actor_refs}
        if key == "sacred":
            trained_cell = (inst.city, inst.s, inst.t, inst.N, inst.K) == \
                ("kaliningrad", "35", "159", 3, 1) and inst.band == (0.15, 0.95) \
                and inst.k_extra == 8
            if trained_cell and "gen14_seed0" in by_key:
                return by_key["gen14_seed0"]
            return by_key.get("gen16_seed0")
        if key == "distill":
            return by_key.get("gen24_seed0")
        if key == "dr":
            return by_key.get("gen25_dr_seed0")
        if key == "vanilla":
            return by_key.get("gen21_seed0")
        return None

    @staticmethod
    def _policy_worker(ref: policies.ActorRef, inst) -> np.ndarray:
        pol = policies.load_policy(ref, inst)
        return inst.route_dist_to_stacked_occ_dist(pol.route_distribution())

    @staticmethod
    def _random_worker(inst) -> np.ndarray:
        d = policies.random_init_distribution(inst, seed=0)
        return inst.route_dist_to_stacked_occ_dist(d)

    def _alns_ready(self, result, started_on) -> None:
        if started_on is not self._inst or "alns" not in self._arms:
            return  # stale: the instance or contender set changed meanwhile
        assignment, _expl = result
        self._alns_assignment = assignment
        arm = self._arms["alns"]
        assert arm.engine is not None
        self._arm_ready(arm, arm.engine.alns_spec(assignment))

    def _dist_ready(self, key: str, occ: np.ndarray, started_on) -> None:
        if started_on is not self._inst or key not in self._arms:
            return  # stale
        arm = self._arms[key]
        spec = DefenderSpec(key, arm.label, occ)
        self._arm_ready(arm, spec)

    def _arm_unavailable(self, key: str, detail: str) -> None:
        if key not in self._arms:
            return
        arm = self._arms[key]
        arm.status = "unavailable"
        arm.detail = detail
        self._panels[key].show_state(f"Not available here: {detail}", "empty")
        self._panels[key].value.setText("—")
        self._update_status()

    def _arm_ready(self, arm: ArmState, spec: DefenderSpec) -> None:
        assert arm.engine is not None and self._inst is not None
        arm.spec = spec
        arm.attacker = arm.engine.attacker_specs(spec)[0]  # its own oracle BR
        arm.status = "ready"
        panel = self._panels[arm.key]
        panel.show_map()
        marg = spec.route_dist if spec.route_dist is not None \
            else arm.engine._stacked_route_marginal(spec.occ_dist)
        panel.map.set_route_mixture(list(marg), arm.colour)
        self._update_values()
        self._update_status()
        self._redraw_chart()

    def _ready_arms(self) -> list[ArmState]:
        return [a for a in self._arms.values() if a.status == "ready"]

    def _update_status(self) -> None:
        n_ready = len(self._ready_arms())
        n_loading = sum(1 for a in self._arms.values() if a.status == "loading")
        seeds = ", ".join(f"{a.key} {a.seed}" for a in self._arms.values())
        txt = f"{n_ready}/{len(self._arms)} contenders ready · seeds: {seeds}"
        if n_loading:
            txt += f" · {n_loading} loading…"
        self.status.setText(txt)

    # ------------------------------------------------------------- sortie loop

    def toggle_play(self) -> None:
        if self._playing:
            self.stop_play()
            return
        if len(self._ready_arms()) < 2:
            self.status.setText("Waiting for at least two ready contenders…")
            return
        self._playing = True
        self.play_btn.setText("⏸ Pause (Space)")
        self._begin_sortie()
        self._timer.start()

    def stop_play(self) -> None:
        self._playing = False
        self._timer.stop()
        self.play_btn.setText("▶ Race (Space)")

    def _begin_sortie(self) -> None:
        if self._inst is None:
            return
        self._anim_frac = 0.0
        self._sortie_live = True
        for arm in self._ready_arms():
            assert arm.engine is not None and arm.spec is not None and arm.attacker is not None
            arm.outcome = arm.engine.play_sortie(arm.spec, arm.attacker)
            panel = self._panels[arm.key]
            panel.map.clear_convoys()
            panel.map.show_ambush(arm.outcome.iset_edges, revealed=False)
            arm.dots = [panel.map.add_convoy(arm.colour) for _ in arm.outcome.routes]
            arm.flashed = [False] * len(arm.outcome.routes)

    def _tick(self) -> None:
        if not self._sortie_live:
            return
        self._anim_frac += 0.014
        done = self._anim_frac >= 1.0
        frac = min(1.0, self._anim_frac)
        for arm in self._ready_arms():
            if arm.outcome is None:
                continue
            panel = self._panels[arm.key]
            for ci, (r, dot) in enumerate(zip(arm.outcome.routes, arm.dots)):
                caught_e = arm.outcome.caught_edge[ci]
                stop_frac = 1.0
                if caught_e is not None:
                    fe = panel.map.fraction_of_edge(r, caught_e)
                    stop_frac = fe if fe is not None else self._edge_frac(r, caught_e)
                f = min(frac, stop_frac)
                panel.map.place_on_route(dot, r, f)
                if caught_e is not None and frac >= stop_frac and not arm.flashed[ci]:
                    arm.flashed[ci] = True
                    panel.map.flash(dot)
                    panel.map.mark_lost(dot)
        if done:
            self._sortie_live = False
            for arm in self._ready_arms():
                self._panels[arm.key].map.reveal_ambush()
                if arm.outcome is not None and not arm.outcome.mission_failed \
                        and arm.dots:
                    self._panels[arm.key].map.celebrate(arm.dots[-1])
                arm.outcome = None
            self._update_values()
            self._redraw_chart()
            if self._playing:
                QTimer.singleShot(350, self._maybe_next)

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
        arms = self._ready_arms()
        if len(arms) < 2:
            self.status.setText("Waiting for at least two ready contenders…")
            return
        self.stop_play()
        self.batch_btn.setEnabled(False)
        self.play_btn.setEnabled(False)
        inst = self._inst

        def batch():
            for arm in arms:
                for _ in range(300):
                    arm.engine.play_sortie(arm.spec, arm.attacker)
            return inst

        run_in_background(
            batch,
            on_done=lambda started_on: self._batch_done(started_on),
            on_fail=lambda tb: self._batch_done(None),
        )

    def _batch_done(self, started_on) -> None:
        self.batch_btn.setEnabled(True)
        self.play_btn.setEnabled(True)
        if started_on is not self._inst:
            return  # instance changed mid-batch; discard
        for arm in self._ready_arms():
            self._panels[arm.key].map.clear_convoys()
            self._panels[arm.key].map.clear_ambush()
        self._update_values()
        self._redraw_chart()

    # ------------------------------------------------------------- readouts

    def _update_values(self) -> None:
        from .. import lexicon
        for arm in self._ready_arms():
            assert arm.engine is not None and arm.spec is not None and arm.attacker is not None
            exact = arm.engine.expected_value(arm.spec, arm.attacker)
            st = arm.engine.stats
            self._panels[arm.key].value.setText(lexicon.pct(exact))
            self._panels[arm.key].run_line.setText(
                f"measured {lexicon.pct(st.rate)} over {st.n}" if st.n else "")

    def _redraw_chart(self) -> None:
        if self._inst is None:
            return
        ax = self.chart.clear()
        any_hist = False
        for arm in self._ready_arms():
            assert arm.engine is not None
            st = arm.engine.stats
            if st.history:
                any_hist = True
                ax.plot(range(1, len(st.history) + 1), st.history,
                        color=arm.colour, linewidth=1.8)
            exact = arm.engine.expected_value(arm.spec, arm.attacker)
            ax.axhline(exact, color=arm.colour, linewidth=1.0, linestyle=":", alpha=0.9)
            ax.annotate(f"{arm.label} {lexicon.pct(exact)}", xy=(1.0, exact),
                        xycoords=("axes fraction", "data"), fontsize=9.5, ha="right",
                        va="bottom", color=arm.colour)
        top = max((self._inst.mc_loss_det, 0.3,
                   *(a.engine.expected_value(a.spec, a.attacker)
                     for a in self._ready_arms())), default=1.0)
        ax.set_ylim(-0.03, min(1.03, top + 0.12))
        ax.set_xlabel("run")
        ax.set_ylabel(self._ylabel())
        seeds = ", ".join(f"{a.key} {a.seed}" for a in self._ready_arms())
        self.chart.set_caption(
            "same instance, each arm against its own best-response "
            f"interdictor · seeds: {seeds}" if seeds else "pick contenders above", "live")
        if not any_hist and self._ready_arms():
            ax.annotate("press Play or Run 300 to race", xy=(0.5, 0.5),
                        xycoords="axes fraction", ha="center", fontsize=11,
                        color=theme.INK_MUTED)
        self.chart.redraw()

    def _objective_word(self) -> str:
        if self._inst is None or self._inst.objective == "mission":
            return "mission-failure"
        if self._inst.objective == "linear":
            return "expected-fraction-lost"
        return f"P(≥{self._inst.threshold_m} lost)"

    def _ylabel(self) -> str:
        if self._inst is None or self._inst.objective == "mission":
            return "share of missions that failed"
        if self._inst.objective == "linear":
            return "average share of convoys lost"
        return f"share losing {self._inst.threshold_m}+ convoys"

    # ------------------------------------------------------------- export

    def export_view(self):
        return export_widget_grab(self, "playground-compare")
