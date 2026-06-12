import os
import asyncio
import json
import base64
import urllib.request
import urllib.parse
from datetime import datetime
from dotenv import load_dotenv
from greennode_agentbase import (
    GreenNodeAgentBaseApp,
    RequestContext,
    PingStatus,
)
from greennode_agentbase.identity import IAMCredentials
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain.agents import create_agent
from langchain_core.tools import tool
from mcp.client.session import ClientSession
from mcp.client.streamable_http import streamable_http_client
from contextlib import AsyncExitStack
import httpx
import sys

# Load .env if exists
load_dotenv()

app = GreenNodeAgentBaseApp()

# Debug: print environment keys (not values)
print(f"Environment keys: {list(os.environ.keys())}", file=sys.stderr)

LLM_API_KEY = os.getenv("LLM_API_KEY")
LLM_BASE_URL = os.getenv("LLM_BASE_URL")
LLM_MODEL = os.getenv("LLM_MODEL")

if not LLM_MODEL:
    print("ERROR: LLM_MODEL environment variable is missing!", file=sys.stderr)
    # Provide a dummy value to avoid crash during import if possible, 
    # but the agent won't work correctly.
    LLM_MODEL = "missing-model"

SYSTEM_PROMPT = """
You are a Senior Data Engineering Interviewer. Your goal is to conduct a rigorous technical interview for a candidate working on Data Platform projects.
Expertise: PySpark, Delta Lake, Airflow, Data Modeling.
You have access to Notion MCP tools to retrieve information or record interview notes.
"""

llm = ChatOpenAI(
    api_key=LLM_API_KEY,
    base_url=LLM_BASE_URL,
    model=LLM_MODEL,
    temperature=0.7
)

def get_iam_token(client_id: str, client_secret: str) -> str:
    url = "https://iam.api.vngcloud.vn/accounts-api/v2/auth/token"
    data = urllib.parse.urlencode({'grant_type': 'client_credentials'}).encode()
    auth = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()
    req = urllib.request.Request(url, data=data, method="POST", headers={
        "Authorization": f"Basic {auth}",
        "Content-Type": "application/x-www-form-urlencoded"
    })
    with urllib.request.urlopen(req) as f:
        return json.load(f).get("access_token")

async def run_agent(msg: str) -> str:
    gateway_url = os.getenv("MCP_GATEWAY_URL")
    if not gateway_url:
        print("MCP_GATEWAY_URL not set, falling back to basic prompt")
        return (ChatPromptTemplate.from_messages([("system", SYSTEM_PROMPT), ("human", "{message}")]) | llm).invoke({"message": msg}).content

    try:
        creds = IAMCredentials()
        client_id = creds.client_id
        client_secret = creds.client_secret
    except Exception as e:
        print(f"Failed to get IAM credentials from library: {e}")
        client_id = os.getenv("GREENNODE_CLIENT_ID")
        client_secret = os.getenv("GREENNODE_CLIENT_SECRET")
    
    if not client_id:
        print("IAM credentials not found, falling back to basic prompt")
        return (ChatPromptTemplate.from_messages([("system", SYSTEM_PROMPT), ("human", "{message}")]) | llm).invoke({"message": msg}).content

    try:
        token = get_iam_token(client_id, client_secret)
    except Exception as e:
        print(f"Failed to get IAM token: {e}")
        return (ChatPromptTemplate.from_messages([("system", SYSTEM_PROMPT), ("human", "{message}")]) | llm).invoke({"message": msg}).content

    target_url = f"{gateway_url.rstrip('/')}/notion"
    headers = {"Authorization": f"Bearer {token}"}
    
    print(f"Connecting to Notion MCP via gateway: {target_url}")
    async with AsyncExitStack() as stack:
        try:
            http_client = await stack.enter_async_context(httpx.AsyncClient(headers=headers, timeout=60.0))
            streams = await stack.enter_async_context(streamable_http_client(target_url, http_client=http_client))
            mcp_session = await stack.enter_async_context(ClientSession(streams[0], streams[1]))
            await mcp_session.initialize()
            
            tools_res = await mcp_session.list_tools()
            print(f"Discovered {len(tools_res.tools)} tools from Notion MCP")
            
            agent_tools = []
            for t in tools_res.tools:
                def create_mcp_tool(t_name=t.name, t_desc=t.description, t_schema=t.inputSchema):
                    @tool(t_name, description=t_desc, args_schema=t_schema)
                    async def mcp_tool(**kwargs) -> str:
                        """MCP tool wrapper"""
                        try:
                            result = await mcp_session.call_tool(t_name, arguments=kwargs)
                            return "\n".join(c.text for c in result.content if hasattr(c, 'text'))
                        except Exception as e:
                            return f"Error executing {t_name}: {e}"
                    return mcp_tool
                
                agent_tools.append(create_mcp_tool())
            
            agent = create_agent(
                model=llm,
                tools=agent_tools,
                system_prompt=SYSTEM_PROMPT
            )
            
            inputs = {"messages": [{"role": "user", "content": msg}]}
            response = await agent.ainvoke(inputs)
            
            if isinstance(response, dict) and "messages" in response:
                return response["messages"][-1].content
            return str(response)
            
        except Exception as e:
            print(f"MCP Integration Error: {e}")
            import traceback
            traceback.print_exc()
            return (ChatPromptTemplate.from_messages([("system", SYSTEM_PROMPT), ("human", "{message}")]) | llm).invoke({"message": msg}).content

@app.entrypoint
def handler(payload: dict, context: RequestContext) -> dict:
    message = payload.get("message", "Hello")
    
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
    try:
        response_text = loop.run_until_complete(run_agent(message))
    except Exception as e:
        response_text = f"Error generating response: {e}"
    
    return {
        "status": "success",
        "message": response_text,
        "timestamp": datetime.now().isoformat(),
        "session_id": context.session_id,
    }

@app.ping
def health_check() -> PingStatus:
    return PingStatus.HEALTHY

if __name__ == "__main__":
    app.run(port=8080, host="0.0.0.0")
