"""The History tab: the project's development, generation by generation.

Sidebar = time-ordered generations grouped under the three pivots (chapter
dividers) with the node-ordering-fix era divider rendered explicitly. Card =
question, verdict, era badge, verbatim headline quotes with ledger provenance,
training-trajectory charts from the run JSONs, figures where they exist, and a
link into the Documents tab."""

from __future__ import annotations

import re
from pathlib import Path

import numpy as np

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont, QMovie, QPixmap
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QScrollArea,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from .. import theme
from ..sacred_bridge import gen_charts
from ..sacred_bridge.ledgers import Generation, load_narrative_index
from ..sacred_bridge.paths import RUNS_DIR, SACRED_ROOT
from ..widgets.cards import Card, EraBadge, StateLabel, StatusPill, hrule
from ..widgets.charts import ChartWidget
from ..widgets.export import Exportable, export_widget_grab
from ..workers import run_in_background

_ROLE_GEN = Qt.UserRole + 1


class HistoryTab(QWidget, Exportable):
    export_name = "history"
    open_ledger = Signal(str, str)  # (sacred-relative path, scroll-to text)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._gens: dict[str, Generation] = {}
        self._current: Generation | None = None

        lay = QHBoxLayout(self)
        lay.setContentsMargins(12, 8, 12, 12)
        split = QSplitter(Qt.Horizontal)
        lay.addWidget(split)

        side = QWidget()
        side_lay = QVBoxLayout(side)
        side_lay.setContentsMargins(0, 0, 0, 0)
        side_lay.setSpacing(6)
        self.banner = QLabel()
        self.banner.setWordWrap(True)
        self.banner.setStyleSheet(
            f"background: {theme.ERA_PREFIX_BG}; color: {theme.ERA_PREFIX_FG};"
            "border-radius: 6px; padding: 7px 9px; font-size: 13px;")
        self.banner.hide()
        side_lay.addWidget(self.banner)
        self.sidebar = QListWidget()
        self.sidebar.setWordWrap(True)
        self.sidebar.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.sidebar.currentItemChanged.connect(self._select)
        side_lay.addWidget(self.sidebar)
        split.addWidget(side)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.card_host = QWidget()
        self.card_lay = QVBoxLayout(self.card_host)
        self.card_lay.setContentsMargins(4, 0, 12, 12)
        self.card_lay.setSpacing(10)
        self.card_lay.addStretch(1)
        self.scroll.setWidget(self.card_host)
        split.addWidget(self.scroll)
        split.setSizes([330, 950])

        self._populate()

    # ------------------------------------------------------------- sidebar

    def _header_item(self, text: str, subtitle: str = "", accent: str = "") -> QListWidgetItem:
        it = QListWidgetItem(text + (f"\n{subtitle}" if subtitle else ""))
        it.setFlags(Qt.ItemIsEnabled)  # not selectable
        f = QFont()
        f.setBold(True)
        it.setFont(f)
        if accent:
            it.setForeground(Qt.black)
            it.setBackground(Qt.transparent)
        return it

    def _populate(self) -> None:
        try:
            chapters, gens, divider = load_narrative_index()
        except Exception as exc:  # index unreadable = the app is misconfigured
            self.sidebar.addItem(f"narrative index unreadable: {exc}")
            return
        self._gens = {g.id: g for g in gens}
        chap_by_id = {c.id: c for c in chapters}

        current_chapter = None
        for g in gens:
            if g.chapter != current_chapter:
                current_chapter = g.chapter
                c = chap_by_id.get(g.chapter)
                if c:
                    self.sidebar.addItem(self._header_item(c.title.upper(), c.subtitle))
            item = QListWidgetItem(f"{g.title}\n{g.dates}")
            item.setData(_ROLE_GEN, g.id)
            item.setToolTip(g.question)
            self.sidebar.addItem(item)
            if divider and g.id == divider.after:
                d = self._header_item("--- " + divider.title + " ---")
                d.setToolTip(divider.text)
                self.sidebar.addItem(d)

        # select the first selectable item
        for i in range(self.sidebar.count()):
            if self.sidebar.item(i).data(_ROLE_GEN):
                self.sidebar.setCurrentRow(i)
                break

        # honesty about the growing sacred repo: run families on disk with no
        # curated record here are flagged rather than silently missing
        fresh = self._uncurated_families(gens)
        if fresh:
            self.banner.setText(
                "New in sacred, not yet curated here: " + ", ".join(fresh)
                + ". Add records to data/narrative_index.yaml (quotes verbatim) "
                  "and, for charts, a spec in gen_charts._FAMILY_SPECS.")
            self.banner.show()

    @staticmethod
    def _uncurated_families(gens) -> list[str]:
        ids = {g.id for g in gens}
        out = []
        if RUNS_DIR.is_dir():
            for d in sorted(RUNS_DIR.iterdir()):
                m = re.match(r"(gen\d+)", d.name)
                if d.is_dir() and m and m.group(1) not in ids:
                    out.append(d.name)
        return out

    def select_generation(self, gen_id: str) -> None:
        for i in range(self.sidebar.count()):
            if self.sidebar.item(i).data(_ROLE_GEN) == gen_id:
                self.sidebar.setCurrentRow(i)
                return

    # ------------------------------------------------------------- card

    def _clear_card(self) -> None:
        while self.card_lay.count() > 1:
            item = self.card_lay.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

    def _select(self, item: QListWidgetItem, _prev=None) -> None:
        if item is None:
            return
        gid = item.data(_ROLE_GEN)
        if not gid:
            return
        g = self._gens.get(gid)
        if g is None:
            return
        self._current = g
        self.export_name = f"history-{g.id}"
        self._clear_card()
        self._build_card(g)

    def _build_card(self, g: Generation) -> None:
        # ---- header card
        head = Card()
        title_row = QWidget()
        trl = QHBoxLayout(title_row)
        trl.setContentsMargins(0, 0, 0, 0)
        trl.setSpacing(8)
        t = QLabel(g.title)
        t.setProperty("h2", True)
        t.setWordWrap(True)
        trl.addWidget(t, 1)
        trl.addWidget(StatusPill(g.status))
        trl.addWidget(EraBadge(g.era))
        head.layout_().addWidget(title_row)

        meta = QLabel(
            f"{g.dates}"
            + (f"   ·   instance {g.instance}" if g.instance else "")
            + (f"   ·   SHA {g.sha}" if g.sha else "")
        )
        meta.setStyleSheet(f"color: {theme.INK_MUTED}; font-size: 13px;")
        head.layout_().addWidget(meta)

        q = QLabel(g.question)
        q.setWordWrap(True)
        q.setStyleSheet(f"font-size: 15px; color: {theme.INK}; font-style: italic;")
        head.layout_().addWidget(q)

        btn = QPushButton(f"Open ledger: {Path(g.ledger).name}")
        btn.setToolTip(str(SACRED_ROOT / g.ledger))
        first_quote = g.quotes[0].quote if g.quotes else ""
        btn.clicked.connect(lambda _=False, lg=g.ledger, fq=first_quote: self.open_ledger.emit(lg, fq))
        row_w = QWidget()
        rl = QHBoxLayout(row_w)
        rl.setContentsMargins(0, 0, 0, 0)
        rl.addWidget(btn)
        rl.addStretch(1)
        head.layout_().addWidget(row_w)
        self.card_lay.insertWidget(self.card_lay.count() - 1, head)

        # ---- quotes card (the citable numbers, verbatim)
        if g.quotes:
            qc = Card()
            qh = QLabel("The record, verbatim")
            qh.setProperty("h3", True)
            qc.layout_().addWidget(qh)
            for quote in g.quotes:
                lab = QLabel(quote.label)
                lab.setStyleSheet(
                    f"color: {theme.INK_SECONDARY}; font-size: 13px; font-weight: 700;"
                    "text-transform: uppercase; letter-spacing: 0.04em;"
                )
                body = QLabel(quote.quote)
                body.setTextFormat(Qt.MarkdownText)
                body.setWordWrap(True)
                body.setTextInteractionFlags(Qt.TextSelectableByMouse)
                body.setStyleSheet(
                    f"font-size: 15px; color: {theme.INK}; background: {theme.PAGE};"
                    f"border-left: 3px solid {theme.BASELINE}; border-radius: 4px;"
                    "padding: 8px 10px;"
                )
                q_src = quote.source or g.ledger
                src = QLabel(
                    f"ledger: {q_src}"
                    + ("" if quote.verified else "   ⚠ quote could not be re-verified against the ledger")
                )
                src.setStyleSheet(
                    f"color: {'#8c2a22' if not quote.verified else theme.INK_MUTED}; font-size: 12px;"
                )
                src.setCursor(Qt.PointingHandCursor)
                src.mousePressEvent = (
                    lambda ev, lg=q_src, qq=quote.quote: self.open_ledger.emit(lg, qq)
                )
                qc.layout_().addWidget(lab)
                qc.layout_().addWidget(body)
                qc.layout_().addWidget(src)
            self.card_lay.insertWidget(self.card_lay.count() - 1, qc)

        # ---- lesson
        if g.lesson:
            lc = Card()
            lh = QLabel("What it taught the project")
            lh.setProperty("h3", True)
            lb = QLabel(g.lesson)
            lb.setWordWrap(True)
            lc.layout_().addWidget(lh)
            lc.layout_().addWidget(lb)
            self.card_lay.insertWidget(self.card_lay.count() - 1, lc)

        # ---- chart (lazy, worker-loaded)
        if gen_charts.has_chart(g.id):
            cc = Card()
            ch = QLabel("Training record")
            ch.setProperty("h3", True)
            cc.layout_().addWidget(ch)
            placeholder = StateLabel("Loading run artefacts…", "loading")
            cc.layout_().addWidget(placeholder)
            self.card_lay.insertWidget(self.card_lay.count() - 1, cc)
            gid = g.id
            run_in_background(
                gen_charts.load_gen_chart, gid,
                on_done=lambda payload, card=cc, ph=placeholder, cur=gid: self._chart_done(cur, card, ph, payload),
                on_fail=lambda tb, card=cc, ph=placeholder: ph.setText("Chart failed to load."),
            )
        elif g.tb_runs:
            cc = Card()
            ch = QLabel("Training record (TensorBoard)")
            ch.setProperty("h3", True)
            cc.layout_().addWidget(ch)
            placeholder = StateLabel("Reading tfevents…", "loading")
            cc.layout_().addWidget(placeholder)
            self.card_lay.insertWidget(self.card_lay.count() - 1, cc)
            gid = g.id
            run_in_background(
                gen_charts.load_tb_chart, gid, g.tb_runs,
                on_done=lambda payload, card=cc, ph=placeholder, cur=gid: self._chart_done(cur, card, ph, payload),
                on_fail=lambda tb, card=cc, ph=placeholder: ph.setText("tfevents failed to load."),
            )

        # ---- figures
        figs = [SACRED_ROOT / f for f in g.figures]
        figs = [f for f in figs if f.is_file()]
        if figs:
            fc = Card()
            fh = QLabel("Figures from the record")
            fh.setProperty("h3", True)
            fc.layout_().addWidget(fh)
            for f in figs:
                if f.suffix.lower() == ".gif":
                    ml = QLabel()
                    movie = QMovie(str(f))
                    # scaledSize() is invalid before the first frame, so scale
                    # from the decoded frame or the 1300px gif overflows the pane
                    movie.jumpToFrame(0)
                    native = movie.currentImage().size()
                    if native.isValid() and native.width() > 760:
                        movie.setScaledSize(native.scaled(760, 560, Qt.KeepAspectRatio))
                    ml.setMovie(movie)
                    movie.start()
                    fc.layout_().addWidget(ml)
                else:
                    pl = QLabel()
                    pm = QPixmap(str(f))
                    if not pm.isNull():
                        pl.setPixmap(pm.scaledToWidth(760, Qt.SmoothTransformation))
                        fc.layout_().addWidget(pl)
                cap = QLabel(f"figure: {f.relative_to(SACRED_ROOT)}")
                cap.setStyleSheet(f"color: {theme.INK_MUTED}; font-size: 12px;")
                fc.layout_().addWidget(cap)
            self.card_lay.insertWidget(self.card_lay.count() - 1, fc)

        # ---- artefact unavailability honesty
        if g.demo == "chart" and not gen_charts.has_chart(g.id) and not figs and not g.tb_runs:
            self.card_lay.insertWidget(
                self.card_lay.count() - 1,
                StateLabel("No run artefacts available for this generation.", "empty"),
            )

    # ------------------------------------------------------------- chart render

    def _chart_done(self, gen_id: str, card: Card, placeholder: StateLabel, payload: dict) -> None:
        if self._current is None or self._current.id != gen_id:
            return  # user moved on
        if "error" in payload:
            placeholder.setText(f"Not available: {payload['error']}")
            return
        placeholder.hide()
        chart = ChartWidget(title=f"{gen_id}-training", height=3.2, width=7.2)
        ax = chart.axes()
        kind = payload["kind"]
        series = payload["series"]
        refs = payload.get("refs", {})

        if kind == "bars":
            labels = [s["label"] for s in series]
            values = [s["y"] for s in series]
            colours = [
                theme.STRATEGY_COLOURS.get("shortest_path") if "shortest" in l
                else theme.STRATEGY_COLOURS.get("uniform") if "uniform" in l
                else theme.STRATEGY_COLOURS.get("equilibrium") if "equilibrium" in l
                else theme.STRATEGY_COLOURS.get("random_init") if "random" in l
                else theme.BLUE
                for l in labels
            ]
            ax.barh(range(len(labels)), values, color=colours, height=0.62)
            ax.set_yticks(range(len(labels)), labels)
            ax.invert_yaxis()
            ax.set_xlabel("exploitability on the held-out game")
            for i, v in enumerate(values):
                ax.text(v + 0.01, i, f"{v:.3f}", va="center", fontsize=11, color=theme.INK_SECONDARY)
        else:
            palette = [theme.BLUE, theme.AQUA, theme.YELLOW, theme.GREEN, theme.VIOLET,
                       theme.RED, theme.MAGENTA, theme.ORANGE]
            many = len(series) > 6
            arm_colours: dict[str, str] = {}
            for i, s in enumerate(series):
                if kind == "interdiction":
                    colour = theme.STRATEGY_COLOURS["sacred"] if s.get("arm") == "sacred" else theme.STRATEGY_COLOURS["vanilla"]
                elif kind == "c1":
                    # cold = the hero blue; ERB-seeded = the control yellow (it hurts)
                    colour = theme.STRATEGY_COLOURS["vanilla"] if s.get("arm") == "seeded" else theme.STRATEGY_COLOURS["sacred"]
                elif kind == "multiconvoy_arms":
                    arm = s.get("arm", "")
                    colour = arm_colours.setdefault(arm, palette[len(arm_colours) % len(palette)])
                else:
                    colour = palette[i % len(palette)] if not many else theme.BLUE
                alpha = 0.55 if many else 1.0
                if kind == "tb" and len(s["y"]) > 80:
                    # noisy per-episode scalars: faint raw cloud + bold rolling mean
                    y = np.asarray(s["y"], dtype=float)
                    k = max(5, len(y) // 60)
                    smooth = np.convolve(y, np.ones(k) / k, mode="same")
                    ax.plot(s["x"], y, color=colour, alpha=0.16, linewidth=0.7)
                    ax.plot(s["x"], smooth, color=colour, linewidth=1.8,
                            label=s["label"] if len(series) <= 8 else None)
                    continue
                ax.plot(s["x"], s["y"], color=colour, alpha=alpha,
                        linewidth=1.4 if many else 2.0, label=s["label"] if len(series) <= 8 else None)
                if s.get("y2"):
                    ax.plot(s["x"], s["y2"], color=colour, alpha=0.5, linewidth=1.2, linestyle="--")
                if s.get("best") is not None and s.get("best_at") is not None:
                    ax.plot([s["best_at"]], [s["best"]], "o", color=colour, markersize=6,
                            markeredgecolor="white", markeredgewidth=1.2, zorder=5)
            ref_styles = {
                "equilibrium": theme.STRATEGY_COLOURS["equilibrium"],
                "alns": theme.STRATEGY_COLOURS["alns"],
                "shortest_path": theme.STRATEGY_COLOURS["shortest_path"],
                "uniform": theme.STRATEGY_COLOURS["uniform"],
                "static_det": theme.STRATEGY_COLOURS["static_det"],
                "iid_eq": theme.STRATEGY_COLOURS["iid_eq"],
                "history_opt": theme.STRATEGY_COLOURS["history_opt"],
            }
            for name, val in refs.items():
                c = ref_styles.get(name, theme.INK_MUTED)
                ax.axhline(val, color=c, linewidth=1.2, linestyle=":", alpha=0.9)
                ax.annotate(f"{name} {val:.3f}", xy=(1.0, val), xycoords=("axes fraction", "data"),
                            fontsize=10.5, color=c, ha="right", va="bottom")
            ax.set_xlabel("sortie")
            if kind == "generalist":
                ax.set_ylabel("held-out ratio to equilibrium")
            elif kind == "b1lite":
                ax.set_ylabel("per-sortie mission failure")
            elif kind == "f2":
                ax.set_ylabel("exploitability (oracle BR)")
            elif kind == "tb":
                ax.set_ylabel(payload.get("tag", ""))
                ax.set_xlabel("episode")
            else:
                ax.set_ylabel("exploitability (TAP)")
            if len(series) <= 8:
                ax.legend(loc="best", fontsize=10.5)

        src = ", ".join(payload.get("sources", [])[:4])
        more = len(payload.get("sources", [])) - 4
        if more > 0:
            src += f" (+{more} more)"
        root = payload.get("source_root", "models/runs/")
        chart.set_caption(f"{payload['note']}   ·   source: {root}{src}", "ledger")
        card.layout_().addWidget(chart)
        chart.redraw()

    def export_view(self):
        return export_widget_grab(self.card_host, self.export_name)
