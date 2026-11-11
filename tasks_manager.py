# tasks_manager.py
"""Persists the checkbox task list to tasks.json."""
import json
import logging
import os

logger = logging.getLogger("SpeechEditor")

TASKS_FILE = "tasks.json"


def load_tasks() -> list:
    """Returns [{text, done}, ...] — empty list on any problem."""
    if not os.path.exists(TASKS_FILE):
        return []
    try:
        with open(TASKS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        return [t for t in data if isinstance(t, dict) and "text" in t]
    except Exception as e:
        logger.warning(f"Failed to load tasks: {e}")
        return []


def save_tasks(tasks: list):
    try:
        with open(TASKS_FILE, "w", encoding="utf-8") as f:
            json.dump(tasks, f, indent=2)
    except Exception as e:
        logger.error(f"Failed to save tasks: {e}", exc_info=True)
