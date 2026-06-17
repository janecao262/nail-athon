# Jira Assistant

**Agent Description | Claw-a-thon Hackathon | GreenNode AgentBase**

[![Agent Endpoint](https://img.shields.io/badge/Agent_Endpoint-live-brightgreen)](https://endpoint-cea10a20-5bf9-4b6d-83f6-c65e19c9161c.agentbase-runtime.aiplatform.vngcloud.vn/)
[![Jira Board](https://img.shields.io/badge/Jira_Board-BRD-0052CC?logo=jira)](https://nailathon.atlassian.net/jira/software/projects/BRD/boards/34/backlog?atlOrigin=eyJpIjoiZTZmNDZhNWRmNDQ0NDMwNGI2YTE2MDUyNzI0NTIwOTQiLCJwIjoiaiJ9)

---

## 1. Problem

Modern data teams are rarely one role. A typical setup involves a **BI Analyst** translating business questions into analysis, a **Data Engineer** building the pipelines behind it, and a **Business Owner** driving the demand — each with their own view of what should happen next.

This creates weekly friction: the Biz Owner submits requests with no visibility on queue position or ETA; the BI Analyst manually triages across multiple stakeholders without a consistent framework; the Data Engineer gets pulled in mid-sprint without clear priority signals or early blocker flags. All three end up in a coordination meeting just to decide what to work on next.

---

## 2. Target Users

- **BI Analysts** — triaging a high-volume, multi-stakeholder request queue
- **Data Engineers** — understanding what data work is coming next and flagging blockers early
- **Business Owners** — checking request status and ETA without chasing the team
- **Team Leads** — tracking sprint health and workload distribution at a glance

---

## 3. How the Agent Works

**Input →** Input the project key, description, create a new session and the question about what you need.

**Processing →** Built on **GreenNode AgentBase** using a **LangGraph ReAct** loop with `vngcloud-llama-3.1-70b`, the agent selects the right Jira tool: task lookup, overdue detection, sprint overview, workload summary, or ETA estimation. Tickets are structured with machine-readable fields (complexity, urgency, KPI at risk, blockers), enabling the agent to reason about priority — not just retrieve data.

**Output →** Ranked task lists, ETA estimates with risk flags, workload breakdowns, or sprint summaries — in seconds.

---

## 4. Value Delivered

- **Biz Owner** gets self-serve status and ETA visibility
- **BI Analyst** saves 30–60 minutes/week on manual triage
- **Data Engineer** sees upcoming work and blockers early
- **Whole team** replaces the weekly alignment meeting with an always-current board view

The agent eliminates information-gathering overhead so every role can focus on work that moves things forward.

---

## 5. Architecture

```
User / Browser
     │
     └── Chat UI (Starlette)
              │
              ▼ HTTP POST /invocations  (IAM-authenticated)
     GreenNode AgentBase Runtime
              │
              ├── LangGraph ReAct Agent  (main.py)
              │       └── LLM: vngcloud-llama-3.1-70b  (GreenNode MAAS)
              └── Jira Tools  (jira_tools.py)
                      └── Jira REST API
```

| Component | Technology |
|---|---|
| Agent Framework | LangGraph `create_react_agent` |
| LLM | `vngcloud-llama-3.1-70b` via GreenNode MAAS |
| Jira client | `jira` Python library |
| UI | Starlette + vanilla HTML/JS |
| Identity & Auth | VNG Cloud IAM (`client_credentials` flow) |
| Deployment | Docker on GreenNode AgentBase Runtime |

---

## 6. Features

- **Task lookup** — fetch full details of any issue by key
- **Filtered listing** — list issues by status, assignee, or priority
- **Overdue detection** — surface all tasks past their due date
- **Deadline queries** — find everything due before a given date
- **Sprint overview** — show all issues in the active sprint with story points
- **Workload summary** — count open tasks per assignee
- **ETA estimation** — estimate completion time from story points and complexity
- **JQL search** — run arbitrary JQL queries via natural language
- **Multi-project support** — switch between Jira projects without restarting
- **Persistent memory** — session-aware conversations via `AGENTBASE_MEMORY_ID`

---

## 7. Running Locally

### Prerequisites

- Python 3.11+
- A Jira account with an API token
- Access to GreenNode MAAS (for the LLM)

### Setup

```bash
git clone <repo-url>
cd clawathon
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Edit `.env`:

```env
LLM_API_KEY=<your-maas-api-key>
LLM_BASE_URL=https://maas-llm-aiplatform-hcm.api.vngcloud.vn/v1
LLM_MODEL=vngcloud-llama-3.1-70b

JIRA_URL=https://your-org.atlassian.net
JIRA_EMAIL=you@example.com
JIRA_API_TOKEN=<your-jira-api-token>
JIRA_PROJECT_KEY=KAN
```

### Start

```bash
# Agent backend
python main.py

# Chat UI
pip install -r requirements-ui-server.txt
python ui_server.py
```

---

## 8. Platform

Built for the **Claw-a-thon** hackathon on the **GreenNode AI Platform** by VNG Cloud.

- AgentBase Console: https://aiplatform.console.vngcloud.vn/agent-runtime
- MAAS Console: https://aiplatform.console.vngcloud.vn/models