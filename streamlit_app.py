import streamlit as st
import requests
import json

OLLAMA_URL = "http://localhost:11434"
MODEL = "ornith:9b"

HERMES_SYSTEM = (
    "You are Hermes, a helpful, harmless, and honest AI assistant. "
    "Answer clearly and concisely."
)

st.set_page_config(page_title="Hermes — Ornith:9B", page_icon="🔮")
st.title("🔮 Hermes · Ornith:9B")
st.caption(f"Connected to local Ollama · model: `{MODEL}`")

if "messages" not in st.session_state:
    st.session_state.messages = []


def check_ollama():
    try:
        r = requests.get(f"{OLLAMA_URL}/api/tags", timeout=3)
        if r.ok:
            models = [m["name"] for m in r.json().get("models", [])]
            return True, models
    except Exception:
        pass
    return False, []


with st.sidebar:
    st.header("Connection")
    alive, available = check_ollama()
    if alive:
        st.success("Ollama is running")
        if any(MODEL in m for m in available):
            st.success(f"`{MODEL}` found")
        else:
            st.warning(f"`{MODEL}` not listed — ensure it's pulled")
            st.code(f"ollama pull {MODEL}")
        with st.expander("Available models"):
            st.write(available or "none")
    else:
        st.error("Ollama not reachable at localhost:11434")
        st.info("Start Ollama with: `ollama serve`")

    st.divider()
    st.subheader("Settings")
    temperature = st.slider("Temperature", 0.0, 2.0, 0.7, 0.05)
    max_tokens = st.number_input("Max tokens", 64, 4096, 1024, 64)
    system_prompt = st.text_area("System prompt", value=HERMES_SYSTEM, height=120)

    if st.button("Clear chat"):
        st.session_state.messages = []
        st.rerun()


for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])


def stream_response(messages, system, temp, max_tok):
    payload = {
        "model": MODEL,
        "messages": [{"role": "system", "content": system}] + messages,
        "stream": True,
        "options": {"temperature": temp, "num_predict": max_tok},
    }
    with requests.post(
        f"{OLLAMA_URL}/api/chat", json=payload, stream=True, timeout=120
    ) as resp:
        resp.raise_for_status()
        for line in resp.iter_lines():
            if line:
                chunk = json.loads(line)
                delta = chunk.get("message", {}).get("content", "")
                if delta:
                    yield delta
                if chunk.get("done"):
                    break


if prompt := st.chat_input("Message Hermes…"):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        placeholder = st.empty()
        full = ""
        try:
            for chunk in stream_response(
                st.session_state.messages, system_prompt, temperature, max_tokens
            ):
                full += chunk
                placeholder.markdown(full + "▌")
            placeholder.markdown(full)
        except requests.exceptions.ConnectionError:
            full = "⚠️ Cannot reach Ollama. Make sure `ollama serve` is running."
            placeholder.error(full)
        except Exception as e:
            full = f"⚠️ Error: {e}"
            placeholder.error(full)

    st.session_state.messages.append({"role": "assistant", "content": full})
