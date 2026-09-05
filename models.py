# models.py
import logging
import re
from faster_whisper import WhisperModel
from transformers import AutoModelForSeq2SeqLM, AutoTokenizer
import config

logger = logging.getLogger("SpeechGrammarApp")


class SpeechModels:

    def __init__(self):
        self.whisper_model = None
        self.t5_model = None
        self.t5_tokenizer = None

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

    def load_t5(self):
        """Loads the Grammarly CoEdIT T5 model on demand."""
        if self.t5_model is None or self.t5_tokenizer is None:
            logger.info(f"Loading T5 Grammar Model ({config.T5_MODEL_NAME})...")
            self.t5_tokenizer = AutoTokenizer.from_pretrained(config.T5_MODEL_NAME)
            self.t5_model = AutoModelForSeq2SeqLM.from_pretrained(config.T5_MODEL_NAME)
            logger.info("T5 Grammar Model loaded successfully.")

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

    def correct_grammar(self, text: str) -> str:
        """Fixes grammatical errors using the T5 CoEdIT model."""
        if not text:
            return ""

        self.load_t5()
        logger.info("Applying grammar correction...")
        chunks = self._split_into_sentences(text)
        corrected_chunks = []

        for chunk in chunks:
            prompt = config.T5_PROMPT_PREFIX + chunk
            inputs = self.t5_tokenizer(
                prompt, return_tensors="pt", max_length=256, truncation=True
            )
            outputs = self.t5_model.generate(
                **inputs, max_length=256, num_beams=2, early_stopping=True
            )
            corrected_chunk = self.t5_tokenizer.decode(
                outputs[0], skip_special_tokens=True
            )
            corrected_chunks.append(corrected_chunk)

        return " ".join(corrected_chunks)

    def _split_into_sentences(self, text: str):
        """Splits transcript into logical sentence chunks for T5 processing."""
        sentences = re.split(r"(?<=[.!?])\s+", text)
        chunks = []
        current_chunk = ""

        for sentence in sentences:
            if len(current_chunk) + len(sentence) < 150:
                current_chunk += sentence + " "
            else:
                chunks.append(current_chunk.strip())
                current_chunk = sentence + " "

        if current_chunk:
            chunks.append(current_chunk.strip())

        return chunks
