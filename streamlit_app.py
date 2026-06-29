import streamlit as st
import streamlit.components.v1 as components
import time
import json

# Safe import — app renders even if openai failed to install
try:
    from openai import OpenAI
    _OPENAI_OK = True
except Exception as _openai_err:
    _OPENAI_OK = False
    _OPENAI_ERR = str(_openai_err)

st.set_page_config(page_title="Jarvis", page_icon="🤖", layout="wide")

JARVIS_SYSTEM = (
    "You are J.A.R.V.I.S. (Just A Rather Very Intelligent System), "
    "a highly sophisticated AI assistant. Speak in a refined, professional manner "
    "with subtle wit. Address the user respectfully and keep voice replies concise."
)

# ── Session state ────────────────────────────────────────────────────────────
for key, default in {
    "messages": [],
    "voice_text": "",
    "last_activity": time.time(),
}.items():
    if key not in st.session_state:
        st.session_state[key] = default

# ── Sidebar ──────────────────────────────────────────────────────────────────
with st.sidebar:
    st.title("⚙️ Jarvis Config")
    api_key = st.text_input(
        "Together AI Key", type="password",
        help="Free key at together.ai — used to call Hermes"
    )
    model = st.selectbox("Hermes Model", [
        "NousResearch/Hermes-3-Llama-3.1-8B-Turbo",
        "NousResearch/Hermes-3-Llama-3.1-70B-Turbo",
        "NousResearch/Hermes-2-Pro-Llama-3-8B",
    ])
    voice_on = st.toggle("Voice output (TTS)", value=True)
    st.markdown("---")
    if st.button("🗑️ Clear conversation"):
        st.session_state.messages = []
        st.rerun()

    if not _OPENAI_OK:
        st.error(f"openai package failed to load:\n{_OPENAI_ERR}")

# ── Header ───────────────────────────────────────────────────────────────────
st.markdown("## 🤖 J.A.R.V.I.S.")
st.caption("Powered by Hermes via Together AI")

# ── Voice bridge ─────────────────────────────────────────────────────────────
VOICE_HTML = """
<style>
  body{margin:0;font-family:sans-serif}
  #wrap{display:flex;gap:10px;align-items:center;flex-wrap:wrap}
  button{padding:10px 18px;border:none;border-radius:8px;cursor:pointer;font-size:15px}
  #btn-mic{background:#1e90ff;color:#fff}
  #btn-mic.on{background:#e74c3c;animation:pulse 1.2s infinite}
  #btn-mute{background:#555;color:#fff}
  #status{font-size:13px;color:#999;margin-top:6px;width:100%}
  @keyframes pulse{0%,100%{opacity:1}50%{opacity:.5}}
</style>
<div id="wrap">
  <button id="btn-mic"  onclick="toggleMic()">🎤 Speak to Jarvis</button>
  <button id="btn-mute" onclick="mute()">🔇 Mute</button>
</div>
<div id="status">Ready.</div>

<script>
var rec=null, going=false;

function toggleMic(){ going ? stopMic() : startMic(); }

function startMic(){
  var SR=window.SpeechRecognition||window.webkitSpeechRecognition;
  if(!SR){setStatus('⚠️ Use Chrome for voice input.');return;}
  rec=new SR();
  rec.lang='en-US'; rec.continuous=false; rec.interimResults=false;
  rec.onstart=function(){
    going=true;
    document.getElementById('btn-mic').classList.add('on');
    document.getElementById('btn-mic').textContent='⏹ Listening…';
    setStatus('Listening…');
  };
  rec.onresult=function(e){
    var t=e.results[0][0].transcript;
    setStatus('Heard: '+t);
    window.parent.postMessage({type:'streamlit:setComponentValue',value:t},'*');
  };
  rec.onerror=function(e){setStatus('Error: '+e.error);};
  rec.onend=function(){
    going=false;
    document.getElementById('btn-mic').classList.remove('on');
    document.getElementById('btn-mic').textContent='🎤 Speak to Jarvis';
    if(document.getElementById('status').textContent==='Listening…')setStatus('Ready.');
  };
  rec.start();
}

function stopMic(){ if(rec)rec.stop(); }
function mute(){ if(window.speechSynthesis)window.speechSynthesis.cancel(); }

function speak(text){
  if(!window.speechSynthesis)return;
  window.speechSynthesis.cancel();
  var u=new SpeechSynthesisUtterance(text);
  u.rate=0.95; u.pitch=0.85; u.volume=1;
  var vs=window.speechSynthesis.getVoices();
  var v=vs.find(function(x){return /daniel|alex|google uk|en-gb/i.test(x.name+x.lang);});
  if(v)u.voice=v;
  window.speechSynthesis.speak(u);
}

window.addEventListener('message',function(e){
  if(e.data&&e.data.type==='streamlit:render'&&e.data.args&&e.data.args.speak){
    speak(e.data.args.speak);
  }
});

function setStatus(m){document.getElementById('status').textContent=m;}

// Keep-alive so the WebSocket doesn't time out
setInterval(function(){
  window.parent.postMessage({type:'streamlit:keepAlive'},'*');
},20000);
</script>
"""

voice_val = components.html(VOICE_HTML, height=90)

if voice_val and isinstance(voice_val, str) and voice_val.strip():
    st.session_state.voice_text = voice_val.strip()

# ── Chat input ────────────────────────────────────────────────────────────────
typed = st.chat_input("Type a message or use the mic above…")
prompt = typed or (st.session_state.voice_text if st.session_state.voice_text else None)
if prompt:
    st.session_state.voice_text = ""

# ── Conversation display ──────────────────────────────────────────────────────
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.write(msg["content"])

# ── Generate response ─────────────────────────────────────────────────────────
if prompt:
    if not api_key:
        st.warning("⚠️ Enter your Together AI key in the sidebar to activate Jarvis.")
        st.stop()

    if not _OPENAI_OK:
        st.error("The openai package didn't load — check the sidebar for details.")
        st.stop()

    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.write(prompt)

    client = OpenAI(api_key=api_key, base_url="https://api.together.xyz/v1")

    with st.chat_message("assistant"):
        box = st.empty()
        reply = ""
        try:
            stream = client.chat.completions.create(
                model=model,
                messages=[{"role": "system", "content": JARVIS_SYSTEM},
                          *st.session_state.messages],
                stream=True,
                max_tokens=512,
                temperature=0.7,
            )
            for chunk in stream:
                delta = chunk.choices[0].delta.content or ""
                reply += delta
                box.write(reply + "▌")
            box.write(reply)
        except Exception as exc:
            reply = f"⚠️ {exc}"
            box.error(reply)

    st.session_state.messages.append({"role": "assistant", "content": reply})
    st.session_state.last_activity = time.time()

    if voice_on and reply and not reply.startswith("⚠️"):
        tts = f"""<script>
(function(){{
  var text={json.dumps(reply)};
  function go(){{
    var u=new SpeechSynthesisUtterance(text);
    u.rate=0.95;u.pitch=0.85;
    var vs=window.speechSynthesis.getVoices();
    var v=vs.find(function(x){{return /daniel|alex|google uk|en-gb/i.test(x.name+x.lang);}});
    if(v)u.voice=v;
    window.speechSynthesis.speak(u);
  }}
  if(window.speechSynthesis.getVoices().length)go();
  else window.speechSynthesis.onvoiceschanged=go;
}})();
</script>"""
        components.html(tts, height=0)
