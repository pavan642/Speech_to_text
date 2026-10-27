# main.py
import logging
import os
import queue
import sys
import threading
import time
import urllib.request
import warnings
from datetime import datetime

# Suppress harmless NumPy warnings
warnings.filterwarnings("ignore", category=RuntimeWarning, module="numpy")

import numpy as np
from PyQt5.QtCore import QObject, QRect, Qt, QTimer, pyqtSignal, pyqtSlot
from PyQt5.QtGui import QColor, QFont, QIcon, QPainter, QPen, QPixmap, QRegion
from PyQt5.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QFrame,
    QGraphicsDropShadowEffect,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QSplitter,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)
import sounddevice as sd

import config
import history_manager
import settings_manager
from models import SpeechModels

# Configure Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("SpeechGrammarApp")

# Queue marker telling the stream transcriber: "recording stopped, everything
# before this point is the complete session — finalize it."
_FLUSH = object()


class OptimizeWorker(QObject):
    """Runs the optional OpenAI optimization on the finished session text."""
    finished = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(self, speech_models: SpeechModels, raw_text: str, api_key: str, system_prompt: str):
        super().__init__()
        self.speech_models = speech_models
        self.raw_text = raw_text
        self.api_key = api_key
        self.system_prompt = system_prompt

    def run(self):
        try:
            optimized = self.speech_models.optimize_text(
                self.raw_text, self.api_key, self.system_prompt
            )
            self.finished.emit(optimized or "")
        except Exception as e:
            logger.error(f"OpenAI optimization failed: {e}", exc_info=True)
            self.error.emit(f"OpenAI optimization failed: {e}")


class SettingsDialog(QDialog):
    """Modal dialog for configuring the OpenAI API key and the app theme."""

    def __init__(self, current_settings: dict, parent=None):
        super().__init__(parent)
        self.setWindowTitle("⚙️ Settings")
        self.setMinimumWidth(480)
        self.setModal(True)

        layout = QVBoxLayout()
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # --- OpenAI API Configuration ---
        api_group = QGroupBox("OpenAI API Configuration")
        api_layout = QVBoxLayout()

        api_info = QLabel(
            'Get your API key from '
            '<a href="https://platform.openai.com/api-keys">platform.openai.com/api-keys</a>. '
            'When a key is set, each transcription is optimized using the OpenAI API.'
        )
        api_info.setOpenExternalLinks(True)
        api_info.setWordWrap(True)
        api_layout.addWidget(api_info)

        api_key_label = QLabel("API Key:")
        api_layout.addWidget(api_key_label)

        self.api_key_input = QLineEdit()
        self.api_key_input.setEchoMode(QLineEdit.Password)
        self.api_key_input.setPlaceholderText("sk-...")
        self.api_key_input.setText(current_settings.get("openai_api_key", ""))
        api_layout.addWidget(self.api_key_input)

        self.show_key_checkbox = QCheckBox("Show API key")
        self.show_key_checkbox.toggled.connect(
            lambda checked: self.api_key_input.setEchoMode(
                QLineEdit.Normal if checked else QLineEdit.Password
            )
        )
        api_layout.addWidget(self.show_key_checkbox)

        prompt_label = QLabel("System Prompt (how OpenAI rewrites your text):")
        api_layout.addWidget(prompt_label)

        self.prompt_edit = QTextEdit()
        self.prompt_edit.setFixedHeight(90)
        self.prompt_edit.setPlaceholderText(config.OPENAI_SYSTEM_PROMPT)
        self.prompt_edit.setPlainText(
            current_settings.get("openai_prompt") or config.OPENAI_SYSTEM_PROMPT
        )
        api_layout.addWidget(self.prompt_edit)

        reset_prompt_btn = QPushButton("↺ Reset prompt to default")
        reset_prompt_btn.clicked.connect(
            lambda: self.prompt_edit.setPlainText(config.OPENAI_SYSTEM_PROMPT)
        )
        api_layout.addWidget(reset_prompt_btn)

        api_group.setLayout(api_layout)
        layout.addWidget(api_group)

        # --- Speech Recognition ---
        stt_group = QGroupBox("Speech Recognition")
        stt_layout = QVBoxLayout()

        model_label = QLabel("Whisper model (larger = more accurate, slower):")
        stt_layout.addWidget(model_label)

        self.model_combo = QComboBox()
        self.model_combo.addItems(config.WHISPER_MODEL_OPTIONS)
        self.model_combo.setCurrentText(
            current_settings.get("whisper_model", config.WHISPER_MODEL_NAME)
        )
        stt_layout.addWidget(self.model_combo)

        self.live_checkbox = QCheckBox("Live transcription while recording")
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

        # --- History ---
        history_group = QGroupBox("History")
        history_layout = QVBoxLayout()

        self.history_checkbox = QCheckBox("Save each transcription to history/ folder (.md)")
        self.history_checkbox.setChecked(current_settings.get("save_history", True))
        history_layout.addWidget(self.history_checkbox)

        history_group.setLayout(history_layout)
        layout.addWidget(history_group)

        # --- Dialog Buttons ---
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

    def get_settings(self) -> dict:
        return {
            "theme": "dark" if self.dark_radio.isChecked() else "light",
            "openai_api_key": self.api_key_input.text().strip(),
            "whisper_model": self.model_combo.currentText(),
            "openai_prompt": self.prompt_edit.toPlainText().strip(),
            "save_history": self.history_checkbox.isChecked(),
            "noise_reduction": self.noise_checkbox.isChecked(),
            "live_transcription": self.live_checkbox.isChecked(),
        }


class MicLevelIndicator(QWidget):
    """Draggable circular mic indicator (~2 cm across), centered by default.

    Fills with green from the bottom up, tracking the live microphone level.
    Shown only while recording; drag with the mouse to reposition it anywhere.
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

        # Base circle: dark translucent fill + green ring
        painter.setPen(QPen(QColor("#4CAF50"), 3))
        painter.setBrush(QColor(40, 40, 40, 170))
        painter.drawEllipse(rect)

        # Green fill rising with the current voice level (clipped to the circle)
        if self._level > 0:
            fill_h = rect.height() * self._level // 100
            painter.setClipRegion(QRegion(rect, QRegion.Ellipse))
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(76, 175, 80, 220))
            painter.drawRect(
                QRect(rect.left(), rect.bottom() - fill_h + 1, rect.width(), fill_h)
            )
            painter.setClipping(False)

        # Mic glyph in white (visible over both dark base and green fill)
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

    # --- Drag to move ---
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


class SpeechToTextApp(QWidget):
    # Emitted from the audio thread; safely updates the level indicator in the GUI thread
    level_changed = pyqtSignal(int)
    # Emitted when the remote app icon finishes downloading
    icon_fetched = pyqtSignal(QPixmap)
    # Live transcription: a chunk's text is ready / the session queue is drained
    partial_text = pyqtSignal(str)
    stream_drained = pyqtSignal()

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
        self.speech_models = SpeechModels()
        self.settings = settings_manager.load_settings()

        # Persistent live-transcription pipeline (one thread -> strict ordering)
        self.stream_queue = queue.Queue()
        threading.Thread(
            target=self._stream_transcriber, daemon=True, name="StreamTranscriber"
        ).start()

        self.init_ui()
        self.set_app_icon()
        self.apply_theme(self.settings.get("theme", "light"))

        # Floating mic-level indicator (draggable ~2 cm circle, fills with voice level)
        self.level_indicator = MicLevelIndicator(self)
        self.level_changed.connect(self.level_indicator.set_level)
        self.icon_fetched.connect(self._apply_fetched_icon)

        # Live transcription slots
        self.partial_text.connect(self.on_partial_text)
        self.stream_drained.connect(self.on_stream_drained)

        # Pre-load Whisper model asynchronously
        threading.Thread(
            target=self.load_initial_models, daemon=True, name="ModelLoader"
        ).start()

    # -------------------- Theming --------------------

    def apply_theme(self, theme_name: str):
        """Applies the light or dark stylesheet app-wide."""
        app = QApplication.instance()
        if theme_name == "dark":
            app.setStyleSheet(config.DARK_THEME)
        else:
            app.setStyleSheet(config.LIGHT_THEME)

    # -------------------- Settings --------------------

    def open_settings(self):
        dialog = SettingsDialog(self.settings, self)
        if dialog.exec_() == QDialog.Accepted:
            old_model = self.settings.get("whisper_model", config.WHISPER_MODEL_NAME)
            self.settings = dialog.get_settings()
            settings_manager.save_settings(self.settings)
            self.apply_theme(self.settings["theme"])

            key_state = "configured" if self.settings["openai_api_key"] else "not configured"
            self.status_label.setText("Config updated")
            logger.info(f"Settings updated: theme={self.settings['theme']}, api_key={key_state}")

            # Reload Whisper in the background if the model size changed
            new_model = self.settings.get("whisper_model", config.WHISPER_MODEL_NAME)
            if new_model != old_model:
                self.speech_models.set_whisper_model(new_model)
                self.status_label.setText(f"Loading Whisper ({new_model})…")
                self.set_mic_on_style(False)
                threading.Thread(
                    target=self.load_initial_models, daemon=True, name="ModelLoader"
                ).start()

    # -------------------- UI Setup --------------------

    def set_app_icon(self):
        """Sets the app icon WITHOUT blocking startup:
        1. Local file (app_icon.png / icon.png next to main.py) — instant
        2. Drawn fallback set immediately — instant, offline-safe
        3. Remote URL fetched in a background thread; icon upgrades when it arrives
        """
        for name in ("app_icon.png", "app_icon.jpg", "icon.png"):
            if os.path.exists(name):
                self.setWindowIcon(QIcon(name))
                logger.info(f"App icon loaded from local file: {name}")
                return

        # Instant fallback so the window can show right away
        self.setWindowIcon(QIcon(self._draw_mic_icon()))

        # Network fetch happens off the main thread
        threading.Thread(
            target=self._fetch_icon_from_url, daemon=True, name="IconLoader"
        ).start()

    def _fetch_icon_from_url(self):
        """Downloads the configured icon URL in the background."""
        try:
            req = urllib.request.Request(
                config.APP_ICON_URL, headers={"User-Agent": "Mozilla/5.0"}
            )
            data = urllib.request.urlopen(req, timeout=5).read()
            pixmap = QPixmap()
            pixmap.loadFromData(data)
            if not pixmap.isNull():
                self.icon_fetched.emit(pixmap)  # applied in the GUI thread
                logger.info("App icon loaded from URL")
        except Exception as e:
            logger.warning(f"Failed to load window icon from URL: {e}")

    @pyqtSlot(QPixmap)
    def _apply_fetched_icon(self, pixmap):
        self.setWindowIcon(QIcon(pixmap))

    @staticmethod
    def _draw_mic_icon() -> QPixmap:
        """Renders a clean 64x64 microphone icon — no assets or network needed."""
        pixmap = QPixmap(64, 64)
        pixmap.fill(Qt.transparent)

        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)

        color = QColor("#4CAF50")
        # Mic body (rounded capsule)
        painter.setBrush(color)
        painter.setPen(Qt.NoPen)
        painter.drawRoundedRect(24, 6, 16, 30, 8, 8)

        # Cradle (U-shaped arc under the capsule)
        painter.setBrush(Qt.NoBrush)
        painter.setPen(QPen(color, 4, Qt.SolidLine, Qt.RoundCap))
        painter.drawArc(16, 20, 32, 32, 180 * 16, 180 * 16)

        # Stem and base
        painter.drawLine(32, 52, 32, 58)
        painter.drawLine(22, 58, 42, 58)

        painter.end()
        return pixmap

    def set_mic_on_style(self, enabled: bool):
        """Green gradient when ready, neutral gray while disabled/recording."""
        if enabled:
            self.mic_on_btn.setEnabled(True)
            self.mic_on_btn.setStyleSheet(
                "QPushButton { background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1,"
                " stop:0 #56B656, stop:1 #2E7D32); color: white; padding: 12px;"
                " border-radius: 11px; border: none; font-weight: bold; }"
                "QPushButton:hover { background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1,"
                " stop:0 #60C460, stop:1 #358A39); }"
                "QPushButton:pressed { background-color: #2E7D32; }"
            )
        else:
            self.mic_on_btn.setEnabled(False)
            self.mic_on_btn.setStyleSheet(
                "QPushButton { background-color: #B0B7C3; color: #F5F6F8; padding: 12px;"
                " border-radius: 11px; border: none; font-weight: bold; }"
            )

    def _build_history_sidebar(self):
        """Left sidebar: lists past sessions from history/, click to reload."""
        card = QFrame()
        card.setObjectName("card")
        card.setFixedWidth(215)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(14, 14, 14, 14)
        card_layout.setSpacing(8)

        header = QHBoxLayout()
        title = QLabel("🕘  History")
        title.setObjectName("cardTitle")
        title.setFont(QFont("Helvetica Neue", 11, QFont.Bold))
        refresh_btn = QPushButton("↻")
        refresh_btn.setFixedSize(26, 26)
        refresh_btn.setToolTip("Refresh history list")
        refresh_btn.setCursor(Qt.PointingHandCursor)
        refresh_btn.clicked.connect(self._refresh_history)
        header.addWidget(title)
        header.addStretch()
        header.addWidget(refresh_btn)

        self.history_list = QListWidget()
        self.history_list.setFont(QFont("Helvetica Neue", 10))
        self.history_list.itemClicked.connect(self._load_history_item)

        card_layout.addLayout(header)
        card_layout.addWidget(self.history_list)

        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(24)
        shadow.setXOffset(0)
        shadow.setYOffset(4)
        shadow.setColor(QColor(15, 23, 42, 60))
        card.setGraphicsEffect(shadow)

        return card

    def _refresh_history(self):
        """Reloads the sidebar list from the history/ folder (newest first)."""
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

    def _load_history_item(self, item):
        """Loads a past session's text back into the transcript panels."""
        path = item.data(Qt.UserRole)
        try:
            raw, optimized = history_manager.load_session(path)
            self.orig_display.setPlainText(raw + ("\n" if raw else ""))
            self.opt_display.setPlainText(optimized + ("\n" if optimized else ""))
            self.status_label.setText("Session loaded")
        except Exception as e:
            logger.error(f"Failed to load session: {e}", exc_info=True)
            QMessageBox.critical(self, "Error", f"Failed to load session: {e}")

    def _build_card(self, title: str):
        """Creates a rounded, shadowed card panel containing a title + text area."""
        card = QFrame()
        card.setObjectName("card")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(16, 14, 16, 14)
        card_layout.setSpacing(6)

        label = QLabel(title)
        label.setObjectName("cardTitle")
        label.setFont(QFont("Helvetica Neue", 11, QFont.Bold))

        edit = QTextEdit()
        edit.setFont(QFont("Helvetica Neue", 11))
        edit.setFrameShape(QFrame.NoFrame)

        card_layout.addWidget(label)
        card_layout.addWidget(edit)

        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(24)
        shadow.setXOffset(0)
        shadow.setYOffset(4)
        shadow.setColor(QColor(15, 23, 42, 60))
        card.setGraphicsEffect(shadow)

        return card, edit

    def init_ui(self):
        self.setWindowTitle(config.APP_TITLE)
        self.resize(config.WINDOW_WIDTH, config.WINDOW_HEIGHT)

        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(12)

        # 1. Header: status pill (left) · title (center) · settings (right)
        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(0, 0, 0, 0)

        self.status_label = QLabel("Loading Whisper model…")
        self.status_label.setObjectName("statusPill")
        self.status_label.setFont(QFont("Helvetica Neue", 10, QFont.Bold))
        self.status_label.setAlignment(Qt.AlignCenter)
        header_layout.addWidget(self.status_label, 0, Qt.AlignTop)

        header_text = QWidget()
        header_text_layout = QVBoxLayout(header_text)
        header_text_layout.setContentsMargins(0, 0, 0, 0)
        header_text_layout.setSpacing(2)

        title_label = QLabel("🎙️ " + config.APP_TITLE)
        title_label.setFont(QFont("Helvetica Neue", 21, QFont.Bold))
        title_label.setAlignment(Qt.AlignCenter)

        subtitle = QLabel("Live Whisper transcription  ·  OpenAI optimization")
        subtitle.setObjectName("subtitle")
        subtitle.setFont(QFont("Helvetica Neue", 10))
        subtitle.setAlignment(Qt.AlignCenter)

        header_text_layout.addWidget(title_label)
        header_text_layout.addWidget(subtitle)

        self.settings_btn = QPushButton("⚙")
        self.settings_btn.setObjectName("settingsBtn")
        self.settings_btn.setFixedSize(42, 42)
        self.settings_btn.setToolTip("Open Settings")
        self.settings_btn.setCursor(Qt.PointingHandCursor)
        self.settings_btn.clicked.connect(self.open_settings)

        header_layout.addStretch()
        header_layout.addWidget(header_text)
        header_layout.addStretch()
        header_layout.addWidget(self.settings_btn, 0, Qt.AlignTop)
        main_layout.addLayout(header_layout)

        # 2. Speaking indicator — anchored above the Original Transcript card
        speak_row = QHBoxLayout()
        speak_row.setContentsMargins(8, 0, 0, 0)
        speaking_text = getattr(config, "SPEAKING_INDICATOR_TEXT", "🗣️ Speaking...")
        self.speaking_icon_label = QLabel(speaking_text)
        self.speaking_icon_label.setFont(QFont("Helvetica Neue", 13, QFont.Bold))
        self.speaking_icon_label.setStyleSheet("color: #FF9800;")
        self.speaking_icon_label.setVisible(False)  # shown only while recording
        speak_row.addWidget(self.speaking_icon_label)

        # Recording timer — starts with Mic ON, stops with Mic OFF
        self.timer_label = QLabel("⏱ 00:00")
        self.timer_label.setFont(QFont("Helvetica Neue", 13, QFont.Bold))
        self.timer_label.setStyleSheet("color: #FF9800;")
        self.timer_label.setVisible(False)
        speak_row.addSpacing(12)
        speak_row.addWidget(self.timer_label)
        speak_row.addStretch()
        main_layout.addLayout(speak_row)

        self.rec_timer = QTimer(self)
        self.rec_timer.setInterval(500)
        self.rec_timer.timeout.connect(self._update_rec_timer)

        # 4. Dual Text Panels as shadowed cards
        text_splitter = QSplitter(Qt.Horizontal)
        orig_card, self.orig_display = self._build_card("📝  Original Transcript")
        opt_card, self.opt_display = self._build_card("✨  Optimized (OpenAI)")
        text_splitter.addWidget(orig_card)
        text_splitter.addWidget(opt_card)
        text_splitter.setSizes([475, 475])
        main_layout.addWidget(text_splitter)

        # 5. Mic Control Buttons
        mic_btn_layout = QHBoxLayout()
        self.mic_on_btn = QPushButton("🎙️  Mic ON")
        self.mic_on_btn.setFont(QFont("Helvetica Neue", 12, QFont.Bold))
        self.set_mic_on_style(False)  # Disabled initially until models load
        self.mic_on_btn.clicked.connect(self.start_recording)

        self.mic_off_btn = QPushButton("🛑  Mic OFF")
        self.mic_off_btn.setFont(QFont("Helvetica Neue", 12, QFont.Bold))
        self.mic_off_btn.setStyleSheet(
            "QPushButton { background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1,"
            " stop:0 #EF5350, stop:1 #C62828); color: white; padding: 12px;"
            " border-radius: 11px; border: none; font-weight: bold; }"
            "QPushButton:hover { background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1,"
            " stop:0 #F46360, stop:1 #D32F2F); }"
            "QPushButton:pressed { background-color: #C62828; }"
            "QPushButton:disabled { background-color: #B0B7C3; color: #F5F6F8; }"
        )
        self.mic_off_btn.setEnabled(False)
        self.mic_off_btn.clicked.connect(self.stop_recording)

        mic_btn_layout.addWidget(self.mic_on_btn)
        mic_btn_layout.addWidget(self.mic_off_btn)
        main_layout.addLayout(mic_btn_layout)

        # 6. Action Utility Buttons
        action_btn_layout = QHBoxLayout()

        self.copy_orig_btn = QPushButton("📋 Copy Original")
        self.copy_orig_btn.setFont(QFont("Helvetica", 10))
        self.copy_orig_btn.clicked.connect(self.copy_orig_text)

        self.copy_opt_btn = QPushButton("📋 Copy Optimized")
        self.copy_opt_btn.setFont(QFont("Helvetica", 10))
        self.copy_opt_btn.clicked.connect(self.copy_opt_text)

        self.clear_btn = QPushButton("🧹 Clear Text")
        self.clear_btn.setFont(QFont("Helvetica", 10))
        self.clear_btn.clicked.connect(self.clear_text)

        self.close_btn = QPushButton("❌ Close App")
        self.close_btn.setFont(QFont("Helvetica", 10))
        self.close_btn.clicked.connect(self.close)

        action_btn_layout.addWidget(self.copy_orig_btn)
        action_btn_layout.addWidget(self.copy_opt_btn)
        action_btn_layout.addWidget(self.clear_btn)
        action_btn_layout.addWidget(self.close_btn)
        main_layout.addLayout(action_btn_layout)

        # Root layout: history sidebar on the left, main content on the right
        content = QWidget()
        content.setLayout(main_layout)

        root = QHBoxLayout()
        root.setContentsMargins(22, 18, 22, 22)
        root.setSpacing(14)
        root.addWidget(self._build_history_sidebar())
        root.addWidget(content, 1)
        self.setLayout(root)

        self._refresh_history()

    # -------------------- Recording & Processing --------------------

    def load_initial_models(self):
        """Pre-loads Whisper model on startup."""
        try:
            self.speech_models.load_whisper()
            self.status_label.setText("Ready")
            self.set_mic_on_style(True)
        except Exception as e:
            logger.error(f"Error loading initial models: {e}", exc_info=True)
            self.status_label.setText("Error loading model")
            QMessageBox.critical(self, "Error", f"Failed to load Whisper model: {e}")

    def audio_callback(self, indata, frames, time_info, status):
        if not self.is_recording:
            return

        # RMS amplitude -> 0-100 level for the indicator (emitted to GUI thread)
        rms = float(np.sqrt(np.mean(np.square(indata))))
        self.level_changed.emit(min(100, int(rms * 400)))

        # Cut a chunk (with a small overlap tail) for live transcription
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

                # Prepend the tail of the previous chunk so words spoken at the
                # boundary are captured fully; duplicate words are merged later.
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
        """Background loop (app lifetime): transcribes queued audio chunks in
        order and emits text live. A _FLUSH marker finalizes the session."""
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
                    if merged:
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
        """Drops words repeated across the audio overlap between chunks:
        finds the longest suffix/prefix word match (up to 8 words) and
        strips it from the new chunk's start."""
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

    def start_recording(self):
        self.is_recording = True
        with self.frames_lock:
            self.audio_frames = []
            self._buffered_samples = 0
            self._overlap_tail = None
        self.session_raw_parts = []
        self._last_chunk_text = ""

        # Start the recording timer
        self.rec_start_ts = time.time()
        self.timer_label.setText("⏱ 00:00")
        self.timer_label.setVisible(True)
        self.rec_timer.start()

        # Show the floating mic-level indicator (re-center unless the user moved it)
        self.level_indicator.set_level(0)
        if not self.level_indicator.user_moved:
            self.level_indicator.center_on_parent()
        self.level_indicator.show()
        self.level_indicator.raise_()

        # Disable Mic ON button (turns gray) and enable Mic OFF button while recording
        self.set_mic_on_style(False)
        self.mic_off_btn.setEnabled(True)

        # Display large speaking icon
        self.speaking_icon_label.setVisible(True)

        if self.settings.get("live_transcription", True):
            self.status_label.setText("🔴 Recording · live")
        else:
            self.status_label.setText("🔴 Recording")

        self.stream = sd.InputStream(
            samplerate=config.SAMPLE_RATE, channels=1, callback=self.audio_callback
        )
        self.stream.start()

    def stop_recording(self):
        self.is_recording = False
        self.mic_off_btn.setEnabled(False)
        self.rec_timer.stop()

        # Hide the speaking indicators when recording stops
        self.speaking_icon_label.setVisible(False)
        self.timer_label.setVisible(False)
        self.level_indicator.hide()

        if hasattr(self, "stream"):
            self.stream.stop()
            self.stream.close()

        # Queue whatever audio is still buffered, then the flush marker
        with self.frames_lock:
            if self.audio_frames:
                remaining = np.concatenate(self.audio_frames, axis=0).flatten().astype(np.float32)
                self.audio_frames = []
                self._buffered_samples = 0
            else:
                remaining = None

        min_samples = int(config.SAMPLE_RATE * 0.4)  # drop sub-0.4s tail clicks
        if remaining is not None and len(remaining) >= min_samples:
            self.stream_queue.put(remaining)
        self.stream_queue.put(_FLUSH)

        self.status_label.setText("Transcribing…")

    # -------------------- Live transcription slots --------------------

    @pyqtSlot(str)
    def on_partial_text(self, text):
        """A chunk was transcribed while still recording — show it live."""
        self.orig_display.append(text)

    @pyqtSlot()
    def on_stream_drained(self):
        """All audio for the session is transcribed — optimize + finalize."""
        raw_text = " ".join(self.session_raw_parts).strip()
        if not raw_text:
            self.orig_display.append("[No speech recognized]\n")
            self.reset_ui()
            return

        api_key = self.settings.get("openai_api_key", "")
        if api_key:
            self.status_label.setText("Optimizing…")
            self.optimize_worker = OptimizeWorker(
                self.speech_models,
                raw_text,
                api_key,
                self.settings.get("openai_prompt", ""),
            )
            self.optimize_worker.finished.connect(self.on_optimize_finished)
            self.optimize_worker.error.connect(self.on_optimize_error)
            threading.Thread(
                target=self.optimize_worker.run, daemon=True, name="OptimizeWorker"
            ).start()
        else:
            self.opt_display.append(
                "[No OpenAI API key configured — open ⚙️ Settings to add one]\n"
            )
            self._finalize_session("")

    @pyqtSlot(str)
    def on_optimize_finished(self, optimized_text):
        if optimized_text:
            self.opt_display.append(optimized_text + "\n")
        else:
            self.opt_display.append("[OpenAI optimization returned no text]\n")
        self._finalize_session(optimized_text or "")

    @pyqtSlot(str)
    def on_optimize_error(self, err_msg):
        # Keep the raw text visible as fallback, then surface the error
        raw_text = " ".join(self.session_raw_parts).strip()
        self.opt_display.append("[OpenAI optimization failed — raw text]\n" + raw_text + "\n")
        QMessageBox.critical(self, "Error", err_msg)
        self._finalize_session("")

    def _finalize_session(self, optimized_text: str):
        raw_text = " ".join(self.session_raw_parts).strip()
        if raw_text and self.settings.get("save_history", True):
            try:
                history_manager.save_transcription(raw_text, optimized_text)
                self._refresh_history()  # new session appears in the sidebar
            except Exception as e:
                logger.error(f"Failed to save history: {e}", exc_info=True)
        if not self.is_recording:
            self.reset_ui()

    # -------------------- Utility Actions --------------------

    def copy_orig_text(self):
        clipboard = QApplication.clipboard()
        clipboard.setText(self.orig_display.toPlainText())
        self.status_label.setText("Copied original text")

    def copy_opt_text(self):
        clipboard = QApplication.clipboard()
        clipboard.setText(self.opt_display.toPlainText())
        self.status_label.setText("Copied optimized text")

    def clear_text(self):
        self.orig_display.clear()
        self.opt_display.clear()
        self.status_label.setText("Cleared")

    def reset_ui(self):
        self.set_mic_on_style(True)
        self.mic_off_btn.setEnabled(False)
        self.speaking_icon_label.setVisible(False)
        self.level_indicator.hide()
        self.status_label.setText("Ready")

    def _update_rec_timer(self):
        """Ticks while recording: shows elapsed MM:SS next to the speaking icon."""
        if self.rec_start_ts is None:
            return
        elapsed = int(time.time() - self.rec_start_ts)
        self.timer_label.setText(f"⏱ {elapsed // 60:02d}:{elapsed % 60:02d}")

    def resizeEvent(self, event):
        super().resizeEvent(event)
        # Keep the indicator centered on window resize unless the user moved it
        if (
            hasattr(self, "level_indicator")
            and self.level_indicator.isVisible()
            and not self.level_indicator.user_moved
        ):
            self.level_indicator.center_on_parent()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = SpeechToTextApp()
    window.show()
    sys.exit(app.exec_())
