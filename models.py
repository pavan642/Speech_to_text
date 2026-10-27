# models.py
import logging
from faster_whisper import WhisperModel
import config

logger = logging.getLogger("SpeechGrammarApp")


class SpeechModels:

    def __init__(self):
        self.whisper_model = None
        self._openai_client = None
        self._openai_key = None

    def load_whisper(self):
        """Loads the Whisper model for speech transcription."""
        if self.whisper_model is None:
            logger.info("Loading Whisper model...")
            self.whisper_model = WhisperModel(
                config.WHISPER_MODEL_NAME,
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
            vad_filter=False,
        )
        return " ".join([s.text.strip() for s in segments if s.text.strip()])

    def optimize_text(self, text: str, api_key: str) -> str:
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

        logger.info(f"Optimizing text with OpenAI ({config.OPENAI_MODEL})...")
        response = self._openai_client.chat.completions.create(
            model=config.OPENAI_MODEL,
            messages=[
                {"role": "system", "content": config.OPENAI_SYSTEM_PROMPT},
                {"role": "user", "content": text},
            ],
            temperature=0.3,
        )
        return response.choices[0].message.content.strip()
