# history_manager.py
"""Saves each transcription (original + optimized) to a timestamped Markdown file."""
import logging
import os
from datetime import datetime

logger = logging.getLogger("SpeechGrammarApp")

HISTORY_DIR = "history"


def save_transcription(raw_text: str, optimized_text: str) -> str:
    """Writes one transcription session to history/ and returns the file path."""
    os.makedirs(HISTORY_DIR, exist_ok=True)

    now = datetime.now()
    filename = os.path.join(HISTORY_DIR, f"transcription_{now:%Y%m%d_%H%M%S}.md")

    content = f"""# Transcription — {now:%Y-%m-%d %H:%M:%S}

## Original Text
{raw_text}

## Optimized Text (OpenAI)
{optimized_text if optimized_text else "_(not applied)_"}
"""

    with open(filename, "w", encoding="utf-8") as f:
        f.write(content)

    logger.info(f"Transcription saved to {filename}")
    return filename


def list_sessions() -> list:
    """Returns history file paths, newest first."""
    if not os.path.isdir(HISTORY_DIR):
        return []
    files = [
        os.path.join(HISTORY_DIR, f)
        for f in os.listdir(HISTORY_DIR)
        if f.endswith(".md")
    ]
    return sorted(files, reverse=True)  # timestamped names sort chronologically


def load_session(path: str):
    """Parses a history file back into (raw_text, optimized_text)."""
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()

    raw, optimized = content, ""
    marker_raw = "## Original Text"
    marker_opt = "## Optimized Text (OpenAI)"
    if marker_raw in content:
        after = content.split(marker_raw, 1)[1]
        if marker_opt in after:
            raw_part, opt_part = after.split(marker_opt, 1)
            raw = raw_part.strip()
            optimized = opt_part.strip()
            if optimized == "_(not applied)_":
                optimized = ""
        else:
            raw = after.strip()
    return raw, optimized
