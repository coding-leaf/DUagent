#!/usr/bin/env bash
set -Eeuo pipefail
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RUN_DIR="$ROOT_DIR/.run/prod"
LOG_DIR="$ROOT_DIR/.run_logs/prod"
INFRA_COMPOSE="$ROOT_DIR/docker-compose.prod.yml"
INFRA_ENV="$ROOT_DIR/.env"
ENV_TEMPLATE="$ROOT_DIR/deploy/env.production.example"
JUDGE_DIR="$ROOT_DIR/deploy/judge0"
JUDGE_CONFIG="$RUN_DIR/judge0.conf"
JUDGE0_IMAGE="${JUDGE0_IMAGE:-mrkushalsm/judge0:cgv2}"
BACKEND_PORT="${BACKEND_PORT:-8001}"
AGENT_PORT="${AGENT_PORT:-8002}"
usage() {
  cat <<'EOF'
Usage: ./deploy_prod.sh <command> [service]

Commands:
  check                 Validate commands, configuration, and source files
  prepare-infra         Start and validate Docker dependencies only
  deploy                Provision missing infrastructure, build, and start
  start                 Start infrastructure and prepared application services
  stop                  Stop Backend and Agent Service only
  restart               Restart prepared application services
  status                Show application and infrastructure health
  logs [backend|agent]  Follow production logs
  reset-judge0 --confirm
                       Delete Judge0 data and recreate its containers
  --help                 Show this help
EOF
}
log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"; }
fail() { echo "ERROR: $*" >&2; exit 1; }
require_cmd() {
  command -v "$1" >/dev/null 2>&1 || fail "Missing required command: $1"
}
require_file() {
  [[ -f "$1" ]] || fail "Missing required file: ${1#$ROOT_DIR/}"
}
container_exists() {
  docker container inspect "$1" >/dev/null 2>&1
}
container_running() {
  [[ "$(docker inspect -f '{{.State.Running}}' "$1" 2>/dev/null || true)" == "true" ]]
}
container_has_env() {
  docker inspect -f '{{range .Config.Env}}{{println .}}{{end}}' "$1" 2>/dev/null \
    | grep -Fxq "$2"
}
container_has_mount_destination() {
  docker inspect -f '{{range .Mounts}}{{println .Destination}}{{end}}' "$1" 2>/dev/null \
    | grep -Fxq "$2"
}
env_value() {
  local file="$1" key="$2"
  awk -F= -v key="$key" '$1 == key {sub(/^[^=]*=/, ""); print; exit}' "$file"
}
prepare_env() {
  [[ -f "$INFRA_ENV" ]] && return
  require_file "$ENV_TEMPLATE"
  install -m 600 "$ENV_TEMPLATE" "$INFRA_ENV"
  log "已自动创建 .env（权限 600）"
}
validate_env_placeholders() {
  local placeholders
  placeholders="$(grep -En '^[A-Z][A-Z0-9_]*=(replace-with-|.*your-)' "$INFRA_ENV" || true)"
  if [[ -n "$placeholders" ]]; then
    printf '%s\n' "$placeholders" >&2
    fail ".env 仍包含占位值；请编辑 .env 后重试"
  fi

  local debug_val
  debug_val="$(env_value "$INFRA_ENV" "DEBUG" | tr '[:upper:]' '[:lower:]')"
  if [[ "$debug_val" != "false" ]]; then
    fail ".env 中生产环境 DEBUG 必须设为 false"
  fi

  local weak_default="duagent-jwt-secret-change-in-production"
  local key val
  for key in JWT_SECRET_KEY WEBHOOK_SECRET INTERNAL_AGENT_TOKEN; do
    val="$(env_value "$INFRA_ENV" "$key")"
    if [[ -z "$val" ]]; then
      fail ".env 中 $key 不能为空"
    fi
    if [[ "$val" == "$weak_default" || "$val" == duagent-jwt-* ]]; then
      fail ".env 中 $key 不能使用默认弱密钥"
    fi
  done
}
infra_compose() {
  local args=(docker compose)
  [[ -f "$INFRA_ENV" ]] && args+=(--env-file "$INFRA_ENV")
  args+=(-f "$INFRA_COMPOSE" "$@")
  "${args[@]}"
}
preflight() {
  prepare_env
  validate_env_placeholders
  for cmd in docker curl npm python3 uv; do
    require_cmd "$cmd"
  done
  docker compose version >/dev/null 2>&1 || fail "Docker Compose v2 is required"
  docker info >/dev/null 2>&1 || fail "Docker daemon is unavailable"
  require_file "$INFRA_COMPOSE"
  require_file "$INFRA_ENV"
  require_file "$ROOT_DIR/backend/requirements.txt"
  require_file "$ROOT_DIR/backend/schema.sql"
  require_file "$ROOT_DIR/agent_service_v2/uv.lock"
  require_file "$ROOT_DIR/frontend/package-lock.json"
  require_file "$ROOT_DIR/deploy/ensure_default_admin.sh"
  require_file "$ROOT_DIR/deploy/render_judge0_config.sh"
  log "Preflight passed"
}
wait_http() {
  local name="$1" url="$2" attempts="${3:-60}"
  for _ in $(seq 1 "$attempts"); do
    if curl -fsS "$url" >/dev/null 2>&1; then
      log "$name is ready"
      return 0
    fi
    sleep 2
  done
  fail "$name health check timed out: $url"
}
wait_tcp() {
  local name="$1" port="$2" host="${3:-127.0.0.1}" attempts="${4:-60}"
  for _ in $(seq 1 "$attempts"); do
    if (echo >"/dev/tcp/$host/$port") >/dev/null 2>&1; then
      log "$name is accepting connections on $host:$port"
      return 0
    fi
    sleep 2
  done
  fail "$name did not open $host:$port"
}
ensure_service() {
  local container="$1" service="$2"
  if container_exists "$container"; then
    if ! container_running "$container"; then
      log "Starting existing container $container"
      docker start "$container" >/dev/null
    else
      log "Reusing running container $container"
    fi
    return 0
  fi
  log "Creating missing container $container"
  infra_compose up -d "$service"
}
detect_mysql_version() {
  local host="$1" port="$2" user="$3" pwd="$4"
  local ver=""
  if command -v mysql >/dev/null 2>&1; then
    ver="$(MYSQL_PWD="$pwd" mysql -h "$host" -P "$port" -u"$user" -N -B -e "SELECT VERSION();" 2>/dev/null || true)"
  fi
  if [[ -z "$ver" ]]; then
    ver="$(python3 -c "
import socket, sys
try:
    s = socket.socket()
    s.settimeout(3)
    s.connect((sys.argv[1], int(sys.argv[2])))
    data = s.recv(1024)
    s.close()
    if len(data) > 5 and data[4] == 10:
        print(data[5:].split(b'\x00')[0].decode('utf-8', errors='ignore'))
except Exception:
    pass
" "$host" "$port" 2>/dev/null || true)"
  fi
  echo "$ver"
}
ensure_core_infrastructure() {
  local mysql_host mysql_port qdrant_port
  mysql_host="$(env_value "$INFRA_ENV" DB_HOST 2>/dev/null || true)"
  mysql_host="${mysql_host:-127.0.0.1}"
  mysql_port="$(env_value "$INFRA_ENV" DB_PORT 2>/dev/null || true)"
  mysql_port="${mysql_port:-3306}"
  qdrant_port="$(env_value "$INFRA_ENV" QDRANT_HTTP_PORT 2>/dev/null || true)"

  # If port is not yet occupied by native MySQL, manage eduagent-mysql container
  if ! (echo >"/dev/tcp/${mysql_host}/${mysql_port}") >/dev/null 2>&1; then
    ensure_service eduagent-mysql mysql
  else
    log "Reusing running MySQL on ${mysql_host}:${mysql_port}"
    local db_user db_pwd mysql_ver
    db_user="$(env_value "$INFRA_ENV" DB_USER 2>/dev/null || true)"
    db_pwd="$(env_value "$INFRA_ENV" DB_PASSWORD 2>/dev/null || true)"
    mysql_ver="$(detect_mysql_version "${mysql_host}" "${mysql_port}" "${db_user:-root}" "$db_pwd")"
    if [[ -n "$mysql_ver" ]]; then
      log "Detected MySQL version: $mysql_ver"
      if [[ "$mysql_ver" =~ ^5\. ]]; then
        log "[INFO] Detected MySQL 5.x. Core backend services are backward-compatible. Official production recommends MySQL 8.0+ via Docker."
      fi
    fi
  fi

  ensure_service eduagent-qdrant qdrant
  ensure_service eduagent-agentscope-redis redis
  wait_tcp "MySQL" "${mysql_port}" "${mysql_host}"
  "$ROOT_DIR/deploy/ensure_default_admin.sh" "$INFRA_ENV" "$ROOT_DIR/backend/schema.sql"
  wait_http "Qdrant" "http://127.0.0.1:${qdrant_port:-6333}/collections"
  docker exec eduagent-agentscope-redis redis-cli ping | grep -qx PONG || fail "Redis PING failed"
  if ! docker inspect -f '{{range .Mounts}}{{println .Destination}}{{end}}' eduagent-qdrant \
    | grep -qx '/qdrant/storage'; then
    log "WARNING: existing eduagent-qdrant has no persistent /qdrant/storage mount"
  fi
}
ensure_judge0() {
  local judge0_runtime_matches=true
  local name postgres_password redis_password
  "$ROOT_DIR/deploy/render_judge0_config.sh" "$INFRA_ENV" "$JUDGE_CONFIG"
  postgres_password="$(env_value "$JUDGE_CONFIG" POSTGRES_PASSWORD)"
  redis_password="$(env_value "$JUDGE_CONFIG" REDIS_PASSWORD)"
  for name in judge0-v1130-redis-1 judge0-v1130-db-1; do
    if container_exists "$name" && ! container_running "$name"; then
      log "Starting existing Judge0 dependency $name"
      docker start "$name" >/dev/null
    fi
  done
  if container_exists judge0-v1130-redis-1 \
    && ! docker exec judge0-v1130-redis-1 redis-cli -a "$redis_password" ping 2>/dev/null | grep -qx PONG; then
    fail "Judge0 Redis password differs from .env; discard Judge0 data with: ./deploy_prod.sh reset-judge0 --confirm"
  fi
  if container_exists judge0-v1130-db-1 \
    && ! docker exec -e PGPASSWORD="$postgres_password" judge0-v1130-db-1 \
      psql -h 127.0.0.1 -U judge0 -d judge0 -Atqc 'SELECT 1' >/dev/null 2>&1; then
    fail "Judge0 PostgreSQL password differs from .env; discard Judge0 data with: ./deploy_prod.sh reset-judge0 --confirm"
  fi
  for name in judge0-v1130-server-1 judge0-v1130-workers-1; do
    [[ "$(docker inspect -f '{{.Config.Image}} {{.HostConfig.CgroupnsMode}}' "$name" 2>/dev/null || true)" \
      == "$JUDGE0_IMAGE host" ]] \
      || judge0_runtime_matches=false
    container_has_env "$name" "POSTGRES_HOST=db" || judge0_runtime_matches=false
    container_has_env "$name" "REDIS_HOST=redis" || judge0_runtime_matches=false
    container_has_env "$name" "POSTGRES_PASSWORD=$postgres_password" || judge0_runtime_matches=false
    container_has_env "$name" "REDIS_PASSWORD=$redis_password" || judge0_runtime_matches=false
    container_has_mount_destination "$name" "/judge0.conf" && judge0_runtime_matches=false
  done
  if curl -fsS "http://127.0.0.1:2358/languages" >/dev/null 2>&1 \
    && [[ "$judge0_runtime_matches" == true ]]; then
    log "Reusing healthy Judge0"
    return 0
  fi
  log "Recreating Judge0 server and workers with $JUDGE0_IMAGE"
  JUDGE0_IMAGE="$JUDGE0_IMAGE" docker compose -f "$JUDGE_DIR/docker-compose.yml" \
    up -d --force-recreate server workers
  wait_http "Judge0" "http://127.0.0.1:2358/languages" 90
}
reset_judge0() {
  [[ "${1:-}" == "--confirm" ]] \
    || fail "This deletes Judge0 PostgreSQL and Redis data. Re-run: ./deploy_prod.sh reset-judge0 --confirm"
  "$ROOT_DIR/deploy/render_judge0_config.sh" "$INFRA_ENV" "$JUDGE_CONFIG"
  log "Deleting Judge0 containers and data volumes"
  JUDGE0_IMAGE="$JUDGE0_IMAGE" docker compose -f "$JUDGE_DIR/docker-compose.yml" down -v
  JUDGE0_IMAGE="$JUDGE0_IMAGE" docker compose -f "$JUDGE_DIR/docker-compose.yml" up -d
  wait_http "Judge0" "http://127.0.0.1:2358/languages" 90
}
install_and_build() {
  if [[ ! -x "$ROOT_DIR/.venv/bin/python" ]]; then
    python3 -m venv "$ROOT_DIR/.venv"
  fi
  "$ROOT_DIR/.venv/bin/python" -m pip install -r "$ROOT_DIR/backend/requirements.txt"
  uv sync --project "$ROOT_DIR/agent_service_v2" --frozen --no-dev
  (
    cd "$ROOT_DIR/frontend"
    npm ci
    VITE_API_BASE_URL=/api/v1 VITE_USE_MOCK=false npm run build
  )
  [[ -f "$ROOT_DIR/frontend/dist/index.html" ]] || fail "Frontend build did not create dist/index.html"
}
process_running() {
  local pid_file="$1" marker="$2" pid
  [[ -f "$pid_file" ]] || return 1
  pid="$(<"$pid_file")"
  kill -0 "$pid" >/dev/null 2>&1 || return 1
  tr '\0' ' ' <"/proc/$pid/cmdline" | grep -Fq "$marker"
}
start_process() {
  local name="$1" pid_file="$2" log_file="$3" workdir="$4" marker="$5"
  shift 5
  process_running "$pid_file" "$marker" && fail "$name is already running"
  if [[ -f "$pid_file" ]]; then rm -f "$pid_file"; fi
  (
    cd "$workdir"
    nohup "$@" >>"$log_file" 2>&1 &
    echo $! >"$pid_file"
  )
  sleep 1
  process_running "$pid_file" "$marker" || fail "$name exited during startup; see $log_file"
  log "$name started with PID $(<"$pid_file")"
}
stop_process() {
  local name="$1" pid_file="$2" marker="$3" pid
  if ! process_running "$pid_file" "$marker"; then
    rm -f "$pid_file"
    log "$name is not running"
    return 0
  fi
  pid="$(<"$pid_file")"
  kill "$pid"
  for _ in $(seq 1 20); do
    kill -0 "$pid" >/dev/null 2>&1 || break
    sleep 0.5
  done
  if kill -0 "$pid" >/dev/null 2>&1; then kill -KILL "$pid"; fi
  rm -f "$pid_file"
  log "$name stopped"
}
start_apps() {
  local qdrant_port redis_port
  mkdir -p "$RUN_DIR" "$LOG_DIR"
  [[ -x "$ROOT_DIR/.venv/bin/python" ]] || fail "Run deploy first to install Backend dependencies"
  [[ -x "$ROOT_DIR/agent_service_v2/.venv/bin/uvicorn" ]] || fail "Run deploy first to install Agent dependencies"
  [[ -f "$ROOT_DIR/frontend/dist/index.html" ]] || fail "Run deploy first to build Frontend"
  qdrant_port="$(env_value "$INFRA_ENV" QDRANT_HTTP_PORT 2>/dev/null || true)"
  redis_port="$(env_value "$INFRA_ENV" REDIS_PORT 2>/dev/null || true)"
  start_process "Agent Service" "$RUN_DIR/agent.pid" "$LOG_DIR/agent.log" \
    "$ROOT_DIR/agent_service_v2" "agent_service_v2.main:app" \
    env BACKEND_INTERNAL_AGENT_TOKEN="$(env_value "$INFRA_ENV" INTERNAL_AGENT_TOKEN)" \
    QDRANT_URL="http://127.0.0.1:${qdrant_port:-6333}" \
    AGENTSCOPE_REDIS_PORT="${redis_port:-6379}" \
    COURSE_CATALOG_STORAGE_ROOT="$ROOT_DIR/backend/storage/course_catalogs" \
    "$ROOT_DIR/agent_service_v2/.venv/bin/uvicorn" agent_service_v2.main:app \
    --env-file "$INFRA_ENV" --host 127.0.0.1 --port "$AGENT_PORT"
  wait_http "Agent Service" "http://127.0.0.1:$AGENT_PORT/openapi.json" 90
  start_process "Backend" "$RUN_DIR/backend.pid" "$LOG_DIR/backend.log" \
    "$ROOT_DIR/backend" "app.main:app" \
    env QDRANT_URL="http://127.0.0.1:${qdrant_port:-6333}" \
    COURSE_CATALOG_STORAGE_ROOT="$ROOT_DIR/backend/storage/course_catalogs" \
    "$ROOT_DIR/.venv/bin/python" -m uvicorn app.main:app --env-file "$INFRA_ENV" \
    --host 0.0.0.0 --port "$BACKEND_PORT"
  wait_http "Backend" "http://127.0.0.1:$BACKEND_PORT/health" 60
  wait_http "Frontend" "http://127.0.0.1:$BACKEND_PORT/" 30
}
stop_apps() {
  stop_process "Backend" "$RUN_DIR/backend.pid" "app.main:app"
  stop_process "Agent Service" "$RUN_DIR/agent.pid" "agent_service_v2.main:app"
}
show_status() {
  for item in "Backend:$RUN_DIR/backend.pid:app.main:app" "Agent:$RUN_DIR/agent.pid:agent_service_v2.main:app"; do
    IFS=: read -r name pid_file marker <<<"$item"
    if process_running "$pid_file" "$marker"; then echo "$name: running"; else echo "$name: stopped"; fi
  done
  docker ps -a --filter 'name=eduagent-' --filter 'name=judge0-v1130-' \
    --format 'container: {{.Names}} | {{.Status}}'
}
command="${1:---help}"
case "$command" in
  --help|-h) usage ;;
  check) preflight ;;
  prepare-infra)
    preflight
    ensure_core_infrastructure
    ensure_judge0
    ;;
  deploy)
    preflight
    ensure_core_infrastructure
    ensure_judge0
    install_and_build
    stop_apps
    start_apps
    ;;
  start)
    preflight
    ensure_core_infrastructure
    ensure_judge0
    start_apps
    ;;
  stop) stop_apps ;;
  restart) stop_apps; start_apps ;;
  status) show_status ;;
  reset-judge0)
    preflight
    reset_judge0 "${2:-}"
    ;;
  logs)
    case "${2:-}" in
      backend) tail -F "$LOG_DIR/backend.log" ;;
      agent) tail -F "$LOG_DIR/agent.log" ;;
      *) tail -F "$LOG_DIR/backend.log" "$LOG_DIR/agent.log" ;;
    esac
    ;;
  *) usage >&2; exit 2 ;;
esac
