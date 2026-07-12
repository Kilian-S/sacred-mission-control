"""Shared building blocks: cards, era badges, provenance-captioned numbers,
empty/loading/error states."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from .. import theme


class Card(QFrame):
    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setProperty("card", True)
        self._lay = QVBoxLayout(self)
        self._lay.setContentsMargins(16, 14, 16, 14)
        self._lay.setSpacing(8)

    def layout_(self) -> QVBoxLayout:
        return self._lay


class EraBadge(QLabel):
    STYLES = {
        "pre-fix": (theme.ERA_PREFIX_BG, theme.ERA_PREFIX_FG, "PRE-FIX ERA"),
        "post-fix": (theme.ERA_POSTFIX_BG, theme.ERA_POSTFIX_FG, "POST-FIX"),
        "campaign": ("#e4e2f2", "#3d3580", "CAMPAIGN ERA"),
    }

    def __init__(self, era: str, parent: QWidget | None = None):
        bg, fg, text = self.STYLES.get(era, ("#eee", "#333", era.upper()))
        super().__init__(text, parent)
        self.setStyleSheet(
            f"background: {bg}; color: {fg}; border-radius: 4px; padding: 2px 8px;"
            "font-size: 12px; font-weight: 700; letter-spacing: 0.06em;"
        )
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.setToolTip(
            "The 2026-07-09 node-ordering fix divides results into eras; "
            "the two are never mixed in one visual."
        )


class StatusPill(QLabel):
    """Verdict token (PASS / FAIL / LOCKED / ...)."""

    GOOD = {"PASS", "PASS_STRONG", "LOCKED", "LOCK_PASSED", "MET", "CLOSED", "CURVES_BANKED", "DONE", "CORE_DONE"}
    BAD = {"FAIL", "GATE_FAIL", "REVERSED", "NOT_MET", "NO_TRANSFER", "NO_PASS", "NULL", "RETRACTED", "DIVERGED_THEN_FLAT"}

    def __init__(self, status: str, parent: QWidget | None = None):
        text = status.replace("_", " ")
        super().__init__(text, parent)
        if status in self.GOOD:
            bg, fg = "#d9e9dc", "#1d5c2e"
        elif status in self.BAD:
            bg, fg = "#f6dfdc", "#8c2a22"
        else:
            bg, fg = "#e9e8e2", theme.INK_SECONDARY
        self.setStyleSheet(
            f"background: {bg}; color: {fg}; border-radius: 4px; padding: 2px 8px;"
            "font-size: 12px; font-weight: 700; letter-spacing: 0.04em;"
        )
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)


class ProvenancedNumber(QWidget):
    """A headline number that cannot exist without its provenance caption."""

    def __init__(
        self,
        value: str,
        label: str,
        provenance: str,
        kind: str = "ledger",  # ledger | live
        big: bool = True,
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(1)

        v = QLabel(value)
        v.setStyleSheet(
            f"font-size: {28 if big else 20}px; font-weight: 700; color: {theme.INK};"
        )
        v.setTextInteractionFlags(Qt.TextSelectableByMouse)
        lab = QLabel(label)
        lab.setStyleSheet(f"font-size: 14px; color: {theme.INK_SECONDARY};")
        lab.setWordWrap(True)

        prov = QLabel(
            f"computed live · {provenance}" if kind == "live" else provenance
        )
        prov.setWordWrap(True)
        prov.setTextInteractionFlags(Qt.TextSelectableByMouse)
        if kind == "live":
            prov.setStyleSheet(
                f"font-size: 12px; color: {theme.LIVE_ACCENT}; font-weight: 600;"
            )
        else:
            prov.setStyleSheet(f"font-size: 12px; color: {theme.INK_MUTED};")

        lay.addWidget(v)
        lay.addWidget(lab)
        lay.addWidget(prov)


class StateLabel(QLabel):
    """Empty / loading / error placeholder, honest by design (brief §4.4)."""

    def __init__(self, text: str, kind: str = "empty", parent: QWidget | None = None):
        super().__init__(text, parent)
        self.setAlignment(Qt.AlignCenter)
        self.setWordWrap(True)
        colour = {"empty": theme.INK_MUTED, "loading": theme.INK_SECONDARY, "error": "#8c2a22"}.get(kind, theme.INK_MUTED)
        self.setStyleSheet(f"color: {colour}; font-size: 15px; padding: 24px;")


def hrule() -> QFrame:
    line = QFrame()
    line.setFrameShape(QFrame.HLine)
    line.setStyleSheet(f"color: {theme.GRID}; background: {theme.GRID}; max-height: 1px; border: none;")
    return line


def row(*widgets: QWidget, spacing: int = 8, stretch_last: bool = False) -> QWidget:
    w = QWidget()
    lay = QHBoxLayout(w)
    lay.setContentsMargins(0, 0, 0, 0)
    lay.setSpacing(spacing)
    for wd in widgets:
        lay.addWidget(wd)
    if stretch_last:
        lay.addStretch(1)
    return w
