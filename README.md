# DUagent 生产部署指南

这份分支只保留运行代码和生产部署脚本。完成部署后，通过 Backend 的 `8001` 端口同时访问前端页面和 API；Agent Service 只监听本机 `8002` 端口。

## 1. 部署结构

| 服务 | 运行方式 | 默认地址 |
| --- | --- | --- |
| Frontend | 构建后由 Backend 同源托管 | `http://服务器IP:8001` |
| Backend | 宿主机 Python 进程 | `0.0.0.0:8001` |
| Agent Service | 宿主机 Python 进程 | `127.0.0.1:8002` |
| MySQL | Docker | `127.0.0.1:3306` |
| Qdrant | Docker | `127.0.0.1:6333/6334` |
| AgentScope Redis | Docker | `127.0.0.1:6379` |
| Judge0 | Docker | `127.0.0.1:2358` |

部署脚本会复用同名的已有容器，只创建缺失的 Docker 依赖。执行 `stop` 不会停止数据库、Qdrant、Redis 或 Judge0。

## 2. 准备服务器

服务器需要以下命令：

```bash
docker --version
docker compose version
docker info
python3 --version
npm --version
uv --version
curl --version
```

要求：

- Docker Compose 必须是 v2，即使用 `docker compose` 命令。
- 当前用户必须有权限执行 `docker info`。
- Python 需要支持创建 `venv`。
- Node.js/npm 用于构建前端，`uv` 用于安装 Agent Service。

### 2.1 自动检查与安装（可选）

初始化脚本仅支持 Ubuntu 24.04+ 的 amd64/arm64。先执行只读检查：

```bash
./bootstrap_ubuntu.sh check
```

没有干净环境时，可以查看计划但不修改系统：

```bash
./bootstrap_ubuntu.sh dry-run
```

只有确认需要安装缺失工具时才执行：

```bash
sudo ./bootstrap_ubuntu.sh install
```

安装模式会跳过满足要求的现有工具，不卸载、不降级，也不操作项目容器和数据卷。检测到与 Docker CE 冲突的软件包时会停止并要求人工处理。若脚本把当前用户加入 `docker` 组，需要退出服务器会话并重新登录，再执行：

```bash
./bootstrap_ubuntu.sh check
./deploy_prod.sh check
```

安装源采用 [Docker 官方 Ubuntu 仓库](https://docs.docker.com/engine/install/ubuntu/)、[NodeSource Node.js 22 仓库](https://github.com/nodesource/distributions) 和 [Astral uv 官方安装器](https://docs.astral.sh/uv/getting-started/installation/)。

## 3. 拉取生产分支

首次部署：

```bash
git clone \
  --branch release/prod \
  --single-branch \
  https://github.com/coding-leaf/DUagent.git \
  DUagent-prod

cd DUagent-prod
git branch --show-current
git log -1 --oneline
```

当前分支应为 `release/prod`。

已有目录更新：

```bash
cd DUagent-prod
git pull --ff-only origin release/prod
```

## 4. 配置唯一的 `.env`

生产部署只维护根目录一份 `.env`。首次执行预检时，脚本会自动复制中文模板并将权限设置为 `600`：

```bash
./deploy_prod.sh check
nano .env
```

首次预检会因为 `.env` 仍有占位值而停止，这是预期行为。脚本不会覆盖已经存在的 `.env`；填写完成后，在下一节重新执行预检即可。

模板已用中文标记填写要求。至少需要确认以下配置：

- `DB_PASSWORD`：新 MySQL 使用新强密码；复用已有 `eduagent-mysql` 时填写其真实密码。
- `JWT_SECRET_KEY`：Backend 登录令牌签名密钥。
- `WEBHOOK_SECRET`：Backend 与 Agent Service 共用的 Webhook 密钥。
- `INTERNAL_AGENT_TOKEN`：Backend 与 Agent Service 共用的内部接口令牌。
- `LLM_BASE_URL`、`LLM_API_KEY`、`LLM_MODEL`：对话模型配置。
- `EMBEDDING_BASE_URL`、`EMBEDDING_API_KEY`、`EMBEDDING_MODEL`：向量模型配置。
- `JUDGE0_POSTGRES_PASSWORD`、`JUDGE0_REDIS_PASSWORD`：Judge0 内部独立密码。

可使用下面的命令生成随机密钥，每个配置分别生成一次：

```bash
openssl rand -hex 32
```

检查是否仍有未替换的值：

```bash
grep -En '^[A-Z][A-Z0-9_]*=(replace-with-|.*your-)' .env
```

没有输出才继续。部署脚本也会执行同样的占位值检查，避免使用模板密码启动服务。`.env` 已被 Git 忽略，不要提交、截图或发送其中的真实密码和 API Key。

## 5. 检查并部署

先执行预检：

```bash
./deploy_prod.sh check
```

看到 `Preflight passed` 后正式部署：

```bash
./deploy_prod.sh deploy
```

首次部署会安装 Backend 和 Agent Service 依赖、安装前端依赖并构建页面，耗时比后续更新长。部署期间不要中断终端。

脚本的基础设施策略：

- 已存在且正在运行：直接复用。
- 已存在但已停止：自动启动。
- 容器缺失：通过 Compose 自动创建。
- MySQL 中缺少 `users` 表：导入 `backend/schema.sql` 初始化数据库结构。
- 已有有效管理员：保留原账号和密码，不重复创建、不覆盖数据。
- 没有有效管理员且默认标识未被占用：自动补建默认管理员。
- 默认邮箱、用户名或 ID 被普通账号占用：为避免静默提权，停止部署并明确报错。
- Judge0 `2358` 健康检查通过：直接复用现有 Judge0。

数据库初始化或管理员缺失时创建的默认管理员：

```text
账号：admin@admin.com
密码：Admin123456
```

首次登录后立即修改密码。管理员初始化检查是幂等的，后续部署不会重置已有管理员密码。

## 6. 验证部署

查看总体状态：

```bash
./deploy_prod.sh status
```

检查服务：

```bash
curl -fsS http://127.0.0.1:8001/health
curl -fsS http://127.0.0.1:8002/openapi.json >/dev/null && echo "Agent Service 正常"
curl -fsS http://127.0.0.1:2358/languages >/dev/null && echo "Judge0 正常"
```

### Judge0 cgroup v2 验证

本部署使用 `mrkushalsm/judge0:cgv2` 作为 Judge0 server 和 worker 镜像，以兼容仅提供 cgroup v2 的 Docker 主机。该镜像不是 Judge0 官方镜像；首次升级后必须实际执行一次代码提交，不能只检查 `/languages`。

```bash
curl -fsS -X POST 'http://127.0.0.1:2358/submissions?base64_encoded=false&wait=true' \
  -H 'Content-Type: application/json' \
  -d '{"source_code":"print(\"judge0 cgroup v2 ok\")","language_id":71,"stdin":""}'
```

响应中的 `status.id` 应为 `3`，且 `stdout` 应为 `judge0 cgroup v2 ok`。如果执行日志出现 `Failed to create control group /sys/fs/cgroup/memory`，说明当前运行的仍是旧镜像；执行 `./deploy_prod.sh deploy` 会仅重建 Judge0 的 server 和 workers，保留其 PostgreSQL 和 Redis 数据卷。

浏览器访问：

```text
http://服务器IP:8001
```

如果本机可以访问但其他设备不能访问，请检查服务器防火墙或云安全组是否允许 TCP `8001`。MySQL、Qdrant、Redis、Judge0 和 Agent Service 默认只监听本机，不应直接暴露到公网。

## 7. 日常管理

```bash
# 启动已经安装和构建好的应用
./deploy_prod.sh start

# 仅停止 Backend 和 Agent Service
./deploy_prod.sh stop

# 重启 Backend 和 Agent Service
./deploy_prod.sh restart

# 查看状态
./deploy_prod.sh status

# 查看 Backend 日志
./deploy_prod.sh logs backend

# 查看 Agent Service 日志
./deploy_prod.sh logs agent

# 同时查看两侧日志
./deploy_prod.sh logs
```

日志保存在 `.run_logs/prod/`，PID 文件保存在 `.run/prod/`。

## 8. 更新版本

```bash
cd DUagent-prod
git pull --ff-only origin release/prod
./deploy_prod.sh deploy
./deploy_prod.sh status
```

`git pull` 不会覆盖根 `.env`。再次执行 `deploy` 会更新依赖、重新构建前端并重启应用，但不会删除数据库卷。

## 9. 常见问题

### `Preflight passed` 后出现大量安装输出

正常。首次部署需要创建两个 Python 虚拟环境并安装 100 个以上的 Agent 依赖，还会执行 `npm ci` 和 Vite 构建。

### `Backend is not running` 或 `Agent Service is not running`

首次部署在启动前会先尝试停止旧进程。没有旧进程时出现这两行是正常现象，继续观察后续是否出现 `started` 和 `is ready`。

### 前端提示 chunk 大于 500 KB

这是 Vite 的性能提示，不是构建失败。只要最后出现 `built` 和 `Frontend is ready` 即可。

### Backend 或 Agent Service 启动失败

```bash
./deploy_prod.sh logs backend
./deploy_prod.sh logs agent
```

同时检查端口占用：

```bash
ss -lntp | grep -E ':(8001|8002)\b'
```

### Docker 服务异常

```bash
docker ps -a
docker compose --env-file .env -f docker-compose.prod.yml config
```

### Judge0 升级后需要回滚

不要执行 `docker compose down -v`。将 `deploy/judge0/docker-compose.yml` 中 server 和 workers 的 `JUDGE0_IMAGE` 默认值改回 `judge0/judge0:1.13.0`，再执行：

```bash
./deploy_prod.sh deploy
```

这只会重建 Judge0 的 server 和 workers，不会删除 Judge0 的 PostgreSQL 或 Redis 数据卷。

不要使用 `docker compose down -v`，它会删除项目管理的数据卷。

### Qdrant 没有持久化挂载

如果部署输出：

```text
WARNING: existing eduagent-qdrant has no persistent /qdrant/storage mount
```

说明复用的旧 Qdrant 把向量数据写在容器层。当前容器继续运行不受影响，但删除或重建容器可能造成数据丢失。不要直接删除该容器；应先创建快照或备份 `/qdrant/storage`，再迁移到 `eduagent_qdrant_data` 命名卷。

## 10. 安全检查

- 不提交根 `.env`、生成的 Judge0 配置、日志或运行目录。
- 不在聊天、截图、Issue 或日志中暴露 API Key、数据库密码和内部 Token。
- 泄露过的密钥必须在服务商控制台撤销并重新生成，仅删除消息不够。
- 部署后立即修改默认管理员密码。
- 不对公网开放 `3306`、`6333`、`6379`、`8002` 和 `2358`。
- 操作 Docker 数据卷前先备份，并确认当前容器的挂载情况。
