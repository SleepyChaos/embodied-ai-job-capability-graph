#!/usr/bin/env bash
set -e

# Start backend API
cd "$(dirname "$0")/apps/api"
EMBODIED_DB_PATH="${COZE_WORKSPACE_PATH}/data/embodied_ai_jobs_v4.db" \
  nohup python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8000 \
  > /app/work/logs/bypass/backend.log 2>&1 &

# Start frontend dev server
cd "$(dirname "$0")/apps/web"
exec pnpm exec vite --host 0.0.0.0 --port "${DEPLOY_RUN_PORT}"
