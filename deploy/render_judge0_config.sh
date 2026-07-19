#!/usr/bin/env bash
set -Eeuo pipefail

ENV_FILE="${1:?root .env path is required}"
OUTPUT_FILE="${2:?output path is required}"

env_value() {
  local key="$1"
  awk -F= -v key="$key" '$1 == key {sub(/^[^=]*=/, ""); sub(/\r$/, ""); print; exit}' "$ENV_FILE"
}

postgres_password="$(env_value JUDGE0_POSTGRES_PASSWORD)"
redis_password="$(env_value JUDGE0_REDIS_PASSWORD)"
[[ -n "$postgres_password" && "$postgres_password" != replace-* ]] || {
  echo "ERROR: Set JUDGE0_POSTGRES_PASSWORD in .env" >&2
  exit 1
}
[[ -n "$redis_password" && "$redis_password" != replace-* ]] || {
  echo "ERROR: Set JUDGE0_REDIS_PASSWORD in .env" >&2
  exit 1
}

mkdir -p "$(dirname "$OUTPUT_FILE")"
umask 077
{
  printf 'REDIS_HOST=redis\nREDIS_PORT=6379\nREDIS_PASSWORD=%s\n' "$redis_password"
  printf 'POSTGRES_HOST=db\nPOSTGRES_PORT=5432\nPOSTGRES_DB=judge0\n'
  printf 'POSTGRES_USER=judge0\nPOSTGRES_PASSWORD=%s\n' "$postgres_password"
  printf 'ENABLE_WAIT_RESULT=true\n'
  printf 'COUNT=%s\n' "$(env_value JUDGE0_WORKER_COUNT)"
  printf 'CPU_TIME_LIMIT=%s\n' "$(env_value JUDGE0_CPU_TIME_LIMIT)"
  printf 'WALL_TIME_LIMIT=%s\n' "$(env_value JUDGE0_WALL_TIME_LIMIT)"
  printf 'MEMORY_LIMIT=%s\n' "$(env_value JUDGE0_MEMORY_LIMIT)"
  printf 'MAX_PROCESSES_AND_OR_THREADS=%s\n' "$(env_value JUDGE0_MAX_PROCESSES)"
} >"$OUTPUT_FILE"
