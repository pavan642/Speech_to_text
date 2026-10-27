# config.py

# Audio Settings
SAMPLE_RATE = 16000

# Model Configurations
WHISPER_MODEL_NAME = "base"
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
WINDOW_WIDTH = 950
WINDOW_HEIGHT = 650
SPEAKING_INDICATOR_TEXT = "🗣️ Speaking..."

# Theme Stylesheets
LIGHT_THEME = """
QWidget { background-color: #F5F5F5; color: #222222; }
QTextEdit { background-color: #FFFFFF; color: #333333; border: 1px solid #CCCCCC; border-radius: 4px; padding: 4px; }
QLineEdit { background-color: #FFFFFF; color: #333333; border: 1px solid #CCCCCC; border-radius: 4px; padding: 6px; }
QPushButton { background-color: #E0E0E0; color: #222222; padding: 8px; border-radius: 5px; border: 1px solid #BBBBBB; }
QPushButton:hover { background-color: #D5D5D5; }
QPushButton:disabled { background-color: #EEEEEE; color: #999999; }
QGroupBox { border: 1px solid #CCCCCC; border-radius: 6px; margin-top: 14px; font-weight: bold; }
QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 4px; }
QToolTip { background-color: #FFFFFF; color: #222222; border: 1px solid #CCCCCC; }
"""

DARK_THEME = """
QWidget { background-color: #2B2B2B; color: #EAEAEA; }
QTextEdit { background-color: #1E1E1E; color: #EAEAEA; border: 1px solid #444444; border-radius: 4px; padding: 4px; }
QLineEdit { background-color: #1E1E1E; color: #EAEAEA; border: 1px solid #555555; border-radius: 4px; padding: 6px; }
QPushButton { background-color: #3C3C3C; color: #EAEAEA; padding: 8px; border-radius: 5px; border: 1px solid #555555; }
QPushButton:hover { background-color: #4A4A4A; }
QPushButton:disabled { background-color: #333333; color: #777777; }
QGroupBox { border: 1px solid #555555; border-radius: 6px; margin-top: 14px; font-weight: bold; }
QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 4px; }
QToolTip { background-color: #3C3C3C; color: #EAEAEA; border: 1px solid #555555; }
"""
