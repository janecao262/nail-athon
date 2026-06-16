# Jira Assistant — Claw-a-thon

An AI-powered Jira assistant built on the **GreenNode AgentBase** platform. Ask questions about your Jira project in plain English and get actionable answers.

---

## Overview

The agent connects to your Jira instance and lets engineers and project managers query tasks, check sprint health, identify overdue work, and get ETA estimates — all through a conversational interface.

It ships with two frontends:
- **`ui_server.py`** — a lightweight Starlette server with a custom HTML/JS chat UI
- **`ui.py`** — a Streamlit-based chat UI

---

## Architecture

```
User / Browser
     │
     ├── ui_server.py (Starlette + HTML chat UI)
     │         OR
     │   ui.py (Streamlit)
     │       │
     │       ▼ HTTP POST /invocations  (IAM-authenticated)
     │
GreenNode AgentBase Runtime
     │
     ├── LangGraph ReAct Agent  (main.py)
     │       └── LLM: vngcloud-llama-3.1-70b  (GreenNode MAAS)
     │
     └── Jira Tools  (jira_tools.py)
             └── Jira REST API
```

**Key components:**

| Component | Technology |
|---|---|
| Agent Framework | LangGraph `create_react_agent` |
| LLM | `vngcloud-llama-3.1-70b` via GreenNode MAAS (OpenAI-compatible) |
| Jira client | `jira` Python library |
| UI (option A) | Starlette + vanilla HTML/JS (`ui_server.py`) |
| UI (option B) | Streamlit (`ui.py`) |
| Identity & Auth | VNG Cloud IAM (`client_credentials` flow) |
| Deployment | Docker on GreenNode AgentBase Runtime |

---

## Features

- **Task lookup** — fetch full details of any issue by key
- **Filtered listing** — list issues by status, assignee, or priority
- **Overdue detection** — surface all tasks past their due date
- **Deadline queries** — find everything due before a given date
- **Sprint overview** — show all issues in the active sprint with story points
- **Workload summary** — count open tasks per assignee
- **ETA estimation** — estimate completion time from story points and complexity
- **JQL search** — run arbitrary JQL queries via natural language
- **Multi-project support** — switch between Jira projects in the UI without restarting
- **Persistent memory** — optional session-aware conversations via `AGENTBASE_MEMORY_ID`
- **Dynamic Jira config** — credentials can be passed per-request (multi-tenant friendly)

---

## API

### Send a message to the agent

```
POST /
Content-Type: application/json

{
  "message": "Are there any overdue tasks?",
  "jira_config": {
    "url": "https://your-org.atlassian.net",
    "email": "you@example.com",
    "token": "<jira-api-token>",
    "project": "KAN"
  }
}
```

`jira_config` is only required on the first message of a session. Subsequent messages in the same session reuse the stored config. You can also set credentials via environment variables instead.

**Response:**
```json
{
  "status": "success",
  "message": "Found 3 overdue issue(s):\n  KAN-12 | Fix login bug | In Progress | Alice | Due: 2026-06-10\n  ...",
  "timestamp": "2026-06-16T10:00:00.000000",
  "session_id": "<session-id>"
}
```

### Health check

```
GET /ping
```

Returns `200 OK` when the agent is healthy.

---

## Running Locally

### Prerequisites

- Python 3.11+
- A Jira account with an API token
- Access to GreenNode MAAS (for the LLM)

### Setup

```bash
# 1. Clone the repo
git clone <repo-url>
cd clawathon

# 2. Create and activate virtual environment
python -m venv venv
source venv/bin/activate        # macOS/Linux
# .\venv\Scripts\activate       # Windows

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure environment
cp .env.example .env
```

Edit `.env` with your credentials:

```env
# LLM (GreenNode MAAS — OpenAI-compatible)
LLM_API_KEY=<your-maas-api-key>
LLM_BASE_URL=https://maas-llm-aiplatform-hcm.api.vngcloud.vn/v1
LLM_MODEL=vngcloud-llama-3.1-70b

# Jira credentials (can also be passed per-request via jira_config)
JIRA_URL=https://your-org.atlassian.net
JIRA_EMAIL=you@example.com
JIRA_API_TOKEN=<your-jira-api-token>
JIRA_PROJECT_KEY=KAN

# Optional: enable persistent conversation memory
# AGENTBASE_MEMORY_ID=<memory-id>

# GreenNode IAM credentials (auto-injected in production by AgentBase Runtime)
GREENNODE_CLIENT_ID=<your-client-id>
GREENNODE_CLIENT_SECRET=<your-client-secret>
```

### Start the agent backend

```bash
python main.py
```

The agent starts on `http://localhost:8080`.

### Start the chat UI

```bash
# Option A — Starlette UI (recommended)
pip install -r requirements-ui-server.txt
python ui_server.py

# Option B — Streamlit UI
pip install -r requirements-ui.txt
streamlit run ui.py
```

### Test it directly

```bash
curl -X POST http://localhost:8080 \
  -H "Content-Type: application/json" \
  -d '{"message": "How many open tasks are there?"}'
```

---

## Deployment

The agent and UI are containerized and deployed on **GreenNode AgentBase Runtime**.

### Build & push

```bash
bash build_and_push.sh        # Agent image
bash build_and_push_ui.sh     # UI image
```

### Update the running runtime

```bash
bash update_runtime_v2.sh     # Update agent runtime
bash deploy_ui_runtime.sh     # Deploy UI runtime
```

The runtime auto-injects `GREENNODE_CLIENT_ID`, `GREENNODE_CLIENT_SECRET`, and `GREENNODE_AGENT_IDENTITY` — do not set these manually in production.

---

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `LLM_API_KEY` | Yes | GreenNode MAAS API key |
| `LLM_BASE_URL` | Yes | LLM endpoint (OpenAI-compatible) |
| `LLM_MODEL` | Yes | Model name, e.g. `vngcloud-llama-3.1-70b` |
| `JIRA_URL` | Yes* | Jira instance URL |
| `JIRA_EMAIL` | Yes* | Jira account email |
| `JIRA_API_TOKEN` | Yes* | Jira API token |
| `JIRA_PROJECT_KEY` | No | Default project key, e.g. `KAN` |
| `AGENTBASE_MEMORY_ID` | No | Enables persistent conversation memory |
| `AGENT_ENDPOINT` | No (UI) | Agent runtime invocation URL (used by UI servers) |
| `GREENNODE_CLIENT_ID` | Auto | Injected by AgentBase Runtime in production |
| `GREENNODE_CLIENT_SECRET` | Auto | Injected by AgentBase Runtime in production |
| `GREENNODE_AGENT_IDENTITY` | Auto | Injected by AgentBase Runtime in production |

\* Can be omitted if passed per-request via `jira_config`.

---

## Project Structure

```
clawathon/
├── main.py                    # Agent entrypoint — HTTP server, LangGraph ReAct agent
├── jira_tools.py              # LangChain tools wrapping the Jira REST API
├── ui.py                      # Streamlit chat frontend
├── ui_server.py               # Starlette chat frontend (custom HTML/JS UI)
├── test_mcp_connection.py     # MCP gateway connectivity test
├── requirements.txt           # Agent dependencies
├── requirements-ui.txt        # Streamlit UI dependencies
├── requirements-ui-server.txt # Starlette UI dependencies
├── Dockerfile                 # Agent container image
├── Dockerfile.ui              # UI container image
├── .env.example               # Environment variable template
├── build_and_push.sh          # Build and push agent Docker image
├── build_and_push_ui.sh       # Build and push UI Docker image
├── update_runtime_v2.sh       # Update the AgentBase agent runtime
├── deploy_ui_runtime.sh       # Deploy the UI runtime
├── check_gateway_state.sh     # Check MCP gateway state
├── test_gateway.sh            # Test MCP tools via gateway
└── list_gateways.sh           # List all configured gateways
```

---

## Dependencies

```
greennode-agentbase       # GreenNode AgentBase SDK
greennode-agent-bridge    # AgentBase memory/events bridge
langchain-openai          # LLM integration (OpenAI-compatible)
langgraph                 # Agent framework (ReAct)
jira                      # Jira REST API client
python-dotenv             # Environment variable loading
```

---

## Platform

Built for the **Claw-a-thon** hackathon on the **GreenNode AI Platform** by VNG Cloud.

- AgentBase Console: https://aiplatform.console.vngcloud.vn/agent-runtime
- MAAS (LLM) Console: https://aiplatform.console.vngcloud.vn/models
