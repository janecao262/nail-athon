import os
import asyncio
import json
import base64
import urllib.request
import urllib.parse
from dotenv import load_dotenv
from mcp.client.session import ClientSession
from mcp.client.streamable_http import streamable_http_client
from contextlib import AsyncExitStack
from greennode_agentbase.identity import IAMCredentials
import httpx

load_dotenv()

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

async def test_mcp():
    gateway_url = os.getenv("MCP_GATEWAY_URL")
    if not gateway_url:
        print("MCP_GATEWAY_URL not set")
        return

    try:
        creds = IAMCredentials()
        client_id = creds.client_id
        client_secret = creds.client_secret
    except:
        client_id = os.getenv("GREENNODE_CLIENT_ID")
        client_secret = os.getenv("GREENNODE_CLIENT_SECRET")

    if not client_id or not client_secret:
        print("Credentials missing")
        return

    token = get_iam_token(client_id, client_secret)
    target_url = f"{gateway_url.rstrip('/')}/notion"
    headers = {"Authorization": f"Bearer {token}"}
    
    print(f"Connecting to {target_url}...")
    try:
        async with AsyncExitStack() as stack:
            http_client = await stack.enter_async_context(httpx.AsyncClient(headers=headers))
            streams = await stack.enter_async_context(streamable_http_client(target_url, http_client=http_client))
            mcp_session = await stack.enter_async_context(ClientSession(streams[0], streams[1]))
            await mcp_session.initialize()
            
            tools_res = await mcp_session.list_tools()
            print(f"Found {len(tools_res.tools)} tools:")
            for t in tools_res.tools:
                print(f"- {t.name}: {t.description}")
    except ExceptionGroup as eg:
        for e in eg.exceptions:
            if isinstance(e, httpx.HTTPStatusError):
                print(f"HTTP Status Error: {e.response.status_code}")
                print(f"Response Body: {e.response.text}")
            else:
                print(f"Sub-exception: {e}")
    except httpx.HTTPStatusError as e:
        print(f"HTTP Status Error: {e.response.status_code}")
        print(f"Response Body: {e.response.text}")
    except Exception as e:
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_mcp())
