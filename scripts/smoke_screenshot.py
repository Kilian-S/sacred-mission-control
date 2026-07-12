"""Scripted smoke: open the app, walk every tab (and History generations),
screenshot each state, then quit. Used at every milestone and by M5's audit.

Steps with asynchronous work carry a READY predicate: the smoke polls it
(up to a timeout) before shooting, so a screenshot can never silently capture
the pre-completion state (the old fixed 2.2 s delay produced byte-identical
before/after ZST shots).

Usage: .venv/bin/python scripts/smoke_screenshot.py [outdir]
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

from smc import theme
from smc.app import MainWindow


def main() -> int:
    outdir = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parents[1] / "screenshots"
    outdir.mkdir(parents=True, exist_ok=True)

    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    from PySide6.QtGui import QPalette, QColor
    pal = QPalette()
    pal.setColor(QPalette.Window, QColor(theme.PAGE))
    pal.setColor(QPalette.Base, QColor(theme.SURFACE))
    pal.setColor(QPalette.Text, QColor(theme.INK))
    pal.setColor(QPalette.WindowText, QColor(theme.INK))
    app.setPalette(pal)
    app.setStyleSheet(theme.build_qss())
    theme.apply_matplotlib_style()

    win = MainWindow()
    win.show()

    shots: list[tuple[str, callable]] = []
    tab_names = ["home", "playground", "objectives", "history", "documents"]
    for i, name in enumerate(tab_names):
        shots.append((name, lambda idx=i: win.tabs.setCurrentIndex(idx)))

    # a few History generations for the M1 record
    for gid in ["gen08", "gen13", "gen14", "gen16", "gen19"]:
        def go(g=gid):
            win.tabs.setCurrentIndex(3)
            win.history_tab.select_generation(g)
        shots.append((f"history-{gid}", go))

    def open_doc():
        win.tabs.setCurrentIndex(4)
        win.documents_tab.open_by_name("experiments/gen14_evidence.md")
    shots.append(("documents-ledger", open_doc))

    # M3: the duel with the gen19 policy playing against the adaptive attacker
    pg = win.playground_tab

    def duel_select():
        win.tabs.setCurrentIndex(1)
        pg.mode_combo.setCurrentIndex(1)
        d = pg.duel
        for i in range(d.def_combo.count()):
            if str(d.def_combo.itemData(i)).startswith("policy:gen19"):
                d.def_combo.setCurrentIndex(i)
                break
    shots.append(("duel-load", duel_select))

    def duel_run():
        win.tabs.setCurrentIndex(1)
        pg.duel._run_batch()
    shots.append(("duel-batch", duel_run))
    shots.append(("duel-batch2", duel_run))

    # M3: the ambush mode against the equilibrium mixture, with a placed ambush
    def ambush_mode():
        win.tabs.setCurrentIndex(1)
        pg.mode_combo.setCurrentIndex(2)
        a = pg.ambush
        for i in range(a.def_combo.count()):
            if a.def_combo.itemData(i) == "equilibrium":
                a.def_combo.setCurrentIndex(i)
                break
        if a._inst is not None and a._inst.K == 1 and a._inst.interdiction_sets:
            iset = a._inst.interdiction_sets[len(a._inst.interdiction_sets) // 2]
            uv = tuple(iset[0])
            a._edge_clicked(str(uv[0]), str(uv[-1]))
    shots.append(("ambush-placed", ambush_mode))

    # back to watch mode with a batch run for the convergence chart
    def watch_batch():
        win.tabs.setCurrentIndex(1)
        pg.mode_combo.setCurrentIndex(0)
        if pg.watch._engine is not None:
            pg.watch._run_batch()
    shots.append(("watch-batch", watch_batch))

    # M4: every objectives exhibit
    obj = win.objectives_tab
    for i in range(6):
        def go_ex(idx=i):
            win.tabs.setCurrentIndex(2)
            obj.select_exhibit(idx)
        shots.append((f"objective-{i + 1}", go_ex))

    def zst_eval():
        win.tabs.setCurrentIndex(2)
        obj.select_exhibit(5)
        obj._exhibits[5][1]._evaluate()
    shots.append(("zst-eval-start", zst_eval))
    shots.append(("zst-eval-done", lambda: None))

    def obj5_race():
        win.tabs.setCurrentIndex(2)
        obj.select_exhibit(4)
        ex = obj._exhibits[4][1]
        if hasattr(ex, "_contenders"):
            for _ in range(40):
                ex._race_tick()
    shots.append(("objective-5-race", obj5_race))

    def obj4_race():
        win.tabs.setCurrentIndex(2)
        obj.select_exhibit(3)
        obj._exhibits[3][1]._run_race()
    shots.append(("objective-4-race", obj4_race))

    shots.append(("home-final", lambda: win.tabs.setCurrentIndex(0)))

    # ready predicates: shoot only once the step's asynchronous work landed
    def _duel_loaded():
        d = win.playground_tab.duel
        return d._policy is not None or "failed" in d.run_label.text()

    def _zst_done():
        ex = obj._exhibits[5][1]
        return ex.eval_btn.isEnabled() and ("Generalist" in ex.result_label.text()
                                            or "failed" in ex.zst_label.text())

    ready = {
        "playground": lambda: win.playground_tab._inst is not None,
        "duel-load": _duel_loaded,
        "duel-batch": lambda: win.playground_tab.duel.batch_btn.isEnabled(),
        "duel-batch2": lambda: win.playground_tab.duel.batch_btn.isEnabled(),
        "watch-batch": lambda: win.playground_tab.watch.batch_btn.isEnabled(),
        "objective-3": lambda: obj._exhibits[2][1].family_state.isHidden(),
        "objective-4": lambda: hasattr(obj._exhibits[3][1], "_test_rows"),
        "objective-5": lambda: hasattr(obj._exhibits[4][1], "_contenders"),
        "objective-4-race": lambda: obj._exhibits[3][1].race_btn.isEnabled(),
        "zst-eval-done": _zst_done,
    }

    state = {"i": 0, "waited": 0.0}

    def step():
        i = state["i"]
        if i > 0:
            prev_name = shots[i - 1][0]
            win.grab().save(str(outdir / f"{i - 1:02d}-{prev_name}.png"))
        if i >= len(shots):
            print(f"Saved {len(shots)} screenshots to {outdir}")
            app.quit()
            return
        name, action = shots[i]
        action()
        state["i"] += 1
        state["waited"] = 0.0
        QTimer.singleShot(2200, lambda: settle(name))

    def settle(name: str, poll_ms: int = 250, timeout_s: float = 45.0):
        cond = ready.get(name)
        if cond is not None and not cond() and state["waited"] < timeout_s:
            state["waited"] += poll_ms / 1000.0
            QTimer.singleShot(poll_ms, lambda: settle(name))
            return
        if cond is not None and state["waited"] >= timeout_s:
            print(f"WARNING: step {name} never became ready; shooting anyway")
        step()

    QTimer.singleShot(1200, step)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
