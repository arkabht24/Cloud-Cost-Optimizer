import streamlit as st

from azure.resource_fetcher import build_subscription_set_command, get_active_subscription, run_azure_cli
from rag.api_client import request_analysis

st.set_page_config(page_title="Azure Cost Insight", page_icon="💼", layout="wide")

st.markdown(
    """
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Merriweather:wght@700;800&family=Inter:wght@400;500;600;700&display=swap');

        html, body, [class*="css"] {
            font-family: 'Inter', sans-serif;
        }

        .stApp {
            background: #fdf3ea;
        }

        /* ---- Top header: solid, premium, thin accent line ---- */
        [data-testid="stHeader"] {
            background: #141414 !important;
            border-bottom: 3px solid #d04a02 !important;
        }
        [data-testid="stHeader"] * {
            color: #f5f0ec !important;
        }
        [data-testid="stToolbar"] button svg {
            fill: #f5f0ec !important;
        }
        [data-testid="stStatusWidget"] {
            color: #f5f0ec !important;
        }

        /* ---- Sidebar: light, black text ---- */
        [data-testid="stSidebar"] {
            background: #fffaf5;
            border-right: 1px solid #ecdfd3;
        }
        [data-testid="stSidebar"] * {
            color: #141414 !important;
        }
        [data-testid="stSidebar"] .stCaption {
            color: #6b6259 !important;
        }
        [data-testid="stSidebar"] h1 {
            font-family: 'Merriweather', serif !important;
            font-size: 1.9rem !important;
            margin-bottom: 0.1rem !important;
        }
        [data-testid="stSidebarUserContent"] {
            padding-top: 1.5rem;
        }

        /* ---- Buttons ---- */
        .stButton > button {
            background: #ffffff;
            color: #141414;
            border: 1.5px solid #d04a02;
            border-radius: 8px;
            font-weight: 600;
            transition: all 0.15s ease;
        }
        .stButton > button:hover {
            background: #d04a02;
            color: #ffffff;
            border-color: #d04a02;
            box-shadow: 0 3px 10px rgba(208, 74, 2, 0.3);
        }
        [data-testid="stSidebar"] .stButton > button:hover {
            color: #ffffff !important;
        }

        /* ---- Inputs ---- */
        .stTextInput > div > div > input {
            border: 1px solid #d8cabb;
            border-radius: 8px;
            background: #ffffff;
            color: #141414 !important;
        }
        .stTextInput > div > div > input:focus {
            border-color: #d04a02;
            box-shadow: 0 0 0 1px #d04a02;
        }
        .stTextInput label p {
            color: #141414 !important;
            font-weight: 600 !important;
        }

        /* ---- Status/alert boxes ---- */
        div[data-testid="stAlertContainer"] {
            background: #ffffff !important;
            border: 1px solid #ecdfd3 !important;
            border-radius: 8px !important;
        }
        div[data-testid="stAlertContainer"] p {
            color: #141414 !important;
        }
        .stSuccess { border-left: 4px solid #2f7d4f !important; }
        .stWarning { border-left: 4px solid #d04a02 !important; }
        .stInfo { border-left: 4px solid #2b5f8a !important; }
        .stError { border-left: 4px solid #b3261e !important; }

        .block-container {
            padding-top: 2.5rem;
            max-width: 1100px;
        }
        h1 {
            font-family: 'Merriweather', serif !important;
            font-weight: 800 !important;
            letter-spacing: -0.02em !important;
            color: #141414 !important;
        }
        [data-testid="stMain"] h1 {
            font-size: 2.6rem !important;
        }
        h2, h3 {
            color: #141414 !important;
            font-weight: 700 !important;
        }
        [data-testid="stMain"] {
            background: #fdf3ea;
        }

        hr {
            border-color: #ecdfd3 !important;
        }

        /* ---- Status chips (subscription / resource group) ---- */
        .status-chip {
            display: flex;
            align-items: center;
            gap: 10px;
            background: #ffffff;
            border: 1px solid #ecdfd3;
            border-radius: 8px;
            padding: 10px 14px;
            margin-bottom: 10px;
        }
        .status-chip .dot {
            width: 9px;
            height: 9px;
            border-radius: 50%;
            flex-shrink: 0;
        }
        .status-chip.active .dot {
            background: #2f7d4f;
            box-shadow: 0 0 0 3px rgba(47, 125, 79, 0.15);
        }
        .status-chip.inactive .dot {
            background: #b8ada0;
        }
        .status-chip .chip-text {
            display: flex;
            flex-direction: column;
            line-height: 1.25;
        }
        .status-chip .chip-label {
            font-size: 0.72rem;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.04em;
            color: #8a8074;
        }
        .status-chip .chip-value {
            font-family: 'Courier New', monospace;
            font-size: 0.9rem;
            font-weight: 600;
            color: #141414;
        }

        /* ---- Chat message cards ---- */
        [data-testid="stChatMessage"] {
            background: #ffffff !important;
            border: 1px solid #ecdfd3;
            border-radius: 14px;
            padding: 4px 6px;
            margin-bottom: 14px;
            box-shadow: 0 2px 8px rgba(20, 20, 20, 0.05);
        }
        [data-testid="stChatMessage"] p,
        [data-testid="stChatMessage"] li {
            color: #141414 !important;
        }
        [data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarUser"]) {
            background: #fff3ea !important;
            border-color: #f3d3b8;
        }
        [data-testid="stChatMessageAvatarUser"] {
            background: #141414 !important;
        }
        [data-testid="stChatMessageAvatarAssistant"] {
            background: #d04a02 !important;
        }

        /* ---- Bottom chat input bar ---- */
        [data-testid="stBottom"] > div {
            background: linear-gradient(90deg, #d04a02 0%, #f2801f 100%) !important;
            border-top: none !important;
            padding-top: 0.6rem !important;
            padding-bottom: 0.6rem !important;
        }
        [data-testid="stChatInput"] {
            background: #ffffff !important;
            border: none !important;
            border-radius: 14px !important;
            box-shadow: 0 4px 14px rgba(0, 0, 0, 0.18);
        }
        [data-testid="stChatInput"] textarea {
            background: #ffffff !important;
            color: #141414 !important;
        }
        [data-testid="stChatInput"] textarea::placeholder {
            color: #8a8074 !important;
        }
        [data-testid="stChatInput"] > div {
            background: #ffffff !important;
        }
        [data-testid="stChatInputSubmitButton"] {
            background: #141414 !important;
            border-radius: 10px !important;
        }
        [data-testid="stChatInputSubmitButton"] svg {
            fill: #ffffff !important;
        }
        [data-testid="stChatInputSubmitButton"]:hover {
            background: #d04a02 !important;
        }
    </style>
    """,
    unsafe_allow_html=True,
)


def mask_value(value: str, full: bool = False) -> str:
    """Mask a sensitive value. full=True hides it completely; otherwise keeps a few edge chars."""
    if not value:
        return ""
    if full:
        return "•" * 12
    if len(value) <= 8:
        return "•" * len(value)
    return f"{value[:4]}{'•' * 8}{value[-4:]}"


def status_chip(label: str, value: str = "", active: bool = True) -> None:
    """Render a small dynamic status card instead of a raw success/info box."""
    state_class = "active" if active else "inactive"
    display_value = f'<span class="chip-value">{value}</span>' if value else ""
    st.markdown(
        f"""
        <div class="status-chip {state_class}">
            <div class="dot"></div>
            <div class="chip-text">
                <span class="chip-label">{label}</span>
                {display_value}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

# ---------- Session state ----------
if "messages" not in st.session_state:
    st.session_state.messages = []
if "resource_group" not in st.session_state:
    st.session_state.resource_group = ""
if "subscription" not in st.session_state:
    st.session_state.subscription = get_active_subscription()

# ---------- Sidebar: config ----------
with st.sidebar:
    st.title("Azure Cost Insight")
    st.caption("Cost intelligence workspace")

    subscription_input = st.text_input(
        "Azure Subscription ID",
        value=st.session_state.subscription,
        placeholder="Enter subscription ID",
        type="password",
    )

    if st.button("Use this subscription", use_container_width=True):
        selected_subscription = subscription_input.strip()
        if not selected_subscription:
            st.warning("Please enter a subscription ID.")
        else:
            try:
                run_azure_cli(build_subscription_set_command(selected_subscription))
                st.session_state.subscription = selected_subscription
                status_chip("Subscription updated", mask_value(selected_subscription, full=True), active=True)
            except Exception as exc:
                st.error(f"Unable to set subscription: {exc}")

    rg_input = st.text_input(
        "Azure Resource Group",
        value=st.session_state.resource_group,
        placeholder="e.g. my-resource-group (or demo-cost-lab)",
    )
    st.caption("Use `demo-cost-lab` to explore with local sample resources; no Azure subscription is needed.")

    if st.button("Set Resource Group", use_container_width=True):
        st.session_state.resource_group = rg_input.strip()

    if st.session_state.resource_group:
        status_chip("Resource group", st.session_state.resource_group, active=True)
    else:
        status_chip("Resource group", "Not set", active=False)

    if st.session_state.subscription:
        status_chip("Active subscription", mask_value(st.session_state.subscription, full=True), active=True)
    else:
        status_chip("Active subscription", "Not set", active=False)

    st.divider()
    if st.button("Clear chat", use_container_width=True):
        st.session_state.messages = []
        st.rerun()

# ---------- Main chat area ----------
st.header("💬 Ask about your Azure costs")

if not st.session_state.resource_group:
    st.info("Set your Azure Resource Group in the sidebar to begin.")
    st.stop()

# Replay history
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# Chat input
question = st.chat_input("Ask a cost optimization question...")

if question:
    st.session_state.messages.append({"role": "user", "content": question})
    with st.chat_message("user"):
        st.markdown(question)

    with st.chat_message("assistant"):
        with st.spinner("Analyzing..."):
            try:
                api_response = request_analysis(
                    question,
                    st.session_state.resource_group,
                    st.session_state.subscription,
                )
                response = api_response["answer"]
            except Exception as e:
                response = f"⚠️ Error running analysis: `{e}`"
        st.markdown(response)

    st.session_state.messages.append({"role": "assistant", "content": response})
