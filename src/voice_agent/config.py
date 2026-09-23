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
