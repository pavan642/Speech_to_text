# main.py — TextIQ: dictation + rich documents + Claude integration
import logging
import os
import queue
import re
import shutil
import subprocess
import sys
import threading
import time
import urllib.request
import warnings
from datetime import datetime

# Suppress harmless NumPy warnings
warnings.filterwarnings("ignore", category=RuntimeWarning, module="numpy")

import numpy as np
from PyQt5.QtCore import (
    QIdentityProxyModel,
    QModelIndex,
    QObject,
    QRect,
    Qt,
    QTimer,
    pyqtSignal,
    pyqtSlot,
)
from PyQt5.QtGui import (
    QColor,
    QFont,
    QIcon,
    QKeySequence,
    QPainter,
    QPen,
    QPixmap,
    QRegion,
    QTextCharFormat,
    QTextCursor,
    QTextDocument,
    QTextDocumentWriter,
    QTextListFormat,
)
from PyQt5.QtWidgets import (
    QApplication,
    QCheckBox,
    QColorDialog,
    QComboBox,
    QDialog,
    QFileDialog,
    QFileSystemModel,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QGridLayout,
    QMenu,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QShortcut,
    QSplitter,
    QTabBar,
    QTextEdit,
    QTreeView,
    QVBoxLayout,
    QWidget,
    QDateTimeEdit,
)
from PyQt5.QtCore import QDateTime
from PyQt5.QtPrintSupport import QPrinter
import sounddevice as sd

import config
import documents_manager as docs
import git_manager
import history_manager
import reminders_manager
import settings_manager
from models import SpeechModels
from tts_manager import TextToSpeech
from ui.pane import EditorPane
from ui.sidebar import build_left_column, build_speech_panel
from ui.toolbar import build_tools_row, build_toolbar

# Configure Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("SpeechEditor")

# Queue marker: "recording stopped — everything before this is the full session"
_FLUSH = object()


class ClaudeWorker(QObject):
    """Runs a Claude text-optimization call in a background thread.
    finished carries (purpose, result): 'editor' or 'panel'."""
    finished = pyqtSignal(str, str)
    error = pyqtSignal(str)

    def __init__(self, speech_models, text, api_key, model, purpose, system_prompt=""):
        super().__init__()
        self.speech_models = speech_models
        self.text = text
        self.api_key = api_key
        self.model = model
        self.purpose = purpose
        self.system_prompt = system_prompt

    def run(self):
        try:
            result = self.speech_models.optimize_with_claude(
                self.text, self.api_key, self.model, self.system_prompt
            )
            self.finished.emit(self.purpose, result or "")
        except Exception as e:
            logger.error(f"Claude optimization failed: {e}", exc_info=True)
            self.error.emit(f"Claude optimization failed: {e}")


class MicLevelIndicator(QWidget):
    """Draggable circular mic indicator (~2 cm across), centered by default.

    Fills with green from the bottom up, tracking the live microphone level.
    Shown only while dictating; drag with the mouse to reposition it anywhere.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        dpi = self.logicalDpiX() or 72
        diameter = max(48, round(dpi * 2 / 2.54))  # 2 cm in logical pixels
        self.setFixedSize(diameter, diameter)
        self._level = 0
        self._drag_offset = None
        self.user_moved = False
        self.setCursor(Qt.OpenHandCursor)
        self.setToolTip("Recording level — drag to move")
        self.hide()

    def set_level(self, level: int):
        self._level = max(0, min(100, int(level)))
        self.update()

    def center_on_parent(self):
        if self.parent():
            area = self.parent().rect()
            self.move(
                (area.width() - self.width()) // 2,
                (area.height() - self.height()) // 2,
            )
            self.user_moved = False

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        rect = self.rect().adjusted(2, 2, -2, -2)

        painter.setPen(QPen(QColor("#4CAF50"), 3))
        painter.setBrush(QColor(40, 40, 40, 170))
        painter.drawEllipse(rect)

        if self._level > 0:
            fill_h = rect.height() * self._level // 100
            painter.setClipRegion(QRegion(rect, QRegion.Ellipse))
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(76, 175, 80, 220))
            painter.drawRect(
                QRect(rect.left(), rect.bottom() - fill_h + 1, rect.width(), fill_h)
            )
            painter.setClipping(False)

        w, h = self.width(), self.height()
        cx = w // 2
        painter.setPen(QPen(QColor("#FFFFFF"), max(2, w // 26), Qt.SolidLine, Qt.RoundCap))
        painter.setBrush(QColor("#FFFFFF"))
        bw, bh = int(w * 0.20), int(h * 0.32)
        painter.drawRoundedRect(cx - bw // 2, int(h * 0.15), bw, bh, bw / 2, bw / 2)
        painter.setBrush(Qt.NoBrush)
        painter.drawArc(
            int(w * 0.26), int(h * 0.28), int(w * 0.48), int(h * 0.42), 180 * 16, 180 * 16
        )
        painter.drawLine(cx, int(h * 0.70), cx, int(h * 0.82))
        painter.drawLine(cx - int(w * 0.13), int(h * 0.82), cx + int(w * 0.13), int(h * 0.82))
        painter.end()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._drag_offset = event.globalPos() - self.frameGeometry().topLeft()
            self.setCursor(Qt.ClosedHandCursor)

    def mouseMoveEvent(self, event):
        if self._drag_offset is not None and event.buttons() & Qt.LeftButton:
            self.move(event.globalPos() - self._drag_offset)
            self.user_moved = True

    def mouseReleaseEvent(self, event):
        self._drag_offset = None
        self.setCursor(Qt.OpenHandCursor)


class SettingsDialog(QDialog):
    """Modal dialog: Claude API, documents folder, speech recognition, theme."""

    def __init__(self, current_settings: dict, parent=None):
        super().__init__(parent)
        self.setWindowTitle("⚙️ Settings")
        self.setMinimumWidth(520)
        self.setModal(True)

        layout = QVBoxLayout()
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # --- Claude API ---
        claude_group = QGroupBox("Claude API (Anthropic)")
        claude_layout = QVBoxLayout()

        info = QLabel(
            'Get your key from <a href="https://console.anthropic.com/">console.anthropic.com</a>. '
            'Claude optimizes your dictated and written text.'
        )
        info.setOpenExternalLinks(True)
        info.setWordWrap(True)
        claude_layout.addWidget(info)

        claude_layout.addWidget(QLabel("API Key:"))
        self.api_key_input = QLineEdit()
        self.api_key_input.setEchoMode(QLineEdit.Password)
        self.api_key_input.setPlaceholderText("sk-ant-...")
        self.api_key_input.setText(current_settings.get("claude_api_key", ""))
        claude_layout.addWidget(self.api_key_input)

        self.show_key_checkbox = QCheckBox("Show API key")
        self.show_key_checkbox.toggled.connect(
            lambda c: self.api_key_input.setEchoMode(
                QLineEdit.Normal if c else QLineEdit.Password
            )
        )
        claude_layout.addWidget(self.show_key_checkbox)

        claude_layout.addWidget(QLabel("Model:"))
        self.model_combo = QComboBox()
        self.model_combo.setEditable(True)
        self.model_combo.addItems(config.CLAUDE_MODEL_OPTIONS)
        self.model_combo.setCurrentText(
            current_settings.get("claude_model", config.CLAUDE_MODEL)
        )
        claude_layout.addWidget(self.model_combo)

        claude_group.setLayout(claude_layout)
        layout.addWidget(claude_group)

        # --- Documents ---
        docs_group = QGroupBox("Documents")
        docs_layout = QVBoxLayout()
        docs_layout.addWidget(QLabel("Folder where documents are stored:"))

        folder_row = QHBoxLayout()
        self.folder_input = QLineEdit()
        self.folder_input.setText(
            current_settings.get("documents_folder", config.DEFAULT_DOCUMENTS_FOLDER)
        )
        browse_btn = QPushButton("📁 Browse…")
        browse_btn.clicked.connect(self._browse_folder)
        folder_row.addWidget(self.folder_input, 1)
        folder_row.addWidget(browse_btn)
        docs_layout.addLayout(folder_row)

        docs_layout.addWidget(QLabel("Default format for new documents:"))
        self.doc_format_combo = QComboBox()
        self.doc_format_combo.addItems(["Markdown (.md)", "HTML (.html)", "Plain text (.txt)"])
        current_ext = current_settings.get("doc_extension", ".md")
        self.doc_format_combo.setCurrentIndex(
            {".md": 0, ".html": 1, ".txt": 2}.get(current_ext, 0)
        )
        docs_layout.addWidget(self.doc_format_combo)

        docs_group.setLayout(docs_layout)
        layout.addWidget(docs_group)

        # --- Git Integration ---
        git_group = QGroupBox("Git Integration")
        git_layout = QVBoxLayout()

        git_layout.addWidget(QLabel("Remote URL (embed a token for HTTPS, or use SSH):"))
        self.git_url_input = QLineEdit()
        self.git_url_input.setPlaceholderText("https://<token>@github.com/you/repo.git")
        self.git_url_input.setText(current_settings.get("git_remote_url", ""))
        git_layout.addWidget(self.git_url_input)

        git_layout.addWidget(QLabel("Branch:"))
        self.git_branch_input = QLineEdit()
        self.git_branch_input.setText(current_settings.get("git_branch", "main"))
        git_layout.addWidget(self.git_branch_input)

        git_note = QLabel(
            "The ⬆ Push button commits and pushes ALL files in the app folder "
            "(settings.json and history/ are git-ignored)."
        )
        git_note.setWordWrap(True)
        git_layout.addWidget(git_note)

        git_group.setLayout(git_layout)
        layout.addWidget(git_group)

        # --- Speech Recognition ---
        stt_group = QGroupBox("Speech Recognition")
        stt_layout = QVBoxLayout()

        stt_layout.addWidget(QLabel("Whisper model (larger = more accurate, slower):"))
        self.whisper_combo = QComboBox()
        self.whisper_combo.addItems(config.WHISPER_MODEL_OPTIONS)
        self.whisper_combo.setCurrentText(
            current_settings.get("whisper_model", config.WHISPER_MODEL_NAME)
        )
        stt_layout.addWidget(self.whisper_combo)

        self.live_checkbox = QCheckBox("Live dictation while recording")
        self.live_checkbox.setChecked(current_settings.get("live_transcription", True))
        stt_layout.addWidget(self.live_checkbox)

        self.noise_checkbox = QCheckBox("Reduce background noise before transcription")
        self.noise_checkbox.setChecked(current_settings.get("noise_reduction", True))
        stt_layout.addWidget(self.noise_checkbox)

        stt_group.setLayout(stt_layout)
        layout.addWidget(stt_group)

        # --- Appearance ---
        theme_group = QGroupBox("Appearance")
        theme_layout = QHBoxLayout()
        self.light_radio = QRadioButton("☀️ Light")
        self.dark_radio = QRadioButton("🌙 Dark")
        if current_settings.get("theme", "light") == "dark":
            self.dark_radio.setChecked(True)
        else:
            self.light_radio.setChecked(True)
        theme_layout.addWidget(self.light_radio)
        theme_layout.addWidget(self.dark_radio)
        theme_layout.addStretch()
        theme_group.setLayout(theme_layout)
        layout.addWidget(theme_group)

        # --- Dialog buttons ---
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        save_btn = QPushButton("💾 Save")
        save_btn.setObjectName("primaryBtn")
        save_btn.setDefault(True)
        save_btn.clicked.connect(self.accept)
        btn_layout.addWidget(cancel_btn)
        btn_layout.addWidget(save_btn)
        layout.addLayout(btn_layout)

        self.setLayout(layout)

    def _browse_folder(self):
        chosen = QFileDialog.getExistingDirectory(
            self, "Choose documents folder", self.folder_input.text() or "."
        )
        if chosen:
            self.folder_input.setText(chosen)

    def get_settings(self) -> dict:
        return {
            "theme": "dark" if self.dark_radio.isChecked() else "light",
            "claude_api_key": self.api_key_input.text().strip(),
            "claude_model": self.model_combo.currentText().strip() or config.CLAUDE_MODEL,
            "whisper_model": self.whisper_combo.currentText(),
            "live_transcription": self.live_checkbox.isChecked(),
            "noise_reduction": self.noise_checkbox.isChecked(),
            "documents_folder": self.folder_input.text().strip()
            or config.DEFAULT_DOCUMENTS_FOLDER,
            "doc_extension": [".md", ".html", ".txt"][self.doc_format_combo.currentIndex()],
            "git_remote_url": self.git_url_input.text().strip(),
            "git_branch": self.git_branch_input.text().strip() or "main",
        }


class SpeechEditorApp(QWidget):
    level_changed = pyqtSignal(int)
    icon_fetched = pyqtSignal(QPixmap)
    partial_text = pyqtSignal(str)
    stream_drained = pyqtSignal()
    git_done = pyqtSignal(str)
    git_failed = pyqtSignal(str)

    VOICE_COMMANDS = {
        "new line": "\n",
        "new paragraph": "\n\n",
        "comma": ",",
        "period": ".",
        "full stop": ".",
        "question mark": "?",
        "exclamation mark": "!",
        "colon": ":",
        "semicolon": ";",
    }

    # Font Awesome (free) icons, matched by tooltip text — qtawesome renders them
    ICON_MAP = {
        "New document": "fa5s.file-medical",
        "Save document": "fa5s.save",
        "Delete document": "fa5s.trash-alt",
        "Undo": "fa5s.undo",
        "Redo": "fa5s.redo",
        "Bold": "fa5s.bold",
        "Italic": "fa5s.italic",
        "Underline": "fa5s.underline",
        "Strikethrough": "fa5s.strikethrough",
        "Text color": "fa5s.palette",
        "Highlight color": "fa5s.highlighter",
        "Bullet list": "fa5s.list-ul",
        "Numbered list": "fa5s.list-ol",
        "task checkbox": "fa5s.check-square",
        "Align left": "fa5s.align-left",
        "Align center": "fa5s.align-center",
        "Align right": "fa5s.align-right",
        "Justify": "fa5s.align-justify",
        "Code snippet": "fa5s.code",
        "Insert table": "fa5s.table",
        "Clear formatting": "fa5s.eraser",
        "Find in document": "fa5s.search",
        "Optimize selection": "fa5s.magic",
        "Export": "fa5s.file-export",
        "Split view": "fa5s.columns",
        "Commit & push": "fa5s.cloud-upload-alt",
        "Set a reminder": "fa5s.bell",
        "Read selection": "fa5s.volume-up",
        "Stop reading": "fa5s.stop-circle",
    }

    # The active editor pane drives the legacy self.editor / self.current_doc_path
    # accessors used throughout the formatting/toolbar code.
    @property
    def editor(self):
        return self.active_pane.editor if getattr(self, "active_pane", None) else None

    @property
    def current_doc_path(self):
        return self.active_pane.path if getattr(self, "active_pane", None) else None

    @current_doc_path.setter
    def current_doc_path(self, value):
        if getattr(self, "active_pane", None):
            self.active_pane.path = value

    def __init__(self):
        super().__init__()
        self.is_recording = False
        self.audio_frames = []
        self._buffered_samples = 0
        self._overlap_tail = None
        self._last_chunk_text = ""
        self.frames_lock = threading.Lock()
        self.session_raw_parts = []
        self.rec_start_ts = None

        # Editor panes (split view) — created in init_ui
        self.pane1 = None
        self.pane2 = None
        self.active_pane = None
        self._opt_had_selection = False

        # Debounced auto-save (2.5s after typing stops)
        self.autosave_timer = QTimer(self)
        self.autosave_timer.setSingleShot(True)
        self.autosave_timer.setInterval(2500)
        self.autosave_timer.timeout.connect(self._autosave_now)

        # Throttled word count (500ms — avoids recounting on every keystroke)
        self.word_count_timer = QTimer(self)
        self.word_count_timer.setSingleShot(True)
        self.word_count_timer.setInterval(500)
        self.word_count_timer.timeout.connect(self._update_word_count)

        # Document reminders — checked every 30s
        self.reminder_timer = QTimer(self)
        self.reminder_timer.setInterval(30000)
        self.reminder_timer.timeout.connect(self._check_reminders)
        self.reminder_timer.start()

        # Font Awesome icon provider (qtawesome, lazy-imported)
        self._qta = None

        self.speech_models = SpeechModels()
        self.tts = TextToSpeech()
        self.settings = settings_manager.load_settings()

        # Persistent live-transcription pipeline (one thread -> strict ordering)
        self.stream_queue = queue.Queue()
        threading.Thread(
            target=self._stream_transcriber, daemon=True, name="StreamTranscriber"
        ).start()

        self.init_ui()
        self.set_app_icon()
        self.apply_theme(self.settings.get("theme", "light"))

        self.level_indicator = MicLevelIndicator(self)
        self.level_changed.connect(self.level_indicator.set_level)
        self.icon_fetched.connect(self._apply_fetched_icon)
        self.partial_text.connect(self.on_partial_text)
        self.stream_drained.connect(self.on_stream_drained)
        self.git_done.connect(self.on_git_done)
        self.git_failed.connect(self.on_git_failed)

        docs.ensure_folder(self.settings["documents_folder"])
        self.refresh_docs()
        self._refresh_history()

        threading.Thread(
            target=self.load_initial_models, daemon=True, name="ModelLoader"
        ).start()

    # -------------------- Theming & icon --------------------

    def apply_theme(self, theme_name: str):
        app = QApplication.instance()
        app.setStyleSheet(config.DARK_THEME if theme_name == "dark" else config.LIGHT_THEME)

    def set_app_icon(self):
        for name in ("app_icon.png", "app_icon.jpg", "icon.png"):
            if os.path.exists(name):
                self.setWindowIcon(QIcon(name))
                return
        self.setWindowIcon(QIcon(self._draw_mic_icon()))
        threading.Thread(
            target=self._fetch_icon_from_url, daemon=True, name="IconLoader"
        ).start()

    def _fetch_icon_from_url(self):
        try:
            req = urllib.request.Request(
                config.APP_ICON_URL, headers={"User-Agent": "Mozilla/5.0"}
            )
            data = urllib.request.urlopen(req, timeout=5).read()
            pixmap = QPixmap()
            pixmap.loadFromData(data)
            if not pixmap.isNull():
                self.icon_fetched.emit(pixmap)
        except Exception as e:
            logger.warning(f"Failed to load window icon from URL: {e}")

    @pyqtSlot(QPixmap)
    def _apply_fetched_icon(self, pixmap):
        self.setWindowIcon(QIcon(pixmap))

    @staticmethod
    def _draw_mic_icon() -> QPixmap:
        pixmap = QPixmap(64, 64)
        pixmap.fill(Qt.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)
        color = QColor("#4CAF50")
        painter.setBrush(color)
        painter.setPen(Qt.NoPen)
        painter.drawRoundedRect(24, 6, 16, 30, 8, 8)
        painter.setBrush(Qt.NoBrush)
        painter.setPen(QPen(color, 4, Qt.SolidLine, Qt.RoundCap))
        painter.drawArc(16, 20, 32, 32, 180 * 16, 180 * 16)
        painter.drawLine(32, 52, 32, 58)
        painter.drawLine(22, 58, 42, 58)
        painter.end()
        return pixmap

    # -------------------- Settings --------------------

    def open_settings(self):
        dialog = SettingsDialog(self.settings, self)
        if dialog.exec_() != QDialog.Accepted:
            return

        old_model = self.settings.get("whisper_model", config.WHISPER_MODEL_NAME)
        old_folder = self.settings.get("documents_folder", config.DEFAULT_DOCUMENTS_FOLDER)
        self.settings = dialog.get_settings()
        settings_manager.save_settings(self.settings)
        self.apply_theme(self.settings["theme"])
        self.status_label.setText("Config updated")
        self._refresh_status_items()

        new_model = self.settings.get("whisper_model", config.WHISPER_MODEL_NAME)
        if new_model != old_model:
            self.speech_models.set_whisper_model(new_model)
            self.status_label.setText(f"Loading Whisper ({new_model})…")
            self.dictate_btn.setEnabled(False)
            threading.Thread(
                target=self.load_initial_models, daemon=True, name="ModelLoader"
            ).start()

        new_folder = self.settings.get("documents_folder", config.DEFAULT_DOCUMENTS_FOLDER)
        if new_folder != old_folder:
            docs.ensure_folder(new_folder)
            self.current_doc_path = None
            self.editor.clear()
            self.doc_name_label.setText("No document")
            self.refresh_docs()

    # -------------------- UI construction --------------------

    def _fa(self, name: str) -> QIcon:
        """Font Awesome icon via qtawesome (lazy; empty QIcon if unavailable)."""
        if self._qta is None:
            try:
                import qtawesome as qta
                self._qta = qta
            except Exception:
                self._qta = False
        if self._qta:
            try:
                return self._qta.icon(name)
            except Exception:
                pass
        return QIcon()

    def _tool_btn(self, text, tooltip, handler, checkable=False):
        # Apply a Font Awesome icon matched by the tooltip, if available
        icon = QIcon()
        for key, fa_name in self.ICON_MAP.items():
            if key in tooltip:
                icon = self._fa(fa_name)
                break
        if not icon.isNull():
            # Drop a leading emoji when we have a real icon for it
            if text and ord(text[0]) > 127 and " " in text:
                text = text.split(" ", 1)[1]
            # Single-letter style buttons (B/I/U/S, arrows) become icon-only
            if len(text.strip()) == 1 or text.strip() in ("↶", "↷", "⇤", "☰", "⇥", "≣"):
                text = ""
        btn = QPushButton(text)
        if not icon.isNull():
            btn.setIcon(icon)
        btn.setToolTip(tooltip)
        btn.setCursor(Qt.PointingHandCursor)
        btn.setFont(QFont("Helvetica Neue", 10, QFont.Bold))
        btn.clicked.connect(handler)
        if checkable:
            btn.setCheckable(True)
        return btn

    def _make_card(self, object_name: str = "panel"):
        """Flat IDE-style panel — squared edges, no shadows (VS Code look)."""
        panel = QFrame()
        panel.setObjectName(object_name)
        return panel

    def init_ui(self):
        self.setWindowTitle(config.APP_TITLE)
        self.resize(config.WINDOW_WIDTH, config.WINDOW_HEIGHT)

        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # 1. Top bar + tools row (built in ui/toolbar.py)
        build_toolbar(self, main_layout)
        build_tools_row(self, main_layout)

        # 3. Body: left (documents + history) · center (editor) · right (speech + Claude)
        body_row = QHBoxLayout()
        body_row.setContentsMargins(10, 0, 10, 8)
        body_row.setSpacing(8)

        body_row.addWidget(build_left_column(self))

        # Center: one or two editor panes side by side (split view)
        center = self._make_card("editorArea")
        cl = QVBoxLayout(center)
        cl.setContentsMargins(0, 0, 0, 0)
        cl.setSpacing(0)
        self.panes_splitter = QSplitter(Qt.Horizontal)
        self.panes_splitter.setChildrenCollapsible(False)
        self.pane1 = EditorPane(self)
        self.panes_splitter.addWidget(self.pane1)
        self.active_pane = self.pane1
        cl.addWidget(self.panes_splitter)
        body_row.addWidget(center, 1)

        # Keyboard shortcuts
        QShortcut(QKeySequence(QKeySequence.Find), self, activated=self.show_find)
        QShortcut(QKeySequence(QKeySequence.Bold), self, activated=self.toggle_bold)
        QShortcut(QKeySequence(QKeySequence.Italic), self, activated=self.toggle_italic)
        QShortcut(QKeySequence(QKeySequence.Underline), self, activated=self.toggle_underline)
        QShortcut(QKeySequence(QKeySequence.Save), self, activated=self.save_document)
        QShortcut(QKeySequence(QKeySequence.New), self, activated=lambda: self.new_document(self.active_pane))
        QShortcut(QKeySequence(QKeySequence.Close), self, activated=self.close_current_tab)
        QShortcut(QKeySequence("Ctrl+Shift+S"), self, activated=self.toggle_split_view)

        body_row.addWidget(build_speech_panel(self))

        main_layout.addLayout(body_row, 1)

        # 4. Bottom status bar (IDE style)
        status_bar = QFrame()
        status_bar.setObjectName("statusBar")
        status_bar.setFixedHeight(24)
        sb = QHBoxLayout(status_bar)
        sb.setContentsMargins(10, 0, 10, 0)
        sb.setSpacing(16)
        self.status_label = QLabel("Loading Whisper model…")
        self.status_label.setObjectName("statusBarItem")
        sb.addWidget(self.status_label)
        sb.addStretch()
        self.status_words_label = QLabel("0 words · 0 chars")
        self.status_words_label.setObjectName("statusBarItem")
        sb.addWidget(self.status_words_label)
        self.status_model_label = QLabel()
        self.status_model_label.setObjectName("statusBarItem")
        self.status_git_label = QLabel()
        self.status_git_label.setObjectName("statusBarItem")
        sb.addWidget(self.status_model_label)
        sb.addWidget(self.status_git_label)
        main_layout.addWidget(status_bar)

        self._refresh_status_items()

        # Root layout with outer margins
        content = QWidget()
        content.setLayout(main_layout)
        root = QVBoxLayout()
        root.setContentsMargins(0, 0, 0, 0)
        root.addWidget(content)
        self.setLayout(root)

    def _refresh_history(self):
        """Reloads the history list from the history/ folder (newest first)."""
        self.history_list.clear()
        for path in history_manager.list_sessions():
            name = os.path.basename(path)
            ts = name.replace("transcription_", "").replace(".md", "")
            try:
                label = datetime.strptime(ts, "%Y%m%d_%H%M%S").strftime("%b %d · %H:%M:%S")
            except ValueError:
                label = name
            item = QListWidgetItem(label)
            item.setData(Qt.UserRole, path)
            item.setToolTip(path)
            self.history_list.addItem(item)

    def load_history_item(self, item):
        """Opens a past dictation session as a read-only tab."""
        path = item.data(Qt.UserRole)
        try:
            raw, _optimized = history_manager.load_session(path)
        except Exception as e:
            logger.error(f"Failed to load session: {e}", exc_info=True)
            QMessageBox.critical(self, "Error", f"Failed to load session: {e}")
            return
        pane = self.active_pane
        self.save_pane(pane)
        title = "🕘 " + item.text()
        meta = {"history": True, "content": raw, "title": title}
        pane.tabs.blockSignals(True)
        idx = pane.tabs.addTab(title)
        pane.tabs.setTabData(idx, meta)
        pane.tabs.blockSignals(False)

        x_btn = QPushButton("✕")
        x_btn.setFixedSize(16, 16)
        x_btn.setToolTip("Close tab")
        x_btn.setCursor(Qt.PointingHandCursor)
        x_btn.setStyleSheet("border: none; color: #9D9D9D; font-size: 11px; padding: 0;")
        x_btn.clicked.connect(lambda _=False, m=meta, pn=pane: self._close_tab_by_meta(pn, m))
        pane.tabs.setTabButton(idx, QTabBar.RightSide, x_btn)

        pane.tabs.setCurrentIndex(idx)

    def _refresh_status_items(self):
        """Right side of the status bar: active Whisper model + git branch."""
        self.status_model_label.setText(
            "🧠 " + self.settings.get("whisper_model", config.WHISPER_MODEL_NAME)
        )
        self.status_git_label.setText(
            "⎇ " + (self.settings.get("git_branch") or "main")
        )

    def _set_dictate_style(self, recording: bool):
        if recording:
            self.dictate_btn.setText("Stop")
            self.dictate_btn.setIcon(self._fa("fa5s.stop-circle"))
            self.dictate_btn.setStyleSheet(
                "QPushButton { background-color: #A1260D; color: white; padding: 8px;"
                " border-radius: 3px; border: none; font-weight: bold; }"
                "QPushButton:hover { background-color: #B62D12; }"
            )
        else:
            self.dictate_btn.setText("Start")
            self.dictate_btn.setIcon(self._fa("fa5s.microphone"))
            self.dictate_btn.setStyleSheet(
                "QPushButton { background-color: #388A34; color: white; padding: 8px;"
                " border-radius: 3px; border: none; font-weight: bold; }"
                "QPushButton:hover { background-color: #42A03D; }"
                "QPushButton:disabled { background-color: #3C3C3C; color: #9D9D9D; }"
            )

    # -------------------- Formatting actions --------------------

    def toggle_bold(self):
        fmt = QTextCharFormat()
        fmt.setFontWeight(QFont.Normal if self.editor.fontWeight() >= QFont.Bold else QFont.Bold)
        self.editor.mergeCurrentCharFormat(fmt)
        self.editor.setFocus()

    def toggle_italic(self):
        fmt = QTextCharFormat()
        fmt.setFontItalic(not self.editor.fontItalic())
        self.editor.mergeCurrentCharFormat(fmt)
        self.editor.setFocus()

    def toggle_underline(self):
        fmt = QTextCharFormat()
        fmt.setFontUnderline(not self.editor.fontUnderline())
        self.editor.mergeCurrentCharFormat(fmt)
        self.editor.setFocus()

    def toggle_strikethrough(self):
        fmt = QTextCharFormat()
        fmt.setFontStrikeOut(not self.editor.currentCharFormat().fontStrikeOut())
        self.editor.mergeCurrentCharFormat(fmt)
        self.editor.setFocus()

    def apply_heading(self, level: int):
        fmt = QTextCharFormat()
        fmt.setFontWeight(QFont.Bold)
        fmt.setFontPointSize({1: 18, 2: 15, 3: 13}[level])
        self.editor.mergeCurrentCharFormat(fmt)
        self.editor.setFocus()

    def _apply_font_size(self):
        try:
            size = float(self.font_size_combo.currentText())
        except ValueError:
            return
        fmt = QTextCharFormat()
        fmt.setFontPointSize(size)
        self.editor.mergeCurrentCharFormat(fmt)
        self.editor.setFocus()

    def pick_text_color(self):
        color = QColorDialog.getColor(parent=self, title="Text color")
        if color.isValid():
            fmt = QTextCharFormat()
            fmt.setForeground(color)
            self.editor.mergeCurrentCharFormat(fmt)
        self.editor.setFocus()

    def pick_highlight_color(self):
        color = QColorDialog.getColor(parent=self, title="Highlight color")
        if color.isValid():
            fmt = QTextCharFormat()
            fmt.setBackground(color)
            self.editor.mergeCurrentCharFormat(fmt)
        self.editor.setFocus()

    def toggle_list(self, numbered: bool):
        """Toggles bullet/numbered list on the current block."""
        cursor = self.editor.textCursor()
        if cursor.block().textList():
            fmt = cursor.blockFormat()
            fmt.setObjectIndex(-1)  # detach from the list
            cursor.setBlockFormat(fmt)
        else:
            style = QTextListFormat.ListDecimal if numbered else QTextListFormat.ListDisc
            cursor.createList(style)
        self.editor.setFocus()

    def align(self, alignment):
        self.editor.setAlignment(alignment)
        self.editor.setFocus()

    def clear_formatting(self):
        dark = self.settings.get("theme") == "dark"
        fmt = QTextCharFormat()
        fmt.setFontFamily("Helvetica Neue")
        fmt.setFontPointSize(12)
        fmt.setFontWeight(QFont.Normal)
        fmt.setFontItalic(False)
        fmt.setFontUnderline(False)
        fmt.setFontStrikeOut(False)
        fmt.setForeground(QColor("#D4D4D4" if dark else "#1F1F1F"))
        fmt.setBackground(Qt.transparent)
        self.editor.mergeCurrentCharFormat(fmt)
        self.editor.setFocus()

    # -------------------- Find in document --------------------

    def show_find(self):
        if self.active_pane:
            self.active_pane.show_find()

    def find_next(self):
        if self.active_pane:
            self.active_pane.find_next()

    def find_prev(self):
        if self.active_pane:
            self.active_pane.find_prev()

    # -------------------- Word count / format state --------------------

    def _schedule_word_count(self):
        """Called per keystroke — restarts the 500ms throttle timer."""
        self.word_count_timer.start()

    def _update_word_count(self):
        if not self.active_pane:
            return
        text = self.active_pane.editor.toPlainText()
        self.status_words_label.setText(f"{len(text.split())} words · {len(text)} chars")

    _FMT_BASE = {
        "bold": "font-weight: 900;",
        "italic": "font-style: italic;",
        "underline": "text-decoration: underline;",
    }

    def _update_format_state(self, pane=None):
        pane = pane or self.active_pane
        if not pane:
            return
        fmt = pane.editor.currentCharFormat()
        for btn, key, on in (
            (self.bold_btn, "bold", fmt.fontWeight() >= QFont.Bold),
            (self.italic_btn, "italic", fmt.fontItalic()),
            (self.underline_btn, "underline", fmt.fontUnderline()),
        ):
            style = self._FMT_BASE[key]
            if on:
                style += " background-color: #007ACC; color: white; border-radius: 3px;"
            btn.setStyleSheet(style)

    # -------------------- Markdown-style auto-formatting --------------------

    def _maybe_markdown_autofmt(self, pane):
        """Notion-style transforms while typing:
        '# '→H1, '## '→H2, '### '→H3, '- '→bullet list, '[] '→☐ task."""
        editor = pane.editor
        cursor = editor.textCursor()
        if cursor.hasSelection():
            return
        block_text = cursor.block().text()

        def _clear_line():
            c = editor.textCursor()
            c.movePosition(QTextCursor.StartOfBlock)
            c.movePosition(QTextCursor.EndOfBlock, QTextCursor.KeepAnchor)
            c.insertText("")
            return c

        m = re.match(r"^(#{1,3})\s$", block_text)
        if m:
            fmt = QTextCharFormat()
            fmt.setFontWeight(QFont.Bold)
            fmt.setFontPointSize({1: 18, 2: 15, 3: 13}[len(m.group(1))])
            editor.blockSignals(True)
            c = _clear_line()
            c.mergeCurrentCharFormat(fmt)
            editor.blockSignals(False)
            pane._on_text_changed()
            return

        if re.match(r"^-\s$", block_text):
            editor.blockSignals(True)
            c = _clear_line()
            c.createList(QTextListFormat.ListDisc)
            editor.blockSignals(False)
            pane._on_text_changed()
            return

        if re.match(r"^\[\s?\]\s$", block_text):
            editor.blockSignals(True)
            c = _clear_line()
            c.insertText("☐ ")
            editor.blockSignals(False)
            pane._on_text_changed()

    # -------------------- Voice commands --------------------

    def _apply_voice_commands(self, text: str) -> str:
        """'new line' / 'comma' / 'period' … become real punctuation."""
        pattern = r"\b(" + "|".join(
            re.escape(k) for k in sorted(self.VOICE_COMMANDS, key=len, reverse=True)
        ) + r")\b"
        text = re.sub(
            pattern,
            lambda m: self.VOICE_COMMANDS[m.group(1).lower()],
            text,
            flags=re.IGNORECASE,
        )
        return re.sub(r"\s+([,.!?;:])", r"\1", text)  # no space before punctuation

    # -------------------- Split view --------------------

    def toggle_split_view(self):
        if self.pane2 is None:
            self.pane2 = EditorPane(self, closable=True)
            self.panes_splitter.addWidget(self.pane2)
            self.panes_splitter.setSizes([1, 1])
            self._activate_pane(self.pane2)
            self.status_label.setText("Split view on")
        else:
            self.save_pane(self.pane2)
            closing = self.pane2
            self.pane2 = None
            if self.active_pane is closing:
                self.active_pane = self.pane1
            closing.setParent(None)
            closing.deleteLater()
            self._activate_pane(self.pane1)
            self.status_label.setText("Split view off")

    # -------------------- Export --------------------

    def export_document(self):
        """Toolbar: export the document open in the active editor pane."""
        if not self.active_pane:
            return
        default = docs.display_name(self.active_pane.path) if self.active_pane.path else "document"
        self._export_content(
            self.active_pane.editor.toPlainText(),
            self.active_pane.editor.document(),
            default,
        )

    def export_document_path(self, path: str):
        """Per-file export (documents tree action button)."""
        try:
            content = docs.read_document(path)
        except Exception as e:
            logger.error(f"Failed to read document: {e}", exc_info=True)
            QMessageBox.critical(self, "Error", f"Failed to read document: {e}")
            return
        doc = QTextDocument()
        if path.lower().endswith(".html"):
            doc.setHtml(content)
        else:
            doc.setPlainText(content)
        self._export_content(doc.toPlainText(), doc, docs.display_name(path))

    def _export_content(self, plain_text: str, text_document, default_name: str):
        if not plain_text.strip():
            self.status_label.setText("Nothing to export")
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Export document", default_name,
            "Markdown (*.md);;Plain text (*.txt);;PDF (*.pdf)",
        )
        if not path:
            return
        try:
            lower = path.lower()
            if lower.endswith(".pdf"):
                printer = QPrinter(QPrinter.HighResolution)
                printer.setOutputFormat(QPrinter.PdfFormat)
                printer.setOutputFileName(path)
                text_document.print_(printer)
            elif lower.endswith(".txt"):
                with open(path, "w", encoding="utf-8") as f:
                    f.write(plain_text)
            else:
                if not lower.endswith(".md"):
                    path += ".md"
                try:
                    writer = QTextDocumentWriter(path, b"markdown")
                    if not writer.write(text_document):
                        raise OSError("markdown writer unavailable")
                except Exception:
                    with open(path, "w", encoding="utf-8") as f:
                        f.write(plain_text)  # graceful fallback: plain text
            self.status_label.setText("Exported")
        except Exception as e:
            logger.error(f"Export failed: {e}", exc_info=True)
            QMessageBox.critical(self, "Error", f"Export failed: {e}")


    def apply_code_style(self):
        dark = self.settings.get("theme") == "dark"
        fmt = QTextCharFormat()
        fmt.setFontFamily("Menlo")
        fmt.setBackground(QColor("#2D2D3A") if dark else QColor("#EEF0F4"))
        fmt.setForeground(QColor("#7CE38B") if dark else QColor("#C7254E"))
        self.editor.mergeCurrentCharFormat(fmt)
        self.editor.setFocus()

    def insert_table(self):
        rows, ok = QInputDialog.getInt(self, "Insert Table", "Rows:", 3, 1, 30)
        if not ok:
            return
        cols, ok = QInputDialog.getInt(self, "Insert Table", "Columns:", 3, 1, 10)
        if not ok:
            return
        self.editor.textCursor().insertTable(rows, cols)
        self.editor.setFocus()

    # -------------------- Documents --------------------

    def refresh_docs(self):
        folder = self.settings["documents_folder"]
        docs.ensure_folder(folder)
        self.fs_model.setRootPath(folder)
        self.docs_tree.setRootIndex(self.fs_model.index(folder))
        self.docs_tree.expand(self.fs_model.index(folder))  # show top-level files

    def _on_doc_search(self, text: str):
        """Filters the folder tree by filename substring."""
        term = text.strip()
        self.fs_model.setNameFilters(
            [f"*{term}*{e}" for e in docs.SUPPORTED_EXTS] if term
            else [f"*{e}" for e in docs.SUPPORTED_EXTS]
        )

    def run_content_search(self):
        """Searches INSIDE every document; results open in a temporary,
        never-saved tab (in-memory only, no file is created)."""
        term = self.doc_search.text().strip()
        if not term:
            return

        folder = self.settings["documents_folder"]
        lower_term = term.lower()
        results = []
        for root_dir, _dirs, files in os.walk(folder):
            for fname in sorted(files):
                if os.path.splitext(fname.lower())[1] not in docs.SUPPORTED_EXTS:
                    continue
                fpath = os.path.join(root_dir, fname)
                try:
                    content = docs.read_document(fpath)
                    if fname.lower().endswith(".html"):
                        doc = QTextDocument()
                        doc.setHtml(content)
                        content = doc.toPlainText()  # search text, not tags
                except Exception:
                    continue
                if lower_term in content.lower():
                    matches = [
                        ln.strip() for ln in content.splitlines()
                        if lower_term in ln.lower() and ln.strip()
                    ]
                    results.append((os.path.relpath(fpath, folder), matches[:5]))

        if results:
            lines = [f"🔍 “{term}” — found in {len(results)} file(s)\n"]
            for rel, matches in results:
                lines.append(f"\n📄 {rel}")
                lines.extend(f"   • {m}" for m in matches)
            body = "\n".join(lines)
        else:
            body = f"🔍 No matches for “{term}” in any document."

        # Temporary results tab — path is None, so it is never saved
        pane = self.active_pane
        title = f"🔍 {term[:18]}"
        meta = {"search": True, "content": body, "title": title}
        pane.tabs.blockSignals(True)
        idx = pane.tabs.addTab(title)
        pane.tabs.setTabData(idx, meta)
        pane.tabs.blockSignals(False)

        x_btn = QPushButton("✕")
        x_btn.setFixedSize(16, 16)
        x_btn.setToolTip("Close tab")
        x_btn.setCursor(Qt.PointingHandCursor)
        x_btn.setStyleSheet("border: none; color: #9D9D9D; font-size: 11px; padding: 0;")
        x_btn.clicked.connect(lambda _=False, m=meta, pn=pane: self._close_tab_by_meta(pn, m))
        pane.tabs.setTabButton(idx, QTabBar.RightSide, x_btn)

        pane.tabs.setCurrentIndex(idx)
        self.status_label.setText("Search results (temporary — not saved)")

    def _on_doc_tree_clicked(self, index):
        if self.fs_model.isDir(index):
            # Single click expands/collapses the folder
            self.docs_tree.setExpanded(index, not self.docs_tree.isExpanded(index))
        else:
            self.open_document_path(self.fs_model.filePath(index))

    def _panes(self):
        return [p for p in (self.pane1, self.pane2) if p is not None]

    def _activate_pane(self, pane):
        if pane and pane is not self.active_pane:
            self.active_pane = pane
            self._update_word_count()
            self._update_format_state(pane)

    def new_document(self, pane=None):
        pane = pane or self.active_pane
        # Create inside the selected tree folder (or the docs root)
        folder = self.settings["documents_folder"]
        idx = self.docs_tree.currentIndex()
        if idx.isValid():
            p = self.fs_model.filePath(idx)
            folder = p if self.fs_model.isDir(idx) else os.path.dirname(p)
        self._new_document_in(folder, pane)

    def _new_document_in(self, folder: str, pane=None):
        pane = pane or self.active_pane
        name, ok = QInputDialog.getText(
            self, "New Document",
            "Document name (optionally add .md / .txt / .html):",
        )
        if not ok or not name.strip():
            return
        self.save_pane(pane)

        path = docs.create_document(
            folder, name.strip(), ext=self.settings.get("doc_extension", ".md")
        )
        self.refresh_docs()
        self.docs_tree.expand(self.fs_model.index(folder))
        self.docs_tree.setCurrentIndex(self.fs_model.index(path))
        self.open_document_path(path, pane)

    def new_folder(self, parent_folder=None):
        """Creates a folder — inside the selected tree folder (or the docs root)."""
        if parent_folder is None:
            parent_folder = self.settings["documents_folder"]
            idx = self.docs_tree.currentIndex()
            if idx.isValid():
                p = self.fs_model.filePath(idx)
                parent_folder = p if self.fs_model.isDir(idx) else os.path.dirname(p)

        name, ok = QInputDialog.getText(self, "New Folder", "Folder name:")
        if not ok or not name.strip():
            return
        path = docs.create_folder(parent_folder, name.strip())
        self.docs_tree.expand(self.fs_model.index(parent_folder))
        self.docs_tree.setCurrentIndex(self.fs_model.index(path))
        self.status_label.setText("Folder created")

    def _delete_folder(self, path: str):
        name = os.path.basename(path)
        if QMessageBox.question(
            self, "Delete Folder",
            f"Delete folder “{name}” and ALL its contents permanently?",
        ) != QMessageBox.Yes:
            return
        # Close any open tabs whose file lives inside this folder
        for pane in self._panes():
            for i in range(pane.tabs.count() - 1, -1, -1):
                meta = pane.tabs.tabData(i) or {}
                p = meta.get("path", "")
                if p and p.startswith(path + os.sep):
                    if pane.path == p:
                        pane.path = None
                    pane.tabs.removeTab(i)
        shutil.rmtree(path, ignore_errors=True)
        self.status_label.setText("Folder deleted")

    def open_document_path(self, path: str, pane=None):
        if not path:
            return
        pane = pane or self.active_pane

        # Already open in this pane? Focus its tab.
        for i in range(pane.tabs.count()):
            meta = pane.tabs.tabData(i) or {}
            if meta.get("path") == path:
                if i == pane.tabs.currentIndex():
                    self._switch_to_tab(pane, i)  # already focused: reload
                else:
                    pane.tabs.setCurrentIndex(i)
                return

        title = docs.display_name(path)
        # Block signals: addTab on an empty bar fires currentChanged BEFORE the
        # tab data is set, which caused "Failed to open document: 'path'".
        pane.tabs.blockSignals(True)
        idx = pane.tabs.addTab(title)
        pane.tabs.setTabData(idx, {"path": path, "title": title})
        pane.tabs.blockSignals(False)

        # Per-tab 🔊 read button (document-level TTS)
        read_btn = QPushButton("")
        _v_icon = self._fa("fa5s.volume-up")
        if _v_icon.isNull():
            read_btn.setText("🔊")
        else:
            read_btn.setIcon(_v_icon)
        read_btn.setFixedSize(18, 18)
        read_btn.setToolTip("Read this document aloud")
        read_btn.setCursor(Qt.PointingHandCursor)
        read_btn.setStyleSheet("border: none; font-size: 10px; padding: 0;")
        read_btn.clicked.connect(lambda _=False, p=path: self.read_document_path(p))
        pane.tabs.setTabButton(idx, QTabBar.LeftSide, read_btn)

        # Per-tab ✕ close button (always visible)
        x_btn = QPushButton("✕")
        x_btn.setFixedSize(16, 16)
        x_btn.setToolTip("Close tab")
        x_btn.setCursor(Qt.PointingHandCursor)
        x_btn.setStyleSheet("border: none; color: #9D9D9D; font-size: 11px; padding: 0;")
        x_btn.clicked.connect(lambda _=False, p=path, pn=pane: self._close_tab_by_path(pn, p))
        pane.tabs.setTabButton(idx, QTabBar.RightSide, x_btn)

        pane.tabs.setCurrentIndex(idx)
        self._activate_pane(pane)

    # -------------------- Editor tabs --------------------

    def _switch_to_tab(self, pane, index: int):
        """Loads the tab's content into that pane's editor."""
        if index < 0 or index >= pane.tabs.count():
            return
        meta = pane.tabs.tabData(index)
        if not meta:
            return  # tab without data (mid-creation) — nothing to load

        self._activate_pane(pane)
        self.save_pane(pane)  # never lose the doc being switched away from

        pane.editor.blockSignals(True)
        if meta.get("history") or meta.get("search"):
            pane.path = None
            pane.history_content = meta.get("content", "")
            pane.editor.setPlainText(pane.history_content)
            pane.editor.setReadOnly(True)
            self.status_label.setText("Viewing " + meta.get("title", "result"))
        else:
            try:
                content = docs.read_document(meta["path"])
                if meta["path"].lower().endswith(".html"):
                    pane.editor.setHtml(content)
                else:  # .md / .txt open as plain text
                    pane.editor.setPlainText(content)
                pane.path = meta["path"]
                pane.history_content = None
                pane.editor.setReadOnly(False)
                self.status_label.setText("Document opened")
            except Exception as e:
                pane.editor.blockSignals(False)
                logger.error(f"Failed to open document: {e}", exc_info=True)
                QMessageBox.critical(self, "Error", f"Failed to open document: {e}")
                return
        pane.editor.blockSignals(False)
        pane.set_dirty(False)
        self.history_list.clearSelection()
        self._update_word_count()

    def close_tab(self, pane, index: int):
        if index < 0 or index >= pane.tabs.count():
            return
        meta = pane.tabs.tabData(index) or {}
        if index == pane.tabs.currentIndex() and meta.get("path") and pane.dirty:
            self.save_pane(pane)
        pane.tabs.removeTab(index)
        # removeTab re-switches current automatically -> _switch_to_tab loads it
        if pane.tabs.count() == 0:
            pane.path = None
            pane.history_content = None
            pane.editor.setReadOnly(False)
            pane.editor.blockSignals(True)
            pane.editor.clear()
            pane.editor.blockSignals(False)
            pane.set_dirty(False)
            self.status_label.setText("Ready")

    def close_current_tab(self):
        if self.active_pane:
            self.close_tab(self.active_pane, self.active_pane.tabs.currentIndex())

    def _close_tab_by_path(self, pane, path: str):
        for i in range(pane.tabs.count()):
            meta = pane.tabs.tabData(i) or {}
            if meta.get("path") == path:
                self.close_tab(pane, i)
                return

    def _close_tab_by_meta(self, pane, target_meta):
        for i in range(pane.tabs.count()):
            if pane.tabs.tabData(i) is target_meta:
                self.close_tab(pane, i)
                return

    # -------------------- Save / autosave --------------------

    def save_pane(self, pane) -> bool:
        if pane and pane.path and pane.dirty and not pane.editor.isReadOnly():
            try:
                lower = pane.path.lower()
                if lower.endswith(".txt"):
                    with open(pane.path, "w", encoding="utf-8") as f:
                        f.write(pane.editor.toPlainText())
                elif lower.endswith(".md"):
                    ok = QTextDocumentWriter(pane.path, b"markdown").write(
                        pane.editor.document()
                    )
                    if not ok:  # graceful fallback
                        with open(pane.path, "w", encoding="utf-8") as f:
                            f.write(pane.editor.toPlainText())
                else:
                    docs.save_document(pane.path, pane.editor.toHtml())
                pane.set_dirty(False)
                self._flash_saved(pane)
                return True
            except Exception as e:
                logger.error(f"Save failed: {e}", exc_info=True)
        return False

    def _flash_saved(self, pane):
        """Subtle save feedback: tab title flashes ✓ for ~1.2s, then restores."""
        i = pane.tabs.currentIndex()
        if i < 0:
            return
        meta = pane.tabs.tabData(i) or {}
        title = meta.get("title", "")
        pane.tabs.setTabText(i, f"✓ {title}")
        QTimer.singleShot(1200, pane._refresh_tab_title)

    def _save_current_silently(self):
        self.save_pane(self.active_pane)

    def save_document(self):
        if not (self.active_pane and self.active_pane.path):
            self.new_document(self.active_pane)
            return
        if self.save_pane(self.active_pane):
            self.status_label.setText("Saved")

    def _autosave_arm(self):
        self.autosave_timer.start()  # single-shot — each keystroke restarts it

    def _autosave_now(self):
        saved = False
        for pane in self._panes():
            saved = self.save_pane(pane) or saved
        if saved:
            self.status_label.setText("Auto-saved")

    def read_document_path(self, path: str):
        """TTS for a specific document (tab button / tree context menu)."""
        try:
            doc = QTextDocument()
            doc.setHtml(docs.read_document(path))
            if self.tts.speak(doc.toPlainText()):
                self.status_label.setText("Reading aloud…")
        except Exception as e:
            logger.error(f"TTS failed: {e}", exc_info=True)
            QMessageBox.critical(self, "Error", f"TTS failed: {e}")

    # -------------------- Tree context menu (read / delete) --------------------

    def _docs_context_menu(self, pos):
        idx = self.docs_tree.indexAt(pos)
        if not idx.isValid():
            return
        path = self.fs_model.filePath(idx)
        menu = QMenu(self)

        if self.fs_model.isDir(idx):
            # Folder actions
            new_doc_act = menu.addAction("📄  New document here")
            new_folder_act = menu.addAction("📁  New folder here")
            menu.addSeparator()
            reveal_dir_act = menu.addAction("🔍  Reveal in Finder")
            del_folder_act = menu.addAction("🗑  Delete folder…")
            chosen = menu.exec_(self.docs_tree.viewport().mapToGlobal(pos))
            if chosen == new_doc_act:
                self._new_document_in(path)
            elif chosen == new_folder_act:
                self.new_folder(path)
            elif chosen == reveal_dir_act:
                self._reveal_in_finder(path)
            elif chosen == del_folder_act:
                self._delete_folder(path)
            return

        # File actions — full per-file menu (record/speak, delete, reminder, …)
        open_act = menu.addAction("📄  Open")
        menu.addSeparator()
        read_act = menu.addAction("🔊  Read aloud")
        stop_act = menu.addAction("⏹  Stop reading")
        opt_act = menu.addAction("✨  Optimize with Claude")
        menu.addSeparator()
        export_act = menu.addAction("⇩  Export…")
        remind_act = menu.addAction("⏰  Set reminder…")
        reveal_act = menu.addAction("🔍  Reveal in Finder")
        menu.addSeparator()
        del_act = menu.addAction("🗑  Delete…")
        chosen = menu.exec_(self.docs_tree.viewport().mapToGlobal(pos))

        if chosen == open_act:
            self.open_document_path(path)
        elif chosen == read_act:
            self.read_document_path(path)
        elif chosen == stop_act:
            self.tts.stop()
        elif chosen == opt_act:
            self.optimize_file_path(path)
        elif chosen == export_act:
            self.export_document_path(path)
        elif chosen == remind_act:
            self._set_reminder_for_path(path)
        elif chosen == reveal_act:
            self._reveal_in_finder(path)
        elif chosen == del_act:
            self._delete_document_path(path)

    def optimize_file_path(self, path: str):
        """Right-click 'Optimize with Claude': result shows in the right panel."""
        try:
            content = docs.read_document(path)
            if path.lower().endswith(".html"):
                doc = QTextDocument()
                doc.setHtml(content)
                content = doc.toPlainText()
        except Exception as e:
            logger.error(f"Failed to read document: {e}", exc_info=True)
            QMessageBox.critical(self, "Error", f"Failed to read document: {e}")
            return
        if not content.strip():
            self.status_label.setText("Nothing to optimize")
            return
        self._run_claude_optimize(content, purpose="panel")

    def _reveal_in_finder(self, path: str):
        try:
            if sys.platform == "darwin":
                subprocess.run(["open", "-R", path], check=False)
            elif os.name == "nt":
                subprocess.run(["explorer", "/select,", path], check=False)
            else:
                subprocess.run(["xdg-open", os.path.dirname(path)], check=False)
        except Exception as e:
            logger.warning(f"Reveal in file manager failed: {e}")

    def _delete_document_path(self, path: str):
        name = docs.display_name(path)
        if QMessageBox.question(
            self, "Delete Document", f"Delete “{name}” permanently?"
        ) != QMessageBox.Yes:
            return
        # Close its tab first (without triggering a save of stale content)
        for pane in self._panes():
            for i in range(pane.tabs.count()):
                meta = pane.tabs.tabData(i) or {}
                if meta.get("path") == path:
                    if pane.path == path:
                        pane.path = None
                    pane.tabs.removeTab(i)
                    break
        docs.delete_document(path)
        for pane in self._panes():
            if pane.tabs.count() == 0 and pane.path is None and not pane.editor.isReadOnly():
                pane.editor.blockSignals(True)
                pane.editor.clear()
                pane.editor.blockSignals(False)
        self.status_label.setText("Deleted")

    def _save_current_silently(self):
        if self.current_doc_path:
            try:
                docs.save_document(self.current_doc_path, self.editor.toHtml())
            except Exception as e:
                logger.error(f"Auto-save failed: {e}", exc_info=True)

    def save_document(self):
        if not self.current_doc_path:
            self.new_document()
            return
        try:
            docs.save_document(self.current_doc_path, self.editor.toHtml())
            self.refresh_docs()
            self.status_label.setText("Saved")
        except Exception as e:
            logger.error(f"Save failed: {e}", exc_info=True)
            QMessageBox.critical(self, "Error", f"Save failed: {e}")

    def delete_document(self):
        if not self.current_doc_path:
            self.status_label.setText("No document selected")
            return
        self._delete_document_path(self.current_doc_path)

    # -------------------- Dictation (speech -> text at cursor) --------------------

    def load_initial_models(self):
        try:
            self.speech_models.load_whisper()
            self.status_label.setText("Ready")
            self.dictate_btn.setEnabled(True)
        except Exception as e:
            logger.error(f"Error loading Whisper: {e}", exc_info=True)
            self.status_label.setText("Error loading model")
            QMessageBox.critical(self, "Error", f"Failed to load Whisper model: {e}")

    def toggle_dictation(self):
        if self.is_recording:
            self.stop_dictation()
        else:
            self.start_dictation()

    def start_dictation(self):
        self.is_recording = True
        with self.frames_lock:
            self.audio_frames = []
            self._buffered_samples = 0
            self._overlap_tail = None
        self._last_chunk_text = ""
        self.session_raw_parts = []
        self._last_inserted = ""
        self.stt_display.clear()

        self.rec_start_ts = time.time()
        self.timer_label.setText("⏱ 00:00")
        self.timer_label.setVisible(True)
        self.rec_timer.start()

        self.level_indicator.set_level(0)
        if not self.level_indicator.user_moved:
            self.level_indicator.center_on_parent()
        self.level_indicator.show()
        self.level_indicator.raise_()

        self.speaking_icon_label.setVisible(True)
        self._set_dictate_style(True)
        self.status_label.setText(
            "🔴 Dictating · live" if self.settings.get("live_transcription", True)
            else "🔴 Dictating"
        )

        self.stream = sd.InputStream(
            samplerate=config.SAMPLE_RATE, channels=1, callback=self.audio_callback
        )
        self.stream.start()

    def stop_dictation(self):
        self.is_recording = False
        self.rec_timer.stop()
        self.speaking_icon_label.setVisible(False)
        self.timer_label.setVisible(False)
        self.level_indicator.hide()
        self._set_dictate_style(False)

        if hasattr(self, "stream"):
            self.stream.stop()
            self.stream.close()

        with self.frames_lock:
            if self.audio_frames:
                remaining = np.concatenate(self.audio_frames, axis=0).flatten().astype(np.float32)
                self.audio_frames = []
                self._buffered_samples = 0
            else:
                remaining = None

        min_samples = int(config.SAMPLE_RATE * 0.4)
        if remaining is not None and len(remaining) >= min_samples:
            self.stream_queue.put(remaining)
        self.stream_queue.put(_FLUSH)

        self.status_label.setText("Transcribing…")

    def audio_callback(self, indata, frames, time_info, status):
        if not self.is_recording:
            return

        rms = float(np.sqrt(np.mean(np.square(indata))))
        self.level_changed.emit(min(100, int(rms * 400)))

        chunk = None
        with self.frames_lock:
            self.audio_frames.append(indata.copy())
            self._buffered_samples += len(indata)
            if (
                self.settings.get("live_transcription", True)
                and self._buffered_samples >= config.SAMPLE_RATE * config.STREAM_CHUNK_SECONDS
            ):
                new_audio = np.concatenate(self.audio_frames, axis=0).flatten().astype(np.float32)
                self.audio_frames = []
                self._buffered_samples = 0

                overlap = int(config.SAMPLE_RATE * config.STREAM_OVERLAP_SECONDS)
                chunk = (
                    np.concatenate([self._overlap_tail, new_audio])
                    if self._overlap_tail is not None
                    else new_audio
                )
                self._overlap_tail = new_audio[-overlap:] if len(new_audio) > overlap else new_audio

        if chunk is not None:
            self.stream_queue.put(chunk)

    def _stream_transcriber(self):
        """Background loop (app lifetime): transcribes queued chunks in order."""
        while True:
            item = self.stream_queue.get()
            try:
                if item is _FLUSH:
                    self.stream_drained.emit()
                    continue
                text = self._transcribe_chunk(item)
                if text:
                    merged = self._merge_chunk_text(self._last_chunk_text, text)
                    self._last_chunk_text = text
                    merged = self._apply_voice_commands(merged)
                    if merged.strip():
                        self.session_raw_parts.append(merged)
                        self.partial_text.emit(merged)
            except Exception as e:
                logger.error(f"Live chunk transcription failed: {e}", exc_info=True)

    def _transcribe_chunk(self, audio_data) -> str:
        if self.settings.get("noise_reduction", True):
            audio_data = self.speech_models.denoise_audio(audio_data)
        return self.speech_models.transcribe_audio(audio_data)

    @staticmethod
    def _merge_chunk_text(prev_text: str, new_text: str) -> str:
        """Drops words repeated across the audio overlap between chunks."""
        if not prev_text:
            return new_text
        prev_words = prev_text.split()
        new_words = new_text.split()
        max_k = min(8, len(prev_words), len(new_words))
        for k in range(max_k, 0, -1):
            tail = [w.strip(".,!?\"'").lower() for w in prev_words[-k:]]
            head = [w.strip(".,!?\"'").lower() for w in new_words[:k]]
            if tail == head:
                return " ".join(new_words[k:])
        return new_text

    @pyqtSlot(str)
    def on_partial_text(self, text):
        """Live dictation: insert at the cursor AND mirror into the speech panel.
        Saying 'scratch that' removes the previously dictated chunk."""
        if text.strip().lower().rstrip(".!") == "scratch that":
            self._undo_last_dictation()
            return
        self.editor.insertPlainText(text + " ")
        self.editor.ensureCursorVisible()
        self.stt_display.append(text)
        self._last_inserted = text

    def _undo_last_dictation(self):
        """'scratch that' voice command: removes the last dictated chunk from
        the editor, the STT panel, and the session history parts."""
        if not getattr(self, "_last_inserted", ""):
            self.status_label.setText("Nothing to scratch")
            return
        cursor = self.editor.textCursor()
        cursor.movePosition(QTextCursor.End)
        for _ in range(len(self._last_inserted) + 1):  # +1 for the trailing space
            cursor.deletePreviousChar()
        if self.session_raw_parts:
            self.session_raw_parts.pop()
        self.stt_display.undo()  # remove the last appended line
        self._last_inserted = ""
        self.status_label.setText("Scratched last chunk")

    @pyqtSlot()
    def on_stream_drained(self):
        """Dictation session finished — archive it to the history panel."""
        raw_text = " ".join(self.session_raw_parts).strip()
        if raw_text and self.settings.get("save_history", True):
            try:
                history_manager.save_transcription(raw_text, "")
                self._refresh_history()
            except Exception as e:
                logger.error(f"Failed to save history: {e}", exc_info=True)
        if not self.is_recording:
            self.status_label.setText("Ready")

    # -------------------- Text to speech --------------------

    def read_aloud(self):
        cursor = self.editor.textCursor()
        text = cursor.selectedText() if cursor.hasSelection() else self.editor.toPlainText()
        if self.tts.speak(text):
            self.status_label.setText("Reading aloud…")
        else:
            self.status_label.setText("Nothing to read" if not text.strip() else "TTS unavailable")

    # -------------------- Claude optimization --------------------

    def _run_claude_optimize(self, text: str, purpose: str):
        api_key = self.settings.get("claude_api_key", "")
        if not api_key:
            QMessageBox.information(
                self,
                "Claude API key needed",
                "Add your Claude API key in ⚙️ Settings first.",
            )
            return
        self.status_label.setText("Optimizing with Claude…")
        self.optimize_btn.setEnabled(False)
        # Toolbar (editor) optimizations use the selected preset style
        system_prompt = ""
        if purpose == "editor":
            system_prompt = config.OPTIMIZE_PRESETS.get(
                self.preset_combo.currentText(), ""
            )
        self.claude_worker = ClaudeWorker(
            self.speech_models,
            text,
            api_key,
            self.settings.get("claude_model", config.CLAUDE_MODEL),
            purpose,
            system_prompt,
        )
        self.claude_worker.finished.connect(self.on_claude_finished)
        self.claude_worker.error.connect(self.on_claude_error)
        threading.Thread(
            target=self.claude_worker.run, daemon=True, name="ClaudeWorker"
        ).start()

    def optimize_speech_text(self):
        """Right panel: optimize the dictated speech→text content."""
        text = self.stt_display.toPlainText().strip()
        if not text:
            self.status_label.setText("Nothing to optimize")
            return
        self._run_claude_optimize(text, purpose="panel")

    def optimize_document_text(self):
        """Toolbar (per document): optimize the selection, or the full document."""
        cursor = self.editor.textCursor()
        self._opt_had_selection = cursor.hasSelection()
        text = cursor.selectedText() if self._opt_had_selection else self.editor.toPlainText()
        if not text.strip():
            self.status_label.setText("Nothing to optimize")
            return
        self._run_claude_optimize(text, purpose="editor")

    @pyqtSlot(str, str)
    def on_claude_finished(self, purpose, result):
        self.optimize_btn.setEnabled(True)
        self.status_label.setText("Ready")
        if not result:
            result = "[Claude returned an empty result]"
        if purpose == "panel":
            self.optimize_display.setPlainText(result)
        else:
            if getattr(self, "_opt_had_selection", False):
                # Replace the selected text in place (undoable via ↶)
                self.editor.textCursor().insertText(result)
            else:
                self.editor.setPlainText(result)
            self.status_label.setText("Optimized")

    @pyqtSlot(str)
    def on_claude_error(self, err_msg):
        self.optimize_btn.setEnabled(True)
        self.status_label.setText("Optimization failed")
        QMessageBox.critical(self, "Error", err_msg)

    # -------------------- In-editor tasks (checkbox lines) --------------------

    def toggle_task_marker(self):
        """Cycles the current line:  plain → ☐ task → ☑ done → plain.
        Tasks live inside the document itself, saved with the .html file."""
        cursor = self.editor.textCursor()
        cursor.movePosition(QTextCursor.StartOfBlock)
        cursor.movePosition(QTextCursor.EndOfBlock, QTextCursor.KeepAnchor)
        line = cursor.selectedText()
        if line.startswith("☐ "):
            new_line = "☑ " + line[2:]
        elif line.startswith("☑ "):
            new_line = line[2:]
        else:
            new_line = "☐ " + line
        cursor.insertText(new_line)
        self.editor.setFocus()

    # -------------------- Git push --------------------

    def push_to_git(self):
        if not self.settings.get("git_remote_url"):
            QMessageBox.information(
                self,
                "Git not configured",
                "Set your Git remote URL in ⚙️ Settings first.",
            )
            return
        self._save_current_silently()  # include the open document in the commit
        self.status_label.setText("Pushing to git…")
        self.git_push_btn.setEnabled(False)
        threading.Thread(
            target=self._git_push_worker, daemon=True, name="GitPush"
        ).start()

    def _git_push_worker(self):
        try:
            output = git_manager.push_all(
                repo_path=os.path.dirname(os.path.abspath(__file__)),
                remote_url=self.settings.get("git_remote_url", ""),
                branch=self.settings.get("git_branch", "main"),
                message=f"Update {datetime.now():%Y-%m-%d %H:%M:%S} via Speech Editor",
            )
            self.git_done.emit(output)
        except Exception as e:
            logger.error(f"Git push failed: {e}", exc_info=True)
            self.git_failed.emit(str(e))

    @pyqtSlot(str)
    def on_git_done(self, output):
        self.git_push_btn.setEnabled(True)
        self.status_label.setText("Pushed to git")
        logger.info(f"Git push output:\n{output}")

    @pyqtSlot(str)
    def on_git_failed(self, err_msg):
        self.git_push_btn.setEnabled(True)
        self.status_label.setText("Git push failed")
        QMessageBox.critical(self, "Git Push Failed", err_msg)

    # -------------------- Document reminders --------------------

    def set_reminder(self):
        """⏰ toolbar: reminder for the document open in the active pane."""
        if not (self.active_pane and self.active_pane.path):
            self.status_label.setText("Open a document first")
            return
        self._set_reminder_for_path(self.active_pane.path)

    def _set_reminder_for_path(self, path: str):
        """⏰ per-document reminder: pick a date/time, get a popup when due."""
        dialog = QDialog(self)
        dialog.setWindowTitle("⏰ Set reminder")
        lay = QVBoxLayout(dialog)
        lay.setContentsMargins(16, 16, 16, 16)
        lay.setSpacing(10)
        lay.addWidget(QLabel(
            f"Remind me about “{docs.display_name(path)}” at:"
        ))
        dt_edit = QDateTimeEdit(QDateTime.currentDateTime().addSecs(3600))
        dt_edit.setCalendarPopup(True)
        dt_edit.setDisplayFormat("yyyy-MM-dd HH:mm")
        dt_edit.setMinimumDateTime(QDateTime.currentDateTime())
        lay.addWidget(dt_edit)

        row = QHBoxLayout()
        row.addStretch()
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(dialog.reject)
        ok_btn = QPushButton("Set reminder")
        ok_btn.setObjectName("primaryBtn")
        ok_btn.setDefault(True)
        ok_btn.clicked.connect(dialog.accept)
        row.addWidget(cancel_btn)
        row.addWidget(ok_btn)
        lay.addLayout(row)
        dialog.setLayout(lay)

        if dialog.exec_() == QDialog.Accepted:
            reminders_manager.add_reminder(
                path,
                docs.display_name(path),
                dt_edit.dateTime().toPyDateTime(),
            )
            self.status_label.setText(
                "Reminder set for " + dt_edit.dateTime().toString("MMM d, HH:mm")
            )

    def _check_reminders(self):
        """Every 30s: pop up any reminder whose time has arrived."""
        for reminder in reminders_manager.due_reminders():
            reminders_manager.mark_fired(reminder["path"])
            box = QMessageBox(self)
            box.setWindowTitle("⏰ Reminder")
            box.setIcon(QMessageBox.Information)
            box.setText(f"Time to check “{reminder.get('title', 'document')}”.")
            open_btn = box.addButton("Open document", QMessageBox.AcceptRole)
            box.addButton("Dismiss", QMessageBox.RejectRole)
            box.exec_()
            if box.clickedButton() == open_btn and os.path.exists(reminder["path"]):
                self.open_document_path(reminder["path"])

    # -------------------- Misc --------------------

    def _update_rec_timer(self):
        if self.rec_start_ts is None:
            return
        elapsed = int(time.time() - self.rec_start_ts)
        self.timer_label.setText(f"⏱ {elapsed // 60:02d}:{elapsed % 60:02d}")

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if (
            hasattr(self, "level_indicator")
            and self.level_indicator.isVisible()
            and not self.level_indicator.user_moved
        ):
            self.level_indicator.center_on_parent()

    def closeEvent(self, event):
        self.tts.stop()
        for pane in self._panes():
            self.save_pane(pane)
        super().closeEvent(event)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = SpeechEditorApp()
    window.showMaximized()  # launch full screen, keeping native window chrome
    sys.exit(app.exec_())
