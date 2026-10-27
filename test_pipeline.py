# test_pipeline.py
"""Smoke test: verifies the audio -> text pipeline is healthy in this environment.

Generates a 3-second synthetic speech-like WAV, then runs it through the real
pipeline: noise reduction -> Whisper transcription. Also checks every key
dependency imports cleanly (catches architecture/broken-wheel issues early).

Run:  python3 test_pipeline.py
Exit code 0 = all good, 1 = something is broken.
"""
import os
import platform
import sys
import tempfile
import time
import wave

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
    import numpy as np

    print("=" * 60)
    print("Speech-to-Text pipeline smoke test")
    print("=" * 60)
    print(f"Python {sys.version.split()[0]} · {platform.machine()} · {sys.executable}\n")

    # ---- 1. Dependencies ----
    check("numpy", lambda: np.__version__)
    check("faster-whisper", lambda: __import__("faster_whisper").__version__)
    check("sounddevice", lambda: __import__("sounddevice").__version__)
    check("scipy", lambda: __import__("scipy").__version__)
    check("noisereduce", lambda: __import__("noisereduce").__version__)
    check("openai (+ jiter)", lambda: __import__("openai").__version__, required=False)
    check("PyQt5", lambda: __import__("PyQt5.QtCore").QT_VERSION_STR)

    # ---- 2. Generate a 3s synthetic speech-like WAV ----
    import config

    sr = config.SAMPLE_RATE
    t = np.linspace(0, 3, int(sr * 3), endpoint=False)
    envelope = 0.5 + 0.5 * np.sin(2 * np.pi * 2 * t)  # 2 Hz "syllable" modulation
    signal = envelope * (
        0.30 * np.sin(2 * np.pi * 140 * t)
        + 0.15 * np.sin(2 * np.pi * 280 * t)
        + 0.10 * np.sin(2 * np.pi * 420 * t)
    ).astype(np.float32)

    tmpdir = tempfile.mkdtemp(prefix="stt_smoke_")
    wav_path = os.path.join(tmpdir, "tone_3s.wav")
    with wave.open(wav_path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes((signal * 32767).astype(np.int16).tobytes())
    print(f"\n{PASS} Generated test WAV — {wav_path} (3s @ {sr} Hz)")

    # ---- 3. Run the real pipeline ----
    from models import SpeechModels
    models = SpeechModels()

    def run_denoise():
        out = models.denoise_audio(signal)
        assert len(out) == len(signal), "length changed"
        return f"{len(out)} samples in/out"
    check("noise reduction", run_denoise)

    def run_transcribe():
        t0 = time.time()
        text = models.transcribe_audio(models.denoise_audio(signal))
        assert isinstance(text, str), "expected str"
        note = f"{time.time() - t0:.1f}s"
        return note + (f", text={text!r}" if text else " (empty text is expected for a synthetic tone)")
    check("whisper transcription", run_transcribe)

    # ---- Summary ----
    print("\n" + "=" * 60)
    if failures:
        print(f"{FAIL} {failures} required check(s) failed — fix the items above.")
        sys.exit(1)
    print(f"{PASS} All required checks passed — pipeline is healthy.")
    sys.exit(0)


if __name__ == "__main__":
    main()
