#!/usr/bin/env bash
TOKEN=$(cat .agentbase/token.txt)
BASE=https://agentbase.api.vngcloud.vn/gateway/api/v1
curl -sS "$BASE/gateways?page=1&pageSize=50" -H "Authorization: Bearer $TOKEN" | jq .
