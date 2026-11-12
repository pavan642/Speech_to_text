# config.py

# Audio Settings
SAMPLE_RATE = 16000
STREAM_CHUNK_SECONDS = 4    # live transcription chunk size while recording
STREAM_OVERLAP_SECONDS = 0.7  # overlap between chunks, prevents clipped words

# Model Configurations
WHISPER_MODEL_NAME = "base"  # default size
WHISPER_MODEL_OPTIONS = ["tiny", "base", "small", "medium"]
WHISPER_DEVICE = "cpu"
WHISPER_COMPUTE_TYPE = "int8"

# LLM Settings (LiteLLM — 100+ providers)
LLM_MODEL = "claude-sonnet-5-5"  # default
LLM_MODEL_OPTIONS = [
    "claude-sonnet-5-5",          # Anthropic
    "gpt-4o-mini",                # OpenAI
    "gpt-4o",                     # OpenAI
    "gemini/gemini-2.0-flash",    # Google
    "groq/llama-3.3-70b-versatile",  # Groq
    "mistral/mistral-large-latest",  # Mistral
    "ollama/llama3.2",            # local, free, offline
]
CLAUDE_MODEL = LLM_MODEL  # backwards compat
CLAUDE_MODEL_OPTIONS = LLM_MODEL_OPTIONS
CLAUDE_MAX_TOKENS = 1024
CLAUDE_OPTIMIZE_PROMPT = (
    "You are a text optimization assistant. Rewrite the user's text: correct "
    "all grammatical errors, improve clarity and flow, and format the result "
    "as clear bullet points while strictly preserving the original meaning. "
    "Return only the optimized text, with no commentary or preamble."
)

# Optimize prompt presets (dropdown next to ✨ Optimize)
OPTIMIZE_PRESETS = {
    "Bullet points": CLAUDE_OPTIMIZE_PROMPT,
    "Summary": (
        "Summarize the user's text concisely, capturing every key point. "
        "Return only the summary, with no commentary."
    ),
    "Formal email": (
        "Rewrite the user's text as a polished, professional email with a "
        "proper greeting and sign-off. Return only the email text."
    ),
    "Action items": (
        "Extract every actionable task from the user's text as a numbered "
        "to-do list, assigning owners when mentioned. Return only the list."
    ),
}

# Documents
DEFAULT_DOCUMENTS_FOLDER = "documents"

# Settings file (stores theme + API key locally)
SETTINGS_FILE = "settings.json"

# UI Settings
APP_TITLE = "TextIQ"
APP_ICON_URL = "https://www.shutterstock.com/image-vector/speech-text-voice-recognition-audio-transcription-2680248347"
WINDOW_WIDTH = 1320
WINDOW_HEIGHT = 650
SPEAKING_INDICATOR_TEXT = "🗣️ Speaking..."

# Theme Stylesheets
LIGHT_THEME = """
/* VS Code Light+ inspired */
QWidget { background-color: #FFFFFF; color: #1F1F1F; font-family: "Helvetica Neue"; }
QLabel { background: transparent; }
QLabel#subtitle { color: #616161; }
QLabel#breadcrumb { color: #6F6F6F; }
QLabel#sectionTitle { color: #6F6F6F; font-size: 10px; font-weight: bold; padding: 2px 0; }

/* Panels, tab strip, status bar */
QFrame#panel { background-color: #F3F3F3; border: 1px solid #E0E0E0; }
QFrame#editorArea { background-color: #FFFFFF; border: 1px solid #E0E0E0; }
QFrame#tabBar { background-color: #ECECEC; border: none; border-bottom: 1px solid #E0E0E0; }
QTabBar#docTabs { background: transparent; }
QTabBar#docTabs::tab { background: #ECECEC; color: #6F6F6F; padding: 6px 12px; border-right: 1px solid #E0E0E0; }
QTabBar#docTabs::tab:selected { background: #FFFFFF; color: #1F1F1F; border-top: 2px solid #007ACC; }
QTabBar#docTabs::tab:hover { color: #1F1F1F; }
QTabBar#docTabs::close-button:hover { background: #CECECE; border-radius: 3px; }
QFrame#statusBar { background-color: #007ACC; border: none; }
QLabel#statusBarItem { color: #FFFFFF; background: transparent; font-size: 10px; padding: 0 4px; }

/* Inputs */
QTextEdit { background-color: #FFFFFF; color: #1F1F1F; border: none; padding: 8px; selection-background-color: #ADD6FF; }
QLineEdit { background-color: #FFFFFF; color: #1F1F1F; border: 1px solid #CECECE; border-radius: 3px; padding: 6px 8px; }
QLineEdit:focus { border: 1px solid #007ACC; }
QComboBox { background-color: #FFFFFF; color: #1F1F1F; border: 1px solid #CECECE; border-radius: 3px; padding: 5px 8px; }
QComboBox:hover { border-color: #007ACC; }
QComboBox::drop-down { border: none; width: 24px; }
QComboBox QAbstractItemView { background-color: #FFFFFF; color: #1F1F1F; border: 1px solid #CECECE; selection-background-color: #0060C0; selection-color: white; }

/* Buttons */
QPushButton { background-color: #FFFFFF; color: #1F1F1F; border: 1px solid #CECECE; padding: 5px 10px; border-radius: 3px; }
QPushButton:hover { background-color: #F0F0F0; }
QPushButton:pressed { background-color: #E0E0E0; }
QPushButton:disabled { color: #8A8A8A; }
QPushButton#primaryBtn { background-color: #0E639C; color: white; border: none; padding: 6px 12px; }
QPushButton#primaryBtn:hover { background-color: #1177BB; }
QPushButton#primaryBtn:pressed { background-color: #0B4F7C; }
QPushButton#settingsBtn { border-radius: 6px; padding: 0 12px; font-weight: bold; font-size: 11px; }

/* Settings dialog groups */
QGroupBox { background-color: #F3F3F3; border: 1px solid #E0E0E0; border-radius: 3px; margin-top: 14px; font-weight: bold; }
QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 4px; color: #6F6F6F; }
QCheckBox, QRadioButton { spacing: 6px; background: transparent; }

/* Lists + folder tree */
QListWidget, QTreeView { background-color: transparent; border: none; outline: none; }
QListWidget::item, QTreeView::item { padding: 4px 8px; color: #1F1F1F; }
QListWidget::item:hover, QTreeView::item:hover { background: #E8E8E8; }
QListWidget::item:selected, QTreeView::item:selected { background: #0060C0; color: #FFFFFF; }

/* Toolbar separator */
QFrame#toolbarSep { background-color: #CECECE; max-width: 1px; margin: 4px 3px; }

/* Slim scrollbars */
QScrollBar:vertical { background: transparent; width: 10px; }
QScrollBar::handle:vertical { background: #C1C1C1; min-height: 30px; }
QScrollBar::handle:vertical:hover { background: #A6A6A6; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar:horizontal { background: transparent; height: 10px; }
QScrollBar::handle:horizontal { background: #C1C1C1; min-width: 30px; }
QScrollBar::handle:horizontal:hover { background: #A6A6A6; }
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0; }

QToolTip { background-color: #F3F3F3; color: #1F1F1F; border: 1px solid #CECECE; padding: 4px 8px; }
QLabel#toast { background-color: #1F1F1F; color: #FFFFFF; border-radius: 8px; padding: 8px 16px; font-weight: bold; }
"""

DARK_THEME = """
/* VS Code Dark+ inspired */
QWidget { background-color: #1E1E1E; color: #CCCCCC; font-family: "Helvetica Neue"; }
QLabel { background: transparent; }
QLabel#subtitle { color: #9D9D9D; }
QLabel#breadcrumb { color: #9D9D9D; }
QLabel#sectionTitle { color: #BBBBBB; font-size: 10px; font-weight: bold; padding: 2px 0; }

/* Panels, tab strip, status bar */
QFrame#panel { background-color: #252526; border: 1px solid #3E3E42; }
QFrame#editorArea { background-color: #1E1E1E; border: 1px solid #3E3E42; }
QFrame#tabBar { background-color: #2D2D30; border: none; border-bottom: 1px solid #3E3E42; }
QTabBar#docTabs { background: transparent; }
QTabBar#docTabs::tab { background: #2D2D30; color: #9D9D9D; padding: 6px 12px; border-right: 1px solid #3E3E42; }
QTabBar#docTabs::tab:selected { background: #1E1E1E; color: #FFFFFF; border-top: 2px solid #007ACC; }
QTabBar#docTabs::tab:hover { color: #FFFFFF; }
QTabBar#docTabs::close-button:hover { background: #3E3E42; border-radius: 3px; }
QFrame#statusBar { background-color: #007ACC; border: none; }
QLabel#statusBarItem { color: #FFFFFF; background: transparent; font-size: 10px; padding: 0 4px; }

/* Inputs */
QTextEdit { background-color: #1E1E1E; color: #D4D4D4; border: none; padding: 8px; selection-background-color: #264F78; }
QLineEdit { background-color: #3C3C3C; color: #CCCCCC; border: 1px solid #3E3E42; border-radius: 3px; padding: 6px 8px; }
QLineEdit:focus { border: 1px solid #007ACC; }
QComboBox { background-color: #3C3C3C; color: #CCCCCC; border: 1px solid #3E3E42; border-radius: 3px; padding: 5px 8px; }
QComboBox:hover { border-color: #007ACC; }
QComboBox::drop-down { border: none; width: 24px; }
QComboBox QAbstractItemView { background-color: #252526; color: #CCCCCC; border: 1px solid #3E3E42; selection-background-color: #094771; selection-color: white; }

/* Buttons */
QPushButton { background-color: transparent; color: #CCCCCC; border: 1px solid #3E3E42; padding: 5px 10px; border-radius: 3px; }
QPushButton:hover { background-color: #2A2D2E; }
QPushButton:pressed { background-color: #3E3E42; }
QPushButton:disabled { color: #6E6E6E; }
QPushButton#primaryBtn { background-color: #0E639C; color: white; border: none; padding: 6px 12px; }
QPushButton#primaryBtn:hover { background-color: #1177BB; }
QPushButton#primaryBtn:pressed { background-color: #0B4F7C; }
QPushButton#settingsBtn { border-radius: 6px; padding: 0 12px; font-weight: bold; font-size: 11px; }

/* Settings dialog groups */
QGroupBox { background-color: #252526; border: 1px solid #3E3E42; border-radius: 3px; margin-top: 14px; font-weight: bold; }
QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 4px; color: #BBBBBB; }
QCheckBox, QRadioButton { spacing: 6px; background: transparent; }

/* Lists + folder tree */
QListWidget, QTreeView { background-color: transparent; border: none; outline: none; }
QListWidget::item, QTreeView::item { padding: 4px 8px; color: #CCCCCC; }
QListWidget::item:hover, QTreeView::item:hover { background: #2A2D2E; }
QListWidget::item:selected, QTreeView::item:selected { background: #094771; color: #FFFFFF; }

/* Toolbar separator */
QFrame#toolbarSep { background-color: #3E3E42; max-width: 1px; margin: 4px 3px; }

/* Slim scrollbars */
QScrollBar:vertical { background: transparent; width: 10px; }
QScrollBar::handle:vertical { background: #424242; min-height: 30px; }
QScrollBar::handle:vertical:hover { background: #4F4F4F; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar:horizontal { background: transparent; height: 10px; }
QScrollBar::handle:horizontal { background: #424242; min-width: 30px; }
QScrollBar::handle:horizontal:hover { background: #4F4F4F; }
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0; }

QToolTip { background-color: #252526; color: #CCCCCC; border: 1px solid #454545; padding: 4px 8px; }
QLabel#toast { background-color: #F0F0F0; color: #1F1F1F; border-radius: 8px; padding: 8px 16px; font-weight: bold; }
"""
