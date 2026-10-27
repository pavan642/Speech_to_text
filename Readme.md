Here is a complete technical summary of the modularized **Speech-to-Text Desktop Application**:

---

### **Overview**

The application is a desktop GUI utility built in Python using **PyQt5**. It captures real-time audio input from a microphone, converts the speech into raw text using a quantized Whisper model, and optionally sends the transcription to the **OpenAI API** for optimization (grammar, clarity, and flow) — using a user-configured API key.

---

### **Core Features & Functionality**

1. **Real-time Audio Capture:** Uses `sounddevice` to stream single-channel PCM audio at 16 kHz during recording, concatenating raw audio buffers into a flattened NumPy array upon stopping.
2. **Fast Local Speech Transcription:** Processes the raw audio array using `faster-whisper` (`base` model, quantized to `int8` on CPU) for rapid, lightweight speech-to-text conversion.
3. **Optional OpenAI Text Optimization:** When an OpenAI API key is configured in Settings, each transcription is sent to the OpenAI API (`gpt-4o-mini` by default) which returns an optimized version of the text. When no key is set, only raw transcription is produced.
4. **Settings Dialog (Top-Right ⚙️ Button):**
   * **OpenAI API Key:** Password-masked input with a "Show API key" toggle and a link to `platform.openai.com/api-keys`.
   * **Appearance Theme:** Light ☀️ / Dark 🌙 selection applied app-wide via Qt stylesheets.
   * Settings persist locally to `settings.json` and are restored on next launch.
5. **Light & Dark Themes:** Two full stylesheets defined in `config.py` (panels, buttons, inputs, dialogs). The theme applies instantly when saved.
6. **Asynchronous Multithreading:** Runs all speech recognition and OpenAI API calls inside a background `ProcessingWorker` thread using PyQt signals to keep the desktop interface responsive.
7. **Dual-Panel Display UI:** Shows the raw transcription on the left panel and the OpenAI-optimized text on the right panel, supported by utility controls for copying text, clearing fields, and managing microphone state.

---

### **Architecture & Module Breakdown**

* **`config.py` (Configuration):**
* Centralizes application constants, including audio sampling rate (`16000 Hz`), Whisper model configuration, OpenAI model name & system prompt, UI window dimensions, app icon URL, and the Light/Dark theme stylesheets.


* **`settings_manager.py` (Persistence):**
* `load_settings()` / `save_settings()` — reads and writes user preferences (`theme`, `openai_api_key`) to `settings.json` with graceful fallback to defaults.


* **`models.py` (Machine Learning Engine):**
* **`SpeechModels` Class:** Manages the Whisper model lifecycle and the OpenAI client.
* **Lazy Loading:** Pre-loads Whisper on app startup; the OpenAI client is created on demand and re-created only when the API key changes.
* **`optimize_text()`:** Sends transcribed text to the OpenAI chat completions API with an optimization system prompt.


* **`main.py` (User Interface & Application Entry):**
* **`SpeechToTextApp`:** Main PyQt5 window — header row with the settings button pinned to the top-right corner, dual-panel display, theme application, microphone state handlers, and clipboard action buttons.
* **`SettingsDialog`:** Modal dialog for entering the OpenAI API key and choosing a theme.
* **`ProcessingWorker`:** A `QObject` worker executed via `threading.Thread` that coordinates non-blocking execution between audio input, Whisper transcription, and OpenAI optimization.


---

### **Installation**

Libraries to install before running the application, using requirements.txt:

```bash
pip install -r requirements.txt
```

or direct command:

```bash
pip3 install PyQt5 faster-whisper sounddevice numpy openai
```

### **Additional System Dependencies**

**macOS:** You may need to grant Microphone permissions to your terminal or IDE (e.g., VS Code or iTerm) under System Settings > Privacy & Security > Microphone.

**Linux (Ubuntu/Debian):** If sounddevice or PyQt5 throws binding errors, install PortAudio and Qt5 dependencies via apt:

```bash
sudo apt-get update
sudo apt-get install -y python3-pyqt5 portaudio19-dev
```

### **Running the Application**

```bash
python3 main.py
```

### **Configuration Notes**

* Open **⚙️ Settings** (top-right corner) to paste your OpenAI API key and pick a theme.
* Settings are stored in `settings.json` in the app directory. **This file contains your API key — do not commit or share it.**
* If the OpenAI key is invalid or the API call fails, an error dialog is shown and the raw transcription is still preserved.
