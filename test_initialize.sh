#!/usr/bin/env bash
TOKEN=$(cat .agentbase/token.txt)
GW_ENDPOINT="https://gw-interview-gateway-112073.agentbase-gateway.aiplatform.vngcloud.vn"
TARGET_NAME="notion"

curl -v -X POST "$GW_ENDPOINT/$TARGET_NAME" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2024-11-05", "capabilities": {}, "clientInfo": {"name": "test", "version": "1.0"}}}'
