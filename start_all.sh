#!/bin/bash
echo "======================================"
echo "    Starting EDUagent Environment     "
echo "======================================"

echo "[1/4] Starting Docker containers (mysql, qdrant)..."
docker start eduagent-mysql eduagent-qdrant
sleep 2

# Helper function to kill background processes on exit
trap 'echo "Stopping all services..."; kill $(jobs -p) 2>/dev/null; echo "All services stopped."' EXIT

cd /home/yezisama/workspace/workflow/EDUagent

echo "[2/4] Starting Agent Service v2 on port 8002..."
cd agent_service_v2
./.venv/bin/uvicorn agent_service_v2.main:app --host 127.0.0.1 --port 8002 &
cd ..

echo "[3/4] Starting Backend on port 8001..."
cd backend
# pydantic-settings reads .env directly via env_file config — no need to source
../.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8001 --reload &
cd ..

echo "[4/4] Starting Frontend..."
cd frontend
VITE_USE_MOCK=false VITE_API_BASE_URL=http://localhost:8001/api/v1 npm run dev &
cd ..

echo "======================================"
echo " All services are running!"
echo " Frontend: http://localhost:5173 (or check your Vite port)"
echo " Backend:  http://127.0.0.1:8001"
echo " Agent v2: http://127.0.0.1:8002"
echo " Press Ctrl+C to stop everything."
echo "======================================"

# Wait for all background jobs
wait
