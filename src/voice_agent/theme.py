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
