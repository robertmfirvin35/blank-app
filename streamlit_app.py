import streamlit as st
import streamlit.components.v1 as components
from openai import OpenAI
import time

st.set_page_config(page_title="Jarvis", page_icon="🤖", layout="wide")

JARVIS_SYSTEM = (
    "You are J.A.R.V.I.S. (Just A Rather Very Intelligent System), "
    "a highly sophisticated AI assistant. Speak in a refined, professional manner "
    "with subtle wit. Address the user respectfully and keep voice replies concise."
)

# ── Session state defaults ──────────────────────────────────────────────────
for key, default in {
    "messages": [],
    "voice_text": "",
    "speaking": False,
    "last_activity": time.time(),
}.items():
    if key not in st.session_state:
        st.session_state[key] = default

# ── Sidebar config ──────────────────────────────────────────────────────────
with st.sidebar:
    st.title("⚙️ Jarvis Config")
    api_key = st.text_input("Together AI Key", type="password",
                             help="Get a free key at together.ai")
    model = st.selectbox("Hermes Model", [
        "NousResearch/Hermes-3-Llama-3.1-8B-Turbo",
        "NousResearch/Hermes-3-Llama-3.1-70B-Turbo",
        "NousResearch/Hermes-2-Pro-Llama-3-8B",
    ])
    voice_enabled = st.toggle("Voice Output (TTS)", value=True)
    st.markdown("---")
    if st.button("🗑️ Clear conversation"):
        st.session_state.messages = []
        st.rerun()

# ── Voice bridge (STT + TTS via Web Speech API) ─────────────────────────────
# Uses a Streamlit component for bidirectional JS<->Python messaging.
VOICE_COMPONENT = """
<style>
  body { margin: 0; font-family: sans-serif; }
  #container { display: flex; gap: 10px; align-items: center; flex-wrap: wrap; }
  button {
    padding: 10px 18px; border: none; border-radius: 8px;
    cursor: pointer; font-size: 15px; transition: background 0.2s;
  }
  #start-btn { background: #1e90ff; color: #fff; }
  #start-btn:hover { background: #1278d4; }
  #start-btn.listening { background: #e74c3c; animation: pulse 1.2s infinite; }
  #stop-btn  { background: #555; color: #fff; }
  #stop-btn:hover { background: #333; }
  #status { font-size: 13px; color: #aaa; margin-top: 6px; width: 100%; }
  @keyframes pulse { 0%,100%{opacity:1} 50%{opacity:.5} }
</style>
<div id="container">
  <button id="start-btn" onclick="toggleListen()">🎤 Speak to Jarvis</button>
  <button id="stop-btn" onclick="stopSpeaking()">🔇 Mute Jarvis</button>
</div>
<div id="status">Ready.</div>

<script>
let recognition = null;
let isListening = false;

// ── Speech Recognition (STT) ───────────────────────────────────────────────
function toggleListen() {
  isListening ? stopListen() : startListen();
}

function startListen() {
  const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!SR) {
    setStatus("⚠️ Browser doesn't support speech recognition (try Chrome).");
    return;
  }
  recognition = new SR();
  recognition.lang = 'en-US';
  recognition.continuous = false;
  recognition.interimResults = false;

  recognition.onstart = () => {
    isListening = true;
    document.getElementById('start-btn').classList.add('listening');
    document.getElementById('start-btn').textContent = '⏹ Listening…';
    setStatus('Listening…');
  };

  recognition.onresult = (e) => {
    const text = e.results[0][0].transcript;
    setStatus('Heard: ' + text);
    // Send transcript to Streamlit
    window.parent.postMessage({type: 'streamlit:setComponentValue', value: text}, '*');
  };

  recognition.onerror = (e) => setStatus('Error: ' + e.error);

  recognition.onend = () => {
    isListening = false;
    document.getElementById('start-btn').classList.remove('listening');
    document.getElementById('start-btn').textContent = '🎤 Speak to Jarvis';
    if (document.getElementById('status').textContent === 'Listening…') {
      setStatus('Ready.');
    }
  };

  recognition.start();
}

function stopListen() {
  if (recognition) recognition.stop();
}

// ── Text-to-Speech (TTS) ───────────────────────────────────────────────────
function speak(text) {
  if (!window.speechSynthesis) return;
  window.speechSynthesis.cancel();
  const utt = new SpeechSynthesisUtterance(text);
  utt.rate = 0.95; utt.pitch = 0.85; utt.volume = 1.0;
  // Prefer a British/authoritative voice for Jarvis feel
  const voices = window.speechSynthesis.getVoices();
  const pick = voices.find(v =>
    /daniel|alex|google uk|en-gb/i.test(v.name + v.lang)
  );
  if (pick) utt.voice = pick;
  window.speechSynthesis.speak(utt);
}

function stopSpeaking() {
  if (window.speechSynthesis) window.speechSynthesis.cancel();
}

// ── Bridge: receive messages from Python (via st.components query param) ───
// Streamlit passes a "speak" payload via the component value mechanism.
window.addEventListener('message', (e) => {
  if (e.data && e.data.type === 'speak_response') {
    speak(e.data.text);
  }
});

// Streamlit component init handshake
window.addEventListener('message', (e) => {
  if (e.data && e.data.type === 'streamlit:render') {
    const args = e.data.args || {};
    if (args.speak) speak(args.speak);
  }
});

function setStatus(msg) {
  document.getElementById('status').textContent = msg;
}

// Keep-alive ping so Streamlit doesn't drop the WebSocket
setInterval(() => {
  window.parent.postMessage({type: 'streamlit:keepAlive'}, '*');
}, 25000);
</script>
"""

# ── Layout ──────────────────────────────────────────────────────────────────
st.markdown("## 🤖 J.A.R.V.I.S.")
st.caption(f"Powered by Hermes · {model.split('/')[-1]}")

# Render voice component
voice_val = components.html(VOICE_COMPONENT, height=90)

# ── Handle voice input ───────────────────────────────────────────────────────
# voice_val is the transcript string sent via postMessage
if voice_val and isinstance(voice_val, str) and voice_val.strip():
    st.session_state.voice_text = voice_val.strip()

# ── Chat input (text fallback) ───────────────────────────────────────────────
user_input = st.chat_input("Type a message or use the mic above…")
prompt = user_input or (st.session_state.pop("voice_text", "") if st.session_state.voice_text else None)

# ── Display conversation ─────────────────────────────────────────────────────
chat_area = st.container()
with chat_area:
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.write(msg["content"])

# ── Generate response ────────────────────────────────────────────────────────
if prompt:
    if not api_key:
        st.warning("Enter your Together AI key in the sidebar to activate Jarvis.")
        st.stop()

    st.session_state.messages.append({"role": "user", "content": prompt})
    with chat_area:
        with st.chat_message("user"):
            st.write(prompt)

    client = OpenAI(
        api_key=api_key,
        base_url="https://api.together.xyz/v1",
    )

    with chat_area:
        with st.chat_message("assistant"):
            placeholder = st.empty()
            full_reply = ""
            try:
                stream = client.chat.completions.create(
                    model=model,
                    messages=[
                        {"role": "system", "content": JARVIS_SYSTEM},
                        *st.session_state.messages,
                    ],
                    stream=True,
                    max_tokens=512,
                    temperature=0.7,
                )
                for chunk in stream:
                    delta = chunk.choices[0].delta.content or ""
                    full_reply += delta
                    placeholder.write(full_reply + "▌")
                placeholder.write(full_reply)
            except Exception as e:
                full_reply = f"⚠️ Error: {e}"
                placeholder.write(full_reply)

    st.session_state.messages.append({"role": "assistant", "content": full_reply})
    st.session_state.last_activity = time.time()

    # ── Trigger TTS via a fresh component render with speak payload ──────────
    if voice_enabled and full_reply and not full_reply.startswith("⚠️"):
        # Inject a one-shot TTS component; auto-height=0 keeps it invisible
        tts_js = f"""
        <script>
        (function() {{
          const text = {repr(full_reply)};
          function speak(t) {{
            if (!window.speechSynthesis) return;
            window.speechSynthesis.cancel();
            const utt = new SpeechSynthesisUtterance(t);
            utt.rate = 0.95; utt.pitch = 0.85;
            const voices = window.speechSynthesis.getVoices();
            const pick = voices.find(v => /daniel|alex|google uk|en-gb/i.test(v.name + v.lang));
            if (pick) utt.voice = pick;
            window.speechSynthesis.speak(utt);
          }}
          // Voices may not be loaded yet
          if (window.speechSynthesis.getVoices().length) {{ speak(text); }}
          else {{ window.speechSynthesis.onvoiceschanged = () => speak(text); }}
        }})();
        </script>
        """
        components.html(tts_js, height=0)
