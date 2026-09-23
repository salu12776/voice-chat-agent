"""Speech-to-text with faster-whisper (CPU by default, CUDA when available)."""

from __future__ import annotations

import threading
from pathlib import Path

import ctranslate2
from faster_whisper import WhisperModel

from .config import STTConfig


class STTError(RuntimeError):
    """A user-facing transcription problem."""


class WhisperSTT:
    """Lazily-loaded faster-whisper model."""

    def __init__(self, config: STTConfig) -> None:
        self.config = config
        self._model: WhisperModel | None = None
        self._lock = threading.Lock()

    @property
    def device(self) -> str:
        if self.config.device != "auto":
            return self.config.device
        return "cuda" if ctranslate2.get_cuda_device_count() > 0 else "cpu"

    @property
    def compute_type(self) -> str:
        if self.config.compute_type != "auto":
            return self.config.compute_type
        return "float16" if self.device == "cuda" else "int8"

    def load(self) -> WhisperModel:
        """Load the model on first use (downloads it once from Hugging Face)."""
        with self._lock:
            if self._model is None:
                try:
                    self._model = WhisperModel(
                        self.config.model, device=self.device, compute_type=self.compute_type
                    )
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
