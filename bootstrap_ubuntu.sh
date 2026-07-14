#!/usr/bin/env bash
set -Eeuo pipefail

OS_RELEASE_FILE="${BOOTSTRAP_OS_RELEASE_FILE:-/etc/os-release}"
NODE_SETUP_URL="https://deb.nodesource.com/setup_22.x"
UV_INSTALL_URL="https://astral.sh/uv/install.sh"
DOCKER_GPG_URL="https://download.docker.com/linux/ubuntu/gpg"
FAILURES=0

usage() {
  cat <<'EOF'
Usage: ./bootstrap_ubuntu.sh <command>

Commands:
  check     只读检查系统、版本和当前用户权限
  dry-run   显示可能执行的安装步骤，不修改系统
  install   安装缺失依赖，必须通过 sudo 显式执行
  --help    显示帮助

支持 Ubuntu 24.04+ 的 amd64/arm64。脚本不会操作项目容器或数据卷。
EOF
}

log() { echo "[OK] $*"; }
note() { echo "[INFO] $*"; }
warn() { echo "[WARN] $*" >&2; }
fail() { echo "ERROR: $*" >&2; exit 1; }

os_value() {
  local key="$1"
  awk -F= -v key="$key" '$1 == key {gsub(/^"|"$/, "", $2); print $2; exit}' \
    "$OS_RELEASE_FILE"
}

validate_platform() {
  [[ -r "$OS_RELEASE_FILE" ]] || fail "无法读取系统信息：$OS_RELEASE_FILE"
  local os_id version arch
  os_id="$(os_value ID)"
  version="$(os_value VERSION_ID)"
  [[ "$os_id" == "ubuntu" ]] || fail "仅支持 Ubuntu 24.04+，当前系统：${os_id:-unknown}"
  dpkg --compare-versions "$version" ge 24.04 \
    || fail "仅支持 Ubuntu 24.04+，当前版本：${version:-unknown}"
  arch="$(dpkg --print-architecture)"
  [[ "$arch" == "amd64" || "$arch" == "arm64" ]] \
    || fail "仅支持 amd64/arm64，当前架构：$arch"
  log "平台 Ubuntu $version ($arch)"
}

python_ok() {
  command -v python3 >/dev/null 2>&1 \
    && python3 -c 'import sys, venv; raise SystemExit(sys.version_info < (3, 12))' \
      >/dev/null 2>&1
}

node_ok() {
  command -v node >/dev/null 2>&1 && command -v npm >/dev/null 2>&1 \
    && node -e '
      const [major, minor] = process.versions.node.split(".").map(Number);
      const ok = major > 22 || (major === 22 && minor >= 12) || (major === 20 && minor >= 19);
      process.exit(ok ? 0 : 1);
    '
}

docker_ok() {
  command -v docker >/dev/null 2>&1 \
    && docker compose version >/dev/null 2>&1 \
    && docker info >/dev/null 2>&1
}

docker_cli_ok() {
  command -v docker >/dev/null 2>&1 \
    && docker compose version >/dev/null 2>&1
}

report_check() {
  local name="$1"
  shift
  if "$@"; then
    log "$name"
  else
    warn "$name 缺失、版本不兼容或当前用户无权限"
    FAILURES=$((FAILURES + 1))
  fi
}

run_check() {
  FAILURES=0
  validate_platform
  report_check "curl" command -v curl
  report_check "Python 3.12+ 与 venv" python_ok
  report_check "Node.js/npm（满足 Vite 版本要求）" node_ok
  report_check "uv" command -v uv
  report_check "Docker Engine、Compose v2 与 daemon 权限" docker_ok
  if ((FAILURES > 0)); then
    warn "环境检查未通过：$FAILURES 项需要处理"
    return 1
  fi
  log "环境检查通过"
}

show_dry_run() {
  validate_platform
  note "dry-run 不会修改系统，也不会执行 sudo、apt、systemctl 或用户组变更。"
  note "基础包：ca-certificates curl gnupg python3 python3-venv"
  note "Docker 官方源：$DOCKER_GPG_URL"
  note "Docker 软件包：docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin"
  note "Node.js 22 安装源：$NODE_SETUP_URL"
  note "uv 官方安装器：$UV_INSTALL_URL"
  note "install 模式只处理缺失或版本不兼容的项目，不卸载、不降级现有工具。"
  run_check || true
}

require_root() {
  ((EUID == 0)) || fail "安装系统依赖需要 root，请执行：sudo ./bootstrap_ubuntu.sh install"
}

install_base_packages() {
  note "安装基础包和 Python 3.12 venv"
  apt-get update
  DEBIAN_FRONTEND=noninteractive apt-get install -y \
    ca-certificates curl gnupg python3 python3-venv
  python_ok || fail "系统 python3 不满足 3.12+；请使用 Ubuntu 24.04+"
}

configure_docker_repository() {
  install -m 0755 -d /etc/apt/keyrings
  curl -fsSL "$DOCKER_GPG_URL" -o /etc/apt/keyrings/docker.asc
  chmod a+r /etc/apt/keyrings/docker.asc
  local codename arch
  codename="$(os_value UBUNTU_CODENAME)"
  [[ -n "$codename" ]] || codename="$(os_value VERSION_CODENAME)"
  arch="$(dpkg --print-architecture)"
  printf '%s\n' \
    'Types: deb' \
    'URIs: https://download.docker.com/linux/ubuntu' \
    "Suites: $codename" \
    'Components: stable' \
    "Architectures: $arch" \
    'Signed-By: /etc/apt/keyrings/docker.asc' \
    >/etc/apt/sources.list.d/docker.sources
  apt-get update
}

detect_docker_conflicts() {
  local package
  local conflicts=()
  for package in docker.io docker-compose docker-compose-v2 podman-docker containerd runc; do
    if dpkg-query -W -f='${db:Status-Abbrev}' "$package" 2>/dev/null | grep -q '^ii'; then
      conflicts+=("$package")
    fi
  done
  ((${#conflicts[@]} == 0)) || fail \
    "检测到与 Docker CE 冲突的软件包：${conflicts[*]}；本脚本不会自动卸载，请按 Docker 官方文档人工处理"
}

install_docker() {
  if docker_cli_ok; then
    systemctl enable --now docker
    log "Docker 已满足要求，跳过安装"
    return
  fi
  detect_docker_conflicts
  note "配置 Docker 官方 APT 仓库"
  configure_docker_repository
  DEBIAN_FRONTEND=noninteractive apt-get install -y \
    docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
  systemctl enable --now docker
}

ensure_docker_user_access() {
  local target_user="${SUDO_USER:-}"
  if [[ -n "$target_user" && "$target_user" != "root" ]]; then
    getent group docker >/dev/null || groupadd docker
    if ! id -nG "$target_user" | tr ' ' '\n' | grep -qx docker; then
      usermod -aG docker "$target_user"
      warn "$target_user 已加入 docker 组，请重新登录后再执行普通用户检查"
    fi
  fi
}

install_node() {
  if node_ok; then
    log "Node.js/npm 已满足要求，跳过安装"
    return
  fi
  local setup_script
  setup_script="$(mktemp)"
  trap 'rm -f "$setup_script"' EXIT
  note "安装 Node.js 22"
  curl -fsSL "$NODE_SETUP_URL" -o "$setup_script"
  bash "$setup_script"
  DEBIAN_FRONTEND=noninteractive apt-get install -y nodejs
  node_ok || fail "Node.js/npm 安装后仍不满足 Vite 版本要求"
  rm -f "$setup_script"
  trap - EXIT
}

install_uv() {
  if command -v uv >/dev/null 2>&1; then
    log "uv 已存在，跳过安装"
    return
  fi
  local installer
  installer="$(mktemp)"
  trap 'rm -f "$installer"' EXIT
  note "安装 uv 到 /usr/local/bin"
  curl -fsSL "$UV_INSTALL_URL" -o "$installer"
  env UV_INSTALL_DIR=/usr/local/bin UV_NO_MODIFY_PATH=1 sh "$installer"
  command -v uv >/dev/null 2>&1 || fail "uv 安装失败"
  rm -f "$installer"
  trap - EXIT
}

install_missing() {
  require_root
  validate_platform
  install_base_packages
  install_docker
  ensure_docker_user_access
  install_node
  install_uv
  run_check
  log "系统依赖安装完成；接下来执行 ./deploy_prod.sh check"
}

case "${1:---help}" in
  check) run_check ;;
  dry-run) show_dry_run ;;
  install) install_missing ;;
  --help|-h) usage ;;
  *) usage >&2; exit 2 ;;
esac
