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
