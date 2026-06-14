#!/usr/bin/env bash
set -e
IMAGE=$(cat .agentbase/last_ui_image.txt)
echo "Deploying UI runtime with image: $IMAGE"
bash .agents/skills/agentbase/scripts/runtime.sh update runtime-bdf61ee1-384e-47e4-8367-2cfeb2ac8ae3 \
  --image "$IMAGE" \
  --from-cr \
  --flavor runtime-s2-general-2x4 \
  --env-file .env.ui
