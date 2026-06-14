#!/usr/bin/env bash
set -e
TAG=v$(date +%Y%m%d%H%M%S)
IMAGE=vcr.vngcloud.vn/111480-abp112073/jira-ui:$TAG
echo "Building $IMAGE..."
docker build --platform linux/amd64 -t "$IMAGE" -f Dockerfile.ui .
echo "Pushing $IMAGE..."
docker push "$IMAGE"
echo "$IMAGE" > .agentbase/last_ui_image.txt
echo "Done: $IMAGE"
