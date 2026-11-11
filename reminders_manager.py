# reminders_manager.py
"""Per-document reminders: persists to reminders.json and reports due items."""
import json
import logging
import os
from datetime import datetime

logger = logging.getLogger("SpeechEditor")

REMINDERS_FILE = "reminders.json"


def _load() -> list:
    if not os.path.exists(REMINDERS_FILE):
        return []
    try:
        with open(REMINDERS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        return [r for r in data if isinstance(r, dict) and "path" in r and "when" in r]
    except Exception as e:
        logger.warning(f"Failed to load reminders: {e}")
        return []


def _save(reminders: list):
    try:
        with open(REMINDERS_FILE, "w", encoding="utf-8") as f:
            json.dump(reminders, f, indent=2)
    except Exception as e:
        logger.error(f"Failed to save reminders: {e}", exc_info=True)


def add_reminder(path: str, title: str, when: datetime):
    reminders = _load()
    # One reminder per document — replace any existing one for this path
    reminders = [r for r in reminders if r["path"] != path]
    reminders.append({
        "path": path,
        "title": title,
        "when": when.isoformat(timespec="seconds"),
        "fired": False,
    })
    _save(reminders)
    logger.info(f"Reminder set for “{title}” at {when:%Y-%m-%d %H:%M}")


def remove_reminder(path: str):
    reminders = [r for r in _load() if r["path"] != path]
    _save(reminders)


def pending_reminders() -> list:
    return [r for r in _load() if not r.get("fired")]


def due_reminders(now: datetime = None) -> list:
    """Returns reminders whose time has come and that haven't fired yet."""
    now = now or datetime.now()
    due = []
    for r in _load():
        if r.get("fired"):
            continue
        try:
            when = datetime.fromisoformat(r["when"])
        except (ValueError, TypeError):
            continue
        if when <= now:
            due.append(r)
    return due


def mark_fired(path: str):
    reminders = _load()
    for r in reminders:
        if r["path"] == path:
            r["fired"] = True
    _save(reminders)
