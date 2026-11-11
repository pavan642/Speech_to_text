# tts_manager.py
"""Text-to-speech via the built-in macOS `say` command (no dependencies)."""
import logging
import shutil
import subprocess
import sys

logger = logging.getLogger("SpeechEditor")


class TextToSpeech:

    def __init__(self):
        self._proc = None

    @property
    def supported(self) -> bool:
        return sys.platform == "darwin" and shutil.which("say") is not None

    def speak(self, text: str) -> bool:
        """Speaks text aloud. Returns False if nothing was spoken."""
        self.stop()
        text = (text or "").strip()
        if not text:
            return False
        if not self.supported:
            logger.warning("TTS is currently supported on macOS only (uses `say`).")
            return False
        self._proc = subprocess.Popen(["say", text])
        logger.info("TTS started.")
        return True

    def stop(self):
        if self._proc and self._proc.poll() is None:
            self._proc.terminate()
            logger.info("TTS stopped.")
        self._proc = None
