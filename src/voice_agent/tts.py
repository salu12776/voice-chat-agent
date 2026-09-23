"""Text-to-speech engines behind a small swappable interface."""

from __future__ import annotations

import re
import threading
import urllib.request
from pathlib import Path
from typing import Protocol

import numpy as np

from .config import TTSConfig

Audio = tuple[int, np.ndarray]  # (sample_rate, float32 samples) — what gr.Audio accepts


class TTSError(RuntimeError):
    """A user-facing speech synthesis problem."""


class TTSEngine(Protocol):
    """Anything that can turn text into audio."""

    def voices(self) -> list[str]: ...

    def synthesize(self, text: str, voice: str | None = None, speed: float | None = None) -> Audio: ...


def clean_for_speech(text: str) -> str:
    """Strip markdown and emoji the model may still emit so they aren't read aloud."""
    text = re.sub(r"```.*?```", " ", text, flags=re.S)
    text = re.sub(r"[*_#`>~|]+", "", text)
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    text = re.sub(r"[\U0001F000-\U0001FAFF☀-➿]", "", text)
    return re.sub(r"\s+", " ", text).strip()


_BOUNDARY = re.compile(r"[.!?…]+[\"')\]]*\s+|\n+")
_SOFT_BOUNDARY = re.compile(r"[,;:—–]\s+")
_ABBREVIATIONS = {"mr", "mrs", "ms", "dr", "prof", "st", "jr", "sr", "vs", "etc", "e.g", "i.e", "inc", "no", "approx"}


class SentenceSplitter:
    """Split streamed text into speakable sentences as soon as each one is complete.

    Very short fragments ("Sure!") are merged with the next sentence so audio isn't choppy, and a run-on
    sentence longer than `max_chars` is cut at a comma. The very first clip may also end at a comma once
    it has `first_min_chars`, so the voice starts as early as possible.
    """

    def __init__(self, min_chars: int = 16, max_chars: int = 220, first_min_chars: int = 30) -> None:
        self.min_chars = min_chars
        self.max_chars = max_chars
        self.first_min_chars = first_min_chars
        self.buffer = ""
        self.emitted = 0

    def feed(self, text: str) -> list[str]:
        """Add streamed text; return any sentences that are now complete."""
        self.buffer += text
        sentences: list[str] = []
        start = 0
        for match in _BOUNDARY.finditer(self.buffer):
            before = self.buffer[start : match.start()].split()
            if match.group().startswith(".") and before and before[-1].lower().rstrip(".") in _ABBREVIATIONS:
                continue
            if len(self.buffer[start : match.end()].strip()) < self.min_chars:
                continue
            sentences.append(self.buffer[start : match.end()].strip())
            start = match.end()
        self.buffer = self.buffer[start:]

        if not self.emitted and not sentences:
            cut = next((m for m in _SOFT_BOUNDARY.finditer(self.buffer) if m.end() >= self.first_min_chars), None)
            if cut:
                sentences.append(self.buffer[: cut.end()].strip())
                self.buffer = self.buffer[cut.end() :]
        elif len(self.buffer) > self.max_chars:
            cuts = list(_SOFT_BOUNDARY.finditer(self.buffer, 0, self.max_chars))
            if cuts and cuts[-1].end() >= self.min_chars:
                sentences.append(self.buffer[: cuts[-1].end()].strip())
                self.buffer = self.buffer[cuts[-1].end() :]
        self.emitted += len(sentences)
        return sentences

    def flush(self) -> list[str]:
        """Return whatever text is left once the stream ends."""
        rest, self.buffer = self.buffer.strip(), ""
        return [rest] if rest else []


def _download(url: str, dest: Path) -> None:
    """Download `url` to `dest` atomically."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".part")
    try:
        urllib.request.urlretrieve(url, tmp)
        tmp.replace(dest)
    except Exception as exc:
        tmp.unlink(missing_ok=True)
        raise TTSError(f"Couldn't download {dest.name} ({exc}). Check your internet connection.") from exc


class KokoroTTS:
    """Kokoro-82M via kokoro-onnx. Model files are downloaded to models_dir on first use."""

    def __init__(self, config: TTSConfig) -> None:
        self.config = config
        self.model_path = config.models_dir / Path(config.kokoro["model_url"]).name
        self.voices_path = config.models_dir / Path(config.kokoro["voices_url"]).name
        self._engine = None
        self._lock = threading.Lock()

    def load(self):
        """Download (once) and load the ONNX model."""
        with self._lock:
            if self._engine is None:
                from kokoro_onnx import Kokoro

                for path, key in ((self.model_path, "model_url"), (self.voices_path, "voices_url")):
                    if not path.exists():
                        print(f"Downloading {path.name} …")
                        _download(self.config.kokoro[key], path)
                try:
                    self._engine = Kokoro(str(self.model_path), str(self.voices_path))
                except Exception as exc:
                    raise TTSError(f"Couldn't load Kokoro TTS: {exc}") from exc
            return self._engine

    def voices(self) -> list[str]:
        return sorted(self.load().get_voices())

    def synthesize(self, text: str, voice: str | None = None, speed: float | None = None) -> Audio:
        voice = voice or self.config.voice
        # Kokoro voice ids start with the language: a=American, b=British English, etc.
        lang = {"a": "en-us", "b": "en-gb", "e": "es", "f": "fr-fr", "h": "hi", "i": "it", "p": "pt-br",
                "j": "ja", "z": "cmn"}.get(voice[:1], "en-us")
        try:
            samples, rate = self.load().create(
                clean_for_speech(text), voice=voice, speed=speed or self.config.speed, lang=lang
            )
        except TTSError:
            raise
        except Exception as exc:
            raise TTSError(f"Speech synthesis failed: {exc}") from exc
        return rate, samples


class PiperTTS:
    """Piper fallback engine. Requires `uv add piper-tts` and a voice .onnx (+ .onnx.json) in models_dir."""

    def __init__(self, config: TTSConfig) -> None:
        self.config = config
        self.model_path = config.models_dir / config.piper.get("voice_model", "en_US-lessac-medium.onnx")
        self._voice = None

    def load(self):
        if self._voice is None:
            try:
                from piper import PiperVoice
            except ImportError as exc:
                raise TTSError("Piper isn't installed. Run `uv add piper-tts`.") from exc
            if not self.model_path.exists():
                raise TTSError(f"Piper voice not found at {self.model_path}.")
            self._voice = PiperVoice.load(str(self.model_path))
        return self._voice

    def voices(self) -> list[str]:
        return [self.model_path.stem]

    def synthesize(self, text: str, voice: str | None = None, speed: float | None = None) -> Audio:
        piper = self.load()
        chunks = list(piper.synthesize(clean_for_speech(text)))
        if not chunks:
            return piper.config.sample_rate, np.zeros(0, dtype=np.float32)
        samples = np.concatenate([c.audio_float_array for c in chunks])
        return chunks[0].sample_rate, samples


def create_tts(config: TTSConfig) -> TTSEngine:
    """Build the engine named in config.tts.engine."""
    engines = {"kokoro": KokoroTTS, "piper": PiperTTS}
    if config.engine not in engines:
        raise TTSError(f"Unknown TTS engine `{config.engine}`. Choose one of: {', '.join(engines)}.")
    return engines[config.engine](config)
