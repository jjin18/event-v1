#!/usr/bin/env bash
# Dev mode: Vite HMR on :5173 + FastAPI on :8000 in parallel
set -e

REPO_ROOT="$(cd "$(dirname "$0")" && pwd)"

echo "=== Hackathon Judge — Dev Mode ==="

# Backend deps
pip install -q -r "$REPO_ROOT/backend/requirements.txt" &

# Frontend deps
cd "$REPO_ROOT/frontend"
if [ ! -d "node_modules" ]; then
  npm install --silent &
fi
wait

echo ""
echo "  Judge dashboard: http://localhost:5173/judge"
echo "  Admin workspace: http://localhost:5173/admin"
echo "  API:             http://localhost:8000"
echo ""

# Start both servers
cd "$REPO_ROOT"
python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload &
BACKEND_PID=$!

cd "$REPO_ROOT/frontend"
npm run dev &
FRONTEND_PID=$!

# Cleanup on exit
trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; exit" INT TERM

wait
