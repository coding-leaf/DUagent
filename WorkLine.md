# WorkLine

## 2026-07-17 — Judge0 cgroup v2 兼容部署

生产部署中的 Judge0 server 和 workers 改用 `mrkushalsm/judge0:cgv2`，并使用主机 cgroup 命名空间，解决仅提供 cgroup v2 的 Docker 主机上旧版 Judge0 无法创建 `/sys/fs/cgroup/memory/box-*` 的问题。

`deploy_prod.sh` 现在同时校验 Judge0 HTTP 健康状态、运行镜像和 cgroup 命名空间；不匹配时只重建 server 和 workers，保留 Judge0 PostgreSQL 与 Redis 数据卷。README 增加了代码实际执行验证和回滚说明。

**验证：** 部署脚本语法检查、Compose 配置解析、部署配置静态契约检查和 `git diff --check` 通过。实际服务器仍需完成 Python、C、C++ 的 Judge0 提交验证后，记录拉取到的不可变镜像摘要。

**接口漂移：** 无。Backend、Agent Service 和 Judge0 API 路径、语言 ID 均未变更。
