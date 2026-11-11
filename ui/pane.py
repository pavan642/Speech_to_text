# ui/pane.py — EditorPane: tab strip + find bar + rich text editor
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont, QTextCursor, QTextDocument
from PyQt5.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QTabBar,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)


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
        lay.addWidget(self.editor, 1)

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

    # ---- tab signals forwarded to the app ----
    def _on_tab_changed(self, index):
        self.app._switch_to_tab(self, index)
