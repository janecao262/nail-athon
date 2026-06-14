import os
import sys
from datetime import datetime
from dotenv import load_dotenv

# Load .env BEFORE importing jira_tools so module-level os.getenv() calls pick up the values
load_dotenv()

from greennode_agentbase import GreenNodeAgentBaseApp, RequestContext, PingStatus
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent
from greennode_agent_bridge import AgentBaseMemoryEvents
import jira_tools
from jira_tools import ALL_TOOLS

print(f"Environment keys: {list(os.environ.keys())}", file=sys.stderr)

LLM_API_KEY = os.getenv("LLM_API_KEY")
LLM_BASE_URL = os.getenv("LLM_BASE_URL")
LLM_MODEL = os.getenv("LLM_MODEL")
MEMORY_ID = os.getenv("AGENTBASE_MEMORY_ID", "")

if not LLM_MODEL:
    print("ERROR: LLM_MODEL environment variable is missing!", file=sys.stderr)
    LLM_MODEL = "missing-model"

SYSTEM_PROMPT = """You are a Jira Assistant. You help engineers and project managers \
understand their work, plan effectively, and stay on track.

Your capabilities:
- Fetch and summarize task details
- Estimate completion time (ETA) based on description complexity and story points \
(1 story point ≈ 1 developer-day; adjust up for unclear requirements or cross-team dependencies)
- Prioritize and schedule tasks: rank by due date → business impact → blocking status
- Answer questions about task counts, due dates, sprint health, and workload distribution
- Identify overdue tasks and risks

When estimating ETA, always state your assumptions clearly.
When showing task lists, use this format: KEY | Summary | Status | Assignee | Due.
Be concise and actionable.
Always use your tools to fetch real data before answering."""

llm = ChatOpenAI(
    api_key=LLM_API_KEY,
    base_url=LLM_BASE_URL,
    model=LLM_MODEL,
    temperature=0.3,
)

if MEMORY_ID:
    checkpointer = AgentBaseMemoryEvents(memory_id=MEMORY_ID)
    agent = create_react_agent(model=llm, tools=ALL_TOOLS, prompt=SYSTEM_PROMPT, checkpointer=checkpointer)
    print(f"Memory enabled: {MEMORY_ID}", file=sys.stderr)
else:
    agent = create_react_agent(model=llm, tools=ALL_TOOLS, prompt=SYSTEM_PROMPT)
    print("Memory disabled: AGENTBASE_MEMORY_ID not set", file=sys.stderr)

app = GreenNodeAgentBaseApp()

_session_store: dict[str, dict] = {}


def _apply_config(cfg: dict) -> None:
    jira_tools.set_config(
        url=cfg.get("url", ""),
        email=cfg.get("email", ""),
        token=cfg.get("token", ""),
        project=cfg.get("project", ""),
    )


@app.entrypoint
def handler(payload: dict, context: RequestContext) -> dict:
    message = payload.get("message", "Hello")
    session_id = context.session_id
    user_id = context.user_id

    # Require session headers when memory is enabled
    if MEMORY_ID and (not session_id or not user_id):
        return {
            "status": "error",
            "error": "Missing required headers: X-GreenNode-AgentBase-Session-Id and X-GreenNode-AgentBase-User-Id are required.",
        }

    # Jira config: new in payload > known session > env vars
    jira_config = payload.get("jira_config")
    if jira_config:
        _session_store[session_id] = jira_config
        _apply_config(jira_config)
    elif session_id in _session_store:
        _apply_config(_session_store[session_id])

    invoke_config = (
        {"configurable": {"thread_id": session_id, "actor_id": user_id}}
        if MEMORY_ID else {}
    )

    try:
        result = agent.invoke(
            {"messages": [{"role": "user", "content": message}]},
            config=invoke_config,
        )
        response_text = result["messages"][-1].content
    except Exception as e:
        response_text = f"Error generating response: {e}"

    return {
        "status": "success",
        "message": response_text,
        "timestamp": datetime.now().isoformat(),
        "session_id": session_id,
    }


@app.ping
def health_check() -> PingStatus:
    return PingStatus.HEALTHY


if __name__ == "__main__":
    app.run(port=8080, host="0.0.0.0")
