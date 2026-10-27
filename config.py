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

# OpenAI Settings
OPENAI_MODEL = "gpt-4o-mini"
OPENAI_SYSTEM_PROMPT = (
    "You are a text optimization assistant. Rewrite the user's speech "
    "transcription: correct all grammatical errors, improve clarity and flow, "
    "and format the result as clear bullet points while strictly preserving "
    "the original meaning. Return only the bullet-point text, with no "
    "commentary or preamble."
)

# Settings file (stores theme + API key locally)
SETTINGS_FILE = "settings.json"

# UI Settings
APP_TITLE = "Speech to Text App"
APP_ICON_URL = "https://www.shutterstock.com/image-vector/speech-text-voice-recognition-audio-transcription-2680248347"
WINDOW_WIDTH = 1180
WINDOW_HEIGHT = 650
SPEAKING_INDICATOR_TEXT = "🗣️ Speaking..."

# Theme Stylesheets
LIGHT_THEME = """
QWidget { background-color: #EEF1F6; color: #1F2937; font-family: "Helvetica Neue"; }
QLabel { background: transparent; }

/* Cards */
QFrame#card { background-color: #FFFFFF; border: 1px solid #E2E6EE; border-radius: 12px; }
QLabel#cardTitle { color: #5B7FFF; }
QLabel#subtitle { color: #6B7280; }

/* Status pill */
QLabel#statusPill { background-color: #E3EBFF; color: #3B5BDB; border-radius: 11px; padding: 6px 16px; }

/* Inputs */
QTextEdit { background-color: transparent; color: #1F2937; border: none; padding: 4px; selection-background-color: #BFD4FF; }
QLineEdit { background-color: #FFFFFF; color: #1F2937; border: 1px solid #D4DAE4; border-radius: 8px; padding: 8px; }
QLineEdit:focus { border: 1px solid #5B7FFF; }
QComboBox { background-color: #FFFFFF; color: #1F2937; border: 1px solid #D4DAE4; border-radius: 8px; padding: 6px 10px; }
QComboBox:hover { border-color: #5B7FFF; }
QComboBox::drop-down { border: none; width: 24px; }
QComboBox QAbstractItemView { background-color: #FFFFFF; color: #1F2937; border: 1px solid #D4DAE4; selection-background-color: #5B7FFF; selection-color: white; }

/* Buttons */
QPushButton { background-color: #FFFFFF; color: #1F2937; border: 1px solid #D4DAE4; padding: 9px 14px; border-radius: 9px; font-weight: bold; }
QPushButton:hover { background-color: #F2F5FB; border-color: #B9C4D8; }
QPushButton:pressed { background-color: #E5EAF4; }
QPushButton:disabled { color: #9AA3B2; background-color: #EDF0F5; border-color: #E2E6EE; }
QPushButton#settingsBtn { border-radius: 21px; font-size: 17px; padding: 0px; }
QPushButton#primaryBtn { background-color: #5B7FFF; color: white; border: none; }
QPushButton#primaryBtn:hover { background-color: #6D8DFF; }
QPushButton#primaryBtn:pressed { background-color: #4A6FE0; }

/* Settings dialog groups */
QGroupBox { background-color: #FFFFFF; border: 1px solid #E2E6EE; border-radius: 10px; margin-top: 16px; font-weight: bold; }
QGroupBox::title { subcontrol-origin: margin; left: 12px; padding: 0 6px; color: #5B7FFF; }
QCheckBox, QRadioButton { spacing: 6px; background: transparent; }

/* Slim scrollbars */
QScrollBar:vertical { background: transparent; width: 10px; margin: 4px 2px; }
QScrollBar::handle:vertical { background: #C4CCDA; border-radius: 5px; min-height: 30px; }
QScrollBar::handle:vertical:hover { background: #A8B2C6; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar:horizontal { background: transparent; height: 10px; margin: 2px 4px; }
QScrollBar::handle:horizontal { background: #C4CCDA; border-radius: 5px; min-width: 30px; }
QScrollBar::handle:horizontal:hover { background: #A8B2C6; }
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0; }

/* History sidebar list */
QListWidget { background-color: transparent; border: none; outline: none; }
QListWidget::item { padding: 7px 8px; border-radius: 6px; color: #1F2937; }
QListWidget::item:hover { background: #EDF1FA; }
QListWidget::item:selected { background: #5B7FFF; color: white; }

QSplitter::handle { background: transparent; }
QToolTip { background-color: #FFFFFF; color: #1F2937; border: 1px solid #D4DAE4; padding: 4px 8px; }
"""

DARK_THEME = """
QWidget { background-color: #191B20; color: #E7E9EE; font-family: "Helvetica Neue"; }
QLabel { background: transparent; }

/* Cards */
QFrame#card { background-color: #23262E; border: 1px solid #333743; border-radius: 12px; }
QLabel#cardTitle { color: #8FA8FF; }
QLabel#subtitle { color: #9AA3B2; }

/* Status pill */
QLabel#statusPill { background-color: #2A3550; color: #9DB8FF; border-radius: 11px; padding: 6px 16px; }

/* Inputs */
QTextEdit { background-color: transparent; color: #E7E9EE; border: none; padding: 4px; selection-background-color: #3B5BDB; }
QLineEdit { background-color: #1E2027; color: #E7E9EE; border: 1px solid #3A3F4B; border-radius: 8px; padding: 8px; }
QLineEdit:focus { border: 1px solid #7C9EFF; }
QComboBox { background-color: #1E2027; color: #E7E9EE; border: 1px solid #3A3F4B; border-radius: 8px; padding: 6px 10px; }
QComboBox:hover { border-color: #7C9EFF; }
QComboBox::drop-down { border: none; width: 24px; }
QComboBox QAbstractItemView { background-color: #1E2027; color: #E7E9EE; border: 1px solid #3A3F4B; selection-background-color: #5B7FFF; selection-color: white; }

/* Buttons */
QPushButton { background-color: #2C303A; color: #E7E9EE; border: 1px solid #3A3F4B; padding: 9px 14px; border-radius: 9px; font-weight: bold; }
QPushButton:hover { background-color: #343945; border-color: #4A5162; }
QPushButton:pressed { background-color: #3A404D; }
QPushButton:disabled { color: #6B7280; background-color: #23262E; border-color: #2E323C; }
QPushButton#settingsBtn { border-radius: 21px; font-size: 17px; padding: 0px; }
QPushButton#primaryBtn { background-color: #5B7FFF; color: white; border: none; }
QPushButton#primaryBtn:hover { background-color: #6D8DFF; }
QPushButton#primaryBtn:pressed { background-color: #4A6FE0; }

/* Settings dialog groups */
QGroupBox { background-color: #23262E; border: 1px solid #333743; border-radius: 10px; margin-top: 16px; font-weight: bold; }
QGroupBox::title { subcontrol-origin: margin; left: 12px; padding: 0 6px; color: #8FA8FF; }
QCheckBox, QRadioButton { spacing: 6px; background: transparent; }

/* Slim scrollbars */
QScrollBar:vertical { background: transparent; width: 10px; margin: 4px 2px; }
QScrollBar::handle:vertical { background: #4A4F5C; border-radius: 5px; min-height: 30px; }
QScrollBar::handle:vertical:hover { background: #5A6070; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar:horizontal { background: transparent; height: 10px; margin: 2px 4px; }
QScrollBar::handle:horizontal { background: #4A4F5C; border-radius: 5px; min-width: 30px; }
QScrollBar::handle:horizontal:hover { background: #5A6070; }
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0; }

/* History sidebar list */
QListWidget { background-color: transparent; border: none; outline: none; }
QListWidget::item { padding: 7px 8px; border-radius: 6px; color: #E7E9EE; }
QListWidget::item:hover { background: #2C303A; }
QListWidget::item:selected { background: #5B7FFF; color: white; }

QSplitter::handle { background: transparent; }
QToolTip { background-color: #2C303A; color: #E7E9EE; border: 1px solid #3A3F4B; padding: 4px 8px; }
"""
