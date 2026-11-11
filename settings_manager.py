# settings_manager.py
"""Loads and saves user preferences to a local JSON file."""
import json
import logging
import os

import config

logger = logging.getLogger("SpeechEditor")

DEFAULT_SETTINGS = {
    "theme": "light",
    "claude_api_key": "",
    "claude_model": config.CLAUDE_MODEL,
    "whisper_model": config.WHISPER_MODEL_NAME,
    "live_transcription": True,
    "noise_reduction": True,
    "documents_folder": config.DEFAULT_DOCUMENTS_FOLDER,
    "doc_extension": ".md",
    "save_history": True,
    "git_remote_url": "",
    "git_branch": "main",
}


def load_settings() -> dict:
    """Loads settings from disk, falling back to defaults for missing keys."""
    if not os.path.exists(config.SETTINGS_FILE):
        return dict(DEFAULT_SETTINGS)

    try:
        with open(config.SETTINGS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        settings = dict(DEFAULT_SETTINGS)
        settings.update({k: v for k, v in data.items() if k in DEFAULT_SETTINGS})
        return settings
    except Exception as e:
        logger.warning(f"Failed to load settings file, using defaults: {e}")
        return dict(DEFAULT_SETTINGS)


def save_settings(settings: dict):
    """Persists settings to disk."""
    try:
        with open(config.SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(settings, f, indent=2)
        logger.info("Settings saved.")
    except Exception as e:
        logger.error(f"Failed to save settings: {e}", exc_info=True)
