================================================
FILE: README.md
================================================
# Echo — a local voice agent

Talk to a local LLM in your browser. Everything runs on your machine:

| Step | Engine |
|---|---|
| Speech → text | [faster-whisper](https://github.com/SYSTRAN/faster-whisper) (`base.en`, CPU int8; uses CUDA automatically if available) |
| Thinking | [Ollama](https://ollama.com) (`llama3.2:3b` by default) |
| Text → speech | [Kokoro-82M](https://huggingface.co/hexgrad/Kokoro-82M) via [kokoro-onnx](https://github.com/thewh1teagle/kokoro-onnx) |
| UI | [Gradio](https://gradio.app) with a custom theme, light and dark mode |

## Setup

1. **Install uv**
   ```powershell
   # Windows
   powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
   ```
   ```bash
   # macOS / Linux
   curl -LsSf https://astral.sh/uv/install.sh | sh
   ```

2. **Install and start Ollama.** Download it from <https://ollama.com/download>. The desktop app starts the server automatically; otherwise run `ollama serve`.

3. **Pull the model**
   ```bash
   ollama pull llama3.2:3b
   ```

4. **Install dependencies**
   ```bash
   uv sync
   ```

5. **Run**
   ```bash
   uv run app.py
   ```
   Open <http://127.0.0.1:7860>.

On first run the app downloads the Whisper model (~150 MB, to the Hugging Face cache) and the Kokoro model and voices (~350 MB, to `models/`). Later starts are offline.

## Using it

- Click **Record**, speak, then click **Stop**. Your words are transcribed into the chat and the reply streams in. It's spoken **sentence by sentence while it's still being written**, so the voice starts after the first sentence instead of after the whole answer.
- Starting a new recording or pressing **Clear** interrupts the current reply. The full reply stays in the small player for replay.
- Or type in the text box and press **Enter**.
- **Settings** (collapsed at the bottom): model (any installed Ollama model), temperature, voice (54 Kokoro voices), auto-play.
- **Clear** resets the conversation. Memory lasts for the browser session and is capped (see `max_history_*` in `config.toml`).

## Configuration

Everything lives in [`config.toml`](config.toml): agent name, tagline and **system prompt**, the Ollama host and default model, the Whisper model size, the default voice and speed, and the server host and port. Restart the app after editing.

Set `VOICE_AGENT_CONFIG=path/to/other.toml` to use a different config file.

## Using it from a phone

Browsers only allow the microphone on `https://` or `localhost`. To use it from a phone:

- **Same Wi-Fi, typing only:** set `host = "0.0.0.0"` under `[server]` and open `http://<your-PC-ip>:7860`. Typing works, but the mic is blocked over plain http.
- **Mic on phone:** set `share = true` under `[server]` for a temporary public `https://*.gradio.live` link. Note that this exposes the app to anyone who has the link.

## Swapping the TTS engine

TTS lives behind the `TTSEngine` protocol in `src/voice_agent/tts.py` (`voices()` + `synthesize()`). A Piper fallback is included:

```bash
uv add piper-tts
# download a voice, e.g. en_US-lessac-medium.onnx + .onnx.json, into models/
```
then set `engine = "piper"` under `[tts]`. To add another engine, write a class with those two methods and register it in `create_tts()`.

## Project layout

```
app.py                     entry point
config.toml                settings and system prompt
src/voice_agent/
  config.py                typed config loader
  stt.py                   faster-whisper wrapper
  llm.py                   Ollama: health check, model list, streaming chat, history cap
  pipeline.py              runs LLM + TTS in parallel threads, yields text and per-sentence audio
  tts.py                   TTSEngine protocol, Kokoro/Piper engines, sentence splitter
  ui.py                    Gradio layout and event handlers
  theme.py                 theme, CSS, mic-permission helper, browser audio queue
```

## Troubleshooting

| Symptom | Fix |
|---|---|
| Orange banner "Can't reach Ollama" | Start Ollama (`ollama serve` or open the app), then click ↻ in Settings |
| "Model … isn't installed" | `ollama pull <model>` then ↻ |
| "Microphone access is blocked" | Allow the mic in the browser's site settings (lock icon), reload |
| "No microphone found" | Plug in or enable a mic; check Windows Settings → Privacy → Microphone |
| Slow replies / pauses between sentences | The LLM and TTS share the CPU. Try `gemma3:1b` in Settings, or `tiny.en` for `[stt] model` |
| No sound, but text appears | The browser blocked autoplay. Click anywhere on the page once, or use the replay player |
| Windows "symlinks" warning on first run | Harmless (Hugging Face cache); enable Developer Mode to silence it |
# voice-chat-agent



================================================
FILE: app.py
================================================
"""Entry point: `uv run app.py`."""

from voice_agent import main

if __name__ == "__main__":
    main()



================================================
FILE: config.toml
================================================
# Echo voice agent configuration.
# Edit values here; restart the app to apply.

[agent]
name = "Echo"
tagline = "Your private voice assistant — runs 100% on this computer."
system_prompt = """
You are Echo, a friendly and helpful voice assistant.
Your replies are spoken aloud, so:
- Keep answers short and conversational: usually one to three sentences.
- Never use markdown, bullet points, code blocks, emojis, or special symbols.
- Write numbers and abbreviations the way they should be spoken.
- If a question is unclear, ask a brief clarifying question.
Be warm, curious, and to the point.
"""

[llm]
host = "http://localhost:11434"
model = "llama3.2:3b"
temperature = 0.7
# Conversation memory: only the most recent turns are sent to the model.
max_history_turns = 10        # one turn = one user message + one reply
max_history_chars = 12000     # rough budget so long chats never overflow the context

[stt]
model = "base.en"             # tiny.en / base.en / small.en / small (multilingual)
device = "auto"               # auto / cpu / cuda
compute_type = "auto"         # auto picks int8 on CPU, float16 on GPU
language = "en"

[tts]
engine = "kokoro"             # kokoro / piper
voice = "af_heart"
speed = 1.0
autoplay = true
models_dir = "models"

[tts.kokoro]
# fp32 model: ~2.5x faster than the int8 one on older Intel CPUs (benchmarked on an i5-8350U).
model_url = "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/kokoro-v1.0.onnx"
voices_url = "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/voices-v1.0.bin"

[tts.piper]
# Only used when engine = "piper" (requires `uv add piper-tts`). Path is relative to models_dir.
voice_model = "en_US-lessac-medium.onnx"

[server]
host = "127.0.0.1"
port = 7860
share = false



================================================
FILE: pyproject.toml
================================================
[project]
name = "voice-agent"
version = "0.1.0"
description = "Add your description here"
readme = "README.md"
authors = [
    { name = "Muhammad Salman", email = "miansalman2412@gmail.com" }
]
requires-python = ">=3.13"
dependencies = [
    "faster-whisper>=1.2.1",
    "gradio>=6.28.0",
    "kokoro-onnx>=0.6.1",
    "numpy>=2.5.3",
    "ollama>=0.6.2",
    "soundfile>=0.14.0",
]

[project.scripts]
voice-agent = "voice_agent:main"

[build-system]
requires = ["uv_build>=0.12.17,<0.13.0"]
build-backend = "uv_build"



================================================
FILE: .python-version
================================================
3.13



================================================
FILE: src/voice_agent/__init__.py
================================================
"""Local voice agent: faster-whisper + Ollama + Kokoro, served with Gradio."""

from .config import load_config
from .theme import CSS, HEAD, build_theme
from .ui import VoiceAgentApp


def main() -> None:
    """Build and launch the web UI."""
    config = load_config()
    app = VoiceAgentApp(config)
    app.warm_up()
    demo = app.build()
    demo.queue().launch(
        server_name=config.server.host,
        server_port=config.server.port,
        share=config.server.share,
        theme=build_theme(),
        css=CSS,
        head=HEAD,
        inbrowser=False,
    )



================================================
FILE: src/voice_agent/config.py
================================================
"""Load the app configuration from config.toml into typed dataclasses."""

from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG_PATH = PROJECT_ROOT / "config.toml"


@dataclass
class AgentConfig:
    name: str = "Echo"
    tagline: str = "Your private voice assistant."
    system_prompt: str = "You are a helpful voice assistant. Keep replies short."


@dataclass
class LLMConfig:
    host: str = "http://localhost:11434"
    model: str = "llama3.2:3b"
    temperature: float = 0.7
    max_history_turns: int = 10
    max_history_chars: int = 12000


@dataclass
class STTConfig:
    model: str = "base.en"
    device: str = "auto"
    compute_type: str = "auto"
    language: str | None = "en"


@dataclass
class TTSConfig:
    engine: str = "kokoro"
    voice: str = "af_heart"
    speed: float = 1.0
    autoplay: bool = True
    models_dir: Path = PROJECT_ROOT / "models"
    kokoro: dict[str, str] = field(default_factory=dict)
    piper: dict[str, str] = field(default_factory=dict)


@dataclass
class ServerConfig:
    host: str = "127.0.0.1"
    port: int = 7860
    share: bool = False


@dataclass
class Config:
    agent: AgentConfig
    llm: LLMConfig
    stt: STTConfig
    tts: TTSConfig
    server: ServerConfig


def load_config(path: Path | str | None = None) -> Config:
    """Read config.toml (or VOICE_AGENT_CONFIG) and fill in defaults for missing keys."""
    path = Path(path or os.environ.get("VOICE_AGENT_CONFIG", DEFAULT_CONFIG_PATH))
    data = tomllib.loads(path.read_text(encoding="utf-8")) if path.exists() else {}

    agent = AgentConfig(**data.get("agent", {}))
    agent.system_prompt = agent.system_prompt.strip()

    tts_data = dict(data.get("tts", {}))
    models_dir = Path(tts_data.pop("models_dir", "models"))
    if not models_dir.is_absolute():
        models_dir = PROJECT_ROOT / models_dir

    return Config(
        agent=agent,
        llm=LLMConfig(**data.get("llm", {})),
        stt=STTConfig(**data.get("stt", {})),
        tts=TTSConfig(models_dir=models_dir, **tts_data),
        server=ServerConfig(**data.get("server", {})),
    )



================================================
FILE: src/voice_agent/llm.py
================================================
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



================================================
FILE: src/voice_agent/pipeline.py
================================================
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



================================================
FILE: src/voice_agent/stt.py
================================================
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



================================================
FILE: src/voice_agent/theme.py
================================================
"""Custom Gradio theme, CSS and browser-side helpers for the voice agent UI."""

from __future__ import annotations

import gradio as gr


def build_theme() -> gr.themes.Base:
    """Indigo/violet theme with Inter, soft surfaces and proper dark-mode colors."""
    return gr.themes.Base(
        primary_hue=gr.themes.colors.indigo,
        secondary_hue=gr.themes.colors.violet,
        neutral_hue=gr.themes.colors.slate,
        radius_size=gr.themes.sizes.radius_lg,
        spacing_size=gr.themes.sizes.spacing_lg,
        text_size=gr.themes.sizes.text_md,
        font=[gr.themes.GoogleFont("Inter"), "ui-sans-serif", "system-ui", "sans-serif"],
        font_mono=[gr.themes.GoogleFont("JetBrains Mono"), "ui-monospace", "monospace"],
    ).set(
        body_background_fill="#f6f7fb",
        body_background_fill_dark="#0b0d14",
        background_fill_primary="#ffffff",
        background_fill_primary_dark="#131722",
        background_fill_secondary="#f1f3f9",
        background_fill_secondary_dark="#1a1f2e",
        block_background_fill="#ffffff",
        block_background_fill_dark="#131722",
        block_border_color="#e6e8f0",
        block_border_color_dark="#252b3b",
        block_border_width="1px",
        block_shadow="0 1px 2px rgba(16, 24, 40, 0.04), 0 4px 16px rgba(16, 24, 40, 0.04)",
        block_shadow_dark="0 1px 2px rgba(0, 0, 0, 0.4)",
        block_label_background_fill="transparent",
        block_label_background_fill_dark="transparent",
        input_background_fill="#f6f7fb",
        input_background_fill_dark="#0f131c",
        input_border_color="#e1e4ee",
        input_border_color_dark="#2a3142",
        input_border_color_focus="*primary_400",
        input_border_color_focus_dark="*primary_500",
        button_primary_background_fill="linear-gradient(135deg, *primary_500, *secondary_500)",
        button_primary_background_fill_dark="linear-gradient(135deg, *primary_500, *secondary_600)",
        button_primary_background_fill_hover="linear-gradient(135deg, *primary_600, *secondary_600)",
        button_primary_background_fill_hover_dark="linear-gradient(135deg, *primary_400, *secondary_500)",
        button_primary_text_color="#ffffff",
        button_primary_text_color_dark="#ffffff",
        button_primary_border_color="transparent",
        button_primary_border_color_dark="transparent",
        button_secondary_background_fill="#ffffff",
        button_secondary_background_fill_dark="#1a1f2e",
        button_secondary_background_fill_hover="#f1f3f9",
        button_secondary_background_fill_hover_dark="#232a3b",
        slider_color="*primary_500",
        slider_color_dark="*primary_400",
        color_accent_soft="*primary_50",
        color_accent_soft_dark="rgba(99, 102, 241, 0.15)",
    )


CSS = """
:root {
  --va-user-bubble: linear-gradient(135deg, #6366f1, #8b5cf6);
  --va-bot-bubble: #ffffff;
  --va-bot-border: #e6e8f0;
  --va-muted: #64748b;
  --va-glow: rgba(99, 102, 241, 0.35);
}
.dark {
  --va-bot-bubble: #1a1f2e;
  --va-bot-border: #2a3142;
  --va-muted: #94a3b8;
  --va-glow: rgba(129, 140, 248, 0.35);
}

footer { display: none !important; }
.gradio-container { max-width: 880px !important; margin: 0 auto !important; padding: 12px 16px !important; }
#app { gap: 14px; }

/* ---------- Header ---------- */
#header { display: flex; align-items: center; gap: 14px; padding: 6px 2px 2px; }
#header .orb {
  width: 46px; height: 46px; border-radius: 50%; flex: none;
  background: radial-gradient(circle at 30% 30%, #a5b4fc, #6366f1 45%, #7c3aed);
  box-shadow: 0 6px 24px var(--va-glow);
  display: grid; place-items: center; color: white;
}
#header .orb svg { width: 22px; height: 22px; }
#header h1 { margin: 0; font-size: 1.45rem; font-weight: 700; letter-spacing: -0.02em; line-height: 1.2; }
#header p { margin: 2px 0 0; color: var(--va-muted); font-size: 0.92rem; }

/* ---------- Health banner ---------- */
.va-banner {
  display: flex; gap: 10px; align-items: flex-start;
  padding: 12px 14px; border-radius: 14px; font-size: 0.92rem; line-height: 1.45;
  background: #fff7ed; color: #9a3412; border: 1px solid #fed7aa;
}
.dark .va-banner { background: rgba(251, 146, 60, 0.1); color: #fdba74; border-color: rgba(251, 146, 60, 0.3); }
.va-banner code { background: rgba(0,0,0,0.06); padding: 1px 6px; border-radius: 6px; font-size: 0.88em; }
.dark .va-banner code { background: rgba(255,255,255,0.08); }

/* ---------- Chat ---------- */
#chat { border-radius: 20px !important; }
#chat .message-row .message, #chat .message { font-size: 0.98rem; line-height: 1.55; }
#chat .message-row.user-row .message, #chat .user .message-content, #chat .message.user {
  background: var(--va-user-bubble) !important; color: #fff !important; border: none !important;
  border-radius: 18px 18px 4px 18px !important;
}
#chat .message.user * { color: #fff !important; }
#chat .message-row.bot-row .message, #chat .message.bot {
  background: var(--va-bot-bubble) !important; border: 1px solid var(--va-bot-border) !important;
  border-radius: 18px 18px 18px 4px !important;
}
.va-empty { text-align: center; color: var(--va-muted); padding: 24px; }
.va-empty .big { font-size: 1.15rem; font-weight: 600; color: var(--body-text-color); margin-bottom: 6px; }
.va-empty .hints { display: flex; flex-wrap: wrap; gap: 8px; justify-content: center; margin-top: 14px; }
.va-empty .hints span {
  border: 1px solid var(--va-bot-border); background: var(--va-bot-bubble);
  border-radius: 999px; padding: 6px 12px; font-size: 0.85rem;
}

/* ---------- Status pill + reply player ---------- */
#status-row { align-items: center; gap: 12px; flex-wrap: nowrap; }
#status-row > * { min-width: 0; }
.va-status {
  display: inline-flex; align-items: center; gap: 8px; white-space: nowrap;
  padding: 7px 14px; border-radius: 999px; font-size: 0.86rem; font-weight: 500;
  background: var(--background-fill-secondary); color: var(--va-muted);
  border: 1px solid var(--va-bot-border);
}
.va-status .dot { width: 8px; height: 8px; border-radius: 50%; background: #94a3b8; }
.va-status[data-state="ready"] .dot { background: #22c55e; }
.va-status[data-state="listening"] { color: #dc2626; border-color: rgba(220,38,38,0.35); background: rgba(220,38,38,0.07); }
.va-status[data-state="listening"] .dot { background: #ef4444; animation: va-pulse 1s infinite; }
.va-status[data-state="transcribing"] .dot,
.va-status[data-state="thinking"] .dot { background: #6366f1; animation: va-pulse 0.9s infinite; }
.va-status[data-state="thinking"], .va-status[data-state="transcribing"] { color: #4f46e5; border-color: rgba(99,102,241,0.35); background: rgba(99,102,241,0.08); }
.dark .va-status[data-state="thinking"], .dark .va-status[data-state="transcribing"] { color: #a5b4fc; }
.va-status[data-state="speaking"] { color: #7c3aed; border-color: rgba(139,92,246,0.35); background: rgba(139,92,246,0.08); }
.dark .va-status[data-state="speaking"] { color: #c4b5fd; }
.va-status[data-state="speaking"] .dot { background: #8b5cf6; animation: va-pulse 0.6s infinite; }
.va-status[data-state="error"] { color: #b45309; border-color: rgba(245,158,11,0.4); background: rgba(245,158,11,0.08); white-space: normal; }
.dark .va-status[data-state="error"] { color: #fcd34d; }
.va-status[data-state="error"] .dot { background: #f59e0b; }
@keyframes va-pulse { 0%,100% { transform: scale(1); opacity: 1; } 50% { transform: scale(1.6); opacity: 0.5; } }

#reply-audio { min-width: 0 !important; }

/* ---------- Composer: big mic + text ---------- */
#composer { gap: 12px; align-items: stretch; }
#mic { min-width: 220px !important; border-radius: 20px !important; }
#mic .record-button, #mic .stop-button {
  height: 64px !important; width: 100% !important; min-width: 180px; justify-content: center !important;
  border-radius: 999px !important; font-size: 1.02rem !important; font-weight: 600 !important;
  padding: 0 22px !important; gap: 10px; cursor: pointer;
  transition: transform .12s ease, box-shadow .2s ease;
}
#mic .record-button {
  background: var(--va-user-bubble) !important; color: #fff !important; border: none !important;
  box-shadow: 0 8px 24px var(--va-glow);
}
#mic .record-button:hover { transform: translateY(-1px); box-shadow: 0 10px 28px var(--va-glow); }
#mic .record-button::before {
  content: "" !important; width: 22px !important; height: 22px !important; margin: 0 !important;
  border-radius: 0 !important; background: #fff !important;
  -webkit-mask: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24'%3E%3Cpath d='M12 14a3 3 0 0 0 3-3V5a3 3 0 0 0-6 0v6a3 3 0 0 0 3 3Zm5-3a5 5 0 0 1-10 0H5a7 7 0 0 0 6 6.92V21h2v-3.08A7 7 0 0 0 19 11h-2Z'/%3E%3C/svg%3E") center / contain no-repeat;
          mask: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24'%3E%3Cpath d='M12 14a3 3 0 0 0 3-3V5a3 3 0 0 0-6 0v6a3 3 0 0 0 3 3Zm5-3a5 5 0 0 1-10 0H5a7 7 0 0 0 6 6.92V21h2v-3.08A7 7 0 0 0 19 11h-2Z'/%3E%3C/svg%3E") center / contain no-repeat;
}
#mic .stop-button {
  background: #ef4444 !important; color: #fff !important; border: none !important;
  box-shadow: 0 0 0 6px rgba(239,68,68,0.18), 0 8px 24px rgba(239,68,68,0.35);
  animation: va-ring 1.4s infinite;
}
#mic .stop-button::before { background: #fff !important; border-radius: 3px !important; width: 14px !important; height: 14px !important; margin: 0 !important; }
@keyframes va-ring { 0%,100% { box-shadow: 0 0 0 4px rgba(239,68,68,0.2); } 50% { box-shadow: 0 0 0 12px rgba(239,68,68,0.06); } }
#mic .mic-select { max-width: 100%; }

#text-col { gap: 10px; }
#text-input textarea { font-size: 1rem !important; }
#send-btn { min-height: 44px; font-weight: 600; }
.va-hint { color: var(--va-muted); font-size: 0.82rem; text-align: center; }
.va-hint:empty { display: none; }
.va-hint.warn { color: #b45309; }
.dark .va-hint.warn { color: #fcd34d; }

#banner:not(:has(.va-banner)) { display: none !important; }
#clear-btn { flex: none; white-space: nowrap; border-radius: 999px !important; }
#settings { border-radius: 18px !important; }
#refresh-btn { max-width: 52px; min-width: 52px !important; align-self: end; }

/* ---------- Phones ---------- */
@media (max-width: 640px) {
  .gradio-container { padding: 8px 10px !important; }
  #header h1 { font-size: 1.2rem; }
  #header p { font-size: 0.82rem; }
  #header .orb { width: 38px; height: 38px; }
  #composer { flex-direction: column !important; }
  #mic { min-width: 0 !important; }
  /* Keep the mic on screen: shrink the chat instead of the composer. */
  #chat, #chat [style*="height"] { height: 44dvh !important; min-height: 240px !important; }
  #mic .controls { justify-content: center; }
  #mic .controls > * { flex: 1 1 100%; }
  #mic .record-button, #mic .stop-button { width: 100% !important; }
  #status-row { flex-wrap: wrap; }
}
"""

# Browser-side helper: explain microphone problems (insecure origin, permission denied).
HEAD = """
<script>
(() => {
  const show = (msg) => {
    const el = document.querySelector('#mic-hint');
    if (el) { el.textContent = msg; el.classList.add('warn'); }
  };
  const check = () => {
    if (!document.querySelector('#mic-hint')) return setTimeout(check, 300);
    if (!window.isSecureContext || !navigator.mediaDevices?.getUserMedia) {
      show('🎙️ The microphone only works on https:// or localhost. Type below, or open the app via localhost / a share link.');
      return;
    }
    navigator.permissions?.query({ name: 'microphone' }).then((p) => {
      const update = () => p.state === 'denied'
        && show('🎙️ Microphone access is blocked. Allow it in your browser\\'s site settings (lock icon in the address bar), then reload — or just type below.');
      update(); p.onchange = update;
    }).catch(() => {});
  };
  // Surface permission errors from any getUserMedia call Gradio makes.
  if (navigator.mediaDevices?.getUserMedia) {
    const orig = navigator.mediaDevices.getUserMedia.bind(navigator.mediaDevices);
    navigator.mediaDevices.getUserMedia = (c) => orig(c).catch((err) => {
      if (err?.name === 'NotAllowedError') show('🎙️ Microphone permission was denied. Allow it in your browser\\'s site settings and reload — or just type below.');
      else if (err?.name === 'NotFoundError') show('🎙️ No microphone found. Plug one in, or type below.');
      throw err;
    });
  }
  window.addEventListener('load', check);
})();

// Sentence-by-sentence playback. The server sends {turn, clips, final} with clips cumulative per turn;
// we play each new clip once, in order, and stop when a new turn starts, on Clear, or when recording.
window.vaAudio = (() => {
  let turn = null, clips = [], next = 0, final = false, player = null;

  const setReady = () => {
    const pill = document.querySelector('#status .va-status');
    if (!pill || pill.dataset.state !== 'speaking') return;
    pill.dataset.state = 'ready';
    pill.lastChild.textContent = 'Ready';
  };

  const playNext = () => {
    if (player) return;
    if (next >= clips.length) {
      if (final && clips.length) setReady();
      return;
    }
    player = new Audio(clips[next++]);
    const advance = () => { player = null; playNext(); };
    player.onended = advance;
    player.onerror = advance;
    player.play().catch((err) => {
      // Autoplay blocked (no prior click on the page): skip live playback; the replay player still works.
      player = null;
      if (err?.name === 'NotAllowedError') { next = clips.length; final = true; setReady(); }
      else playNext();
    });
  };

  const stop = () => {
    if (player) { player.onended = player.onerror = null; player.pause(); player = null; }
    turn = null; clips = []; next = 0; final = false;
  };

  const feed = (raw) => {
    if (!raw) return stop();
    let msg;
    try { msg = JSON.parse(raw); } catch { return; }
    if (msg.turn !== turn) { stop(); turn = msg.turn; }
    clips = msg.clips || [];
    final = !!msg.final;
    playNext();
  };

  return { feed, stop };
})();
</script>
"""



================================================
FILE: src/voice_agent/tts.py
================================================
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



================================================
FILE: src/voice_agent/ui.py
================================================
"""Gradio Blocks UI: layout and event wiring for the voice agent."""

from __future__ import annotations

import base64
import html
import io
import json
import threading
import uuid
from collections.abc import Iterator
from typing import Any

import gradio as gr
import numpy as np
import soundfile as sf

from .config import Config
from .llm import LLMError, Message, OllamaLLM
from .pipeline import stream_reply
from .stt import STTError, WhisperSTT
from .tts import Audio, TTSEngine, TTSError, create_tts

# Outputs shared by every conversation turn, in wiring order.
TURN_OUTPUTS = ("chat", "history", "status", "audio", "banner", "feed")

STATUS_LABELS = {
    "ready": "Ready",
    "listening": "Listening…",
    "transcribing": "Transcribing…",
    "thinking": "Thinking…",
    "speaking": "Speaking…",
    "error": "Something went wrong",
}

MIC_ICON = (
    '<svg viewBox="0 0 24 24" fill="currentColor"><path d="M12 14a3 3 0 0 0 3-3V5a3 3 0 0 0-6 0v6a3 3 0 0 0 3 '
    '3Zm5-3a5 5 0 0 1-10 0H5a7 7 0 0 0 6 6.92V21h2v-3.08A7 7 0 0 0 19 11h-2Z"/></svg>'
)

VOICE_GROUPS = {
    "af": "US English · female", "am": "US English · male",
    "bf": "UK English · female", "bm": "UK English · male",
    "ef": "Spanish · female", "em": "Spanish · male", "ff": "French · female",
    "hf": "Hindi · female", "hm": "Hindi · male", "if": "Italian · female", "im": "Italian · male",
    "jf": "Japanese · female", "jm": "Japanese · male", "pf": "Portuguese · female", "pm": "Portuguese · male",
    "zf": "Mandarin · female", "zm": "Mandarin · male",
}


def status_html(state: str, detail: str | None = None) -> str:
    """Render the status pill."""
    label = html.escape(detail or STATUS_LABELS[state])
    return f'<div class="va-status" data-state="{state}"><span class="dot"></span>{label}</div>'


def banner_html(message: str | None) -> str:
    """Render the warning banner (empty string hides it)."""
    if not message:
        return ""
    # Turn `code` spans into <code> for readability.
    parts = html.escape(message).split("`")
    body = "".join(f"<code>{p}</code>" if i % 2 else p for i, p in enumerate(parts))
    return f'<div class="va-banner"><span>⚠️</span><div>{body}</div></div>'


def voice_choices(voices: list[str]) -> list[tuple[str, str]]:
    """Friendly labels such as 'Heart — US English · female'."""
    return [
        (f"{v.split('_', 1)[-1].title()} — {VOICE_GROUPS.get(v[:2], v[:2])}", v) for v in voices
    ]


def to_int16(samples: np.ndarray) -> np.ndarray:
    return (np.clip(samples, -1.0, 1.0) * 32767).astype(np.int16)


def pack(**updates: Any) -> tuple[Any, ...]:
    """Order named updates as TURN_OUTPUTS; outputs not given are left unchanged."""
    return tuple(updates.get(name, gr.skip()) for name in TURN_OUTPUTS)


def wav_data_uri(audio: Audio, pad_seconds: float = 0.12) -> str:
    """Encode one sentence clip as a WAV data URI, with a short pause after it."""
    rate, samples = audio
    padded = np.concatenate([samples, np.zeros(int(rate * pad_seconds), dtype=samples.dtype)])
    buffer = io.BytesIO()
    sf.write(buffer, padded, rate, format="WAV", subtype="PCM_16")
    return "data:audio/wav;base64," + base64.b64encode(buffer.getvalue()).decode("ascii")


def feed_payload(turn: str, clips: list[str], final: bool) -> str:
    """Message for the browser audio queue (see theme.HEAD). Clips are cumulative so none can be missed."""
    return json.dumps({"turn": turn, "clips": clips, "final": final})


class VoiceAgentApp:
    """Owns the model wrappers and builds the Gradio interface."""

    def __init__(self, config: Config) -> None:
        self.config = config
        self.llm = OllamaLLM(config.llm)
        self.stt = WhisperSTT(config.stt)
        self.tts: TTSEngine = create_tts(config.tts)

    def warm_up(self) -> None:
        """Load the speech models in the background so the first turn is fast."""

        def _load() -> None:
            for name, loader in (("speech recognition", self.stt.load), ("text-to-speech", self.tts.voices)):
                try:
                    loader()
                    print(f"✓ {name} model ready")
                except Exception as exc:  # reported again, nicely, on first use
                    print(f"✗ {name} model failed to load: {exc}")

        threading.Thread(target=_load, daemon=True).start()

    # ---------- event handlers ----------

    def check_health(self, model: str | None) -> tuple[str, dict[str, Any]]:
        """Refresh the banner and model dropdown from Ollama."""
        health = self.llm.health(model or self.config.llm.model)
        choices = health.models or [model or self.config.llm.model]
        value = model if model in choices else (
            self.config.llm.model if self.config.llm.model in choices else choices[0]
        )
        if not health.ok and health.models and value != (model or self.config.llm.model):
            # Configured model missing but others exist: switch to one and say so.
            health = self.llm.health(value)
            msg = f"Model `{model or self.config.llm.model}` isn't installed, so I switched to `{value}`. " \
                  f"Run `ollama pull {self.config.llm.model}` to use it."
            return banner_html(msg), gr.Dropdown(choices=choices, value=value)
        return banner_html(None if health.ok else health.message), gr.Dropdown(choices=choices, value=value)

    def respond(
        self, user_text: str, history: list[Message], model: str, temperature: float, voice: str, autoplay: bool
    ) -> Iterator[tuple[Any, ...]]:
        """Stream the reply into the chat while speaking it sentence by sentence.

        Yields pack(...) tuples. With auto-play on, each finished sentence is sent to the browser audio
        queue right away; the complete reply also lands in the replay player at the end.
        """
        turn = uuid.uuid4().hex
        user_msg = {"role": "user", "content": user_text}
        chat = [*history, user_msg, {"role": "assistant", "content": ""}]
        # A new turn id makes the browser stop whatever is still playing from the previous reply.
        yield pack(
            chat=chat, history=history, status=status_html("thinking"), audio=None, feed=feed_payload(turn, [], False)
        )

        reply = ""
        clips: list[str] = []
        parts: list[Audio] = []
        tts_failed = False
        try:
            for kind, payload in stream_reply(
                self.llm, self.tts, history, user_text, self.config.agent.system_prompt,
                model=model, temperature=temperature, voice=voice,
            ):
                if kind == "text":
                    reply += payload
                    chat[-1] = {"role": "assistant", "content": reply}
                    yield pack(chat=chat)
                elif kind == "audio":
                    parts.append(payload)
                    if autoplay:
                        clips.append(wav_data_uri(payload))
                        yield pack(status=status_html("speaking"), feed=feed_payload(turn, clips, False))
                else:
                    tts_failed = True
                    gr.Warning(str(payload))
        except LLMError as exc:
            chat[-1] = {"role": "assistant", "content": f"⚠️ {exc}"}
            # The failed turn is shown but not stored, so it isn't sent to the model next time.
            yield pack(
                chat=chat, status=status_html("error", "Couldn't reach the model"),
                banner=banner_html(str(exc)), feed="",
            )
            return

        reply = reply.strip() or "Sorry, I don't have an answer for that."
        chat[-1] = {"role": "assistant", "content": reply}
        new_history = [*history, user_msg, {"role": "assistant", "content": reply}]

        if tts_failed:
            status: Any = status_html("error", "Voice unavailable — reply shown as text")
        elif autoplay and clips:
            status = gr.skip()  # still "Speaking…"; the browser flips it to Ready when playback ends
        else:
            status = status_html("ready")
        full_audio = None
        if parts:
            rate = parts[0][0]
            full_audio = gr.Audio(value=(rate, to_int16(np.concatenate([p[1] for p in parts]))), autoplay=False)
        yield pack(
            chat=chat, history=new_history, status=status, audio=full_audio,
            banner=banner_html(None), feed=feed_payload(turn, clips, True),
        )

    def voice_turn(
        self, audio_path: str | None, history: list[Message], model: str, temperature: float, voice: str, autoplay: bool
    ) -> Iterator[tuple[Any, ...]]:
        """Transcribe the recording, then respond. Yields respond()'s outputs plus the mic value."""
        if not audio_path:
            yield (*pack(status=status_html("ready")), None)
            return
        yield (*pack(chat=[*history, {"role": "user", "content": "🎙️ …"}], status=status_html("transcribing")), gr.skip())
        try:
            text = self.stt.transcribe(audio_path)
        except STTError as exc:
            gr.Warning(str(exc))
            yield (*pack(chat=history, status=status_html("error", "Couldn't transcribe that")), None)
            return
        if not text:
            yield (*pack(chat=history, status=status_html("error", "I didn't catch that — try again?")), None)
            return
        first = True
        for outputs in self.respond(text, history, model, temperature, voice, autoplay):
            yield (*outputs, None if first else gr.skip())
            first = False

    def text_turn(
        self, text: str, history: list[Message], model: str, temperature: float, voice: str, autoplay: bool
    ) -> Iterator[tuple[Any, ...]]:
        """Respond to typed input. Yields respond()'s outputs plus the textbox value."""
        text = (text or "").strip()
        if not text:
            yield (*pack(), gr.skip())
            return
        first = True
        for outputs in self.respond(text, history, model, temperature, voice, autoplay):
            yield (*outputs, "" if first else gr.skip())
            first = False

    # ---------- layout ----------

    def build(self) -> gr.Blocks:
        cfg = self.config
        try:
            voices = voice_choices(self.tts.voices())
        except TTSError as exc:
            print(f"TTS unavailable: {exc}")
            voices = [(cfg.tts.voice, cfg.tts.voice)]

        with gr.Blocks(title=f"{cfg.agent.name} · Voice Agent", fill_height=True) as demo:
            history = gr.State([])

            with gr.Column(elem_id="app"):
                gr.HTML(
                    f'<div id="header"><div class="orb">{MIC_ICON}</div><div>'
                    f"<h1>{html.escape(cfg.agent.name)}</h1><p>{html.escape(cfg.agent.tagline)}</p></div></div>"
                )
                banner = gr.HTML("", elem_id="banner")

                chatbot = gr.Chatbot(
                    elem_id="chat",
                    show_label=False,
                    layout="bubble",
                    height="calc(100dvh - 430px)",
                    min_height=320,
                    autoscroll=True,
                    placeholder=(
                        '<div class="va-empty"><div class="big">Hi, I\'m '
                        f"{html.escape(cfg.agent.name)} 👋</div>"
                        "Tap <b>Record</b> and talk to me, or type a message below."
                        '<div class="hints"><span>What can you do?</span><span>Tell me a fun fact</span>'
                        "<span>Help me plan my day</span></div></div>"
                    ),
                )

                with gr.Row(elem_id="status-row"):
                    status = gr.HTML(status_html("ready"), elem_id="status", scale=0, min_width=160)
                    reply_audio = gr.Audio(
                        elem_id="reply-audio",
                        show_label=False,
                        interactive=False,
                        autoplay=False,  # live playback is handled sentence by sentence in the browser
                        container=False,
                        scale=1,
                    )
                    clear_btn = gr.Button(
                        "🗑️ Clear", variant="secondary", size="sm", scale=0, min_width=90, elem_id="clear-btn"
                    )

                with gr.Row(elem_id="composer", equal_height=True):
                    mic = gr.Audio(
                        elem_id="mic",
                        sources=["microphone"],
                        type="filepath",
                        show_label=False,
                        scale=2,
                        waveform_options=gr.WaveformOptions(
                            waveform_color="#a5b4fc", waveform_progress_color="#6366f1", show_recording_waveform=True
                        ),
                    )
                    with gr.Column(elem_id="text-col", scale=3):
                        text_in = gr.Textbox(
                            elem_id="text-input",
                            placeholder="…or type a message and press Enter",
                            show_label=False,
                            lines=1,
                            max_lines=4,
                            autofocus=True,
                        )
                        send_btn = gr.Button("Send", variant="primary", elem_id="send-btn")
                gr.HTML('<div id="mic-hint" class="va-hint"></div>')
                # Carries sentence clips to the browser audio queue (window.vaAudio in theme.HEAD).
                tts_feed = gr.Textbox(visible="hidden", elem_id="tts-feed")

                with gr.Accordion("⚙️  Settings", open=False, elem_id="settings"):
                    with gr.Row():
                        model_dd = gr.Dropdown(
                            label="Model", choices=[cfg.llm.model], value=cfg.llm.model, scale=4,
                            info="Installed Ollama models",
                        )
                        refresh_btn = gr.Button("↻", elem_id="refresh-btn", scale=0, min_width=52)
                    temperature = gr.Slider(
                        0.0, 1.5, value=cfg.llm.temperature, step=0.05, label="Temperature",
                        info="Lower = focused, higher = creative",
                    )
                    voice_dd = gr.Dropdown(label="Voice", choices=voices, value=cfg.tts.voice)
                    autoplay = gr.Checkbox(label="Auto-play spoken replies", value=cfg.tts.autoplay)

            # ---------- wiring ----------
            settings = [history, model_dd, temperature, voice_dd, autoplay]
            common = dict(show_progress="hidden")

            demo.load(self.check_health, [model_dd], [banner, model_dd], **common)
            refresh_btn.click(self.check_health, [model_dd], [banner, model_dd], **common)

            turn_outputs = [chatbot, history, status, reply_audio, banner, tts_feed]
            stop_audio_js = "() => window.vaAudio?.stop()"

            tts_feed.change(None, tts_feed, None, js="(payload) => window.vaAudio?.feed(payload)")
            turns = [mic.stop_recording(self.voice_turn, [mic, *settings], [*turn_outputs, mic], **common)]
            for trigger in (text_in.submit, send_btn.click):
                turns.append(trigger(self.text_turn, [text_in, *settings], [*turn_outputs, text_in], **common))

            # Starting to talk interrupts the assistant (text and voice), so it never hears itself.
            mic.start_recording(
                lambda: status_html("listening"), None, status, js=stop_audio_js, cancels=turns, **common
            )
            clear_btn.click(
                lambda: ([], [], status_html("ready"), None, ""), None,
                [chatbot, history, status, reply_audio, tts_feed], js=stop_audio_js, cancels=turns, **common,
            )

        return demo


