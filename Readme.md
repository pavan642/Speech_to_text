# 🎙️ Speech to Text — Live Whisper Transcription + OpenAI Optimization

A desktop app (Python + PyQt5) that captures microphone audio and transcribes it **live** using a local quantized Whisper model — with noise reduction, voice-activity detection, and optional one-shot text optimization via your own OpenAI API key. Runs fully offline for transcription; OpenAI is used only for post-processing.

---

## ✨ Features

| Feature | Details |
|---|---|
| **Live streaming transcription** | Text appears every ~4s while you speak — no waiting for Mic OFF. Overlapping chunks (0.7s) prevent clipped words at boundaries. |
| **Noise reduction** | High-pass filter (cuts rumble/hum < 85 Hz) + spectral gating (`noisereduce`) for fans/AC. Toggleable. |
| **Voice Activity Detection** | Built-in Silero VAD skips silence — fewer hallucinations, faster processing. |
| **OpenAI optimization** | Sends the finished transcript to `gpt-4o-mini` with your editable system prompt (bullet points, summary, formal email…). |
| **Whisper model picker** | `tiny` / `base` / `small` / `medium` — trade speed for accuracy, reloads in background. |
| **Light & dark themes** | Modern card UI with shadows, gradients, slim scrollbars. Instant switch. |
| **Recording timer** | Elapsed `MM:SS` shown next to the speaking indicator while the mic is on. |
| **Mic level indicator** | Draggable ~2 cm circle that fills green with your live voice level. |
| **Session history** | Every session saved to `history/*.md`; sidebar lists past sessions — click to reload into the panels. |
| **Graceful degradation** | No API key? Transcription still works. OpenAI call fails? Raw text preserved + error popup. Broken `openai` install? App still starts. |
| **Smoke test** | `test_pipeline.py` verifies the whole environment in seconds. |

---

## 🖥️ UI Overview

```
┌──────────────────────────────────────────────────────────────┐
│ [ Ready ]        🎙️ Speech to Text                       [⚙] │
│ 🕘 History     🗣️ Speaking...  ⏱ 00:12  (while recording)    │
│ ┌───────────┐  ┌─────────────────────┬─────────────────────┐ │
│ │ Oct 27    │  │ 📝 Original         │ ✨ Optimized        │ │
│ │ 14:32:05  │  │   Transcript        │   (OpenAI)          │ │
│ │ Oct 27    │  │  (live, streaming)  │  (on Mic OFF)       │ │
│ │ 12:10:44  │  │                     │                     │ │
│ └───────────┘  └─────────────────────┴─────────────────────┘ │
│                [ 🎙️ Mic ON ]  [ 🛑 Mic OFF ]                 │
│        [📋 Copy Original] [📋 Copy Optimized] [🧹] [❌]       │
└──────────────────────────────────────────────────────────────┘
```

---

## 🚀 Installation

```bash
pip install -r requirements.txt
```

or directly:

```bash
pip3 install PyQt5 faster-whisper sounddevice numpy openai noisereduce
```

**macOS:** grant Microphone permission to your terminal/IDE under *System Settings → Privacy & Security → Microphone*.

**Linux (Ubuntu/Debian):** if `sounddevice`/PyQt5 fail:

```bash
sudo apt-get update && sudo apt-get install -y python3-pyqt5 portaudio19-dev
```

## ▶️ Run

```bash
python3 main.py
```

## ✅ Smoke test

Verifies dependencies (incl. architecture issues like broken wheels), then runs a generated 3s WAV through denoise → transcribe:

```bash
python3 test_pipeline.py
# exit code 0 = healthy, 1 = something broken (details printed)
```

---

## ⚙️ Settings (⚙ button, top-right)

Everything persists to `settings.json`:

| Setting | Default | Notes |
|---|---|---|
| OpenAI API key | — | Password-masked; enables the Optimized panel |
| System prompt | bullet-points rewriter | Fully editable, "Reset to default" button |
| Whisper model | `base` | `tiny`→`medium`; larger = better + slower (+one-time download) |
| Live transcription | on | Off = transcribe once at Mic OFF |
| Noise reduction | on | High-pass + spectral gating |
| Theme | light | Light ☀️ / Dark 🌙 |
| Save history | on | Writes `history/transcription_<ts>.md` |

> ⚠️ `settings.json` contains your API key and `history/` contains transcripts — both are in `.gitignore`. Don't commit them.

---

## 🧩 Architecture

```
mic ──► audio_callback ──► 4s chunks (+0.7s overlap) ──► stream_queue
                                                              │
                              persistent transcriber thread ◄─┘
                          (high-pass → noisereduce → VAD → Whisper)
                                                              │
                              live text ──► Original panel ◄──┘
Mic OFF ──► tail chunk + FLUSH ──► session drained
                                                              │
                          OpenAI optimize (once, full text) ──┘
                                                              │
                                    history/*.md + sidebar ◄──┘
```

| File | Role |
|---|---|
| `main.py` | PyQt5 UI, streaming pipeline, workers, settings dialog, level indicator |
| `models.py` | `SpeechModels` — Whisper lifecycle, denoise, OpenAI optimize (all lazy-imported) |
| `config.py` | Constants, chunk/overlap timings, theme stylesheets |
| `settings_manager.py` | `settings.json` load/save with defaults |
| `history_manager.py` | Save/list/load `history/*.md` sessions |
| `test_pipeline.py` | Environment + pipeline smoke test |

---

## 🛠️ Troubleshooting

**`mach-o file, but is an incompatible architecture (have 'x86_64', need 'arm64')`** — stale Intel wheels in `~/Library/Python/3.9`. Fix:

```bash
python3 -m pip install --force-reinstall --no-cache-dir <package>
python3 test_pipeline.py   # verify
```

**Live text lags behind speech** — you're transcribing slower than real-time. Drop to a smaller Whisper model or disable noise reduction.

**First transcription pauses** — one-time downloads: Whisper model (~40 MB–1.5 GB depending on size) and the Silero VAD model (~2 MB).
