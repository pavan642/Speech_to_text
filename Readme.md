# 🎙️ TextIQ — dictate, write, and optimize documents with Claude

A **VS Code-style desktop editor** (Python + PyQt5) where your **voice becomes text at the cursor** — with a real document workflow: folder-tree file manager with tabs, split view, full rich-text formatting, autosave, content search, text-to-speech, per-file reminders, **Claude (Anthropic) text optimization**, and git push. Transcription runs **fully offline** (local Whisper); Claude is used only for optional text optimization.

---

## ✨ Feature tour

### 🎙️ Speech
| Feature | Details |
|---|---|
| **Dictate at cursor** | Click **Start** in the SPEECH panel, speak — text streams into the editor at your cursor, live (~4s chunks with 0.7s overlap, no clipped words) |
| **Live STT mirror** | The same text appears in the panel's *Speech → Text* view |
| **Voice commands** | "new line", "comma", "period", "question mark"… become real punctuation; say **"scratch that"** to undo the last dictated chunk |
| **Noise reduction + VAD** | High-pass filter + spectral gating (`noisereduce`) + Silero VAD |
| **Recording timer + level ring** | Elapsed `MM:SS` and a draggable mic-level indicator |
| **Speech history** | Every dictation session is archived (left panel), opens as a read-only tab |

### 📝 Editor
- **Tabs**: open many documents, per-tab **✕** close, dirty `●` indicator, **✓ flash** on save, drag to reorder
- **Split view**: two full editors side by side (⫿ button / Ctrl+Shift+S), second pane has its own **Close** button
- **Formatting (2-row toolbar)**: undo/redo, **B**/*I*/U/S, H1–H3, font size, text & highlight color, bullet/numbered lists, **☐ task checkboxes**, alignment, code style, tables, clear formatting
- **Markdown-style auto-format**: type `# `, `- `, `[] ` → heading / list / task
- **Autosave** (2.5s debounce), **word & character count** in the status bar, active-format highlighting (B/I/U light up)
- **Find in document** (⌘F) with next/prev + wrap-around
- **Export**: `.md` / `.txt` / **PDF** (toolbar, or per file via right-click)

### 📁 Documents
- **Folder tree** (left panel) with subfolders, single-click expand, filename **search filter** + **Enter for full-content search** (results open in a temporary, never-saved tab)
- **New / New Folder** buttons; files land in the selected folder
- **Right-click any file** → full menu: Open · Read aloud · Stop · Optimize with Claude · Export · Reminder · Reveal in Finder · Delete (with confirm)
- **Choose your format**: `.md` (default), `.html`, or `.txt` — in Settings, or by typing the extension in the file name (`report.txt`)
- **Reminders** ⏰: per-document date/time picker → popup when due, with "Open document"

### 🤖 Claude (Anthropic)
- **✨ Optimize** (toolbar): optimizes the **selection** or the **whole document**, replaces it in place
- **Preset styles**: Bullet points / Summary / Formal email / Action items (dropdown)
- **Speech optimize**: the dictated text in the right panel optimizes into the result view below it
- API key + model configurable in Settings (lazy import — app works without `anthropic` installed)

### 🛠 App
- **VS Code-style themes**: Dark+ and Light+ (flat panels, tab strip, **blue status bar** with status · word count · Whisper model · git branch)
- **Font Awesome icons** via `qtawesome` (optional — graceful text fallback)
- **⬆ Push**: commit & push everything to your configured git remote/branch (Settings)
- **TTS**: read selection/document aloud (macOS `say`), per-tab 🔊 button, context-menu per file
- **Keyboard shortcuts**: ⌘B/I/U · ⌘S save · ⌘N new · ⌘W close tab · ⌘F find · Ctrl+Shift+S split

---

## 🖥️ Layout

```
[New Save 🔍 │ ✨Optimize▾ ⫿Split │ ⬆Push        ⚙]   row 1
[↶↷ B I U S │ H1 H2 H3 12 🎨🖍 │ • 1. ☐ │ ⇤☰⇥≣ │ </> ▦ 🧹 Delete ⇩ ⏰]  row 2
┌────────────┬────────────────────────────┬────────────┐
│📁 DOCUMENTS│  [New][tab 🔊t ✕][tab ✕][New]│ 🎙️ SPEECH │
│ 🔍 search  │ ─────────────────────────── │ [ Start ]  │
│ ▸ folder   │                             │ 🗣️ ⏱ 00:12 │
│   file.md  │         EDITOR              │ ┌STT──────┐│
│   note.txt │    (or two panes, split)    │ └─────────┘│
│🕘 SPEECH   │                             │ [🔊][⏹]    │
│  HISTORY   │                             │ ✨ OPTIMIZE │
│            │                             │ [Optimize] │
│            │                             │ ┌result───┐│
└────────────┴────────────────────────────┴────────────┘
[ status │ 123 words · 1042 chars │ 🧠 base │ ⎇ main ]  status bar
```

---

## 🚀 Install & run

```bash
make install      # pip install -r requirements.txt + pytest tools
make icons        # optional: qtawesome (Font Awesome icons)
make run          # python3 main.py
```

or manually:

```bash
pip3 install PyQt5 faster-whisper sounddevice numpy anthropic noisereduce qtawesome
python3 main.py
```

**macOS:** grant Microphone permission to your terminal/IDE (*System Settings → Privacy & Security → Microphone*). TTS uses the built-in `say` command.

## ✅ Tests

```bash
make test     # 31 happy-flow UI tests (headless, pytest-qt)
make smoke    # dependency + audio pipeline smoke test
```

CI runs both on every push (`.github/workflows/tests.yml`, macOS runner).

## ⚙️ Settings (⚙ top right)

| Setting | Default | Notes |
|---|---|---|
| Claude API key + model | `claude-sonnet-5-5` | console.anthropic.com |
| Documents folder | `documents/` | 📁 browse |
| Document format | `.md` | `.md` / `.html` / `.txt` |
| Git remote + branch | `main` | token in HTTPS URL or SSH |
| Whisper model | `base` | tiny→medium |
| Live dictation / noise reduction | on | |
| Theme | light | VS Dark+ / Light+ |

> ⚠️ `settings.json` (API key), `history/`, `reminders.json` are git-ignored.

## 🧩 Code layout

```
main.py               app window, dictation pipeline, tabs/docs logic, Claude, git, reminders
ui/pane.py            EditorPane (tabs + find bar + editor)
ui/toolbar.py         top bar + tools row
ui/sidebar.py         documents tree + speech history + speech panel
models.py             Whisper, denoise, Claude optimize (all lazy-imported)
documents_manager.py  local doc storage (.md/.html/.txt, folders)
history_manager.py    speech session archive
reminders_manager.py  per-document reminders
tts_manager.py        macOS `say` wrapper
git_manager.py        init/add/commit/push
settings_manager.py   settings.json persistence
test_app.py           31 UI tests · test_pipeline.py env smoke test · Makefile · CI
```

## 🛠️ Troubleshooting

- **`have 'x86_64', need 'arm64'`** — stale Intel wheels: `python3 -m pip install --force-reinstall --no-cache-dir <pkg>`, then `make smoke`
- **Dictation lags** — smaller Whisper model or disable noise reduction
- **Icons missing** — `make icons` (installs qtawesome); without it, text labels are used everywhere
