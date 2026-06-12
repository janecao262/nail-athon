#!/usr/bin/env bash
cd notion-mcp
TAG=v$(date +%Y%m%d%H%M%S)
IMAGE=vcr.vngcloud.vn/111480-abp112073/notion-mcp:$TAG
echo "Building $IMAGE..."
docker build --platform linux/amd64 -t $IMAGE .
echo "Pushing $IMAGE..."
docker push $IMAGE
echo $IMAGE > ../.agentbase/last_notion_image.txt
cd ..
