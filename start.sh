#!/bin/bash
set -e

WORKSPACE="${COZE_WORKSPACE_PATH:-/workspace/projects}"
PORT="${DEPLOY_RUN_PORT:-5000}"

# Start backend API
cd "$WORKSPACE/apps/api"
EMBODIED_DB_PATH="$WORKSPACE/data/embodied_ai_jobs_v4.db" \
  nohup python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8000 > /app/work/logs/bypass/backend.log 2>&1 &

echo "Backend API started on port 8000"

# Start frontend dev server
cd "$WORKSPACE/apps/web"
DEPLOY_RUN_PORT="$PORT" pnpm dev
