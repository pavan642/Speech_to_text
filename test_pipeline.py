# test_pipeline.py
"""Smoke test: verifies the TextIQ environment and core modules are healthy.

Checks every key dependency imports cleanly (catches architecture/broken-wheel
issues early), app modules import, and each storage manager round-trips.
No model downloads, no window creation — fast enough for CI.

Run:  python3 test_pipeline.py
Exit code 0 = all good, 1 = something is broken.
"""
import os
import platform
import sys
import tempfile

PASS, FAIL, WARN = "✅", "❌", "⚠️ "
failures = 0


def check(label, fn, required=True):
    global failures
    try:
        result = fn()
        print(f"{PASS} {label}" + (f" — {result}" if result else ""))
        return True
    except Exception as e:
        if required:
            failures += 1
            print(f"{FAIL} {label} — {e}")
        else:
            print(f"{WARN}  {label} — {e} (optional, feature will be skipped)")
        return False


def main():
    print("=" * 60)
    print("TextIQ environment smoke test")
    print("=" * 60)
    print(f"Python {sys.version.split()[0]} · {platform.machine()} · {sys.executable}\n")

    # ---- 1. Third-party dependencies ----
    check("numpy", lambda: __import__("numpy").__version__)
    check("PyQt5", lambda: __import__("PyQt5.QtCore").QT_VERSION_STR)
    check("faster-whisper", lambda: __import__("faster_whisper").__version__)
    check("sounddevice", lambda: __import__("sounddevice").__version__)
    check("scipy", lambda: __import__("scipy").__version__)
    check("noisereduce", lambda: __import__("noisereduce").__version__)
    check("anthropic (Claude)", lambda: __import__("anthropic").__version__, required=False)
    check("qtawesome (icons)", lambda: __import__("qtawesome").__version__, required=False)
    check("keyring (secure key storage)", lambda: __import__("keyring").__version__, required=False)

    # ---- 2. App modules import ----
    def import_app_modules():
        import main  # noqa: F401  (module-level code: logging setup only)
        import models, config, settings_manager  # noqa: F401
        import documents_manager, history_manager, reminders_manager  # noqa: F401
        import tts_manager, git_manager  # noqa: F401
        import ui.pane, ui.toolbar, ui.sidebar  # noqa: F401
        return "main + models + managers + ui/*"
    check("app modules import", import_app_modules)

    # ---- 3. Managers round-trip in a temp dir ----
    tmp = tempfile.mkdtemp(prefix="textiq_smoke_")

    def docs_roundtrip():
        import documents_manager as dm
        folder = os.path.join(tmp, "docs")
        path = dm.create_document(folder, "smoke", ext=".md")
        dm.save_document(path, "smoke content")
        assert dm.read_document(path) == "smoke content"
        dup = dm.duplicate_document(path)
        renamed = dm.rename_document(path, "smoke_renamed")
        dm.delete_document(dup)
        dm.delete_document(renamed)
        assert not os.path.exists(dup) and not os.path.exists(renamed)
        return "create/save/read/duplicate/rename/delete"
    check("documents manager", docs_roundtrip)

    def history_roundtrip():
        import history_manager as hm
        monkey_dir = os.path.join(tmp, "history")
        original = hm.HISTORY_DIR
        hm.HISTORY_DIR = monkey_dir
        try:
            path = hm.save_transcription("raw", "opt")
            raw, opt = hm.load_session(hm.list_sessions()[0])
            assert raw == "raw" and opt == "opt"
        finally:
            hm.HISTORY_DIR = original
    check("history manager", history_roundtrip)

    def reminders_roundtrip():
        import reminders_manager as rm
        from datetime import datetime, timedelta
        original = rm.REMINDERS_FILE
        rm.REMINDERS_FILE = os.path.join(tmp, "r.json")
        try:
            rm.add_reminder("/tmp/x.md", "x", datetime.now() - timedelta(minutes=1))
            assert len(rm.due_reminders()) == 1
            rm.mark_fired("/tmp/x.md")
            assert rm.due_reminders() == []
        finally:
            rm.REMINDERS_FILE = original
    check("reminders manager", reminders_roundtrip)

    def settings_roundtrip():
        import settings_manager as sm
        original_file = sm.config.SETTINGS_FILE
        sm.config.SETTINGS_FILE = os.path.join(tmp, "settings.json")
        try:
            s = sm.load_settings()
            assert "theme" in s and "claude_api_key" in s
            sm.save_settings(s)
            assert os.path.exists(sm.config.SETTINGS_FILE)
        finally:
            sm.config.SETTINGS_FILE = original_file
    check("settings manager", settings_roundtrip)

    def denoise_runs():
        import numpy as np
        from models import SpeechModels
        audio = (0.1 * np.sin(2 * np.pi * 200 * np.linspace(0, 1, 16000))).astype(np.float32)
        out = SpeechModels().denoise_audio(audio)
        assert len(out) == len(audio)
        return "16k samples in/out"
    check("noise reduction pipeline", denoise_runs)

    # ---- Summary ----
    print("\n" + "=" * 60)
    if failures:
        print(f"{FAIL} {failures} required check(s) failed — fix the items above.")
        sys.exit(1)
    print(f"{PASS} All required checks passed — environment is healthy.")
    sys.exit(0)


if __name__ == "__main__":
    main()
