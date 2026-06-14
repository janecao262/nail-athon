import base64
import json
import os
import urllib.parse
import urllib.request
import uuid

import requests
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

AGENT_URL = os.getenv(
    "AGENT_ENDPOINT",
    "https://endpoint-a5e99572-5764-42b1-b2ff-e6beab2eca92.agentbase-runtime.aiplatform.vngcloud.vn/invocations",
)
IAM_TOKEN_URL = "https://iam.api.vngcloud.vn/accounts-api/v2/auth/token"
CLIENT_ID = os.getenv("GREENNODE_CLIENT_ID")
CLIENT_SECRET = os.getenv("GREENNODE_CLIENT_SECRET")


# ── Auth ──────────────────────────────────────────────────────────────────────

@st.cache_data(ttl=270)  # refresh before the 5-minute IAM token expiry
def _get_iam_token(client_id: str, client_secret: str) -> str:
    data = urllib.parse.urlencode({"grant_type": "client_credentials"}).encode()
    auth = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()
    req = urllib.request.Request(
        IAM_TOKEN_URL, data=data, method="POST",
        headers={"Authorization": f"Basic {auth}", "Content-Type": "application/x-www-form-urlencoded"},
    )
    with urllib.request.urlopen(req) as f:
        return json.load(f)["access_token"]


def get_token() -> str | None:
    if not CLIENT_ID or not CLIENT_SECRET:
        return None
    try:
        return _get_iam_token(CLIENT_ID, CLIENT_SECRET)
    except Exception as e:
        st.error(f"Failed to get IAM token: {e}")
        return None


# ── Session state ─────────────────────────────────────────────────────────────

if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())

if "messages" not in st.session_state:
    st.session_state.messages = []

if "user_id" not in st.session_state:
    st.session_state.user_id = os.getenv("JIRA_EMAIL", "demo-user")


# ── Page config ───────────────────────────────────────────────────────────────

st.set_page_config(page_title="Jira Assistant", page_icon="📋", layout="centered")
st.title("📋 Jira Assistant")
st.caption(f"Project: **{os.getenv('JIRA_PROJECT_KEY', 'KAN')}** · Session: `{st.session_state.session_id[:8]}…`")

# Sidebar
with st.sidebar:
    st.header("Session")
    st.write(f"**User:** {st.session_state.user_id}")
    st.write(f"**Session ID:** `{st.session_state.session_id[:8]}…`")
    if st.button("🔄 New session"):
        st.session_state.session_id = str(uuid.uuid4())
        st.session_state.messages = []
        st.rerun()

    st.divider()
    st.header("Quick questions")
    suggestions = [
        "How many open tasks are there?",
        "List all open tasks prioritized by urgency",
        "Are there any overdue tasks?",
        "Which tasks are due before 2026-07-01?",
        "Show workload summary per assignee",
        "Estimate the ETA for KAN-1",
    ]
    for s in suggestions:
        if st.button(s, use_container_width=True):
            st.session_state._quick_input = s
            st.rerun()


# ── Chat history ──────────────────────────────────────────────────────────────

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])


# ── Input handling ────────────────────────────────────────────────────────────

quick = st.session_state.pop("_quick_input", None)
user_input = st.chat_input("Ask anything about your Jira project…") or quick

if user_input:
    st.session_state.messages.append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.markdown(user_input)

    token = get_token()
    if not token:
        st.error("No IAM credentials found. Set GREENNODE_CLIENT_ID and GREENNODE_CLIENT_SECRET in .env")
        st.stop()

    with st.chat_message("assistant"):
        with st.spinner("Thinking…"):
            try:
                resp = requests.post(
                    AGENT_URL,
                    json={"message": user_input},
                    headers={
                        "Authorization": f"Bearer {token}",
                        "Content-Type": "application/json",
                        "X-GreenNode-AgentBase-Session-Id": st.session_state.session_id,
                        "X-GreenNode-AgentBase-User-Id": st.session_state.user_id,
                    },
                    timeout=120,
                )
                resp.raise_for_status()
                data = resp.json()
                if data.get("status") == "error":
                    answer = f"⚠️ {data.get('error', 'Unknown error')}"
                else:
                    answer = data.get("message", "No response.")
            except requests.exceptions.Timeout:
                answer = "⚠️ Request timed out. The agent is still processing — try again."
            except Exception as e:
                answer = f"⚠️ Error: {e}"

        st.markdown(answer)

    st.session_state.messages.append({"role": "assistant", "content": answer})
