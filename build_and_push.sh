#!/usr/bin/env bash
TAG=v$(date +%Y%m%d%H%M%S)
IMAGE=vcr.vngcloud.vn/111480-abp112073/jira-assistant:$TAG
echo "Building $IMAGE..."
docker build --platform linux/amd64 -t $IMAGE .
echo "Pushing $IMAGE..."
docker push $IMAGE
echo $IMAGE > .agentbase/last_image.txt
