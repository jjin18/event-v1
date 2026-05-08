#!/usr/bin/env bash
set -e

REPO_ROOT="$(cd "$(dirname "$0")" && pwd)"

echo "=== Hackathon Judging Platform ==="

# ---- Backend deps ----
echo "[1/4] Installing backend dependencies..."
cd "$REPO_ROOT"
pip install -q -r backend/requirements.txt

# ---- Frontend build (if not already built) ----
cd "$REPO_ROOT/frontend"
if [ ! -d "node_modules" ]; then
  echo "[2/4] Installing frontend dependencies..."
  npm install --silent
fi

echo "[3/4] Building frontend..."
npm run build

# ---- Start backend ----
cd "$REPO_ROOT"
echo "[4/4] Starting FastAPI on :${PORT:-8000} ..."
echo ""
echo "  Judge dashboard: http://localhost:${PORT:-8000}/judge"
echo "  Admin workspace: http://localhost:${PORT:-8000}/admin"
echo ""
echo "  Seed test data:  python backend/seed.py"
echo ""

exec python -m uvicorn backend.main:app \
  --host 0.0.0.0 \
  --port "${PORT:-8000}" \
  --workers 1
