"""Load the app configuration from config.toml into typed dataclasses."""

from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG_PATH = PROJECT_ROOT / "config.toml"

# Online hosts set these variables (Render: RENDER, Hugging Face: SPACE_ID).
# When one is present, the app switches to its lightweight online-demo setup.
ON_CLOUD = bool(os.environ.get("RENDER") or os.environ.get("SPACE_ID"))


@dataclass
class AgentConfig:
    name: str = "Echo"
    tagline: str = "Your private voice assistant."
    system_prompt: str = "You are a helpful voice assistant. Keep replies short."


@dataclass
class LLMConfig:
    provider: str = "ollama"  # "ollama" (local) or "groq" (online demo)
    host: str = "http://localhost:11434"
    model: str = "llama3.2:3b"
    temperature: float = 0.7
    max_history_turns: int = 10
    max_history_chars: int = 12000


@dataclass
class STTConfig:
    engine: str = "whisper"  # "whisper" (local faster-whisper) or "groq" (online demo)
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
    """Read config.toml (or VOICE_AGENT_CONFIG), fill in defaults, then apply environment overrides."""
    path = Path(path or os.environ.get("VOICE_AGENT_CONFIG", DEFAULT_CONFIG_PATH))
    data = tomllib.loads(path.read_text(encoding="utf-8")) if path.exists() else {}

    agent = AgentConfig(**data.get("agent", {}))
    agent.system_prompt = agent.system_prompt.strip()

    tts_data = dict(data.get("tts", {}))
    models_dir = Path(tts_data.pop("models_dir", "models"))
    if not models_dir.is_absolute():
        models_dir = PROJECT_ROOT / models_dir

    llm_data = dict(data.get("llm", {}))
    stt_data = dict(data.get("stt", {}))
    server_data = dict(data.get("server", {}))

    if ON_CLOUD:
        # Online demo: no local models (a free server has too little memory), so speech-to-text and
        # the reply come from Groq and the voice from edge-tts. The local app is unchanged.
        llm_data["provider"] = "groq"
        llm_data["model"] = "llama-3.1-8b-instant"
        stt_data["engine"] = "groq"
        tts_data["engine"] = "edge"
        tts_data["voice"] = "en-US-AvaNeural"
        server_data.update(host="0.0.0.0", port=int(os.environ.get("PORT", 7860)), share=False)
        agent.tagline = "Online demo. The full version runs 100% on my laptop with Whisper, Llama 3.2 and Kokoro."

    # Explicit environment variables always win.
    if os.environ.get("LLM_PROVIDER"):
        llm_data["provider"] = os.environ["LLM_PROVIDER"]
    if os.environ.get("LLM_MODEL"):
        llm_data["model"] = os.environ["LLM_MODEL"]

    return Config(
        agent=agent,
        llm=LLMConfig(**llm_data),
        stt=STTConfig(**stt_data),
        tts=TTSConfig(models_dir=models_dir, **tts_data),
        server=ServerConfig(**server_data),
    )
