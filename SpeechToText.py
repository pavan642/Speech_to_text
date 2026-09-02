# To run : python3 SpeechToText.py
# libraries to install 
# pip3 install PyQt5 faster-whisper sounddevice numpy transformers torch

#. Summary
#
# This desktop application captures speech from a microphone, converts it to text, cleans up its grammar, and displays both versions side-by-side.
#
# **Core Functionality & Architecture**
#
# * **User Interface (`PyQt5`):** Displays a dual-panel text view (**Original Text** on the left, **Grammar Corrected Text** on the right), a status indicator, audio controls (**Mic ON / Mic OFF**), and utility action buttons (**Copy Original**, **Copy Corrected**, **Clear**, and **Close**).
# * **Audio Capture (`sounddevice` & `numpy`):** Captures single-channel PCM audio at 16 kHz during active recording and compiles the buffer frames into a flattened $1\text{D}$ array when **Mic OFF** is pressed.
# * **Transcription Engine (`faster-whisper`):** Processes the raw audio array using a quantized (`int8`) Whisper Base model on the CPU to extract a fast, raw text transcription.
# * **Grammar & Beautification (`transformers` & `Grammarly CoEdIT`):** Uses `grammarly/coedit-large` to polish the output. To prevent text truncation on long transcriptions, a regex function splits the transcript into sentence-level chunks ($\le 150$ characters), passes each chunk through the model with the prompt `"Fix grammatical errors in this text: "`, and reassembles the corrected output.
# * **Multithreading & Logging:** Executes AI operations asynchronously inside background threads (`ProcessingWorker`) to keep the desktop window responsive. Uses PyQt signals (`pyqtSignal`) for thread-safe UI updates and logs runtime steps directly to `sys.stdout`.


import logging
import re
import sys
import threading
import time
import warnings

# Suppress harmless NumPy warnings on Mac
warnings.filterwarnings("ignore", category=RuntimeWarning, module="numpy")

from faster_whisper import WhisperModel
import numpy as np
from PyQt5.QtCore import QObject, Qt, pyqtSignal, pyqtSlot
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import (
    QApplication,
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
from transformers import AutoModelForSeq2SeqLM, AutoTokenizer

# Configure Logging using StreamHandler
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("SpeechGrammarApp")

SAMPLE_RATE = 16000


class ProcessingWorker(QObject):
    finished = pyqtSignal(str, str)
    error = pyqtSignal(str)

    def __init__(self, whisper_model, t5_model, t5_tokenizer, audio_data):
        super().__init__()
        self.whisper_model = whisper_model
        self.t5_model = t5_model
        self.t5_tokenizer = t5_tokenizer
        self.audio_data = audio_data

    def split_into_sentences(self, text):
        """Splits transcript into logical sentence chunks for T5 processing."""
        sentences = re.split(r"(?<=[.!?])\s+", text)
        chunks = []
        current_chunk = ""

        for sentence in sentences:
            if len(current_chunk) + len(sentence) < 150:
                current_chunk += sentence + " "
            else:
                chunks.append(current_chunk.strip())
                current_chunk = sentence + " "

        if current_chunk:
            chunks.append(current_chunk.strip())

        return chunks

    def run(self):
        try:
            # 1. Transcribe Audio
            logger.info("Transcribing audio with Whisper...")
            segments, info = self.whisper_model.transcribe(
                self.audio_data,
                beam_size=1,
                language="en",
                condition_on_previous_text=False,
                vad_filter=False,
            )
            raw_text = " ".join([s.text.strip() for s in segments if s.text.strip()])

            if not raw_text:
                self.finished.emit("", "")
                return

            logger.info(f"Raw Output Length: {len(raw_text)} chars")

            # 2. Chunk-based Grammar Correction with Grammarly CoEdIT
            corrected_chunks = []
            if self.t5_model and self.t5_tokenizer:
                logger.info("Applying chunked grammar correction with Grammarly CoEdIT...")
                chunks = self.split_into_sentences(raw_text)

                for chunk in chunks:
                    prompt = "Fix grammatical errors in this text: " + chunk
                    inputs = self.t5_tokenizer(
                        prompt, return_tensors="pt", max_length=256, truncation=True
                    )
                    outputs = self.t5_model.generate(
                        **inputs, max_length=256, num_beams=2, early_stopping=True
                    )
                    corrected_chunk = self.t5_tokenizer.decode(
                        outputs[0], skip_special_tokens=True
                    )
                    corrected_chunks.append(corrected_chunk)

                corrected_text = " ".join(corrected_chunks)
            else:
                corrected_text = raw_text

            logger.info(f"Corrected Output Length: {len(corrected_text)} chars")
            self.finished.emit(raw_text, corrected_text)

        except Exception as e:
            logger.error(f"Processing failed: {e}", exc_info=True)
            self.error.emit(str(e))


class SpeechToTextGrammarApp(QWidget):

    def __init__(self):
        super().__init__()
        self.is_recording = False
        self.audio_frames = []
        self.whisper_model = None
        self.t5_model = None
        self.t5_tokenizer = None

        self.init_ui()
        threading.Thread(
            target=self.load_models, daemon=True, name="ModelLoader"
        ).start()

    def init_ui(self):
        self.setWindowTitle("Speech to Text App")
        self.resize(950, 600)

        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(10)

        # Header
        title_label = QLabel("Speech to Text App")
        title_label.setFont(QFont("Helvetica", 18, QFont.Bold))
        title_label.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(title_label)

        self.status_label = QLabel("Status: Loading AI Models...")
        self.status_label.setFont(QFont("Helvetica", 10))
        self.status_label.setStyleSheet("color: #0066CC;")
        self.status_label.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(self.status_label)

        # Dual Text Box Splitter
        text_splitter = QSplitter(Qt.Horizontal)

        # Original Text
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

        # Corrected Text
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

        # Mic Buttons
        mic_btn_layout = QHBoxLayout()
        self.mic_on_btn = QPushButton("🎙️ Mic ON")
        self.mic_on_btn.setFont(QFont("Helvetica", 11, QFont.Bold))
        self.mic_on_btn.setStyleSheet(
            "background-color: #4CAF50; color: white; padding: 8px; border-radius: 5px;"
        )
        self.mic_on_btn.setEnabled(False)
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

        # Action Buttons
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

    def load_models(self):
        try:
            logger.info("Loading Whisper base model...")
            self.whisper_model = WhisperModel(
                "base", device="cpu", compute_type="int8"
            )

            # Using Grammarly CoEdIT-Large model
            model_name = "grammarly/coedit-large"
            logger.info(f"Loading Grammar Model ({model_name})...")
            self.t5_tokenizer = AutoTokenizer.from_pretrained(model_name)
            self.t5_model = AutoModelForSeq2SeqLM.from_pretrained(model_name)

            logger.info("All models loaded cleanly.")
            self.status_label.setText("Status: Ready (Models Loaded)")
            self.mic_on_btn.setEnabled(True)
        except Exception as e:
            logger.error(f"Model loading error: {e}", exc_info=True)
            self.status_label.setText("Status: Error loading models")
            QMessageBox.critical(self, "Error", f"Failed to load AI models: {e}")

    def audio_callback(self, indata, frames, time_info, status):
        if self.is_recording:
            self.audio_frames.append(indata.copy())

    def start_recording(self):
        self.is_recording = True
        self.audio_frames = []
        self.mic_on_btn.setEnabled(False)
        self.mic_off_btn.setEnabled(True)
        self.status_label.setText("Status: 🔴 Recording... Speak into mic")

        self.stream = sd.InputStream(
            samplerate=SAMPLE_RATE, channels=1, callback=self.audio_callback
        )
        self.stream.start()

    def stop_recording(self):
        self.is_recording = False
        self.mic_off_btn.setEnabled(False)
        self.status_label.setText("Status: Processing transcription & grammar...")

        if hasattr(self, "stream"):
            self.stream.stop()
            self.stream.close()

        if not self.audio_frames:
            self.reset_ui()
            return

        audio_data = np.concatenate(self.audio_frames, axis=0).flatten().astype(np.float32)

        self.worker = ProcessingWorker(
            self.whisper_model, self.t5_model, self.t5_tokenizer, audio_data
        )
        self.worker.finished.connect(self.on_processing_finished)
        self.worker.error.connect(self.on_processing_error)

        threading.Thread(target=self.worker.run, daemon=True).start()

    @pyqtSlot(str, str)
    def on_processing_finished(self, raw_text, corrected_text):
        if raw_text:
            self.orig_display.append(raw_text + "\n")
            self.corr_display.append(corrected_text + "\n")
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
        self.mic_on_btn.setEnabled(True)
        self.mic_off_btn.setEnabled(False)
        self.status_label.setText("Status: Ready")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = SpeechToTextGrammarApp()
    window.show()
    sys.exit(app.exec_())
