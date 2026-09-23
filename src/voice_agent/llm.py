"""Ollama client: health checks, model listing, history trimming and streaming chat."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass

import httpx
import ollama

from .config import LLMConfig

Message = dict[str, str]


class LLMError(RuntimeError):
    """A user-facing problem talking to Ollama."""


@dataclass
class HealthStatus:
    ok: bool
    message: str
    models: list[str]


class OllamaLLM:
    """Thin wrapper around the official `ollama` client."""

    def __init__(self, config: LLMConfig) -> None:
        self.config = config
        self.client = ollama.Client(host=config.host)

    def list_models(self) -> list[str]:
        """Return the names of locally installed models. Raises LLMError if Ollama is down."""
        try:
            response = self.client.list()
        except (httpx.ConnectError, ConnectionError) as exc:
            raise LLMError(
                f"Can't reach Ollama at {self.config.host}. "
                "Start it with `ollama serve` (or open the Ollama app) and refresh."
            ) from exc
        return sorted(m.model for m in response.models if m.model)

    def health(self, model: str | None = None) -> HealthStatus:
        """Check that Ollama is running and that `model` is installed."""
        model = model or self.config.model
        try:
            models = self.list_models()
        except LLMError as exc:
            return HealthStatus(False, str(exc), [])
        if not _has_model(models, model):
            return HealthStatus(
                False,
                f"Model `{model}` isn't installed. Run `ollama pull {model}` in a terminal, then refresh.",
                models,
            )
        return HealthStatus(True, f"Connected to Ollama · {model}", models)

    def stream_chat(
        self,
        history: list[Message],
        user_text: str,
        system_prompt: str,
        model: str | None = None,
        temperature: float | None = None,
    ) -> Iterator[str]:
        """Stream the reply to `user_text`, yielding text chunks as they arrive."""
        messages = [{"role": "system", "content": system_prompt}]
        messages += trim_history(history, self.config.max_history_turns, self.config.max_history_chars)
        messages.append({"role": "user", "content": user_text})
        model = model or self.config.model
        try:
            stream = self.client.chat(
                model=model,
                messages=messages,
                stream=True,
                options={"temperature": self.config.temperature if temperature is None else temperature},
            )
            for chunk in stream:
                if text := chunk.message.content:
                    yield text
        except (httpx.ConnectError, ConnectionError) as exc:
            raise LLMError("Lost connection to Ollama. Is `ollama serve` still running?") from exc
        except ollama.ResponseError as exc:
            if exc.status_code == 404:
                raise LLMError(f"Model `{model}` isn't installed. Run `ollama pull {model}`.") from exc
            raise LLMError(f"Ollama error: {exc.error}") from exc


def _has_model(models: list[str], name: str) -> bool:
    """Match `llama3.2` against `llama3.2:latest` as Ollama does."""
    candidates = {name, f"{name}:latest"}
    return any(m in candidates for m in models)


def trim_history(history: list[Message], max_turns: int, max_chars: int) -> list[Message]:
    """Keep the most recent user/assistant messages within the turn and character budgets."""
    recent = [m for m in history if m.get("role") in ("user", "assistant")][-max_turns * 2 :]
    kept: list[Message] = []
    total = 0
    for message in reversed(recent):
        total += len(message["content"])
        if total > max_chars:
            break
        kept.append(message)
    kept.reverse()
    # Never start the context with a dangling assistant reply.
    while kept and kept[0]["role"] == "assistant":
        kept.pop(0)
    return kept
