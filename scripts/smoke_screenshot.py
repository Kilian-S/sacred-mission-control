"""Scripted smoke: open the app, walk every tab (and History generations),
screenshot each state, then quit. Used at every milestone and by M5's audit.

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

    state = {"i": 0}

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
        QTimer.singleShot(2200, step)

    QTimer.singleShot(1200, step)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
