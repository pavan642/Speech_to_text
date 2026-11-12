# models.py
import logging
import time

import numpy as np
import config

# LLM request timeout (seconds)
LLM_TIMEOUT = 60

logger = logging.getLogger("SpeechEditor")


class SpeechModels:

    def __init__(self):
        self.whisper_model = None
        self.whisper_model_name = config.WHISPER_MODEL_NAME
        self._claude_client = None
        self._claude_key = None

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

    def transcribe_audio(self, audio_data, language: str = "en") -> str:
        """Transcribes raw audio float array using Whisper.
        language=None lets Whisper auto-detect."""
        self.load_whisper()
        logger.info("Transcribing audio with Whisper...")
        segments, _ = self.whisper_model.transcribe(
            audio_data,
            beam_size=1,
            language=language or None,
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

    # ---------- LLM optimization via LiteLLM (100+ providers) ----------

    @staticmethod
    def resolve_model(api_key: str, api_base: str = "") -> str:
        """Auto-picks a default model from the API key format:
        sk-ant-…→Claude, sk-…→GPT-4o-mini, AIza…→Gemini, gsk_…→Groq,
        no key/base URL→local Ollama."""
        key = (api_key or "").strip()
        if key.startswith("sk-ant-"):
            return "claude-sonnet-5-5"
        if key.startswith("AIza"):
            return "gemini/gemini-2.0-flash"
        if key.startswith("gsk_"):
            return "groq/llama-3.3-70b-versatile"
        if key.startswith("sk-"):
            return "gpt-4o-mini"
        if api_base or not key:
            return "ollama/llama3.2"  # local free default
        return config.LLM_MODEL

    def optimize_with_llm(self, text: str, api_key: str, model: str = "",
                          system_prompt: str = "", api_base: str = "") -> str:
        """Optimizes text via any LiteLLM-supported provider (OpenAI, Anthropic,
        Gemini, Groq, Ollama…). litellm is imported lazily. 60s timeout."""
        if not text:
            return ""

        import litellm  # lazy import

        model_name = model or self.resolve_model(api_key, api_base)
        logger.info(
            f"[LLM] → request: model={model_name} "
            f"base={api_base or 'default'} text_len={len(text)} timeout={LLM_TIMEOUT}s"
        )
        t0 = time.time()
        try:
            response = litellm.completion(
                model=model_name,
                messages=[
                    {"role": "system", "content": system_prompt or config.CLAUDE_OPTIMIZE_PROMPT},
                    {"role": "user", "content": text},
                ],
                api_key=api_key or None,
                api_base=api_base or None,
                max_tokens=config.CLAUDE_MAX_TOKENS,
                timeout=LLM_TIMEOUT,
            )
            elapsed = time.time() - t0
            usage = getattr(response, "usage", None)
            logger.info(f"[LLM] ← response: {elapsed:.1f}s, usage={usage}")
            return (response.choices[0].message.content or "").strip()
        except Exception as e:
            logger.error(f"[LLM] ✗ failed after {time.time() - t0:.1f}s: {e}")
            raise

    def optimize_with_llm_stream(self, text: str, api_key: str, model: str,
                                 system_prompt: str, api_base: str, on_delta):
        """Streams the optimization token-by-token via LiteLLM. 60s timeout."""
        if not text:
            return

        import litellm  # lazy import

        model_name = model or self.resolve_model(api_key, api_base)
        logger.info(
            f"[LLM] → stream request: model={model_name} "
            f"base={api_base or 'default'} text_len={len(text)} timeout={LLM_TIMEOUT}s"
        )
        t0 = time.time()
        chunks = 0
        try:
            stream = litellm.completion(
                model=model_name,
                messages=[
                    {"role": "system", "content": system_prompt or config.CLAUDE_OPTIMIZE_PROMPT},
                    {"role": "user", "content": text},
                ],
                api_key=api_key or None,
                api_base=api_base or None,
                max_tokens=config.CLAUDE_MAX_TOKENS,
                stream=True,
                timeout=LLM_TIMEOUT,
            )
            for chunk in stream:
                try:
                    piece = chunk.choices[0].delta.content
                except (AttributeError, IndexError, TypeError):
                    piece = None
                if piece:
                    on_delta(piece)
                    chunks += 1
            logger.info(f"[LLM] ← stream done: {time.time() - t0:.1f}s, {chunks} chunks")
        except Exception as e:
            logger.error(f"[LLM] ✗ stream failed after {time.time() - t0:.1f}s: {e}")
            raise

    # ---------- Backwards-compatible aliases (older call sites) ----------

    def optimize_with_claude(self, text: str, api_key: str, model: str = "",
                             system_prompt: str = "", api_base: str = "") -> str:
        return self.optimize_with_llm(text, api_key, model, system_prompt, api_base)

    def optimize_with_claude_stream(self, text: str, api_key: str, model: str,
                                    system_prompt: str, on_delta, api_base: str = ""):
        return self.optimize_with_llm_stream(
            text, api_key, model, system_prompt, api_base, on_delta
        )
