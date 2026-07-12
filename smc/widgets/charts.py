"""Matplotlib canvases embedded in Qt, with provenance captions and free export."""

from __future__ import annotations

from pathlib import Path

from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from .. import theme
from .export import Exportable, export_figure


class ChartWidget(QWidget, Exportable):
    """A single matplotlib figure with an optional provenance caption below.

    Provenance rule (brief §4): ledger numbers carry a grey "ledger:" caption;
    live-computed numbers carry the accented "computed live" caption. Charts
    built from run JSONs cite the run file; charts of live solves cite the seed.
    """

    def __init__(
        self,
        title: str = "",
        caption: str = "",
        caption_kind: str = "ledger",  # ledger | live | none
        height: float = 3.0,
        width: float = 5.0,
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self.export_name = title or "chart"
        self.figure = Figure(figsize=(width, height), layout="constrained")
        self.canvas = FigureCanvasQTAgg(self.figure)
        self.canvas.setStyleSheet(f"background: {theme.SURFACE};")

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(2)
        lay.addWidget(self.canvas)

        self._caption = QLabel()
        self._caption.setProperty("caption", True)
        self._caption.setWordWrap(True)
        self._caption.setTextInteractionFlags(Qt.TextSelectableByMouse)
        lay.addWidget(self._caption)
        self.set_caption(caption, caption_kind)

    def set_caption(self, caption: str, kind: str = "ledger") -> None:
        if not caption:
            self._caption.hide()
            return
        if kind == "live":
            self._caption.setText(f"computed live · {caption}")
            self._caption.setStyleSheet(
                f"color: {theme.LIVE_ACCENT}; font-size: 13px; font-weight: 600;"
            )
        else:
            self._caption.setText(caption)
            self._caption.setStyleSheet(f"color: {theme.INK_MUTED}; font-size: 13px;")
        self._caption.show()

    def axes(self):
        if not self.figure.axes:
            return self.figure.add_subplot(111)
        return self.figure.axes[0]

    def clear(self):
        self.figure.clear()
        return self.figure.add_subplot(111)

    def redraw(self) -> None:
        self.canvas.draw_idle()

    def export_view(self) -> list[Path]:
        return export_figure(self.figure, self.export_name)
