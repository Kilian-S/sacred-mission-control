"""A three-step coach overlay: shown once per game on first open, replayable
from the "?" button (REDESIGN.md §3.2). Dismissable, stored in QSettings,
suppressed entirely when SMC_DISABLE_COACH is set (the smoke harness)."""

from __future__ import annotations

import os

from PySide6.QtCore import QEvent, QObject, QSettings, Qt
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from .. import theme

_SETTINGS = ("sacred-mission-control", "coach")


class CoachOverlay(QWidget):
    """Semi-transparent scrim over a host widget with one card of steps."""

    def __init__(self, host: QWidget, steps: list[str], on_done=None):
        super().__init__(host)
        self._host = host
        self._steps = steps
        self._i = 0
        self._on_done = on_done
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setStyleSheet("background: rgba(20, 20, 18, 130);")

        card = QFrame(self)
        card.setStyleSheet(
            f"background: {theme.SURFACE}; border-radius: 14px;")
        cl = QVBoxLayout(card)
        cl.setContentsMargins(26, 22, 26, 20)
        cl.setSpacing(12)
        self._step_label = QLabel()
        self._step_label.setProperty("fineprint", True)
        cl.addWidget(self._step_label)
        self._text = QLabel()
        self._text.setWordWrap(True)
        self._text.setStyleSheet(f"font-size: 16px; color: {theme.INK};")
        self._text.setMinimumWidth(380)
        cl.addWidget(self._text)
        btn_row = QWidget()
        bl = QHBoxLayout(btn_row)
        bl.setContentsMargins(0, 0, 0, 0)
        self._skip = QPushButton("Skip")
        # explicit inline styles: the card carries its own stylesheet, which can
        # shadow the app-level property selectors, so we do not rely on them here
        self._skip.setStyleSheet(
            f"QPushButton {{ border: none; background: transparent; color: "
            f"{theme.INK_SECONDARY}; padding: 8px 14px; font-size: 14px; }}"
            f"QPushButton:hover {{ color: {theme.INK}; }}")
        self._skip.setCursor(Qt.PointingHandCursor)
        self._skip.clicked.connect(self._finish)
        bl.addWidget(self._skip)
        bl.addStretch(1)
        self._next = QPushButton("Next")
        self._next.setStyleSheet(
            f"QPushButton {{ background: {theme.BLUE}; border: 1px solid {theme.BLUE};"
            f"color: white; font-weight: 600; border-radius: 10px; padding: 9px 22px;"
            f"font-size: 14px; }}"
            f"QPushButton:hover {{ background: #1c5cab; }}")
        self._next.setCursor(Qt.PointingHandCursor)
        self._next.clicked.connect(self._advance)
        bl.addWidget(self._next)
        cl.addWidget(btn_row)
        self._card = card

        host.installEventFilter(self)
        self._sync_geometry()
        self._render()
        self.show()
        self.raise_()

    # ------------------------------------------------------------- flow

    def _render(self) -> None:
        self._step_label.setText(f"Step {self._i + 1} of {len(self._steps)}")
        self._text.setText(self._steps[self._i])
        self._next.setText("Done" if self._i == len(self._steps) - 1 else "Next")
        self._card.adjustSize()
        self._centre_card()

    def _advance(self) -> None:
        if self._i >= len(self._steps) - 1:
            self._finish()
            return
        self._i += 1
        self._render()

    def _finish(self) -> None:
        try:
            self._host.removeEventFilter(self)
        except RuntimeError:
            pass
        if self._on_done:
            self._on_done()
        self.deleteLater()

    def dismiss(self) -> None:
        """Hide immediately without marking the step seen (used when the host
        switches context, e.g. the Playground changes mode)."""
        try:
            self._host.removeEventFilter(self)
        except RuntimeError:
            pass
        self.deleteLater()

    def mousePressEvent(self, event) -> None:
        # clicking the scrim outside the card dismisses
        if not self._card.geometry().contains(event.position().toPoint()):
            self._finish()

    # ------------------------------------------------------------- geometry

    def _sync_geometry(self) -> None:
        self.setGeometry(self._host.rect())
        self._centre_card()

    def _centre_card(self) -> None:
        cs = self._card.sizeHint()
        self._card.move((self.width() - cs.width()) // 2,
                        (self.height() - cs.height()) // 2)

    def eventFilter(self, obj: QObject, event: QEvent) -> bool:
        if obj is self._host and event.type() == QEvent.Resize:
            self._sync_geometry()
        return False

    # ------------------------------------------------------------- entry point

    @staticmethod
    def maybe_show(host: QWidget, key: str, steps: list[str],
                   force: bool = False) -> "CoachOverlay | None":
        """Show once per key (QSettings), or always with force=True. Returns
        the overlay or None. Suppressed by SMC_DISABLE_COACH (smoke runs)."""
        if os.environ.get("SMC_DISABLE_COACH"):
            return None
        settings = QSettings(*_SETTINGS)
        flag = f"seen/{key}"
        if not force and settings.value(flag, False, type=bool):
            return None
        settings.setValue(flag, True)
        return CoachOverlay(host, steps)
