#!/usr/bin/env bash
set -Eeuo pipefail

ENV_FILE="${1:-}"
SCHEMA_FILE="${2:-}"
DEFAULT_ADMIN_ID="admin000000000000000000000001"
DEFAULT_ADMIN_EMAIL="admin@admin.com"
DEFAULT_ADMIN_USERNAME="admin"
DEFAULT_PASSWORD_HASH='$2b$12$k4zj0wRQqBBbfYHl3YGhJOjYhdXZijOubyMDT1Lk2OmuDP1D5kOcm'

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"; }
fail() { echo "ERROR: $*" >&2; exit 1; }
env_value() {
  local key="$1"
  awk -F= -v key="$key" '$1 == key {sub(/^[^=]*=/, ""); print; exit}' "$ENV_FILE"
}
mysql_query() {
  docker exec -e MYSQL_PWD="$db_password" eduagent-mysql \
    mysql -N -B -uroot "$db_name" -e "$1"
}

[[ -f "$ENV_FILE" ]] || fail "环境配置不存在：$ENV_FILE"
[[ -f "$SCHEMA_FILE" ]] || fail "数据库结构文件不存在：$SCHEMA_FILE"
db_password="$(env_value DB_PASSWORD)"
db_name="$(env_value DB_NAME)"
db_name="${db_name:-duagent}"
[[ -n "$db_password" && "$db_password" != replace-* ]] || fail "请先配置 DB_PASSWORD"
[[ "$db_name" =~ ^[A-Za-z0-9_]+$ ]] || fail "DB_NAME 只能包含字母、数字和下划线"

users_table_exists="$(mysql_query \
  "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema=DATABASE() AND table_name='users';")"
if [[ "$users_table_exists" != "1" ]]; then
  log "数据库结构缺失，正在初始化"
  docker exec -e MYSQL_PWD="$db_password" -i eduagent-mysql \
    mysql -uroot "$db_name" <"$SCHEMA_FILE"
fi

active_admin_count="$(mysql_query \
  "SELECT COUNT(*) FROM users WHERE role='admin' AND is_active=1 AND is_deleted=0;")"
if [[ "$active_admin_count" =~ ^[1-9][0-9]*$ ]]; then
  log "已存在有效管理员，保持原账号和密码不变"
  exit 0
fi

identity_conflict_count="$(mysql_query \
  "SELECT COUNT(*) FROM users WHERE id='$DEFAULT_ADMIN_ID' OR username='$DEFAULT_ADMIN_USERNAME' OR email='$DEFAULT_ADMIN_EMAIL';")"
if [[ "$identity_conflict_count" != "0" ]]; then
  fail "默认管理员标识已被占用，但当前没有有效管理员；为避免静默提权，部署已停止"
fi

insert_sql="$(cat <<SQL
INSERT INTO users (
  id, username, email, password_hash, real_name, student_id, role,
  major, grade, guidance_level, is_active, is_deleted, create_by
) VALUES (
  '$DEFAULT_ADMIN_ID', '$DEFAULT_ADMIN_USERNAME', '$DEFAULT_ADMIN_EMAIL',
  '$DEFAULT_PASSWORD_HASH', '系统管理员', 'ADMIN001', 'admin',
  '', '', 'L2', 1, 0, 'system'
);
SQL
)"
mysql_query "$insert_sql" >/dev/null

created_count="$(mysql_query \
  "SELECT COUNT(*) FROM users WHERE email='$DEFAULT_ADMIN_EMAIL' AND role='admin' AND is_active=1 AND is_deleted=0;")"
[[ "$created_count" == "1" ]] || fail "默认管理员创建后校验失败"
log "已创建默认管理员：admin@admin.com / Admin123456；首次登录后必须立即修改密码"
