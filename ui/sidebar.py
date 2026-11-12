# ui/sidebar.py — left column (documents tree + speech history) and right speech panel
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor, QFont, QPainter
from PyQt5.QtWidgets import (
    QFileSystemModel,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QPushButton,
    QTextEdit,
    QTreeView,
    QVBoxLayout,
    QWidget,
)

import documents_manager as docs


class WaveformWidget(QWidget):
    """Mini rolling waveform — last ~64 mic levels as green vertical bars."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._levels = []
        self.setFixedHeight(36)

    def add_level(self, level: int):
        self._levels.append(level)
        if len(self._levels) > 64:
            self._levels.pop(0)
        self.update()

    def clear(self):
        self._levels = []
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        if not self._levels:
            painter.setPen(QColor("#9D9D9D"))
            painter.drawText(self.rect(), Qt.AlignCenter, "～")
            painter.end()
            return
        n = len(self._levels)
        bar_w = max(2, self.width() // 64)
        mid = self.height() / 2
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor("#4CAF50"))
        for i, lv in enumerate(self._levels):
            h = max(2, int(self.height() * lv / 100))
            x = self.width() - (n - i) * bar_w
            painter.drawRect(int(x), int(mid - h / 2), int(bar_w - 1), int(h))
        painter.end()


def build_left_column(app):
    """Left panel: documents (search + folder tree) on top, speech history below."""
    col = QWidget()
    col.setMinimumWidth(180)
    col.setMaximumWidth(460)  # resizable via the body splitter
    lay = QVBoxLayout(col)
    lay.setContentsMargins(0, 0, 0, 0)
    lay.setSpacing(14)

    # ---- Documents card: header buttons + search + folder tree ----
    docs_card = app._make_card()
    dc = QVBoxLayout(docs_card)
    dc.setContentsMargins(14, 14, 14, 14)
    dc.setSpacing(8)

    docs_header = QHBoxLayout()
    t1 = QLabel("📁  DOCUMENTS")
    t1.setObjectName("sectionTitle")
    t1.setFont(QFont("Helvetica Neue", 11, QFont.Bold))
    docs_header.addWidget(t1)
    docs_header.addStretch()
    dc.addLayout(docs_header)

    # Buttons row: New / Add folder / Import
    btn_row = QHBoxLayout()
    btn_row.setSpacing(6)

    add_doc_btn = QPushButton("New")
    _pi = app._fa("fa5s.plus")
    if not _pi.isNull():
        add_doc_btn.setIcon(_pi)
    add_doc_btn.setFixedHeight(22)
    add_doc_btn.setToolTip("New document")
    add_doc_btn.setCursor(Qt.PointingHandCursor)
    add_doc_btn.clicked.connect(app.new_document)

    add_folder_btn = QPushButton("Add folder")
    _fi = app._fa("fa5s.folder-plus")
    if not _fi.isNull():
        add_folder_btn.setIcon(_fi)
    add_folder_btn.setFixedHeight(22)
    add_folder_btn.setToolTip("New folder")
    add_folder_btn.setCursor(Qt.PointingHandCursor)
    add_folder_btn.clicked.connect(lambda: app.new_folder())

    import_btn = QPushButton("Import")
    _ii = app._fa("fa5s.file-import")
    if not _ii.isNull():
        import_btn.setIcon(_ii)
    import_btn.setFixedHeight(22)
    import_btn.setToolTip("Import a file from your system")
    import_btn.setCursor(Qt.PointingHandCursor)
    import_btn.clicked.connect(app.import_file)

    btn_row.addWidget(add_doc_btn)
    btn_row.addWidget(add_folder_btn)
    btn_row.addWidget(import_btn)
    btn_row.addStretch()
    dc.addLayout(btn_row)

    app.doc_search = QLineEdit()
    app.doc_search.setPlaceholderText("🔍 Search in all documents… (Enter)")
    app.doc_search.textChanged.connect(app._on_doc_search)
    app.doc_search.returnPressed.connect(app.run_content_search)
    dc.addWidget(app.doc_search)

    folder = app.settings["documents_folder"]
    app.fs_model = QFileSystemModel(app)
    app.fs_model.setRootPath(folder)
    app.fs_model.setNameFilters([f"*{e}" for e in docs.SUPPORTED_EXTS])
    app.fs_model.setNameFilterDisables(False)

    app.docs_tree = QTreeView()
    app.docs_tree.setModel(app.fs_model)
    app.docs_tree.setRootIndex(app.fs_model.index(folder))
    app.docs_tree.setHeaderHidden(True)
    app.docs_tree.setAnimated(False)
    app.docs_tree.setFont(QFont("Helvetica Neue", 10))
    app.docs_tree.setTextElideMode(Qt.ElideMiddle)  # long names stay visible
    for column_idx in (1, 2, 3):  # hide size/type/date — names only
        app.docs_tree.setColumnHidden(column_idx, True)
    app.docs_tree.setColumnWidth(0, 220)
    app.docs_tree.clicked.connect(app._on_doc_tree_clicked)
    app.docs_tree.setContextMenuPolicy(Qt.CustomContextMenu)
    app.docs_tree.customContextMenuRequested.connect(app._docs_context_menu)

    # Inline rename: double-click a name to edit it in place (Esc cancels)
    from PyQt5.QtWidgets import QAbstractItemView
    app.docs_tree.setEditTriggers(QAbstractItemView.DoubleClicked)
    app.fs_model.fileRenamed.connect(app._on_file_renamed)

    dc.addWidget(app.docs_tree)

    # ---- Speech history card ----
    hist_card = app._make_card()
    hc = QVBoxLayout(hist_card)
    hc.setContentsMargins(14, 14, 14, 14)
    hc.setSpacing(8)
    t2 = QLabel("🕘  SPEECH HISTORY")
    t2.setObjectName("sectionTitle")
    t2.setFont(QFont("Helvetica Neue", 11, QFont.Bold))
    hc.addWidget(t2)
    app.history_list = QListWidget()
    app.history_list.setFont(QFont("Helvetica Neue", 10))
    app.history_list.itemClicked.connect(app.load_history_item)
    app.history_list.setContextMenuPolicy(Qt.CustomContextMenu)
    app.history_list.customContextMenuRequested.connect(app._history_context_menu)
    hc.addWidget(app.history_list)

    lay.addWidget(docs_card, 3)
    lay.addWidget(hist_card, 2)
    return col


def build_speech_panel(app):
    """Right panel: mic start/stop, live speech→text, TTS, Claude optimize."""
    card = app._make_card()
    card.setMinimumWidth(240)
    card.setMaximumWidth(480)  # resizable via the body splitter
    lay = QVBoxLayout(card)
    lay.setContentsMargins(14, 14, 14, 14)
    lay.setSpacing(8)

    title = QLabel("🎙️  SPEECH")
    title.setObjectName("sectionTitle")
    title.setFont(QFont("Helvetica Neue", 11, QFont.Bold))
    lay.addWidget(title)

    app.dictate_btn = QPushButton("Start")
    app.dictate_btn.setFont(QFont("Helvetica Neue", 11, QFont.Bold))
    app.dictate_btn.setCursor(Qt.PointingHandCursor)
    app.dictate_btn.setEnabled(False)  # until Whisper loads
    app.dictate_btn.clicked.connect(app.toggle_dictation)
    app._set_dictate_style(False)
    lay.addWidget(app.dictate_btn)

    speak_row = QHBoxLayout()
    speak_row.setContentsMargins(2, 0, 0, 0)
    app.speaking_icon_label = QLabel("🗣️ Dictating…")
    app.speaking_icon_label.setFont(QFont("Helvetica Neue", 11, QFont.Bold))
    app.speaking_icon_label.setStyleSheet("color: #FF9800;")
    app.speaking_icon_label.setVisible(False)
    speak_row.addWidget(app.speaking_icon_label)
    app.timer_label = QLabel("⏱ 00:00")
    app.timer_label.setFont(QFont("Helvetica Neue", 11, QFont.Bold))
    app.timer_label.setStyleSheet("color: #FF9800;")
    app.timer_label.setVisible(False)
    speak_row.addSpacing(10)
    speak_row.addWidget(app.timer_label)
    speak_row.addStretch()
    lay.addLayout(speak_row)

    # Mini dictation waveform (bars follow the mic level)
    app.waveform = WaveformWidget()
    lay.addWidget(app.waveform)

    from PyQt5.QtCore import QTimer
    app.rec_timer = QTimer(app)
    app.rec_timer.setInterval(500)
    app.rec_timer.timeout.connect(app._update_rec_timer)

    stt_title = QLabel("SPEECH → TEXT")
    stt_title.setObjectName("sectionTitle")
    stt_title.setFont(QFont("Helvetica Neue", 10, QFont.Bold))
    lay.addWidget(stt_title)
    app.stt_display = QTextEdit()
    app.stt_display.setReadOnly(True)
    app.stt_display.setFont(QFont("Helvetica Neue", 10))
    app.stt_display.setFrameShape(QTextEdit.NoFrame)
    app.stt_display.setPlaceholderText("Live transcription appears here while dictating…")
    lay.addWidget(app.stt_display, 1)

    tts_row = QHBoxLayout()
    tts_row.addWidget(app._tool_btn("🔊 Read", "Read selection / document aloud (TTS)", app.read_aloud))
    tts_row.addWidget(app._tool_btn("⏹ Stop", "Stop reading", app.tts.stop))
    tts_row.addStretch()
    lay.addLayout(tts_row)

    claude_title = QLabel("✨  OPTIMIZE (CLAUDE)")
    claude_title.setObjectName("sectionTitle")
    claude_title.setFont(QFont("Helvetica Neue", 11, QFont.Bold))
    lay.addWidget(claude_title)

    app.optimize_btn = QPushButton("Optimize with Claude")
    app.optimize_btn.setIcon(app._fa("fa5s.magic"))
    app.optimize_btn.setObjectName("primaryBtn")
    app.optimize_btn.setCursor(Qt.PointingHandCursor)
    app.optimize_btn.setToolTip("Optimizes the speech→text above with Claude")
    app.optimize_btn.clicked.connect(app.optimize_speech_text)
    lay.addWidget(app.optimize_btn)

    app.optimize_display = QTextEdit()
    app.optimize_display.setReadOnly(True)
    app.optimize_display.setFont(QFont("Helvetica Neue", 10))
    app.optimize_display.setFrameShape(QTextEdit.NoFrame)
    app.optimize_display.setPlaceholderText(
        "Optimized version of your speech text appears here…"
    )
    lay.addWidget(app.optimize_display, 1)

    # Result actions: copy / insert at cursor / replace selection
    opt_actions = QHBoxLayout()
    opt_actions.addWidget(app._tool_btn("Copy", "Copy optimized text to clipboard", app.copy_optimized))
    opt_actions.addWidget(app._tool_btn("Insert", "Insert optimized text at cursor", app.insert_optimized))
    opt_actions.addWidget(app._tool_btn("Replace", "Replace selection with optimized text", app.replace_with_optimized))
    opt_actions.addStretch()
    lay.addLayout(opt_actions)

    return card
