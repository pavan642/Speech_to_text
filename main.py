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
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QSplitter,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)
import sounddevice as sd

import config
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

    def __init__(self, speech_models: SpeechModels, audio_data, use_llm: bool):
        super().__init__()
        self.speech_models = speech_models
        self.audio_data = audio_data
        self.use_llm = use_llm

    def run(self):
        try:
            # 1. Transcribe
            raw_text = self.speech_models.transcribe_audio(self.audio_data)
            if not raw_text:
                self.finished.emit("", "")
                return

            # 2. Optional Grammar Correction
            corrected_text = ""
            if self.use_llm:
                corrected_text = self.speech_models.correct_grammar(raw_text)

            self.finished.emit(raw_text, corrected_text)

        except Exception as e:
            logger.error(f"Processing failed: {e}", exc_info=True)
            self.error.emit(str(e))


class SpeechToTextGrammarApp(QWidget):

    def __init__(self):
        super().__init__()
        self.is_recording = False
        self.audio_frames = []
        self.speech_models = SpeechModels()

        self.init_ui()
        self.set_app_icon_from_url(config.APP_ICON_URL)

        # Pre-load Whisper model asynchronously
        threading.Thread(
            target=self.load_initial_models, daemon=True, name="ModelLoader"
        ).start()

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

        # 1. Header
        title_label = QLabel(config.APP_TITLE)
        title_label.setFont(QFont("Helvetica", 18, QFont.Bold))
        title_label.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(title_label)

        # 2. LLM Toggle Checkbox
        llm_toggle_layout = QHBoxLayout()
        self.llm_toggle = QCheckBox("✨ Enable Local LLM Grammar Correction (CoEdIT)")
        self.llm_toggle.setFont(QFont("Helvetica", 11, QFont.Bold))
        self.llm_toggle.setChecked(False)  # Disabled by default
        self.llm_toggle.setStyleSheet("color: #2E7D32; padding: 5px;")
        llm_toggle_layout.addStretch()
        llm_toggle_layout.addWidget(self.llm_toggle)
        llm_toggle_layout.addStretch()
        main_layout.addLayout(llm_toggle_layout)

        # 3. Speaking Icon Indicator (PLACED BELOW LLM TOGGLE AT 2X SIZE)
        speaking_text = getattr(config, "SPEAKING_INDICATOR_TEXT", "🗣️ Speaking...")
        self.speaking_icon_label = QLabel(speaking_text)
        self.speaking_icon_label.setFont(QFont("Helvetica", 22, QFont.Bold))  # Double font size (22pt)
        self.speaking_icon_label.setStyleSheet("color: #FF9800; padding: 5px;")
        self.speaking_icon_label.setAlignment(Qt.AlignCenter)
        self.speaking_icon_label.setVisible(False)  # Hidden by default
        main_layout.addWidget(self.speaking_icon_label)

        # 4. Status Bar
        self.status_label = QLabel("Status: Loading Whisper Model...")
        self.status_label.setFont(QFont("Helvetica", 10))
        self.status_label.setStyleSheet("color: #0066CC;")
        self.status_label.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(self.status_label)

        # 5. Dual Text Box Splitter
        text_splitter = QSplitter(Qt.Horizontal)

        # Original Text Panel
        orig_box = QWidget()
        orig_layout = QVBoxLayout(orig_box)
        orig_layout.setContentsMargins(0, 0, 0, 0)
        orig_label = QLabel("Original Text:")
        orig_label.setFont(QFont("Helvetica", 11, QFont.Bold))
        self.orig_display = QTextEdit()
        self.orig_display.setFont(QFont("Helvetica", 11))
        self.orig_display.setStyleSheet("background-color: #FFFFFF; color: #333333;")
        orig_layout.addWidget(orig_label)
        orig_layout.addWidget(self.orig_display)

        # Corrected Text Panel
        corr_box = QWidget()
        corr_layout = QVBoxLayout(corr_box)
        corr_layout.setContentsMargins(0, 0, 0, 0)
        corr_label = QLabel("Grammar Corrected Text:")
        corr_label.setFont(QFont("Helvetica", 11, QFont.Bold))
        self.corr_display = QTextEdit()
        self.corr_display.setFont(QFont("Helvetica", 11))
        self.corr_display.setStyleSheet("background-color: #F4F9F4; color: #000000;")
        corr_layout.addWidget(corr_label)
        corr_layout.addWidget(self.corr_display)

        text_splitter.addWidget(orig_box)
        text_splitter.addWidget(corr_box)
        text_splitter.setSizes([475, 475])
        main_layout.addWidget(text_splitter)

        # 6. Mic Control Buttons
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

        # 7. Action Utility Buttons
        action_btn_layout = QHBoxLayout()

        self.copy_orig_btn = QPushButton("📋 Copy Original Text")
        self.copy_orig_btn.setFont(QFont("Helvetica", 10))
        self.copy_orig_btn.clicked.connect(self.copy_orig_text)

        self.copy_corr_btn = QPushButton("📋 Copy Corrected Text")
        self.copy_corr_btn.setFont(QFont("Helvetica", 10))
        self.copy_corr_btn.clicked.connect(self.copy_corr_text)

        self.clear_btn = QPushButton("🧹 Clear Text")
        self.clear_btn.setFont(QFont("Helvetica", 10))
        self.clear_btn.clicked.connect(self.clear_text)

        self.close_btn = QPushButton("❌ Close App")
        self.close_btn.setFont(QFont("Helvetica", 10))
        self.close_btn.setStyleSheet("background-color: #E0E0E0;")
        self.close_btn.clicked.connect(self.close)

        action_btn_layout.addWidget(self.copy_orig_btn)
        action_btn_layout.addWidget(self.copy_corr_btn)
        action_btn_layout.addWidget(self.clear_btn)
        action_btn_layout.addWidget(self.close_btn)
        main_layout.addLayout(action_btn_layout)

        self.setLayout(main_layout)

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
        
        # Display large speaking icon below LLM toggle
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

        use_llm = self.llm_toggle.isChecked()
        if use_llm:
            self.status_label.setText("Status: Transcribing & Applying Grammar Correction...")
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
            use_llm=use_llm,
        )
        self.worker.finished.connect(self.on_processing_finished)
        self.worker.error.connect(self.on_processing_error)

        threading.Thread(target=self.worker.run, daemon=True).start()

    @pyqtSlot(str, str)
    def on_processing_finished(self, raw_text, corrected_text):
        if raw_text:
            self.orig_display.append(raw_text + "\n")
            if corrected_text:
                self.corr_display.append(corrected_text + "\n")
            else:
                self.corr_display.append("[LLM Disabled - No Correction Applied]\n")
        else:
            self.orig_display.append("[No speech recognized]\n")

        self.reset_ui()

    @pyqtSlot(str)
    def on_processing_error(self, err_msg):
        QMessageBox.critical(self, "Error", f"Processing failed: {err_msg}")
        self.reset_ui()

    def copy_orig_text(self):
        clipboard = QApplication.clipboard()
        clipboard.setText(self.orig_display.toPlainText())
        self.status_label.setText("Status: Original text copied to clipboard!")

    def copy_corr_text(self):
        clipboard = QApplication.clipboard()
        clipboard.setText(self.corr_display.toPlainText())
        self.status_label.setText("Status: Corrected text copied to clipboard!")

    def clear_text(self):
        self.orig_display.clear()
        self.corr_display.clear()
        self.status_label.setText("Status: Text cleared")

    def reset_ui(self):
        self.set_mic_on_style(True)
        self.mic_off_btn.setEnabled(False)
        self.speaking_icon_label.setVisible(False)
        self.status_label.setText("Status: Ready")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = SpeechToTextGrammarApp()
    window.show()
    sys.exit(app.exec_())