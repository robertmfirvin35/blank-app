import json
import requests
import streamlit as st
from openai import OpenAI

# ── Page config ──────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="JARVIS",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Dark Jarvis-style CSS ─────────────────────────────────────────────────────
st.markdown("""
<style>
  body, .stApp { background-color: #0a0e1a; color: #c8d8e8; }
  .stChatMessage { background: #0d1526; border: 1px solid #1e3a5f; border-radius: 8px; }
  .stChatMessage [data-testid="stChatMessageContent"] { color: #c8d8e8; }
  .stTextInput > div > div > input { background: #0d1526; color: #c8d8e8; border: 1px solid #1e3a5f; }
  .stSelectbox > div > div { background: #0d1526; color: #c8d8e8; }
  section[data-testid="stSidebar"] { background: #060b14; border-right: 1px solid #1e3a5f; }
  .jarvis-header { text-align: center; color: #4db8ff; font-size: 2.4rem; font-weight: 700;
                   letter-spacing: 0.2em; text-shadow: 0 0 20px #4db8ff88; margin-bottom: 0.2rem; }
  .jarvis-sub { text-align: center; color: #2e6da4; font-size: 0.85rem; letter-spacing: 0.3em;
                margin-bottom: 1.5rem; }
  .tool-badge { background: #0d2540; border: 1px solid #1e5080; border-radius: 4px;
                padding: 2px 8px; font-size: 0.75rem; color: #4db8ff; display: inline-block;
                margin: 2px; }
  .stButton > button { background: #0d2540; color: #4db8ff; border: 1px solid #1e5080;
                       border-radius: 6px; }
  .stButton > button:hover { background: #1e3a5f; border-color: #4db8ff; }
</style>
""", unsafe_allow_html=True)

# ── Models ────────────────────────────────────────────────────────────────────
MODELS = {
    "Hermes 3 (Nous)": "nousresearch/hermes-3-llama-3.1-405b",
    "DeepSeek V3": "deepseek/deepseek-chat",
    "DeepSeek R1 (Reasoning)": "deepseek/deepseek-r1",
    "Hermes 2 Pro": "nousresearch/hermes-2-pro-llama-3-8b",
}

# ── Built-in tools ────────────────────────────────────────────────────────────
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": "Search the web for current information on any topic.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query"}
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "calculate",
            "description": "Evaluate a mathematical expression and return the result.",
            "parameters": {
                "type": "object",
                "properties": {
                    "expression": {"type": "string", "description": "Math expression, e.g. '2**10 + 5'"}
                },
                "required": ["expression"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": "Get current weather for a city.",
            "parameters": {
                "type": "object",
                "properties": {
                    "city": {"type": "string", "description": "City name, e.g. 'New York'"}
                },
                "required": ["city"],
            },
        },
    },
]


def run_tool(name: str, args: dict) -> str:
    if name == "calculate":
        try:
            result = eval(args["expression"], {"__builtins__": {}}, {})
            return f"Result: {result}"
        except Exception as e:
            return f"Error: {e}"

    if name == "web_search":
        try:
            resp = requests.get(
                "https://api.duckduckgo.com/",
                params={"q": args["query"], "format": "json", "no_html": 1, "skip_disambig": 1},
                timeout=8,
            )
            data = resp.json()
            abstract = data.get("AbstractText") or data.get("Answer") or ""
            related = [r["Text"] for r in data.get("RelatedTopics", [])[:3] if "Text" in r]
            if abstract:
                return abstract
            if related:
                return "\n".join(related)
            return "No direct results found. Try rephrasing your query."
        except Exception as e:
            return f"Search error: {e}"

    if name == "get_weather":
        try:
            resp = requests.get(
                f"https://wttr.in/{requests.utils.quote(args['city'])}?format=j1",
                timeout=8,
            )
            data = resp.json()
            cur = data["current_condition"][0]
            desc = cur["weatherDesc"][0]["value"]
            temp_c = cur["temp_C"]
            temp_f = cur["temp_F"]
            feels_c = cur["FeelsLikeC"]
            humidity = cur["humidity"]
            wind = cur["windspeedKmph"]
            return (
                f"{args['city']}: {desc}, {temp_c}°C / {temp_f}°F "
                f"(feels like {feels_c}°C), humidity {humidity}%, wind {wind} km/h"
            )
        except Exception as e:
            return f"Weather error: {e}"

    return f"Unknown tool: {name}"


def get_client(api_key: str) -> OpenAI:
    return OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=api_key,
    )


def chat(client: OpenAI, model_id: str, messages: list, use_tools: bool) -> str:
    kwargs = dict(model=model_id, messages=messages, temperature=0.7)
    if use_tools:
        kwargs["tools"] = TOOLS
        kwargs["tool_choice"] = "auto"

    response = client.chat.completions.create(**kwargs)
    msg = response.choices[0].message

    # Agentic tool loop
    while msg.tool_calls:
        tool_results = []
        tool_summary = []
        for tc in msg.tool_calls:
            args = json.loads(tc.function.arguments)
            result = run_tool(tc.function.name, args)
            tool_results.append({
                "role": "tool",
                "tool_call_id": tc.id,
                "content": result,
            })
            tool_summary.append(f"**[{tc.function.name}]** {result}")

        # Store tool activity in session for display
        st.session_state.last_tool_calls = tool_summary

        messages = messages + [msg] + tool_results
        response = client.chat.completions.create(**kwargs, messages=messages)
        msg = response.choices[0].message

    return msg.content or ""


# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### JARVIS CONFIG")
    api_key = st.text_input("OpenRouter API Key", type="password",
                            placeholder="sk-or-...",
                            help="Get a free key at openrouter.ai")
    model_name = st.selectbox("Model", list(MODELS.keys()))
    use_tools = st.toggle("Enable Tools", value=True)
    if use_tools:
        st.markdown("**Active tools:**")
        for t in TOOLS:
            st.markdown(f'<span class="tool-badge">⚡ {t["function"]["name"]}</span>',
                        unsafe_allow_html=True)
    st.divider()
    system_prompt = st.text_area(
        "System Prompt",
        value=(
            "You are JARVIS, an advanced AI assistant. You are precise, helpful, "
            "and slightly witty. You have access to tools for searching the web, "
            "doing math, and checking weather. Use them proactively when relevant."
        ),
        height=140,
    )
    if st.button("Clear conversation"):
        st.session_state.messages = []
        st.session_state.last_tool_calls = []
        st.rerun()

# ── Main UI ───────────────────────────────────────────────────────────────────
st.markdown('<div class="jarvis-header">J.A.R.V.I.S</div>', unsafe_allow_html=True)
st.markdown('<div class="jarvis-sub">JUST A RATHER VERY INTELLIGENT SYSTEM</div>', unsafe_allow_html=True)

if "messages" not in st.session_state:
    st.session_state.messages = []
if "last_tool_calls" not in st.session_state:
    st.session_state.last_tool_calls = []

# Render chat history
for m in st.session_state.messages:
    role = m["role"]
    if role in ("user", "assistant"):
        with st.chat_message(role):
            st.markdown(m["content"])

# Input
prompt = st.chat_input("What do you need, sir?")

if prompt:
    if not api_key:
        st.error("Please enter your OpenRouter API key in the sidebar.")
        st.stop()

    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    model_id = MODELS[model_name]
    full_messages = [{"role": "system", "content": system_prompt}] + st.session_state.messages

    with st.chat_message("assistant"):
        with st.spinner("Processing..."):
            try:
                client = get_client(api_key)
                reply = chat(client, model_id, full_messages, use_tools)

                if st.session_state.last_tool_calls:
                    with st.expander("Tools used", expanded=False):
                        for tc in st.session_state.last_tool_calls:
                            st.markdown(tc)
                    st.session_state.last_tool_calls = []

                st.markdown(reply)
                st.session_state.messages.append({"role": "assistant", "content": reply})
            except Exception as e:
                st.error(f"Error: {e}")
