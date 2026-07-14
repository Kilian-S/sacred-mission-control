"""The humanist widget kit (REDESIGN.md §2-3): hero numbers, goalpost bars,
outcome strips, map legends and the "From the record" disclosure. Every screen
composes these instead of inventing its own presentation."""

from __future__ import annotations

from PySide6.QtCore import Qt, QRectF
from PySide6.QtGui import QColor, QPainter, QPen, QBrush, QFontMetrics
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from .. import lexicon, theme


class HeroNumber(QWidget):
    """One large number with a plain caption (the keynote pattern)."""

    def __init__(self, caption: str, fine_print: str = "", parent=None):
        super().__init__(parent)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(2)
        self.value_label = QLabel("—")
        self.value_label.setProperty("hero", True)
        self.caption_label = QLabel(caption)
        self.caption_label.setWordWrap(True)
        self.caption_label.setStyleSheet(
            f"color: {theme.INK_SECONDARY}; font-size: 13px;")
        lay.addWidget(self.value_label)
        lay.addWidget(self.caption_label)
        self.fine = QLabel(fine_print)
        self.fine.setProperty("fineprint", True)
        self.fine.setWordWrap(True)
        if fine_print:
            lay.addWidget(self.fine)
        else:
            self.fine.hide()
            lay.addWidget(self.fine)

    def set_value(self, x: float, decimals: int = 0) -> None:
        self.value_label.setText(lexicon.pct(x, decimals))

    def set_text(self, text: str) -> None:
        self.value_label.setText(text)

    def set_caption(self, caption: str) -> None:
        self.caption_label.setText(caption)

    def set_fine_print(self, text: str) -> None:
        self.fine.setText(text)
        self.fine.setVisible(bool(text))


class GoalpostBar(QWidget):
    """A dot between two labelled goalposts: left = the proven optimum,
    right = the best any predictable plan can do. Values are the metric
    (lower is better); the dot's position reads as gap closure."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(64)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self._lo = 0.0     # optimum
        self._hi = 1.0     # deterministic best
        self._value: float | None = None
        self._label = ""

    def set_posts(self, optimum: float, deterministic: float) -> None:
        self._lo, self._hi = float(optimum), float(deterministic)
        self.update()

    def set_value(self, value: float | None, label: str = "") -> None:
        self._value = None if value is None else float(value)
        self._label = label
        self.update()

    def paintEvent(self, _event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        y = h * 0.45
        x0, x1 = 14.0, w - 14.0

        # track
        pen = QPen(QColor(theme.GRID), 6)
        pen.setCapStyle(Qt.RoundCap)
        p.setPen(pen)
        p.drawLine(int(x0), int(y), int(x1), int(y))

        # goalposts
        for x, colour in ((x0, theme.STRATEGY_COLOURS["equilibrium"]),
                          (x1, theme.STRATEGY_COLOURS["alns"])):
            pen = QPen(QColor(colour), 3)
            p.setPen(pen)
            p.drawLine(int(x), int(y - 11), int(x), int(y + 11))

        fm = QFontMetrics(self.font())
        p.setPen(QPen(QColor(theme.INK_MUTED)))
        f = p.font()
        f.setPointSizeF(10.5)
        p.setFont(f)
        p.drawText(int(x0 - 4), int(y + 15), int(w * 0.55), 18,
                   Qt.AlignLeft, f"{lexicon.GOALPOST_LEFT} · {lexicon.pct(self._lo)}")
        p.drawText(int(x1 - w * 0.55 + 4), int(y + 15), int(w * 0.55 - 4), 18,
                   Qt.AlignRight, f"{lexicon.GOALPOST_RIGHT} · {lexicon.pct(self._hi)}")

        if self._value is None or self._hi <= self._lo:
            return
        t = (self._value - self._lo) / (self._hi - self._lo)
        t_clip = min(1.08, max(-0.08, t))
        x = x0 + t_clip * (x1 - x0)
        p.setBrush(QBrush(QColor(theme.BLUE)))
        p.setPen(QPen(QColor("white"), 2.5))
        p.drawEllipse(QRectF(x - 8, y - 8, 16, 16))
        label = self._label or lexicon.pct(self._value)
        f.setPointSizeF(11)
        f.setBold(True)
        p.setFont(f)
        p.setPen(QPen(QColor(theme.INK)))
        tw = fm.horizontalAdvance(label) + 10
        p.drawText(int(min(max(x - tw / 2, 2), w - tw - 2)), int(y - 26), tw, 16,
                   Qt.AlignHCenter, label)


class OutcomeStrip(QWidget):
    """The last N sortie outcomes as green/red dots + a plain tally, so success
    vs failure is visible at a glance (REDESIGN.md §2.7)."""

    def __init__(self, capacity: int = 20, parent=None):
        super().__init__(parent)
        self._capacity = capacity
        self._outcomes: list[bool] = []   # True = failed
        self._n = 0
        self._failed = 0
        self.setMinimumHeight(40)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

    def reset(self) -> None:
        self._outcomes = []
        self._n = 0
        self._failed = 0
        self.update()

    def push(self, failed: bool) -> None:
        self._outcomes.append(bool(failed))
        if len(self._outcomes) > self._capacity:
            self._outcomes.pop(0)
        self._n += 1
        self._failed += int(failed)
        self.update()

    def paintEvent(self, _event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r, gap = 6.0, 6.0
        x, y = 2.0, 8.0
        for failed in self._outcomes:
            colour = "#d03b3b" if failed else "#0ca30c"
            p.setBrush(QBrush(QColor(colour)))
            p.setPen(Qt.NoPen)
            p.drawEllipse(QRectF(x, y, 2 * r, 2 * r))
            x += 2 * r + gap
        p.setPen(QPen(QColor(theme.INK_SECONDARY)))
        f = p.font()
        f.setPointSizeF(11)
        p.setFont(f)
        tally = (f"missions failed: {self._failed} of {self._n}" if self._n
                 else "no runs yet")
        p.drawText(2, int(y + 2 * r + 16), tally)

    @property
    def counts(self) -> tuple[int, int]:
        return self._failed, self._n


class MapLegend(QWidget):
    """The compact always-on legend under every map (one shared vocabulary)."""

    def __init__(self, show_glow: bool = False, show_ambush: bool = True, parent=None):
        super().__init__(parent)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(2, 2, 2, 2)
        lay.setSpacing(14)

        def item(swatch_colour: str, text: str, shape: str = "line"):
            w = QWidget()
            hl = QHBoxLayout(w)
            hl.setContentsMargins(0, 0, 0, 0)
            hl.setSpacing(5)
            chip = QLabel()
            chip.setFixedSize(18, 12)
            if shape == "line":
                chip.setStyleSheet(
                    f"background: {swatch_colour}; border-radius: 3px; max-height: 5px;")
                chip.setFixedSize(18, 5)
            elif shape == "dot":
                chip.setFixedSize(11, 11)
                chip.setStyleSheet(
                    f"background: {swatch_colour}; border-radius: 5px;")
            elif shape == "cross":
                chip.setText("✕")
                chip.setStyleSheet(
                    f"color: {swatch_colour}; font-weight: 800; font-size: 12px;"
                    "background: transparent;")
            label = QLabel(text)
            label.setStyleSheet(f"color: {theme.INK_MUTED}; font-size: 11px;")
            hl.addWidget(chip)
            hl.addWidget(label)
            return w

        lay.addWidget(item(theme.GRID, "city roads"))
        lay.addWidget(item(theme.BLUE, "thicker = used more often"))
        if show_glow:
            lay.addWidget(item("#f5b48a", "where the enemy expects you"))
        if show_ambush:
            lay.addWidget(item(theme.STRATEGY_COLOURS["attacker"], "ambush", "cross"))
        lay.addWidget(item(theme.GREEN, lexicon.BASE_LABEL, "dot"))
        lay.addWidget(item(theme.VIOLET, lexicon.DESTINATION_LABEL, "dot"))
        lay.addStretch(1)


class RecordDisclosure(QWidget):
    """Proof on demand: a collapsed "From the record ▸" row that expands to the
    verbatim ledger quote(s) + citation(s). Keeps the provenance rules while
    letting plain language lead (REDESIGN.md §1.3)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._lay = QVBoxLayout(self)
        self._lay.setContentsMargins(0, 2, 0, 0)
        self._lay.setSpacing(4)
        self.toggle = QToolButton()
        self.toggle.setProperty("disclosure", True)
        self.toggle.setText(f"{lexicon.RECORD_DISCLOSURE} ▸")
        self.toggle.setCursor(Qt.PointingHandCursor)
        self.toggle.setCheckable(True)
        self.toggle.toggled.connect(self._toggled)
        self._lay.addWidget(self.toggle)
        self.body = QWidget()
        self.body_lay = QVBoxLayout(self.body)
        self.body_lay.setContentsMargins(8, 0, 0, 4)
        self.body_lay.setSpacing(6)
        self.body.hide()
        self._lay.addWidget(self.body)

    def _toggled(self, on: bool) -> None:
        self.toggle.setText(
            f"{lexicon.RECORD_DISCLOSURE} {'▾' if on else '▸'}")
        self.body.setVisible(on)

    def add_quote(self, quote: str, citation: str) -> None:
        q = QLabel(quote)
        q.setTextFormat(Qt.MarkdownText)
        q.setWordWrap(True)
        q.setTextInteractionFlags(Qt.TextSelectableByMouse)
        q.setStyleSheet(
            f"font-size: 13px; color: {theme.INK_SECONDARY}; background: {theme.PAGE};"
            f"border-left: 3px solid {theme.BASELINE}; border-radius: 4px;"
            "padding: 6px 8px;")
        src = QLabel(f"ledger: {citation}")
        src.setProperty("fineprint", True)
        self.body_lay.addWidget(q)
        self.body_lay.addWidget(src)

    def add_line(self, text: str) -> None:
        lab = QLabel(text)
        lab.setProperty("fineprint", True)
        lab.setWordWrap(True)
        self.body_lay.addWidget(lab)

    @property
    def has_content(self) -> bool:
        return self.body_lay.count() > 0
