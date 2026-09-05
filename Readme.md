Here is a complete technical summary of the modularized **Speech-to-Text Desktop Application**:

---

### **Overview**

The application is a desktop GUI utility built in Python using **PyQt5**. It captures real-time audio input from a microphone, converts the speech into raw text using a quantized Whisper model, and optionally passes the raw text through a local Hugging Face transformer model (`grammarly/coedit-large`) to correct grammar and polish the sentence structure.

---

### **Core Features & Functionality**

1. **Real-time Audio Capture:** Uses `sounddevice` to stream single-channel PCM audio at 16 kHz during recording, concatenating raw audio buffers into a flattened NumPy array upon stopping.
2. **Fast Local Speech Transcription:** Processes the raw audio array using `faster-whisper` (`base` model, quantized to `int8` on CPU) for rapid, lightweight speech-to-text conversion.
3. **Optional LLM Grammar Correction:** Features a top-level UI toggle (`QCheckBox`).
* **When Enabled:** Splits the raw transcribed text into sentence-level chunks ($\le 150$ characters) using regular expressions and passes them through `grammarly/coedit-large` to generate grammatically corrected text.
* **When Disabled:** Skips the transformer model entirely to save system resources and outputs only the raw transcription.


4. **Asynchronous Multithreading:** Runs all speech recognition and LLM inference tasks inside a background `ProcessingWorker` thread using PyQt signals to keep the desktop interface responsive.
5. **Dual-Panel Display UI:** Shows the raw transcription on the left panel and the grammar-corrected text on the right panel, supported by utility controls for copying text, clearing fields, and managing microphone state.

---

### **Architecture & Module Breakdown**

* **`config.py` (Configuration):**
* Centralizes application constants, including audio sampling rates (`16000 Hz`), model configurations (Whisper `base` and T5 `grammarly/coedit-large`), UI window dimensions, and the external URL for the top-left application icon.


* **`models.py` (Machine Learning Engine):**
* **`SpeechModels` Class:** Manages the lifecycle of both AI models.
* **Lazy Loading:** Pre-loads the Whisper model on app startup while loading the T5 grammar model on-demand only if the user enables the LLM feature.
* **Chunking Logic:** Includes a sentence-splitter method to prevent truncation issues during T5 seq2seq generation.


* **`main.py` (User Interface & Application Entry):**
* **`SpeechToTextGrammarApp`:** Defines the main PyQt5 window, custom window icon fetching, dual-panel display layout, microphone state handlers, and clipboard action buttons.
* **`ProcessingWorker`:** A `QObject` worker executed via `threading.Thread` that coordinates non-blocking execution between audio input and `SpeechModels`.

--------------------------------------------------------------------------------------

App Execution  logs

python3 main.py 
/Users/pavanpersonal/Library/Python/3.9/lib/python/site-packages/urllib3/__init__.py:35: NotOpenSSLWarning: urllib3 v2 only supports OpenSSL 1.1.1+, currently the 'ssl' module is compiled with 'LibreSSL 2.8.3'. See: https://github.com/urllib3/urllib3/issues/3020
  warnings.warn(
2026-09-05 07:15:05,023 [WARNING] Failed to load window icon from URL: HTTP Error 403: Forbidden
2026-09-05 07:15:05,023 [INFO] Loading Whisper model...
2026-09-05 07:15:05,567 [INFO] Whisper model loaded successfully.
2026-09-05 07:15:20,102 [INFO] Transcribing audio with Whisper...
2026-09-05 07:15:20,103 [INFO] Processing audio with duration 00:06.648
/Users/pavanpersonal/Library/Python/3.9/lib/python/site-packages/faster_whisper/feature_extractor.py:224: RuntimeWarning: divide by zero encountered in matmul
  mel_spec = self.mel_filters @ magnitudes
/Users/pavanpersonal/Library/Python/3.9/lib/python/site-packages/faster_whisper/feature_extractor.py:224: RuntimeWarning: overflow encountered in matmul
  mel_spec = self.mel_filters @ magnitudes
/Users/pavanpersonal/Library/Python/3.9/lib/python/site-packages/faster_whisper/feature_extractor.py:224: RuntimeWarning: invalid value encountered in matmul
  mel_spec = self.mel_filters @ magnitudes