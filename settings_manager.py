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
    "llm_api_base": "",
    "whisper_model": config.WHISPER_MODEL_NAME,
    "live_transcription": True,
    "noise_reduction": True,
    "documents_folder": config.DEFAULT_DOCUMENTS_FOLDER,
    "doc_extension": ".txt",
    "save_history": True,
    "git_remote_url": "",
    "git_branch": "main",
    "language": "en",
    "session": {},
}

# Claude API key lives in the OS keychain when the `keyring` package is
# available — never in settings.json. Falls back to JSON storage otherwise.
KEYRING_SERVICE = "TextIQ"
KEYRING_ACCOUNT = "claude_api_key"


def _keyring():
    try:
        import keyring
        return keyring
    except Exception:
        return None


def load_settings() -> dict:
    """Loads settings from disk, falling back to defaults for missing keys.
    The Claude API key is pulled from the OS keychain when available."""
    settings = dict(DEFAULT_SETTINGS)
    if os.path.exists(config.SETTINGS_FILE):
        try:
            with open(config.SETTINGS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            settings.update({k: v for k, v in data.items() if k in DEFAULT_SETTINGS})
        except Exception as e:
            logger.warning(f"Failed to load settings file, using defaults: {e}")

    kr = _keyring()
    if kr and not settings.get("claude_api_key"):
        try:
            key = kr.get_password(KEYRING_SERVICE, KEYRING_ACCOUNT)
            if key:
                settings["claude_api_key"] = key
        except Exception as e:
            logger.warning(f"Keychain read failed: {e}")
    return settings


def save_settings(settings: dict):
    """Persists settings to disk. The Claude API key goes to the OS keychain
    when available — settings.json never stores it."""
    to_store = dict(settings)
    kr = _keyring()
    if kr:
        try:
            key = settings.get("claude_api_key", "")
            if key:
                kr.set_password(KEYRING_SERVICE, KEYRING_ACCOUNT, key)
            else:
                try:
                    kr.delete_password(KEYRING_SERVICE, KEYRING_ACCOUNT)
                except Exception:
                    pass
            to_store["claude_api_key"] = ""  # keep it out of the JSON file
        except Exception as e:
            logger.warning(f"Keychain write failed, key stays in JSON: {e}")

    try:
        with open(config.SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(to_store, f, indent=2)
        logger.info("Settings saved.")
    except Exception as e:
        logger.error(f"Failed to save settings: {e}", exc_info=True)
