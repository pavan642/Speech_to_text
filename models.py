# models.py
import logging
import numpy as np
import config

logger = logging.getLogger("SpeechGrammarApp")


class SpeechModels:

    def __init__(self):
        self.whisper_model = None
        self.whisper_model_name = config.WHISPER_MODEL_NAME
        self._openai_client = None
        self._openai_key = None

    def set_whisper_model(self, model_name: str):
        """Requests a different Whisper model size; forces a reload on next use."""
        if model_name and model_name != self.whisper_model_name:
            logger.info(f"Whisper model changed: {self.whisper_model_name} -> {model_name}")
            self.whisper_model_name = model_name
            self.whisper_model = None  # force reload

    def load_whisper(self):
        """Loads the Whisper model for speech transcription."""
        if self.whisper_model is None:
            # Lazy import: faster_whisper pulls in heavy native libraries
            # (ctranslate2, tokenizers, onnxruntime) — importing it here keeps
            # app startup instant instead of blocking the launch.
            from faster_whisper import WhisperModel

            logger.info(f"Loading Whisper model ({self.whisper_model_name})...")
            self.whisper_model = WhisperModel(
                self.whisper_model_name,
                device=config.WHISPER_DEVICE,
                compute_type=config.WHISPER_COMPUTE_TYPE,
            )
            logger.info("Whisper model loaded successfully.")

    def transcribe_audio(self, audio_data) -> str:
        """Transcribes raw audio float array using Whisper."""
        self.load_whisper()
        logger.info("Transcribing audio with Whisper...")
        segments, _ = self.whisper_model.transcribe(
            audio_data,
            beam_size=1,
            language="en",
            condition_on_previous_text=False,
            vad_filter=True,  # skip silence/noise via built-in Silero VAD
        )
        return " ".join([s.text.strip() for s in segments if s.text.strip()])

    def denoise_audio(self, audio_data):
        """Reduces background noise before transcription:
        1. High-pass filter removes low-frequency rumble/hum (< 85 Hz)
        2. Spectral gating (noisereduce) suppresses stationary noise (fans, AC)

        Libraries are imported lazily — if they are missing, the original
        audio is returned unchanged.
        """
        try:
            import noisereduce as nr
            from scipy.signal import butter, sosfilt
        except ImportError as e:
            logger.warning(f"Noise reduction unavailable ({e}); using raw audio.")
            return audio_data

        logger.info("Applying noise reduction...")
        # 1) High-pass filter: cut rumble and hum below 85 Hz
        sos = butter(4, 85, btype="highpass", fs=config.SAMPLE_RATE, output="sos")
        filtered = sosfilt(sos, audio_data).astype(np.float32)

        # 2) Spectral gating for stationary background noise
        reduced = nr.reduce_noise(
            y=filtered,
            sr=config.SAMPLE_RATE,
            stationary=True,
            prop_decrease=0.85,  # < 1.0 avoids metallic artifacts in speech
        )
        return reduced.astype(np.float32)

    def optimize_text(self, text: str, api_key: str, system_prompt: str = "") -> str:
        """Optimizes the transcribed text using the OpenAI API.

        The openai package is imported lazily here so the app can always
        transcribe speech even when openai (or its dependencies) is not
        installed or fails to load.
        """
        if not text or not api_key:
            return ""

        from openai import OpenAI  # lazy import — only needed for optimization

        # Recreate the client only when the key changes
        if self._openai_client is None or self._openai_key != api_key:
            self._openai_client = OpenAI(api_key=api_key)
            self._openai_key = api_key

        prompt = system_prompt.strip() or config.OPENAI_SYSTEM_PROMPT

        logger.info(f"Optimizing text with OpenAI ({config.OPENAI_MODEL})...")
        response = self._openai_client.chat.completions.create(
            model=config.OPENAI_MODEL,
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": text},
            ],
            temperature=0.3,
        )
        return response.choices[0].message.content.strip()
