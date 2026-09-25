"""LLM clients: Ollama (local) and Groq (hosted), with the same small interface."""

from __future__ import annotations

import json
import os
from collections.abc import Iterator
from dataclasses import dataclass

import httpx
import ollama

from .config import LLMConfig

Message = dict[str, str]


class LLMError(RuntimeError):
    """A user-facing problem talking to the language model."""


@dataclass
class HealthStatus:
    ok: bool
    message: str
    models: list[str]


def build_messages(history: list[Message], user_text: str, system_prompt: str, config: LLMConfig) -> list[Message]:
    messages = [{"role": "system", "content": system_prompt}]
    messages += trim_history(history, config.max_history_turns, config.max_history_chars)
    messages.append({"role": "user", "content": user_text})
    return messages


class OllamaLLM:
    """Thin wrapper around the official `ollama` client (runs on your own computer)."""

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
        messages = build_messages(history, user_text, system_prompt, self.config)
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


class GroqLLM:
    """Hosted model on Groq (OpenAI-compatible API). Used for the public online demo.

    The API key is read from the GROQ_API_KEY environment variable (a Space secret), never from code.
    Only the configured model is exposed, so visitors can't switch to other (paid or larger) models.
    """

    BASE_URL = "https://api.groq.com/openai/v1"
    MAX_TOKENS = 300  # voice replies are short; also keeps usage low

    def __init__(self, config: LLMConfig) -> None:
        self.config = config
        self.api_key = os.environ.get("GROQ_API_KEY", "").strip()
        self.client = httpx.Client(
            base_url=self.BASE_URL,
            timeout=httpx.Timeout(20.0, read=60.0),
            headers={"Authorization": f"Bearer {self.api_key}"},
        )

    def list_models(self) -> list[str]:
        return [self.config.model]

    def health(self, model: str | None = None) -> HealthStatus:
        if not self.api_key:
            return HealthStatus(False, "GROQ_API_KEY is missing. Add it as a secret in the Space settings.", [])
        return HealthStatus(True, f"Online demo · {self.config.model} on Groq", [self.config.model])

    def stream_chat(
        self,
        history: list[Message],
        user_text: str,
        system_prompt: str,
        model: str | None = None,
        temperature: float | None = None,
    ) -> Iterator[str]:
        if not self.api_key:
            raise LLMError("The online demo isn't configured yet (missing API key).")
        payload = {
            "model": self.config.model,
            "messages": build_messages(history, user_text, system_prompt, self.config),
            "stream": True,
            "temperature": self.config.temperature if temperature is None else temperature,
            "max_tokens": self.MAX_TOKENS,
        }
        try:
            with self.client.stream("POST", "/chat/completions", json=payload) as response:
                if response.status_code == 429:
                    raise LLMError("Lots of people are talking to me right now. Please try again in a few seconds.")
                if response.status_code >= 400:
                    response.read()
                    print(f"Groq error {response.status_code}: {response.text[:300]}")  # visible in Space logs
                    raise LLMError("The language model returned an error. Please try again.")
                for line in response.iter_lines():
                    if not line.startswith("data:"):
                        continue
                    data = line[5:].strip()
                    if data == "[DONE]":
                        break
                    try:
                        delta = json.loads(data)["choices"][0].get("delta", {}).get("content")
                    except (ValueError, KeyError, IndexError):
                        continue
                    if delta:
                        yield delta
        except httpx.HTTPError as exc:
            print(f"Groq connection error: {exc}")
            raise LLMError("Couldn't reach the language model. Please try again in a moment.") from exc


def create_llm(config: LLMConfig):
    """Pick the client from config.llm.provider: "ollama" (local) or "groq" (online demo)."""
    if config.provider == "groq":
        return GroqLLM(config)
    return OllamaLLM(config)


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
