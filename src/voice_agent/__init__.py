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
