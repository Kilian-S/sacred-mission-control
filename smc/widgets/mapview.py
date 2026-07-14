"""The interactive city map: QGraphicsScene with pan/zoom, vulnerability heat,
route menus, OD markers, convoy animation and interception flashes.

Pure display + input: no game logic here. Coordinates come pre-projected from
CityMap.projected(); geometry polylines are used where the geojson has them.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from PySide6.QtCore import QObject, QPointF, Qt, QTimer, Signal
from PySide6.QtGui import (
    QBrush,
    QColor,
    QFont,
    QPainter,
    QPainterPath,
    QPen,
    QPolygonF,
)
from PySide6.QtWidgets import (
    QGraphicsEllipseItem,
    QGraphicsItem,
    QGraphicsLineItem,
    QGraphicsPathItem,
    QGraphicsScene,
    QGraphicsSimpleTextItem,
    QGraphicsView,
)

from .. import theme
from ..sacred_bridge.maps import CityMap

_EDGE_KEY = tuple[str, str]


def _ekey(u: str, v: str) -> _EDGE_KEY:
    return (u, v) if u <= v else (v, u)


def _vuln_colour(p: float) -> QColor:
    ramp = theme.VULN_RAMP
    idx = min(len(ramp) - 1, max(0, int(p * len(ramp))))
    return QColor(ramp[idx])


@dataclass
class RouteDisplay:
    index: int
    path_points: list[QPointF]
    cum_lengths: list[float]      # cumulative scene-space length per point
    edge_of_segment: list[_EDGE_KEY]  # graph edge each polyline segment belongs to
    item: QGraphicsPathItem


class ConvoyDot(QGraphicsEllipseItem):
    def __init__(self, radius: float, colour: str):
        super().__init__(-radius, -radius, 2 * radius, 2 * radius)
        self.setBrush(QBrush(QColor(colour)))
        self.setPen(QPen(QColor("white"), radius * 0.35))
        self.setZValue(50)


class MapView(QGraphicsView):
    route_hovered = Signal(int)          # -1 = none
    route_clicked = Signal(int)
    edge_clicked = Signal(str, str)      # (u, v) of a candidate edge

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setRenderHints(QPainter.Antialiasing | QPainter.SmoothPixmapTransform)
        self.setDragMode(QGraphicsView.ScrollHandDrag)
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.setBackgroundBrush(QBrush(QColor(theme.SURFACE)))
        self.setFrameShape(QGraphicsView.NoFrame)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        # items with ItemIgnoresTransformations (labels, the scale bar) leave
        # trails under the default minimal update mode while panning
        self.setViewportUpdateMode(QGraphicsView.FullViewportUpdate)
        self._scene = QGraphicsScene(self)
        self.setScene(self._scene)
        self.setMouseTracking(True)
        self._build_zoom_chip()

        self._city: CityMap | None = None
        self._pos: dict[str, tuple[float, float]] = {}
        self._routes: list[RouteDisplay] = []
        self._route_probs: list[float] = []
        self._heat_items: dict[_EDGE_KEY, QGraphicsPathItem] = {}
        self._ambush_items: list[QGraphicsItem] = []
        self._attention_items: list[QGraphicsItem] = []
        self._convoys: list[ConvoyDot] = []
        self._hover_idx = -1
        self._edge_click_mode = False
        self._route_click_mode = False
        self._display_name = ""

    # ------------------------------------------------------------- zoom/pan

    def _build_zoom_chip(self) -> None:
        """A small +/−/fit control in the corner; plain scrolling no longer
        zooms (it propagates to the page), Cmd+scroll and pinch still do."""
        from PySide6.QtWidgets import QHBoxLayout, QPushButton, QWidget

        self._chip = QWidget(self)
        lay = QHBoxLayout(self._chip)
        lay.setContentsMargins(4, 4, 4, 4)
        lay.setSpacing(2)
        for text, tip, fn in (("−", "Zoom out", lambda: self._zoom(0.8)),
                              ("+", "Zoom in", lambda: self._zoom(1.25)),
                              ("⤢", "Fit the whole view", self._fit_current)):
            b = QPushButton(text)
            b.setFixedSize(26, 26)
            b.setToolTip(tip)
            b.setStyleSheet(
                f"QPushButton {{ background: {theme.SURFACE}; border: 1px solid "
                f"{theme.GRID}; border-radius: 6px; padding: 0; font-size: 14px; }}"
                f"QPushButton:hover {{ border-color: {theme.BASELINE}; }}")
            b.clicked.connect(fn)
            lay.addWidget(b)
        self._chip.setStyleSheet("background: transparent;")
        self._chip.raise_()

    def _zoom(self, factor: float) -> None:
        self.scale(factor, factor)

    def _fit_current(self) -> None:
        if self._routes:
            self.fit_routes()
        else:
            self.fit_all()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, "_chip"):
            self._chip.move(self.width() - self._chip.sizeHint().width() - 8,
                            self.height() - self._chip.sizeHint().height() - 8)

    def wheelEvent(self, event):
        if event.modifiers() & (Qt.ControlModifier | Qt.MetaModifier):
            factor = 1.25 if event.angleDelta().y() > 0 else 0.8
            self.scale(factor, factor)
            event.accept()
        else:
            event.ignore()  # let the page scroll; the chip/pinch/Cmd+scroll zoom

    def event(self, ev):
        # trackpad pinch on macOS
        from PySide6.QtCore import QEvent
        if ev.type() == QEvent.NativeGesture and \
                ev.gestureType() == Qt.NativeGestureType.ZoomNativeGesture:
            self.scale(1.0 + ev.value(), 1.0 + ev.value())
            return True
        return super().event(ev)

    # ------------------------------------------------------------- city

    def set_city(self, city: CityMap) -> None:
        self._scene.clear()
        self._routes = []
        self._heat_items = {}
        self._ambush_items = []
        self._attention_items = []
        self._convoys = []
        self._city = city
        self._pos = city.projected()
        self._display_name = city.city.replace("_", " ").title()

        # two paths for the background network (fast even for Kyiv): longer
        # edges are the arterials, drawn heavier, so the city reads as a city
        # rather than a uniform scribble
        lengths = sorted(l for _u, _v, l in city.edges)
        cut = lengths[int(0.65 * (len(lengths) - 1))] if lengths else 0.0
        minor, major = QPainterPath(), QPainterPath()
        for u, v, length in city.edges:
            pts = self._edge_points(u, v)
            if not pts:
                continue
            path = major if length >= cut else minor
            path.moveTo(pts[0])
            for p in pts[1:]:
                path.lineTo(p)
        bg_minor = QGraphicsPathItem(minor)
        bg_minor.setPen(QPen(QColor(theme.GRID), 3.0))
        bg_minor.setZValue(0)
        self._scene.addItem(bg_minor)
        bg_major = QGraphicsPathItem(major)
        bg_major.setPen(QPen(QColor("#d6d5cb"), 6.0))
        bg_major.setZValue(0)
        self._scene.addItem(bg_major)
        self.fit_all()

    def fit_all(self) -> None:
        rect = self._scene.itemsBoundingRect()
        if rect.isValid():
            self.fitInView(rect.adjusted(-rect.width() * 0.03, -rect.height() * 0.03,
                                         rect.width() * 0.03, rect.height() * 0.03),
                           Qt.KeepAspectRatio)

    def _edge_points(self, u: str, v: str) -> list[QPointF]:
        assert self._city is not None
        geom = self._city.edge_geometry.get(_ekey(u, v))
        if geom and len(geom) >= 2:
            # geometry is stored lon/lat; project the same way as nodes
            pu = self._pos.get(u)
            pv = self._pos.get(v)
            lonlat_u = self._city.nodes.get(u)
            if pu is None or lonlat_u is None:
                return []
            # derive projection constants from a node we know in both spaces
            lon0lat0 = self._proj_origin()
            kx, ky, lon0, lat0 = lon0lat0
            pts = [QPointF((lon - lon0) * kx, -(lat - lat0) * ky) for lon, lat in geom]
            # orient from u to v
            if (pts[0] - QPointF(*pu)).manhattanLength() > (pts[-1] - QPointF(*pu)).manhattanLength():
                pts.reverse()
            return pts
        pu, pv = self._pos.get(u), self._pos.get(v)
        if pu is None or pv is None:
            return []
        return [QPointF(*pu), QPointF(*pv)]

    def _proj_origin(self):
        # recompute the projection constants CityMap.projected() used
        assert self._city is not None
        lats = [lat for _, lat in self._city.nodes.values()]
        lons = [lon for lon, _ in self._city.nodes.values()]
        lat0 = sum(lats) / len(lats)
        lon0 = sum(lons) / len(lons)
        kx = 111_320.0 * math.cos(math.radians(lat0))
        return kx, 110_540.0, lon0, lat0

    # ------------------------------------------------------------- instance

    def show_instance(
        self,
        routes: list[list[str]],
        edge_vuln: dict[frozenset, float],
        s: str,
        t: str,
    ) -> None:
        """Draw vulnerability heat on candidate edges, route overlays, OD markers."""
        for it in list(self._heat_items.values()):
            self._scene.removeItem(it)
        self._heat_items = {}
        for rd in self._routes:
            self._scene.removeItem(rd.item)
        self._routes = []
        self.clear_ambush()
        self.clear_attention()
        self.clear_convoys()

        # heat layer
        for e, p in edge_vuln.items():
            uv = tuple(e)
            if len(uv) != 2:
                continue
            pts = self._edge_points(str(uv[0]), str(uv[1]))
            if not pts:
                continue
            path = QPainterPath(pts[0])
            for q in pts[1:]:
                path.lineTo(q)
            item = QGraphicsPathItem(path)
            pen = QPen(_vuln_colour(p), 26.0)
            pen.setCapStyle(Qt.RoundCap)
            item.setPen(pen)
            item.setZValue(1)
            item.setToolTip(f"edge {uv[0]}-{uv[1]} · vulnerability {p:.2f} (computed live)")
            item.setData(0, ("edge", str(uv[0]), str(uv[1])))
            self._scene.addItem(item)
            self._heat_items[_ekey(str(uv[0]), str(uv[1]))] = item

        # route overlays
        for idx, route in enumerate(routes):
            pts: list[QPointF] = []
            seg_edges: list[_EDGE_KEY] = []
            for a, b in zip(route[:-1], route[1:]):
                ep = self._edge_points(a, b)
                if not ep:
                    continue
                if pts:
                    ep = ep[1:] if (ep and (ep[0] - pts[-1]).manhattanLength() < 1e-6) else ep
                for q in ep:
                    pts.append(q)
                    seg_edges.append(_ekey(a, b))
            if len(pts) < 2:
                continue
            path = QPainterPath(pts[0])
            cum = [0.0]
            for q in pts[1:]:
                path.lineTo(q)
                d = math.hypot(q.x() - pts[len(cum) - 1].x(), q.y() - pts[len(cum) - 1].y())
                cum.append(cum[-1] + d)
            item = QGraphicsPathItem(path)
            item.setZValue(5)
            item.setData(0, ("route", idx))
            item.setAcceptHoverEvents(False)
            self._scene.addItem(item)
            self._routes.append(RouteDisplay(idx, pts, cum, seg_edges[1:] if len(seg_edges) == len(pts) else seg_edges, item))

        self.set_route_mixture([0.0] * len(self._routes))

        # OD markers
        for nid, label, colour in ((s, "BASE", theme.GREEN), (t, "FOB", theme.VIOLET)):
            p = self._pos.get(nid)
            if p is None:
                continue
            dot = QGraphicsEllipseItem(p[0] - 55, p[1] - 55, 110, 110)
            dot.setBrush(QBrush(QColor(colour)))
            dot.setPen(QPen(QColor("white"), 16))
            dot.setZValue(40)
            self._scene.addItem(dot)
            self._heat_items[(f"__od_{label}", nid)] = dot  # cleared with the heat layer
            txt = QGraphicsSimpleTextItem(label)
            f = QFont(theme.FONT_FAMILY, 12)
            f.setBold(True)
            txt.setFont(f)
            txt.setBrush(QBrush(QColor(theme.INK)))
            txt.setZValue(41)
            txt.setPos(p[0] + 70, p[1] - 130)
            txt.setFlag(QGraphicsItem.ItemIgnoresTransformations, True)
            self._scene.addItem(txt)
            self._heat_items[(f"__odt_{label}", nid)] = txt

        self.fit_routes()

    def fit_routes(self) -> None:
        if not self._routes:
            self.fit_all()
            return
        rect = None
        for rd in self._routes:
            r = rd.item.boundingRect()
            rect = r if rect is None else rect.united(r)
        if rect is not None:
            m = max(rect.width(), rect.height()) * 0.12
            self.fitInView(rect.adjusted(-m, -m, m, m), Qt.KeepAspectRatio)

    # ------------------------------------------------------------- mixture

    def set_route_mixture(self, probs: list[float], base_colour: str | None = None) -> None:
        """Route thickness/opacity encode the defender mixture."""
        self._route_probs = list(probs)
        colour = base_colour or theme.STRATEGY_COLOURS["sacred"]
        for rd in self._routes:
            p = probs[rd.index] if rd.index < len(probs) else 0.0
            pen = QPen(QColor(colour), 10 + 55 * p)
            pen.setCapStyle(Qt.RoundCap)
            c = QColor(colour)
            c.setAlphaF(min(1.0, 0.3 + 0.7 * (p ** 0.6)) if p > 0 else 0.15)
            pen.setColor(c)
            rd.item.setPen(pen)
            rd.item.setToolTip(f"route {rd.index}: P = {p:.3f}")
        if self._hover_idx >= 0:
            self._apply_hover(self._hover_idx)

    # ------------------------------------------------------------- attention

    def show_attention(self, edge_weights: dict[tuple[str, str], float]) -> None:
        """The adversary's anticipation: orange mass glowing under the routes.

        Opacity encodes ABSOLUTE probability mass, so a concentrated attacker
        burns bright on one or two edges while an undecided one is a faint
        wash over many; negligible mass (< 1%) is not drawn at all. Pure
        display; the caller computes the weights and labels them live."""
        self.clear_attention()
        for (u, v), wgt in edge_weights.items():
            if wgt < 0.01:
                continue
            pts = self._edge_points(str(u), str(v))
            if not pts:
                continue
            path = QPainterPath(pts[0])
            for q in pts[1:]:
                path.lineTo(q)
            item = QGraphicsPathItem(path)
            c = QColor(theme.STRATEGY_COLOURS["attacker"])
            c.setAlphaF(min(0.85, 0.15 + 2.2 * wgt))
            # wider than the widest route ribbon (65), so the glow halos out
            # from under a fully-concentrated mixture instead of hiding
            pen = QPen(c, 72.0)
            pen.setCapStyle(Qt.RoundCap)
            item.setPen(pen)
            item.setZValue(3)  # above the threat heat, below the route ribbons
            item.setToolTip(f"the interdictor's anticipation here: P = {wgt:.3f} (computed live)")
            self._attention_items.append(item)
            self._scene.addItem(item)

    def clear_attention(self) -> None:
        for it in self._attention_items:
            self._scene.removeItem(it)
        self._attention_items = []

    # ------------------------------------------------------------- ambush

    def show_ambush(self, edges: list[tuple[str, str]], revealed: bool) -> None:
        self.clear_ambush()
        for u, v in edges:
            pts = self._edge_points(u, v)
            if not pts:
                continue
            mid = pts[len(pts) // 2]
            size = 130
            path = QPainterPath()
            path.moveTo(mid.x() - size, mid.y() - size)
            path.lineTo(mid.x() + size, mid.y() + size)
            path.moveTo(mid.x() + size, mid.y() - size)
            path.lineTo(mid.x() - size, mid.y() + size)
            item = QGraphicsPathItem(path)
            colour = QColor(theme.STRATEGY_COLOURS["attacker"])
            if not revealed:
                colour.setAlphaF(0.0)
            pen = QPen(colour, 40)
            pen.setCapStyle(Qt.RoundCap)
            item.setPen(pen)
            item.setZValue(45)
            self._scene.addItem(item)
            self._ambush_items.append(item)

    def reveal_ambush(self) -> None:
        for it in self._ambush_items:
            pen = it.pen()
            c = pen.color()
            c.setAlphaF(0.95)
            pen.setColor(c)
            it.setPen(pen)

    def clear_ambush(self) -> None:
        for it in self._ambush_items:
            self._scene.removeItem(it)
        self._ambush_items = []

    # ------------------------------------------------------------- convoys

    def add_convoy(self, colour: str | None = None) -> ConvoyDot:
        dot = ConvoyDot(70, colour or theme.STRATEGY_COLOURS["sacred"])
        self._scene.addItem(dot)
        self._convoys.append(dot)
        return dot

    def clear_convoys(self) -> None:
        for c in self._convoys:
            self._scene.removeItem(c)
        self._convoys = []

    def fraction_of_edge(self, route_idx: int, edge: tuple[str, str]) -> float | None:
        """Scene-length fraction of a point just past the middle of `edge`
        along the route, or None if the edge is not on the drawn route.

        This is the same parameterisation place_on_route uses, so a convoy
        stopped at this fraction dies ON the ambush edge, not a block away
        (edge-count fractions diverge from scene-length fractions whenever
        edge lengths vary, which on real city graphs is always)."""
        if route_idx >= len(self._routes):
            return None
        rd = self._routes[route_idx]
        total = rd.cum_lengths[-1]
        if total <= 0:
            return None
        key = _ekey(str(edge[0]), str(edge[1]))
        lo = hi = None
        for i, e in enumerate(rd.edge_of_segment):
            if e == key and i + 1 < len(rd.cum_lengths):
                if lo is None:
                    lo = rd.cum_lengths[i]
                hi = rd.cum_lengths[i + 1]
        if lo is None or hi is None:
            return None
        return (lo + 0.55 * (hi - lo)) / total

    def place_on_route(self, dot: ConvoyDot, route_idx: int, frac: float) -> _EDGE_KEY | None:
        """Move a convoy dot to fraction `frac` along a route; returns the
        graph edge under the dot (for interception checks)."""
        if route_idx >= len(self._routes):
            return None
        rd = self._routes[route_idx]
        total = rd.cum_lengths[-1]
        target = frac * total
        # find segment
        lo = 0
        for i in range(1, len(rd.cum_lengths)):
            if rd.cum_lengths[i] >= target:
                lo = i - 1
                break
        else:
            lo = len(rd.cum_lengths) - 2
        seg_len = rd.cum_lengths[lo + 1] - rd.cum_lengths[lo]
        u = 0.0 if seg_len <= 0 else (target - rd.cum_lengths[lo]) / seg_len
        p0, p1 = rd.path_points[lo], rd.path_points[lo + 1]
        dot.setPos(p0.x() + (p1.x() - p0.x()) * u, p0.y() + (p1.y() - p0.y()) * u)
        if lo < len(rd.edge_of_segment):
            return rd.edge_of_segment[lo]
        return None

    def flash(self, dot: ConvoyDot, colour: str | None = None) -> None:
        """Interception flash: expanding fading ring at the dot's position."""
        ring = QGraphicsEllipseItem(-40, -40, 80, 80)
        ring.setPos(dot.pos())
        c = QColor(colour or theme.STRATEGY_COLOURS["shortest_path"])
        pen = QPen(c, 30)
        ring.setPen(pen)
        ring.setBrush(Qt.NoBrush)
        ring.setZValue(60)
        self._scene.addItem(ring)
        steps = {"n": 0}
        timer = QTimer(self)

        def tick():
            steps["n"] += 1
            k = steps["n"]
            r = 40 + k * 28
            ring.setRect(-r, -r, 2 * r, 2 * r)
            c2 = QColor(c)
            c2.setAlphaF(max(0.0, 1.0 - k / 14))
            pen2 = QPen(c2, 30)
            ring.setPen(pen2)
            if k >= 14:
                timer.stop()
                self._scene.removeItem(ring)
                timer.deleteLater()

        timer.timeout.connect(tick)
        timer.start(28)

    def mark_lost(self, dot: ConvoyDot) -> None:
        """The convoy is destroyed: it KEEPS its strategy colour (identity is
        the story) and gains a cross; it is never repainted another
        strategy's colour."""
        r = dot.rect().width() / 2
        for x1, y1, x2, y2 in ((-r, -r, r, r), (-r, r, r, -r)):
            line = QGraphicsLineItem(x1, y1, x2, y2, dot)
            pen = QPen(QColor(theme.INK), r * 0.4)
            pen.setCapStyle(Qt.RoundCap)
            line.setPen(pen)
            line.setZValue(51)
        self.burst_label(dot, "Ambushed ✗", "#d03b3b")

    def celebrate(self, dot: ConvoyDot) -> None:
        """The convoy made it: a green pulse + 'Delivered' at the destination,
        so success is as visible as failure (REDESIGN.md §2.7)."""
        self.flash(dot, "#0ca30c")
        self.burst_label(dot, "Delivered ✓", "#006300")

    def burst_label(self, dot: ConvoyDot, text: str, colour: str) -> None:
        """A short-lived floating outcome word at the dot's position."""
        item = QGraphicsSimpleTextItem(text)
        f = QFont(theme.FONT_FAMILY, 12)
        f.setBold(True)
        item.setFont(f)
        item.setBrush(QBrush(QColor(colour)))
        item.setPen(QPen(QColor("white"), 0.8))
        item.setFlag(QGraphicsItem.ItemIgnoresTransformations, True)
        item.setPos(dot.pos())
        item.setZValue(70)
        self._scene.addItem(item)
        steps = {"n": 0}
        timer = QTimer(self)

        def tick():
            steps["n"] += 1
            k = steps["n"]
            item.setOpacity(max(0.0, 1.0 - k / 26))
            item.moveBy(0, 0)  # position is view-anchored; fade only
            if k >= 26:
                timer.stop()
                self._scene.removeItem(item)
                timer.deleteLater()

        timer.timeout.connect(tick)
        timer.start(45)

    # ------------------------------------------------------------- input modes

    def set_route_click_mode(self, on: bool) -> None:
        self._route_click_mode = on

    def set_edge_click_mode(self, on: bool) -> None:
        self._edge_click_mode = on
        self.setDragMode(QGraphicsView.NoDrag if on else QGraphicsView.ScrollHandDrag)

    def _route_at(self, scene_pos: QPointF) -> int:
        best, best_d = -1, 260.0
        for rd in self._routes:
            for i in range(len(rd.path_points) - 1):
                p0, p1 = rd.path_points[i], rd.path_points[i + 1]
                d = _point_segment_dist(scene_pos, p0, p1)
                if d < best_d:
                    best, best_d = rd.index, d
        return best

    def mouseMoveEvent(self, event):
        super().mouseMoveEvent(event)
        if not self._routes:
            return
        idx = self._route_at(self.mapToScene(event.position().toPoint()))
        if idx != self._hover_idx:
            self._hover_idx = idx
            self._apply_hover(idx)
            self.route_hovered.emit(idx)

    def _apply_hover(self, idx: int) -> None:
        for rd in self._routes:
            pen = rd.item.pen()
            c = pen.color()
            if rd.index == idx:
                c.setAlphaF(1.0)
                pen.setWidthF(max(pen.widthF(), 40))
            else:
                p = self._route_probs[rd.index] if rd.index < len(self._route_probs) else 0.0
                c.setAlphaF(min(1.0, 0.3 + 0.7 * (p ** 0.6)) if p > 0 else 0.15)
                pen.setWidthF(10 + 55 * p)
            pen.setColor(c)
            rd.item.setPen(pen)

    # ------------------------------------------------------------- overlay

    def drawForeground(self, painter: QPainter, rect) -> None:
        """Viewport-anchored cartographic furniture: the city name and a
        scale bar. Drawn in SCENE coordinates (scene units are metres from
        the equirectangular projection), converting pixel margins through the
        current zoom, so it renders identically on screen and under any
        export painter transform (resetTransform would break the 3x PNG)."""
        super().drawForeground(painter, rect)
        if self._city is None:
            return
        m11 = abs(self.transform().m11())  # viewport px per metre
        if m11 <= 0:
            return
        vis = self.mapToScene(self.viewport().rect()).boundingRect()

        def sx(px: float) -> float:
            return px / m11

        painter.save()
        painter.setPen(QColor(theme.INK_SECONDARY))
        if self._display_name:
            f = QFont(theme.FONT_FAMILY)
            f.setPointSizeF(max(1.0, 13 / m11))
            f.setBold(True)
            painter.setFont(f)
            painter.drawText(QPointF(vis.left() + sx(12), vis.top() + sx(24)),
                             self._display_name)
        candidates = (20, 50, 100, 200, 500, 1000, 2000, 5000, 10000)
        metres = next((c for c in candidates if 60 <= c * m11 <= 160), None)
        if metres is not None:
            x0 = vis.left() + sx(12)
            y = vis.bottom() - sx(14)
            painter.setPen(QPen(QColor(theme.INK_SECONDARY), sx(2)))
            painter.drawLine(QPointF(x0, y), QPointF(x0 + metres, y))
            painter.drawLine(QPointF(x0, y - sx(4)), QPointF(x0, y + sx(4)))
            painter.drawLine(QPointF(x0 + metres, y - sx(4)), QPointF(x0 + metres, y + sx(4)))
            f2 = QFont(theme.FONT_FAMILY)
            f2.setPointSizeF(max(1.0, 11 / m11))
            painter.setFont(f2)
            label = f"{metres} m" if metres < 1000 else f"{metres / 1000:g} km"
            painter.drawText(QPointF(x0 + metres + sx(6), y + sx(4)), label)
        painter.restore()

    def mousePressEvent(self, event):
        scene_pos = self.mapToScene(event.position().toPoint())
        if self._route_click_mode and event.button() == Qt.LeftButton:
            idx = self._route_at(scene_pos)
            if idx >= 0:
                self.route_clicked.emit(idx)
                return
        if self._edge_click_mode and event.button() == Qt.LeftButton:
            item = self.itemAt(event.position().toPoint())
            data = item.data(0) if item else None
            if data and isinstance(data, tuple) and data[0] == "edge":
                self.edge_clicked.emit(data[1], data[2])
                return
        super().mousePressEvent(event)


def _point_segment_dist(p: QPointF, a: QPointF, b: QPointF) -> float:
    ax, ay, bx, by, px, py = a.x(), a.y(), b.x(), b.y(), p.x(), p.y()
    dx, dy = bx - ax, by - ay
    L2 = dx * dx + dy * dy
    if L2 <= 0:
        return math.hypot(px - ax, py - ay)
    u = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / L2))
    return math.hypot(px - (ax + u * dx), py - (ay + u * dy))
