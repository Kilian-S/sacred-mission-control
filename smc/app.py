"""SACRED Mission Control: application entry point and main window."""

from __future__ import annotations

import argparse
import sys

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QAction, QKeySequence, QPalette, QColor, QShortcut
from PySide6.QtWidgets import (
    QApplication,
    QLabel,
    QMainWindow,
    QTabWidget,
    QWidget,
)

from . import theme
from .widgets.cards import StateLabel
from .widgets.export import Exportable


class PlaceholderTab(StateLabel):
    """A tab that has not been built yet; states its milestone honestly."""

    def __init__(self, name: str, milestone: str):
        super().__init__(f"{name} arrives with milestone {milestone}.", "empty")


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("SACRED Mission Control")
        self.resize(1360, 880)

        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)
        self.setCentralWidget(self.tabs)

        # Tabs are built lazily where heavy; Documents/History are cheap (text).
        from .tabs.documents import DocumentsTab
        from .tabs.history import HistoryTab

        self.home_tab = self._make_home()
        self.playground_tab = self._make_playground()
        self.objectives_tab = self._make_objectives()
        self.history_tab = HistoryTab()
        self.documents_tab = DocumentsTab()

        self.tabs.addTab(self.home_tab, "Home")
        self.tabs.addTab(self.playground_tab, "Playground")
        self.tabs.addTab(self.objectives_tab, "Objectives")
        self.tabs.addTab(self.history_tab, "History")
        self.tabs.addTab(self.documents_tab, "Documents")

        self.history_tab.open_ledger.connect(self._open_ledger)
        if hasattr(self.home_tab, "go_to"):
            self.home_tab.go_to.connect(self.tabs.setCurrentIndex)

        # Qt on macOS maps "Ctrl" to the Command key ("Meta" would be Control).
        for i in range(5):
            QShortcut(QKeySequence(f"Ctrl+{i + 1}"), self,
                      activated=lambda idx=i: self.tabs.setCurrentIndex(idx))
        QShortcut(QKeySequence("Ctrl+E"), self, activated=self._export_current)

        self.statusBar().showMessage("Ready")

    # ------------------------------------------------------------- tab factories

    def _make_home(self) -> QWidget:
        try:
            from .tabs.home import HomeTab
            return HomeTab()
        except ImportError:
            return PlaceholderTab("Home", "M4")

    def _make_playground(self) -> QWidget:
        try:
            from .tabs.playground import PlaygroundTab
            return PlaygroundTab()
        except ImportError:
            return PlaceholderTab("The Playground", "M2")

    def _make_objectives(self) -> QWidget:
        try:
            from .tabs.objectives import ObjectivesTab
            return ObjectivesTab()
        except ImportError:
            return PlaceholderTab("Objectives", "M4")

    # ------------------------------------------------------------- actions

    def _open_ledger(self, relative: str, scroll_to: str) -> None:
        self.tabs.setCurrentWidget(self.documents_tab)
        self.documents_tab.open_by_name(relative, scroll_to=scroll_to)

    def _export_current(self) -> None:
        w = self.tabs.currentWidget()
        if not isinstance(w, Exportable):
            self.statusBar().showMessage("This view does not export yet.", 4000)
            return
        try:
            paths = list(w.export_view())
            # every visible chart also exports as publication-quality PNG + SVG
            from .widgets.charts import ChartWidget
            from .widgets.export import export_figure
            for chart in w.findChildren(ChartWidget):
                if chart.isVisible() and chart.figure.axes:
                    paths += export_figure(chart.figure, chart.export_name)
        except Exception as exc:
            self.statusBar().showMessage(f"Export failed: {exc}", 6000)
            return
        if paths:
            self.statusBar().showMessage(
                f"Exported {len(paths)} files to {paths[0].parent}", 8000)


def main() -> int:
    parser = argparse.ArgumentParser(description="SACRED Mission Control")
    parser.add_argument("--tab", type=int, default=None, help="open on tab 1-5")
    parser.add_argument("--screenshot", type=str, default=None,
                        help="grab a screenshot to PATH shortly after start, then quit")
    args = parser.parse_args()

    app = QApplication(sys.argv)
    app.setApplicationName("SACRED Mission Control")
    app.setStyle("Fusion")  # keep light mode regardless of macOS appearance

    pal = QPalette()
    pal.setColor(QPalette.Window, QColor(theme.PAGE))
    pal.setColor(QPalette.Base, QColor(theme.SURFACE))
    pal.setColor(QPalette.Text, QColor(theme.INK))
    pal.setColor(QPalette.WindowText, QColor(theme.INK))
    pal.setColor(QPalette.Button, QColor(theme.SURFACE))
    pal.setColor(QPalette.ButtonText, QColor(theme.INK))
    pal.setColor(QPalette.Highlight, QColor(theme.SELECTION_BG))
    pal.setColor(QPalette.HighlightedText, QColor(theme.INK))
    pal.setColor(QPalette.PlaceholderText, QColor(theme.INK_MUTED))
    pal.setColor(QPalette.ToolTipBase, QColor(theme.INK))
    pal.setColor(QPalette.ToolTipText, QColor(theme.SURFACE))
    app.setPalette(pal)
    app.setStyleSheet(theme.build_qss())
    theme.apply_matplotlib_style()

    win = MainWindow()
    if args.tab and 1 <= args.tab <= 5:
        win.tabs.setCurrentIndex(args.tab - 1)
    win.show()

    if args.screenshot:
        def grab():
            win.grab().save(args.screenshot)
            app.quit()
        QTimer.singleShot(2500, grab)

    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
