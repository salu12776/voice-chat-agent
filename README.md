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
