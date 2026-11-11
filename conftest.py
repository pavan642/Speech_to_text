# conftest.py — pytest setup for the TextIQ test suite
import os
import sys

# Qt must run headless in CI/terminal
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import pytest
from PyQt5.QtWidgets import QApplication

import config
import settings_manager


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture()
def app_window(qapp, tmp_path, monkeypatch):
    """A fresh SpeechEditorApp with all persistence redirected to tmp_path."""
    import main as main_module

    monkeypatch.setattr(config, "SETTINGS_FILE", str(tmp_path / "settings.json"))
    monkeypatch.setattr(settings_manager.config, "SETTINGS_FILE", str(tmp_path / "settings.json"))
    monkeypatch.setattr(settings_manager, "DEFAULT_SETTINGS",
                        {**settings_manager.DEFAULT_SETTINGS,
                         "documents_folder": str(tmp_path / "docs"),
                         "theme": "dark"})
    monkeypatch.setattr(history_file := __import__("history_manager"), "HISTORY_DIR",
                        str(tmp_path / "history"))
    monkeypatch.setattr(__import__("tasks_manager"), "TASKS_FILE",
                        str(tmp_path / "tasks.json"))
    monkeypatch.setattr(__import__("reminders_manager"), "REMINDERS_FILE",
                        str(tmp_path / "reminders.json"))

    # Don't download/load a real Whisper model in tests (CI speed)
    monkeypatch.setattr(main_module.SpeechModels, "load_whisper", lambda self: None)

    window = main_module.SpeechEditorApp()
    yield window
    window.tts.stop()
    window.deleteLater()
