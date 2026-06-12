#!/usr/bin/env bash
IMAGE=$(cat .agentbase/last_image.txt)
echo "Updating runtime with image: $IMAGE and env vars"
bash .agents/skills/agentbase/scripts/runtime.sh update runtime-c1f124e2-448f-4723-83ef-02d4e8317c6e \
  --image "$IMAGE" \
  --from-cr \
  --flavor runtime-s2-general-2x4 \
  --env-file .env
