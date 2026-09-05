# config.py

# Audio Settings
SAMPLE_RATE = 16000

# Model Configurations
WHISPER_MODEL_NAME = "base"
WHISPER_DEVICE = "cpu"
WHISPER_COMPUTE_TYPE = "int8"

T5_MODEL_NAME = "grammarly/coedit-large"
T5_PROMPT_PREFIX = "Fix grammatical errors in this text: "

# UI Settings
APP_TITLE = "Speech to Text App"
APP_ICON_URL = "https://www.shutterstock.com/image-vector/speech-text-voice-recognition-audio-transcription-2680248347"
WINDOW_WIDTH = 950
WINDOW_HEIGHT = 650
SPEAKING_INDICATOR_TEXT = "🗣️ Speaking..."
