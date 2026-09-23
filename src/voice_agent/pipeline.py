"""Stream an LLM reply while synthesizing it sentence by sentence in parallel."""

from __future__ import annotations

import queue
import threading
from collections.abc import Iterator
from typing import Any, Literal

from .llm import LLMError, Message, OllamaLLM
from .tts import Audio, SentenceSplitter, TTSEngine, TTSError

EventKind = Literal["text", "audio", "tts_error"]


def stream_reply(
    llm: OllamaLLM,
    tts: TTSEngine,
    history: list[Message],
    user_text: str,
    system_prompt: str,
    *,
    model: str | None = None,
    temperature: float | None = None,
    voice: str | None = None,
) -> Iterator[tuple[EventKind, Any]]:
    """Yield ("text", chunk), ("audio", (rate, samples)) and ("tts_error", exc) events as they happen.

    The LLM and TTS run in their own threads, so the first sentence is being spoken while the model is
    still writing the rest. Audio events arrive in sentence order. Raises LLMError if the model fails.
    Closing the generator (e.g. the user starts a new turn) stops both workers.
    """
    events: queue.Queue[tuple[str, Any]] = queue.Queue()
    sentences: queue.Queue[str | None] = queue.Queue()
    cancel = threading.Event()

    def run_llm() -> None:
        splitter = SentenceSplitter()
        try:
            for chunk in llm.stream_chat(
                history, user_text, system_prompt, model=model, temperature=temperature
            ):
                if cancel.is_set():
                    return
                events.put(("text", chunk))
                for sentence in splitter.feed(chunk):
                    sentences.put(sentence)
            for sentence in splitter.flush():
                sentences.put(sentence)
        except LLMError as exc:
            events.put(("llm_error", exc))
        finally:
            sentences.put(None)
            events.put(("llm_done", None))

    def run_tts() -> None:
        failed = False
        while (sentence := sentences.get()) is not None:
            if cancel.is_set() or failed:
                continue
            try:
                audio: Audio = tts.synthesize(sentence, voice=voice)
                if len(audio[1]):
                    events.put(("audio", audio))
            except TTSError as exc:
                failed = True  # keep the text flowing; stop trying to speak this reply
                events.put(("tts_error", exc))
        events.put(("tts_done", None))

    workers = [threading.Thread(target=run_llm, daemon=True), threading.Thread(target=run_tts, daemon=True)]
    for worker in workers:
        worker.start()

    running = len(workers)
    try:
        while running:
            kind, payload = events.get()
            if kind.endswith("_done"):
                running -= 1
            elif kind == "llm_error":
                raise payload
            else:
                yield kind, payload  # type: ignore[misc]
    finally:
        cancel.set()
