#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_DIR="$ROOT_DIR/.run_logs/start_all"
HOST="127.0.0.1"
BACKEND_PORT="8001"
AGENT_PORT="8002"
FRONTEND_FALLBACK_PORT="5173"

PIDS=()
NAMES=()
LOGS=()
LAST_PID=""

print_header() {
  echo "======================================"
  echo "    Starting EDUagent Environment     "
  echo "======================================"
}

log() {
  echo "[$(date '+%H:%M:%S')] $*"
}

is_port_open() {
  local port="$1"
  (echo >"/dev/tcp/$HOST/$port") >/dev/null 2>&1
}

require_cmd() {
  local cmd="$1"
  if ! command -v "$cmd" >/dev/null 2>&1; then
    echo "Missing required command: $cmd" >&2
    exit 1
  fi
}

ensure_port_free() {
  local port="$1"
  local service="$2"

  if is_port_open "$port"; then
    echo "$service cannot start: $HOST:$port is already in use." >&2
    echo "Stop the existing process first, then rerun ./start_all.sh." >&2
    exit 1
  fi
}

tail_log() {
  local log_file="$1"

  if [[ -f "$log_file" ]]; then
    echo "---- log tail: $log_file ----"
    tail -n 40 "$log_file"
    echo "-----------------------------"
  fi
}

cleanup() {
  local status=$?

  if ((${#PIDS[@]} > 0)); then
    echo
    log "Stopping services started by this script..."
    for pid in "${PIDS[@]}"; do
      if kill -0 "$pid" >/dev/null 2>&1; then
        kill "$pid" >/dev/null 2>&1 || true
      fi
    done
    wait "${PIDS[@]}" >/dev/null 2>&1 || true
    log "All started services stopped."
  fi

  exit "$status"
}

trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

wait_for_port() {
  local name="$1"
  local port="$2"
  local pid="$3"
  local log_file="$4"
  local attempts="${5:-40}"

  for _ in $(seq 1 "$attempts"); do
    if is_port_open "$port"; then
      log "$name is listening on http://$HOST:$port"
      return 0
    fi

    if ! kill -0 "$pid" >/dev/null 2>&1; then
      echo "$name exited before opening port $port." >&2
      tail_log "$log_file"
      exit 1
    fi

    sleep 0.5
  done

  echo "$name did not open port $port in time." >&2
  tail_log "$log_file"
  exit 1
}

wait_for_backend_health() {
  local pid="$1"
  local log_file="$2"
  local attempts="${3:-40}"

  for _ in $(seq 1 "$attempts"); do
    if curl -fsS "http://$HOST:$BACKEND_PORT/health" >/dev/null 2>&1; then
      log "Backend health check passed"
      return 0
    fi

    if ! kill -0 "$pid" >/dev/null 2>&1; then
      echo "Backend exited before health check passed." >&2
      tail_log "$log_file"
      exit 1
    fi

    sleep 0.5
  done

  echo "Backend health check timed out." >&2
  tail_log "$log_file"
  exit 1
}

detect_frontend_url() {
  local log_file="$1"
  local attempts="${2:-40}"
  local url=""

  for _ in $(seq 1 "$attempts"); do
    url="$(grep -Eo 'http://(localhost|127\.0\.0\.1):[0-9]+' "$log_file" | tail -n 1 || true)"
    if [[ -n "$url" ]]; then
      echo "$url"
      return 0
    fi

    sleep 0.5
  done

  if is_port_open "$FRONTEND_FALLBACK_PORT"; then
    echo "http://localhost:$FRONTEND_FALLBACK_PORT"
    return 0
  fi

  return 1
}

start_service() {
  local name="$1"
  local workdir="$2"
  local log_file="$3"
  shift 3

  log "Starting $name..."
  (
    cd "$workdir"
    "$@"
  ) >"$log_file" 2>&1 &

  local pid=$!
  PIDS+=("$pid")
  NAMES+=("$name")
  LOGS+=("$log_file")
  LAST_PID="$pid"

  log "$name started with pid $pid; log: $log_file"
}

print_header
require_cmd docker
require_cmd curl
require_cmd npm

mkdir -p "$LOG_DIR"
cd "$ROOT_DIR"

ensure_port_free "$AGENT_PORT" "Agent Service v2"
ensure_port_free "$BACKEND_PORT" "Backend"

log "[1/4] Starting Docker containers (mysql, qdrant)..."
docker start eduagent-mysql eduagent-qdrant >/dev/null
log "Docker containers are available"

log "[2/4] Starting Agent Service v2 on port $AGENT_PORT..."
agent_log="$LOG_DIR/agent_service_v2.log"
web_search_enabled="${WEB_SEARCH_ENABLED:-true}"
start_service "Agent Service v2" "$ROOT_DIR/agent_service_v2" "$agent_log" env WEB_SEARCH_ENABLED="$web_search_enabled" ./.venv/bin/uvicorn agent_service_v2.main:app --host "$HOST" --port "$AGENT_PORT"
agent_pid="$LAST_PID"
# 首次运行可能需要下载固定版 MCP 包，端口等待需覆盖 30 秒 MCP 启动超时。
wait_for_port "Agent Service v2" "$AGENT_PORT" "$agent_pid" "$agent_log" 120

log "[3/4] Starting Backend on port $BACKEND_PORT..."
backend_log="$LOG_DIR/backend.log"
start_service "Backend" "$ROOT_DIR/backend" "$backend_log" ../.venv/bin/python -m uvicorn app.main:app --host "$HOST" --port "$BACKEND_PORT" --reload
backend_pid="$LAST_PID"
wait_for_port "Backend" "$BACKEND_PORT" "$backend_pid" "$backend_log"
wait_for_backend_health "$backend_pid" "$backend_log"

log "[4/4] Starting Frontend..."
frontend_log="$LOG_DIR/frontend.log"
start_service "Frontend" "$ROOT_DIR/frontend" "$frontend_log" env VITE_USE_MOCK=false VITE_API_BASE_URL=http://localhost:"$BACKEND_PORT"/api/v1 npm run dev -- --host "$HOST"

if ! frontend_url="$(detect_frontend_url "$frontend_log")"; then
  echo "Frontend did not report a dev server URL in time." >&2
  tail_log "$frontend_log"
  exit 1
fi
log "Frontend is available at $frontend_url"

echo "======================================"
echo " All services are running."
echo " Frontend: $frontend_url"
echo " Backend:  http://$HOST:$BACKEND_PORT"
echo " Agent v2: http://$HOST:$AGENT_PORT"
echo " Logs:     $LOG_DIR"
echo " Press Ctrl+C to stop services started by this script."
echo "======================================"

set +e
wait -n "${PIDS[@]}"
exit_status=$?
set -e

echo
log "A service exited; shutting down the remaining services."
for i in "${!PIDS[@]}"; do
  if ! kill -0 "${PIDS[$i]}" >/dev/null 2>&1; then
    log "${NAMES[$i]} exited. Last log lines:"
    tail_log "${LOGS[$i]}"
  fi
done

exit "$exit_status"
