"""Speech-to-text: faster-whisper locally, or Groq's hosted Whisper for the online demo."""

from __future__ import annotations

import os
import threading
from pathlib import Path

import httpx

from .config import STTConfig


class STTError(RuntimeError):
    """A user-facing transcription problem."""


class WhisperSTT:
    """Lazily-loaded faster-whisper model (runs on your own computer)."""

    def __init__(self, config: STTConfig) -> None:
        self.config = config
        self._model = None
        self._lock = threading.Lock()

    @property
    def device(self) -> str:
        if self.config.device != "auto":
            return self.config.device
        import ctranslate2  # imported here so the online demo doesn't need it installed

        return "cuda" if ctranslate2.get_cuda_device_count() > 0 else "cpu"

    @property
    def compute_type(self) -> str:
        if self.config.compute_type != "auto":
            return self.config.compute_type
        return "float16" if self.device == "cuda" else "int8"

    def load(self):
        """Load the model on first use (downloads it once from Hugging Face)."""
        with self._lock:
            if self._model is None:
                try:
                    from faster_whisper import WhisperModel

                    self._model = WhisperModel(self.config.model, device=self.device, compute_type=self.compute_type)
                except Exception as exc:
                    raise STTError(f"Couldn't load the speech model `{self.config.model}`: {exc}") from exc
            return self._model

    def transcribe(self, audio_path: str | Path) -> str:
        """Transcribe an audio file and return the text (empty if nothing was said)."""
        model = self.load()
        try:
            segments, _ = model.transcribe(
                str(audio_path),
                language=self.config.language or None,
                beam_size=1,
                vad_filter=True,
            )
            return " ".join(s.text.strip() for s in segments).strip()
        except Exception as exc:
            raise STTError(f"Transcription failed: {exc}") from exc


class GroqSTT:
    """Groq's hosted Whisper. No model on the server, so it fits a small free instance."""

    URL = "https://api.groq.com/openai/v1/audio/transcriptions"
    MODEL = "whisper-large-v3-turbo"
    MAX_BYTES = 10 * 1024 * 1024  # about a few minutes of audio; stops huge uploads

    def __init__(self, config: STTConfig) -> None:
        self.config = config
        self.api_key = os.environ.get("GROQ_API_KEY", "").strip()
        self.client = httpx.Client(timeout=httpx.Timeout(30.0), headers={"Authorization": f"Bearer {self.api_key}"})

    def load(self) -> None:
        """Nothing to load; kept so the UI can warm up both engines the same way."""
        if not self.api_key:
            raise STTError("GROQ_API_KEY is missing, so speech recognition is off.")

    def transcribe(self, audio_path: str | Path) -> str:
        if not self.api_key:
            raise STTError("Speech recognition isn't configured yet (missing API key).")
        path = Path(audio_path)
        if path.stat().st_size > self.MAX_BYTES:
            raise STTError("That recording is too long. Please keep it under a minute.")
        data = {"model": os.environ.get("STT_MODEL", self.MODEL), "response_format": "json"}
        if self.config.language:
            data["language"] = self.config.language
        try:
            with path.open("rb") as f:
                response = self.client.post(self.URL, data=data, files={"file": (path.name, f, "audio/wav")})
        except httpx.HTTPError as exc:
            print(f"Groq STT connection error: {exc}")
            raise STTError("Couldn't reach the speech service. Please try again.") from exc
        if response.status_code == 429:
            raise STTError("Lots of people are talking to me right now. Please try again in a few seconds.")
        if response.status_code >= 400:
            print(f"Groq STT error {response.status_code}: {response.text[:300]}")
            raise STTError("Speech recognition failed. Please try again.")
        return (response.json().get("text") or "").strip()


def create_stt(config: STTConfig):
    """Pick the engine from config.stt.engine: "whisper" (local) or "groq" (online demo)."""
    return GroqSTT(config) if config.engine == "groq" else WhisperSTT(config)
