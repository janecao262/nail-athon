#!/usr/bin/env bash
TOKEN=$(cat .agentbase/token.txt)
curl -sS "https://agentbase.api.vngcloud.vn/gateway/api/v1/gateways/interview-gateway" -H "Authorization: Bearer $TOKEN" | jq -r .state
