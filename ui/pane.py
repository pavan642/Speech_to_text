# ui/pane.py — EditorPane: tab strip + find bar + rich text editor
from urllib.parse import unquote

from PyQt5.QtCore import QEvent, Qt
from PyQt5.QtGui import QColor, QFont, QPainter, QTextCursor, QTextDocument
from PyQt5.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QStackedWidget,
    QTabBar,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)


class LineNumberGutter(QWidget):
    """Slim line-number strip painted beside the editor (VS Code style)."""

    def __init__(self, editor):
        super().__init__()
        self.editor = editor
        self.setFixedWidth(46)
        editor.verticalScrollBar().valueChanged.connect(self.update)
        editor.document().blockCountChanged.connect(self.update)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setFont(QFont("Menlo", 9))
        painter.setPen(QColor("#8A8A8A"))
        doc = self.editor.document()
        layout = doc.documentLayout()
        scroll = self.editor.verticalScrollBar().value()

        block = doc.begin()
        number = 1
        while block.isValid():
            rect = layout.blockBoundingRect(block)
            y = rect.top() - scroll  # QTextEdit scrolls in pixels
            if y > self.height():
                break
            if y + rect.height() >= 0:
                painter.drawText(
                    0, int(y), self.width() - 6, int(rect.height()),
                    Qt.AlignRight | Qt.AlignTop, str(number),
                )
            block = block.next()
            number += 1
        painter.end()


class EditorPane(QWidget):
    """One editor pane: tab strip (open docs) + find bar + rich text editor.
    The app holds one or two of these side by side (split view)."""

    def __init__(self, app, closable=False):
        super().__init__()
        self.app = app
        self.path = None              # current document path (None = history/empty)
        self.history_content = None   # set when the tab is a read-only history view
        self.dirty = False

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        # --- Tab strip ---
        tab_bar = QFrame()
        tab_bar.setObjectName("tabBar")
        tb = QHBoxLayout(tab_bar)
        tb.setContentsMargins(6, 0, 6, 0)
        tb.setSpacing(4)
        self.tabs = QTabBar()
        self.tabs.setObjectName("docTabs")
        self.tabs.setTabsClosable(False)  # custom ✕ buttons per tab instead
        self.tabs.setMovable(True)
        self.tabs.setExpanding(False)
        self.tabs.setUsesScrollButtons(True)  # many tabs scroll instead of squishing
        self.tabs.setElideMode(Qt.ElideRight)
        self.tabs.currentChanged.connect(self._on_tab_changed)
        tb.addWidget(self.tabs, 1)
        add_btn = QPushButton("New")
        _plus = self.app._fa("fa5s.plus")
        if not _plus.isNull():
            add_btn.setIcon(_plus)
        add_btn.setFixedHeight(24)
        add_btn.setToolTip("New document")
        add_btn.setCursor(Qt.PointingHandCursor)
        add_btn.clicked.connect(lambda: self.app.new_document(self))
        tb.addWidget(add_btn, 0, Qt.AlignVCenter)

        # Corner "Close" only on the split pane — closes the split view
        if closable:
            close_pane_btn = QPushButton("Close")
            close_pane_btn.setFixedHeight(24)
            close_pane_btn.setToolTip("Close split view")
            close_pane_btn.setCursor(Qt.PointingHandCursor)
            close_pane_btn.clicked.connect(self.app.toggle_split_view)
            tb.addWidget(close_pane_btn, 0, Qt.AlignVCenter)
        lay.addWidget(tab_bar)

        # --- Breadcrumb bar (folder / file path, VS Code style) ---
        bc_bar = QFrame()
        bc_bar.setObjectName("tabBar")
        bcl = QHBoxLayout(bc_bar)
        bcl.setContentsMargins(10, 2, 10, 2)
        bcl.setSpacing(0)
        self.breadcrumb = QLabel("")
        self.breadcrumb.setObjectName("breadcrumb")
        self.breadcrumb.setFont(QFont("Helvetica Neue", 9))
        bcl.addWidget(self.breadcrumb)
        bcl.addStretch()
        lay.addWidget(bc_bar)

        # --- Find bar (hidden until 🔍 or Ctrl/Cmd+F) ---
        self.find_bar = QFrame()
        self.find_bar.setObjectName("tabBar")
        fb = QHBoxLayout(self.find_bar)
        fb.setContentsMargins(10, 4, 10, 4)
        fb.setSpacing(6)
        self.find_input = QLineEdit()
        self.find_input.setPlaceholderText("Find in document…")
        self.find_input.returnPressed.connect(self.find_next)
        fb.addWidget(self.find_input, 1)
        fb.addWidget(app._tool_btn("↓", "Next match", self.find_next))
        fb.addWidget(app._tool_btn("↑", "Previous match", self.find_prev))
        self.replace_input = QLineEdit()
        self.replace_input.setPlaceholderText("Replace with…")
        self.replace_input.returnPressed.connect(self.replace_current)
        fb.addWidget(self.replace_input, 1)
        fb.addWidget(app._tool_btn("Replace", "Replace current match", self.replace_current))
        fb.addWidget(app._tool_btn("All", "Replace all matches", self.replace_all))
        fb.addWidget(app._tool_btn("✕", "Close find", self.find_bar.hide))
        self.find_bar.setVisible(False)
        lay.addWidget(self.find_bar)

        # --- Editor ---
        self.editor = QTextEdit()
        self.editor.setFont(QFont("Helvetica Neue", 12))
        self.editor.setFrameShape(QFrame.NoFrame)
        self.editor.setPlaceholderText(
            "Write here… or click 🎙️ Start on the right and speak — text lands at your cursor."
        )
        self.editor.textChanged.connect(self._on_text_changed)
        self.editor.cursorPositionChanged.connect(self._on_cursor_moved)
        # Search-result file links open on click — QTextEdit has no
        # anchorClicked signal, so links are resolved via anchorAt()
        # in the event filter below.
        self.editor.viewport().installEventFilter(self)

        # --- Empty state (shown when no tabs are open) ---
        self.stack = QStackedWidget()
        empty = QWidget()
        el = QVBoxLayout(empty)
        el.addStretch()
        big = QLabel("🎙️")
        big.setAlignment(Qt.AlignCenter)
        big.setFont(QFont("Helvetica Neue", 42))
        msg = QLabel("No document open")
        msg.setObjectName("subtitle")
        msg.setAlignment(Qt.AlignCenter)
        msg.setFont(QFont("Helvetica Neue", 14, QFont.Bold))
        hint = QLabel(
            "⌘N New document   ·   ⌘F Find   ·   ⌘S Save\n"
            "⌘W Close tab   ·   ⌘B Sidebar   ·   🎙️ Dictate with Start"
        )
        hint.setObjectName("subtitle")
        hint.setAlignment(Qt.AlignCenter)
        hint.setFont(QFont("Helvetica Neue", 10))
        el.addWidget(big)
        el.addSpacing(10)
        el.addWidget(msg)
        el.addSpacing(6)
        el.addWidget(hint)
        el.addSpacing(14)

        # Clickable action right on the welcome page
        new_btn = QPushButton("＋  New Document")
        new_btn.setObjectName("primaryBtn")
        new_btn.setFont(QFont("Helvetica Neue", 11, QFont.Bold))
        new_btn.setFixedWidth(200)
        new_btn.setCursor(Qt.PointingHandCursor)
        new_btn.clicked.connect(lambda: self.app.new_document(self))
        el.addWidget(new_btn, 0, Qt.AlignCenter)
        el.addStretch()

        self.stack.addWidget(empty)        # page 0 = welcome

        # page 1 = line-number gutter + editor
        editor_wrap = QWidget()
        er = QHBoxLayout(editor_wrap)
        er.setContentsMargins(0, 0, 0, 0)
        er.setSpacing(0)
        self.gutter = LineNumberGutter(self.editor)
        er.addWidget(self.gutter)
        er.addWidget(self.editor)
        self.stack.addWidget(editor_wrap)

        lay.addWidget(self.stack, 1)

        # --- Per-file action bar (bottom of the pane) ---
        actions = QFrame()
        actions.setObjectName("tabBar")
        ab = QHBoxLayout(actions)
        ab.setContentsMargins(8, 4, 8, 4)
        ab.setSpacing(6)

        ab.addWidget(app._tool_btn("Read", "Read this document aloud", self._act_read))
        ab.addWidget(app._tool_btn("Stop", "Stop reading", lambda: self.app.tts.stop()))
        ab.addWidget(app._tool_btn("Optimize", "Optimize this document with Claude", self._act_optimize))
        ab.addWidget(app._tool_btn("Export", "Export this document (.md/.txt/.pdf)", self._act_export))
        ab.addWidget(app._tool_btn("Remind", "Set a reminder for this document", self._act_remind))
        ab.addWidget(app._tool_btn("Strip tags", "Convert raw HTML in this document to plain text", self._act_strip))
        ab.addStretch()
        ab.addWidget(app._tool_btn("Delete", "Delete this document", self._act_delete))
        lay.addWidget(actions)

        self._update_empty_state()

    # ---- bottom action bar handlers (act on THIS pane's document) ----
    def _act_read(self):
        self.app._activate_pane(self)
        self.app.read_aloud()

    def _act_optimize(self):
        self.app._activate_pane(self)
        self.app.optimize_document_text()

    def _act_export(self):
        self.app._activate_pane(self)
        if self.path:
            self.app.export_document_path(self.path)
        else:
            self.app.export_document()

    def _act_remind(self):
        self.app._activate_pane(self)
        if self.path:
            self.app._set_reminder_for_path(self.path)
        else:
            self.app.status_label.setText("Open a document first")

    def _act_delete(self):
        self.app._activate_pane(self)
        self.app.delete_document()

    def _act_strip(self):
        self.app._activate_pane(self)
        self.app.strip_html_from_document()

    # ---- change / dirty tracking ----
    def _on_text_changed(self):
        if not self.dirty:
            self.dirty = True
            self._refresh_tab_title()
        self.app._autosave_arm()
        self.app._schedule_word_count()
        self.app._maybe_markdown_autofmt(self)

    def _on_cursor_moved(self):
        self.app._update_format_state(self)

    def set_dirty(self, dirty: bool):
        self.dirty = dirty
        self._refresh_tab_title()

    def _update_empty_state(self):
        """Welcome page when nothing is open, editor otherwise."""
        self.stack.setCurrentIndex(1 if self.tabs.count() > 0 else 0)

    def eventFilter(self, obj, event):
        """Enter on task lines continues the checkbox list; link clicks open docs."""
        if (
            obj is self.editor.viewport()
            and event.type() == QEvent.KeyPress
            and event.key() in (Qt.Key_Return, Qt.Key_Enter)
            and self.app._handle_task_enter(self)
        ):
            return True
        if (
            obj is self.editor.viewport()
            and event.type() == QEvent.MouseButtonRelease
            and self.editor.isReadOnly()
        ):
            anchor = self.editor.anchorAt(event.pos())
            if anchor:
                self.app.open_document_path(unquote(anchor))
                return True
        return super().eventFilter(obj, event)

    def _refresh_tab_title(self):
        i = self.tabs.currentIndex()
        if i < 0:
            return
        meta = self.tabs.tabData(i) or {}
        title = meta.get("title", self.tabs.tabText(i).lstrip("● "))
        self.tabs.setTabText(i, ("● " if self.dirty else "") + title)

    # ---- find ----
    def show_find(self):
        self.find_bar.setVisible(True)
        self.find_input.setFocus()
        self.find_input.selectAll()

    def find_next(self):
        self._find(QTextDocument.FindFlags())

    def find_prev(self):
        self._find(QTextDocument.FindBackward)

    def _find(self, flags):
        text = self.find_input.text()
        if not text:
            return
        if not self.editor.find(text, flags):
            cursor = self.editor.textCursor()
            cursor.movePosition(
                QTextCursor.End if flags == QTextDocument.FindBackward else QTextCursor.Start
            )
            self.editor.setTextCursor(cursor)
            self.editor.find(text, flags)

    # ---- replace ----
    def replace_current(self):
        """Replace the current match (if selected), then jump to the next."""
        cursor = self.editor.textCursor()
        if cursor.hasSelection() and cursor.selectedText() == self.find_input.text():
            cursor.insertText(self.replace_input.text())
        self.find_next()

    def replace_all(self):
        find_text = self.find_input.text()
        if not find_text:
            return
        cursor = self.editor.textCursor()
        cursor.movePosition(QTextCursor.Start)
        self.editor.setTextCursor(cursor)
        count = 0
        while self.editor.find(find_text) and count < 10000:
            self.editor.textCursor().insertText(self.replace_input.text())
            count += 1
        self.app.status_label.setText(f"Replaced {count} occurrence(s)")

    # ---- tab signals forwarded to the app ----
    def _on_tab_changed(self, index):
        self.app._switch_to_tab(self, index)
