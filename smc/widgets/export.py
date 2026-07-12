"""Cmd+E export: every view saves itself to ~/Desktop/sacred-mc-exports/.

Matplotlib canvases export true PNG+SVG at publication quality; any other
widget falls back to a high-resolution pixmap grab (PNG only).
"""

from __future__ import annotations

import datetime
import re
from pathlib import Path

from PySide6.QtWidgets import QWidget

from ..sacred_bridge.paths import EXPORT_DIR


def _slug(text: str) -> str:
    s = re.sub(r"[^A-Za-z0-9]+", "-", text).strip("-").lower()
    return s or "view"


def export_paths(name: str) -> tuple[Path, Path]:
    EXPORT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    base = EXPORT_DIR / f"{_slug(name)}-{stamp}"
    return base.with_suffix(".png"), base.with_suffix(".svg")


def export_figure(figure, name: str) -> list[Path]:
    png, svg = export_paths(name)
    figure.savefig(png, dpi=300, bbox_inches="tight")
    figure.savefig(svg, bbox_inches="tight")
    return [png, svg]


def export_widget_grab(widget: QWidget, name: str) -> list[Path]:
    png, _ = export_paths(name)
    pixmap = widget.grab()
    ratio = widget.devicePixelRatioF()
    if ratio:
        pixmap.setDevicePixelRatio(1.0)  # save at native resolution
    pixmap.save(str(png))
    return [png]


def export_view_vector(view, name: str) -> list[Path]:
    """A QGraphicsView (the map) as a true vector SVG plus a 3x PNG, at the
    current composition (what the user sees, including the scale bar)."""
    from PySide6.QtCore import QRectF, QSize
    from PySide6.QtGui import QColor, QImage, QPainter
    from PySide6.QtSvg import QSvgGenerator

    from .. import theme

    png, svg = export_paths(name)
    w, h = view.viewport().width(), view.viewport().height()
    gen = QSvgGenerator()
    gen.setFileName(str(svg))
    gen.setSize(QSize(w, h))
    gen.setViewBox(QRectF(0, 0, w, h))
    gen.setTitle(name)
    painter = QPainter(gen)
    view.render(painter)
    painter.end()

    img = QImage(w * 3, h * 3, QImage.Format_ARGB32)
    img.fill(QColor(theme.SURFACE))
    painter = QPainter(img)
    painter.setRenderHint(QPainter.Antialiasing)
    painter.scale(3, 3)
    view.render(painter)
    painter.end()
    img.save(str(png))
    return [png, svg]


class Exportable:
    """Mixin: widgets that know how to export themselves override export_view."""

    export_name: str = "view"

    def export_view(self) -> list[Path]:
        assert isinstance(self, QWidget)
        return export_widget_grab(self, self.export_name)
