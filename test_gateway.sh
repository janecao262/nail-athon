#!/usr/bin/env bash
TOKEN=$(cat .agentbase/token.txt)
# I need to get an IAM token for the gateway, but wait, the script get_token.sh might already return an IAM token.
# Gateway inboundAuth is IAM.
# So $TOKEN should work.

GW_ENDPOINT="https://gw-interview-gateway-112073.agentbase-gateway.aiplatform.vngcloud.vn"
TARGET_NAME="notion"

# Try to list tools via the gateway
# MCP tools/list is a POST request to /notion/tools/list
curl -sS -X POST "$GW_ENDPOINT/$TARGET_NAME/tools/list" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}}' | jq .
