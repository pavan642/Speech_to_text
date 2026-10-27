# main.py
import logging
import sys
import threading
import urllib.request
import warnings

# Suppress harmless NumPy warnings
warnings.filterwarnings("ignore", category=RuntimeWarning, module="numpy")

import numpy as np
from PyQt5.QtCore import QObject, Qt, pyqtSignal, pyqtSlot
from PyQt5.QtGui import QFont, QIcon, QPixmap
from PyQt5.QtWidgets import (
    QApplication,
    QCheckBox,
    QDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
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
import settings_manager
from models import SpeechModels

# Configure Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("SpeechGrammarApp")


class ProcessingWorker(QObject):
    finished = pyqtSignal(str, str)
    error = pyqtSignal(str)

    def __init__(self, speech_models: SpeechModels, audio_data, api_key: str):
        super().__init__()
        self.speech_models = speech_models
        self.audio_data = audio_data
        self.api_key = api_key

    def run(self):
        try:
            # 1. Transcribe locally with Whisper
            raw_text = self.speech_models.transcribe_audio(self.audio_data)
            if not raw_text:
                self.finished.emit("", "")
                return

            # 2. Optionally optimize via OpenAI — on ANY failure, keep the raw
            #    transcription and still surface the error as a popup.
            optimized_text = ""
            opt_error = None
            if self.api_key:
                try:
                    optimized_text = self.speech_models.optimize_text(raw_text, self.api_key)
                except Exception as e:
                    logger.error(f"OpenAI optimization failed: {e}", exc_info=True)
                    opt_error = str(e)

            # Emit finished first so the transcribed text always reaches the UI.
            self.finished.emit(raw_text, optimized_text)
            if opt_error:
                self.error.emit(f"OpenAI optimization failed: {opt_error}")

        except Exception as e:
            logger.error(f"Processing failed: {e}", exc_info=True)
            self.error.emit(f"Processing failed: {e}")


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

        api_group.setLayout(api_layout)
        layout.addWidget(api_group)

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

        # --- Dialog Buttons ---
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)

        save_btn = QPushButton("💾 Save")
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
        }


class SpeechToTextApp(QWidget):

    def __init__(self):
        super().__init__()
        self.is_recording = False
        self.audio_frames = []
        self.speech_models = SpeechModels()
        self.settings = settings_manager.load_settings()

        self.init_ui()
        self.set_app_icon_from_url(config.APP_ICON_URL)
        self.apply_theme(self.settings.get("theme", "light"))

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
            self.status_label.setStyleSheet("color: #4DA3FF;")
        else:
            app.setStyleSheet(config.LIGHT_THEME)
            self.status_label.setStyleSheet("color: #0066CC;")

    # -------------------- Settings --------------------

    def open_settings(self):
        dialog = SettingsDialog(self.settings, self)
        if dialog.exec_() == QDialog.Accepted:
            self.settings = dialog.get_settings()
            settings_manager.save_settings(self.settings)
            self.apply_theme(self.settings["theme"])

            key_state = "configured" if self.settings["openai_api_key"] else "not configured"
            self.status_label.setText(f"Status: Settings saved (OpenAI key {key_state})")
            logger.info(f"Settings updated: theme={self.settings['theme']}, api_key={key_state}")

    # -------------------- UI Setup --------------------

    def set_app_icon_from_url(self, url: str):
        """Downloads icon image from URL and sets as top-left app icon."""
        try:
            req = urllib.request.Request(
                url, headers={"User-Agent": "Mozilla/5.0"}
            )
            data = urllib.request.urlopen(req).read()
            pixmap = QPixmap()
            pixmap.loadFromData(data)
            self.setWindowIcon(QIcon(pixmap))
        except Exception as e:
            logger.warning(f"Failed to load window icon from URL: {e}")

    def set_mic_on_style(self, enabled: bool):
        """Applies explicit green style when enabled and gray style when disabled."""
        if enabled:
            self.mic_on_btn.setEnabled(True)
            self.mic_on_btn.setStyleSheet(
                "background-color: #4CAF50; color: white; padding: 8px; border-radius: 5px;"
            )
        else:
            self.mic_on_btn.setEnabled(False)
            self.mic_on_btn.setStyleSheet(
                "background-color: #9E9E9E; color: white; padding: 8px; border-radius: 5px;"
            )

    def init_ui(self):
        self.setWindowTitle(config.APP_TITLE)
        self.resize(config.WINDOW_WIDTH, config.WINDOW_HEIGHT)

        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(10)

        # 1. Header: centered title + settings button pinned to the top-right corner
        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(0, 0, 0, 0)

        title_label = QLabel(config.APP_TITLE)
        title_label.setFont(QFont("Helvetica", 18, QFont.Bold))
        title_label.setAlignment(Qt.AlignCenter)

        self.settings_btn = QPushButton("⚙️")
        self.settings_btn.setFont(QFont("Helvetica", 14))
        self.settings_btn.setFixedSize(42, 42)
        self.settings_btn.setToolTip("Open Settings")
        self.settings_btn.setCursor(Qt.PointingHandCursor)
        self.settings_btn.clicked.connect(self.open_settings)

        header_layout.addStretch()
        header_layout.addWidget(title_label)
        header_layout.addStretch()
        header_layout.addWidget(self.settings_btn)
        main_layout.addLayout(header_layout)

        # 2. Speaking Icon Indicator
        speaking_text = getattr(config, "SPEAKING_INDICATOR_TEXT", "🗣️ Speaking...")
        self.speaking_icon_label = QLabel(speaking_text)
        self.speaking_icon_label.setFont(QFont("Helvetica", 22, QFont.Bold))
        self.speaking_icon_label.setStyleSheet("color: #FF9800; padding: 5px;")
        self.speaking_icon_label.setAlignment(Qt.AlignCenter)
        self.speaking_icon_label.setVisible(False)  # Hidden by default
        main_layout.addWidget(self.speaking_icon_label)

        # 3. Status Bar
        self.status_label = QLabel("Status: Loading Whisper Model...")
        self.status_label.setFont(QFont("Helvetica", 10))
        self.status_label.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(self.status_label)

        # 4. Dual Text Box Splitter
        text_splitter = QSplitter(Qt.Horizontal)

        # Original Text Panel
        orig_box = QWidget()
        orig_layout = QVBoxLayout(orig_box)
        orig_layout.setContentsMargins(0, 0, 0, 0)
        orig_label = QLabel("Original Text:")
        orig_label.setFont(QFont("Helvetica", 11, QFont.Bold))
        self.orig_display = QTextEdit()
        self.orig_display.setFont(QFont("Helvetica", 11))
        orig_layout.addWidget(orig_label)
        orig_layout.addWidget(self.orig_display)

        # Optimized Text Panel
        opt_box = QWidget()
        opt_layout = QVBoxLayout(opt_box)
        opt_layout.setContentsMargins(0, 0, 0, 0)
        opt_label = QLabel("Optimized Text (OpenAI):")
        opt_label.setFont(QFont("Helvetica", 11, QFont.Bold))
        self.opt_display = QTextEdit()
        self.opt_display.setFont(QFont("Helvetica", 11))
        opt_layout.addWidget(opt_label)
        opt_layout.addWidget(self.opt_display)

        text_splitter.addWidget(orig_box)
        text_splitter.addWidget(opt_box)
        text_splitter.setSizes([475, 475])
        main_layout.addWidget(text_splitter)

        # 5. Mic Control Buttons
        mic_btn_layout = QHBoxLayout()
        self.mic_on_btn = QPushButton("🎙️ Mic ON")
        self.mic_on_btn.setFont(QFont("Helvetica", 11, QFont.Bold))
        self.set_mic_on_style(False)  # Disabled initially until models load
        self.mic_on_btn.clicked.connect(self.start_recording)

        self.mic_off_btn = QPushButton("🛑 Mic OFF")
        self.mic_off_btn.setFont(QFont("Helvetica", 11, QFont.Bold))
        self.mic_off_btn.setStyleSheet(
            "background-color: #f44336; color: white; padding: 8px; border-radius: 5px;"
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

        self.setLayout(main_layout)

    # -------------------- Recording & Processing --------------------

    def load_initial_models(self):
        """Pre-loads Whisper model on startup."""
        try:
            self.speech_models.load_whisper()
            self.status_label.setText("Status: Ready (Whisper Loaded)")
            self.set_mic_on_style(True)
        except Exception as e:
            logger.error(f"Error loading initial models: {e}", exc_info=True)
            self.status_label.setText("Status: Error loading models")
            QMessageBox.critical(self, "Error", f"Failed to load Whisper model: {e}")

    def audio_callback(self, indata, frames, time_info, status):
        if self.is_recording:
            self.audio_frames.append(indata.copy())

    def start_recording(self):
        self.is_recording = True
        self.audio_frames = []

        # Disable Mic ON button (turns gray) and enable Mic OFF button while recording
        self.set_mic_on_style(False)
        self.mic_off_btn.setEnabled(True)

        # Display large speaking icon
        self.speaking_icon_label.setVisible(True)

        self.status_label.setText("Status: 🔴 Recording... Speak into mic")

        self.stream = sd.InputStream(
            samplerate=config.SAMPLE_RATE, channels=1, callback=self.audio_callback
        )
        self.stream.start()

    def stop_recording(self):
        self.is_recording = False
        self.mic_off_btn.setEnabled(False)

        # Hide the speaking indicator when recording stops
        self.speaking_icon_label.setVisible(False)

        api_key = self.settings.get("openai_api_key", "")
        if api_key:
            self.status_label.setText("Status: Transcribing & Optimizing via OpenAI...")
        else:
            self.status_label.setText("Status: Transcribing Speech...")

        if hasattr(self, "stream"):
            self.stream.stop()
            self.stream.close()

        if not self.audio_frames:
            self.reset_ui()
            return

        audio_data = np.concatenate(self.audio_frames, axis=0).flatten().astype(np.float32)

        self.worker = ProcessingWorker(
            self.speech_models,
            audio_data,
            api_key=api_key,
        )
        self.worker.finished.connect(self.on_processing_finished)
        self.worker.error.connect(self.on_processing_error)

        threading.Thread(target=self.worker.run, daemon=True).start()

    @pyqtSlot(str, str)
    def on_processing_finished(self, raw_text, optimized_text):
        if raw_text:
            self.orig_display.append(raw_text + "\n")
            if optimized_text:
                self.opt_display.append(optimized_text + "\n")
            elif self.settings.get("openai_api_key"):
                # Key is configured but the API call failed — still show the raw text
                self.opt_display.append(
                    "[OpenAI optimization failed — raw text]\n" + raw_text + "\n"
                )
            else:
                self.opt_display.append(
                    "[No OpenAI API key configured — open ⚙️ Settings to add one]\n"
                )
        else:
            self.orig_display.append("[No speech recognized]\n")

        self.reset_ui()

    @pyqtSlot(str)
    def on_processing_error(self, err_msg):
        QMessageBox.critical(self, "Error", err_msg)
        self.reset_ui()

    # -------------------- Utility Actions --------------------

    def copy_orig_text(self):
        clipboard = QApplication.clipboard()
        clipboard.setText(self.orig_display.toPlainText())
        self.status_label.setText("Status: Original text copied to clipboard!")

    def copy_opt_text(self):
        clipboard = QApplication.clipboard()
        clipboard.setText(self.opt_display.toPlainText())
        self.status_label.setText("Status: Optimized text copied to clipboard!")

    def clear_text(self):
        self.orig_display.clear()
        self.opt_display.clear()
        self.status_label.setText("Status: Text cleared")

    def reset_ui(self):
        self.set_mic_on_style(True)
        self.mic_off_btn.setEnabled(False)
        self.speaking_icon_label.setVisible(False)
        self.status_label.setText("Status: Ready")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = SpeechToTextApp()
    window.show()
    sys.exit(app.exec_())
