#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_DIR="$ROOT_DIR/.run_logs/dev"
HOST="127.0.0.1"
BACKEND_PORT="8001"
AGENT_PORT="8002"
FRONTEND_FALLBACK_PORT="5173"
PIDS=()
NAMES=()
LOGS=()
LAST_PID=""

usage() {
  cat <<'EOF'
Usage: ./start_all.sh <command>

Commands:
  setup       Validate .env and install Backend, Agent Service, and frontend dependencies
  start       Prepare Docker dependencies and start Backend, Agent Service, and Vite
  --help      Show this help

Run `./start_all.sh setup` once after cloning or changing dependencies.
EOF
}

log() { echo "[$(date '+%H:%M:%S')] $*"; }
fail() { echo "ERROR: $*" >&2; exit 1; }

env_value() {
  local key="$1"
  awk -F= -v key="$key" '$1 == key { sub(/^[^=]*=/, ""); sub(/\r$/, ""); print; exit }' "$ROOT_DIR/.env"
}

is_port_open() {
  local port="$1"
  (echo >"/dev/tcp/$HOST/$port") >/dev/null 2>&1
}

ensure_port_free() {
  local port="$1" service="$2"
  if is_port_open "$port"; then
    fail "$service cannot start: $HOST:$port is already in use. Stop the existing process first."
  fi
}

tail_log() {
  local log_file="$1"
  [[ -f "$log_file" ]] || return
  echo "---- log tail: $log_file ----"
  tail -n 40 "$log_file"
  echo "-----------------------------"
}

cleanup() {
  local status=$?
  if ((${#PIDS[@]} > 0)); then
    log "Stopping development processes..."
    for pid in "${PIDS[@]}"; do
      kill -0 "$pid" >/dev/null 2>&1 && kill "$pid" >/dev/null 2>&1 || true
    done
    wait "${PIDS[@]}" >/dev/null 2>&1 || true
  fi
  exit "$status"
}

trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

wait_for_http() {
  local name="$1" url="$2" pid="$3" log_file="$4"
  for _ in $(seq 1 80); do
    if curl -fsS "$url" >/dev/null 2>&1; then
      log "$name is ready: $url"
      return 0
    fi
    if ! kill -0 "$pid" >/dev/null 2>&1; then
      echo "$name exited during startup." >&2
      tail_log "$log_file"
      exit 1
    fi
    sleep 0.5
  done
  echo "$name health check timed out." >&2
  tail_log "$log_file"
  exit 1
}

detect_frontend_url() {
  local log_file="$1" url=""
  for _ in $(seq 1 80); do
    url="$(grep -Eo 'http://(localhost|127\.0\.0\.1):[0-9]+' "$log_file" | tail -n 1 || true)"
    [[ -n "$url" ]] && { echo "$url"; return 0; }
    sleep 0.5
  done
  is_port_open "$FRONTEND_FALLBACK_PORT" && { echo "http://localhost:$FRONTEND_FALLBACK_PORT"; return 0; }
  return 1
}

start_service() {
  local name="$1" workdir="$2" log_file="$3"
  shift 3
  log "Starting $name..."
  (
    cd "$workdir"
    "$@"
  ) >"$log_file" 2>&1 &
  LAST_PID=$!
  PIDS+=("$LAST_PID")
  NAMES+=("$name")
  LOGS+=("$log_file")
}

require_dev_dependencies() {
  [[ -x "$ROOT_DIR/.venv/bin/python" ]] || fail "Backend dependencies are missing. Run ./start_all.sh setup"
  [[ -x "$ROOT_DIR/agent_service_v2/.venv/bin/uvicorn" ]] || fail "Agent dependencies are missing. Run ./start_all.sh setup"
  [[ -d "$ROOT_DIR/frontend/node_modules" ]] || fail "Frontend dependencies are missing. Run ./start_all.sh setup"
}

setup() {
  "$ROOT_DIR/deploy_prod.sh" check
  [[ -x "$ROOT_DIR/.venv/bin/python" ]] || python3 -m venv "$ROOT_DIR/.venv"
  "$ROOT_DIR/.venv/bin/python" -m pip install -r "$ROOT_DIR/backend/requirements.txt"
  uv sync --project "$ROOT_DIR/agent_service_v2" --frozen --no-dev
  (
    cd "$ROOT_DIR/frontend"
    npm ci
  )
  log "Development dependencies are ready. Run ./start_all.sh start"
}

start() {
  local qdrant_port redis_port

  require_dev_dependencies
  ensure_port_free "$AGENT_PORT" "Agent Service"
  ensure_port_free "$BACKEND_PORT" "Backend"
  "$ROOT_DIR/deploy_prod.sh" prepare-infra
  mkdir -p "$LOG_DIR"
  qdrant_port="$(env_value QDRANT_HTTP_PORT)"
  redis_port="$(env_value REDIS_PORT)"

  agent_log="$LOG_DIR/agent_service_v2.log"
  start_service "Agent Service" "$ROOT_DIR/agent_service_v2" "$agent_log" \
    env QDRANT_URL="http://$HOST:${qdrant_port:-6333}" \
    AGENTSCOPE_REDIS_PORT="${redis_port:-6379}" \
    COURSE_CATALOG_STORAGE_ROOT="$ROOT_DIR/backend/storage/course_catalogs" \
    ./.venv/bin/uvicorn agent_service_v2.main:app --env-file "$ROOT_DIR/.env" \
    --host "$HOST" --port "$AGENT_PORT" --reload
  agent_pid="$LAST_PID"
  wait_for_http "Agent Service" "http://$HOST:$AGENT_PORT/openapi.json" "$agent_pid" "$agent_log"

  backend_log="$LOG_DIR/backend.log"
  start_service "Backend" "$ROOT_DIR/backend" "$backend_log" \
    env CORS_ORIGINS='["http://localhost:5173","http://127.0.0.1:5173"]' \
    COURSE_CATALOG_STORAGE_ROOT="$ROOT_DIR/backend/storage/course_catalogs" \
    "$ROOT_DIR/.venv/bin/python" -m uvicorn app.main:app --env-file "$ROOT_DIR/.env" \
    --host "$HOST" --port "$BACKEND_PORT" --reload
  backend_pid="$LAST_PID"
  wait_for_http "Backend" "http://$HOST:$BACKEND_PORT/health" "$backend_pid" "$backend_log"

  frontend_log="$LOG_DIR/frontend.log"
  start_service "Frontend" "$ROOT_DIR/frontend" "$frontend_log" \
    env VITE_USE_MOCK=false VITE_API_BASE_URL="http://$HOST:$BACKEND_PORT/api/v1" \
    npm run dev -- --host "$HOST"
  if ! frontend_url="$(detect_frontend_url "$frontend_log")"; then
    fail "Frontend did not report a development URL. See $frontend_log"
  fi

  cat <<EOF
======================================
 Development environment is running.
 Frontend: $frontend_url
 Backend:  http://$HOST:$BACKEND_PORT
 Agent:    http://$HOST:$AGENT_PORT
 Logs:     $LOG_DIR
 Press Ctrl+C to stop development processes.
======================================
EOF

  set +e
  wait -n "${PIDS[@]}"
  exit_status=$?
  set -e
  for i in "${!PIDS[@]}"; do
    if ! kill -0 "${PIDS[$i]}" >/dev/null 2>&1; then
      log "${NAMES[$i]} exited."
      tail_log "${LOGS[$i]}"
    fi
  done
  exit "$exit_status"
}

case "${1:-start}" in
  setup) setup ;;
  start) start ;;
  --help|-h|help) usage ;;
  *) usage >&2; exit 2 ;;
esac
