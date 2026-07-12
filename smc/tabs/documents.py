"""The Documents tab: a markdown reader over the sacred repo and the thesis
directory. File tree, Qt-native markdown rendering, navigable internal links,
back/forward history, and full-text search."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QAction, QKeySequence, QShortcut, QTextCursor, QTextDocument
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QSplitter,
    QStackedWidget,
    QTextBrowser,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from .. import theme
from ..sacred_bridge import docs as docs_bridge
from ..widgets.cards import StateLabel
from ..widgets.export import Exportable, export_widget_grab
from ..workers import run_in_background


class MarkdownView(QTextBrowser):
    """Qt-native markdown rendering with internal-link interception."""

    def __init__(self, on_link, parent=None):
        super().__init__(parent)
        self._on_link = on_link
        self.setOpenLinks(False)
        self.setOpenExternalLinks(False)
        self.anchorClicked.connect(self._clicked)
        self.setStyleSheet(
            f"QTextBrowser {{ background: {theme.SURFACE}; border: 1px solid {theme.GRID}; "
            f"border-radius: 8px; padding: 18px; font-size: 15px; }}"
        )

    def _clicked(self, url: QUrl) -> None:
        self._on_link(url.toString())


class DocumentsTab(QWidget, Exportable):
    export_name = "documents"

    def __init__(self, parent=None):
        super().__init__(parent)
        self._current: Path | None = None
        self._back: list[Path] = []
        self._forward: list[Path] = []

        lay = QHBoxLayout(self)
        lay.setContentsMargins(12, 8, 12, 12)
        split = QSplitter(Qt.Horizontal)
        lay.addWidget(split)

        # ---- left: search + tree/results stack
        left = QWidget()
        llay = QVBoxLayout(left)
        llay.setContentsMargins(0, 0, 0, 0)
        llay.setSpacing(6)

        self.search = QLineEdit()
        self.search.setPlaceholderText("Search all documents…  (Cmd+F)")
        self.search.setClearButtonEnabled(True)
        self.search.returnPressed.connect(self._run_search)
        self.search.textChanged.connect(self._search_maybe_cleared)
        llay.addWidget(self.search)

        self.left_stack = QStackedWidget()
        self.tree = QTreeWidget()
        self.tree.setHeaderHidden(True)
        self.tree.itemActivated.connect(self._tree_open)
        self.tree.itemClicked.connect(self._tree_open)
        self.left_stack.addWidget(self.tree)

        self.results = QListWidget()
        self.results.itemActivated.connect(self._open_result)
        self.results.itemClicked.connect(self._open_result)
        self.left_stack.addWidget(self.results)
        llay.addWidget(self.left_stack)

        split.addWidget(left)

        # ---- right: toolbar + viewer
        right = QWidget()
        rlay = QVBoxLayout(right)
        rlay.setContentsMargins(0, 0, 0, 0)
        rlay.setSpacing(6)

        bar = QWidget()
        blay = QHBoxLayout(bar)
        blay.setContentsMargins(0, 0, 0, 0)
        blay.setSpacing(6)
        self.btn_back = QPushButton("←")
        self.btn_back.setFixedWidth(36)
        self.btn_back.setToolTip("Back (Cmd+[)")
        self.btn_back.clicked.connect(self.go_back)
        self.btn_fwd = QPushButton("→")
        self.btn_fwd.setFixedWidth(36)
        self.btn_fwd.setToolTip("Forward (Cmd+])")
        self.btn_fwd.clicked.connect(self.go_forward)
        self.crumb = QLabel("")
        self.crumb.setStyleSheet(f"color: {theme.INK_MUTED}; font-size: 14px;")
        self.crumb.setTextInteractionFlags(Qt.TextSelectableByMouse)
        blay.addWidget(self.btn_back)
        blay.addWidget(self.btn_fwd)
        blay.addWidget(self.crumb, 1)
        rlay.addWidget(bar)

        self.viewer = MarkdownView(self._follow_link)
        rlay.addWidget(self.viewer, 1)
        split.addWidget(right)
        split.setSizes([320, 900])

        # "Ctrl" = the Command key on macOS. The standard Back/Forward keys are
        # deliberately not bound: they include Cmd+Left/Right, which would steal
        # cursor movement from the search field and the text viewer.
        for keys, fn in ((QKeySequence.Find, self._focus_search),
                         (QKeySequence("Ctrl+["), self.go_back),
                         (QKeySequence("Ctrl+]"), self.go_forward)):
            QShortcut(keys, self, activated=fn, context=Qt.WidgetWithChildrenShortcut)

        self._populate_tree()
        self._nav_buttons()

    # ---------------------------------------------------------------- tree

    def _populate_tree(self) -> None:
        self.tree.clear()
        roots = docs_bridge.doc_roots()
        if not roots:
            self.tree.addTopLevelItem(QTreeWidgetItem(["sacred repo not found"]))
            return
        for root in roots:
            top = QTreeWidgetItem([root.label])
            top.setFlags(top.flags() & ~Qt.ItemIsSelectable)
            self.tree.addTopLevelItem(top)
            dir_items: dict[Path, QTreeWidgetItem] = {root.path: top}
            for md in docs_bridge.list_markdown(root.path):
                rel = md.relative_to(root.path)
                parent = top
                accum = root.path
                for part in rel.parts[:-1]:
                    accum = accum / part
                    if accum not in dir_items:
                        it = QTreeWidgetItem([part])
                        it.setFlags(it.flags() & ~Qt.ItemIsSelectable)
                        dir_items[accum.parent].addChild(it)
                        dir_items[accum] = it
                    parent = dir_items[accum]
                leaf = QTreeWidgetItem([md.name])
                leaf.setData(0, Qt.UserRole, str(md))
                parent.addChild(leaf)
            top.setExpanded(True)

    def _tree_open(self, item: QTreeWidgetItem, _col: int = 0) -> None:
        path = item.data(0, Qt.UserRole)
        if path:
            self.open_document(Path(path))

    # ---------------------------------------------------------------- open/nav

    def open_document(self, path: Path, from_history: bool = False, scroll_to: str = "") -> None:
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            self.viewer.setPlainText(f"Could not read {path}:\n{exc}")
            return
        if self._current and not from_history and self._current != path:
            self._back.append(self._current)
            self._forward.clear()
        self._current = path
        self.viewer.setMarkdown(text)
        self.viewer.moveCursor(QTextCursor.Start)
        try:
            rel = path.relative_to(docs_bridge.SACRED_ROOT)
            self.crumb.setText(f"sacred / {rel}")
        except ValueError:
            try:
                rel = path.relative_to(docs_bridge.THESIS_ROOT)
                self.crumb.setText(f"thesis / {rel}")
            except ValueError:
                self.crumb.setText(str(path))
        if scroll_to:
            self._scroll_to_text(scroll_to)
        self._nav_buttons()

    def open_by_name(self, relative: str, scroll_to: str = "") -> None:
        """Open a document by sacred-relative path (used by other tabs)."""
        p = docs_bridge.SACRED_ROOT / relative
        if p.is_file():
            self.open_document(p, scroll_to=scroll_to)

    def _scroll_to_text(self, needle: str) -> None:
        probe = " ".join(needle.split())[:48]
        if not probe:
            return
        if not self.viewer.find(probe):
            # try a shorter probe; markdown rendering may reflow long strings
            self.viewer.moveCursor(QTextCursor.Start)
            self.viewer.find(probe[:24])

    def _follow_link(self, href: str) -> None:
        if self._current is None:
            return
        target = docs_bridge.resolve_internal_link(self._current, href)
        if target is not None:
            self.open_document(target)

    def go_back(self) -> None:
        if self._back and self._current:
            self._forward.append(self._current)
            self.open_document(self._back.pop(), from_history=True)

    def go_forward(self) -> None:
        if self._forward and self._current:
            self._back.append(self._current)
            self.open_document(self._forward.pop(), from_history=True)

    def _nav_buttons(self) -> None:
        self.btn_back.setEnabled(bool(self._back))
        self.btn_fwd.setEnabled(bool(self._forward))

    # ---------------------------------------------------------------- search

    def _focus_search(self) -> None:
        self.search.setFocus()
        self.search.selectAll()

    def _search_maybe_cleared(self, text: str) -> None:
        if not text:
            self.left_stack.setCurrentWidget(self.tree)

    def _run_search(self) -> None:
        query = self.search.text().strip()
        if len(query) < 2:
            return
        self.results.clear()
        self.results.addItem("Searching…")
        self.left_stack.setCurrentWidget(self.results)
        run_in_background(
            docs_bridge.search_docs, query,
            on_done=self._show_results,
            on_fail=lambda tb: self._show_results([]),
        )

    def _show_results(self, hits) -> None:
        self.results.clear()
        if not hits:
            self.results.addItem("No matches.")
            return
        for h in hits:
            item = QListWidgetItem(f"{h.path.name}:{h.line_no}\n    {h.line}")
            item.setData(Qt.UserRole, (str(h.path), h.line))
            item.setToolTip(str(h.path))
            self.results.addItem(item)

    def _open_result(self, item: QListWidgetItem) -> None:
        data = item.data(Qt.UserRole)
        if not data:
            return
        path, line = data
        self.open_document(Path(path), scroll_to=line)

    # ---------------------------------------------------------------- export

    def export_view(self):
        return export_widget_grab(self.viewer, f"doc-{self._current.stem if self._current else 'empty'}")
