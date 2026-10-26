# DUagent 稳定性收尾与新人交接前修复任务

## Goal

在维持现有三端架构（Frontend → Backend → Agent Service）不变、不新增业务功能的前提下，最小范围修复已核实的四项稳定性与安全问题：
1. **P1-01 前端文件下载回归**：修复两个 `MarkdownViewer.jsx` 因未适配 `apiClient` 响应拦截器已解包 `response.data` 而再次读取 `.data` 导致 `URL.createObjectURL(undefined)` 报错的问题；
2. **P1-02 Webhook 地址安全边界与生产配置校验**：消除 Backend 使用客户端可控 `request.base_url`（Host 头）构造 Webhook 地址的隐患，改为从受信任内部配置生成；在 Agent Service 实施严格的受信任回调目标白名单校验（而非仅黑名单）；并在生产配置与部署预检中强制校验 `DEBUG`、`WEBHOOK_SECRET`、`JWT_SECRET_KEY`；
3. **P2-01 题库批量生成部分失败时的误删边界**：将 `catalog_quiz_generation_service.py` 的旧题软删除条件从单纯按 `knowledge_point` 匹配收窄为按已完成节点的 `(chapter, knowledge_point)` 组合精确限定，防止跨章节同名知识点被误删；
4. **P2-02 质量门禁与回归测试补齐**：将前端 Vitest 单元测试（`frontend-tests`）纳入 `check_all.py` 默认门禁（共 7 项），完善 `--fast` 语义与说明，新增 GitHub Actions CI 工作流（`.github/workflows/ci.yml`），并为上述三项核心修复补齐自动化回归测试。

## Requirements

### 1. P1-01：前端文件下载回归修复 (`frontend`)
- **涉及文件**：
  - `frontend/src/components/common/MarkdownViewer.jsx`
  - `frontend/src/components/workspace/plugins/MarkdownViewer.jsx`
  - `frontend/src/components/common/MarkdownViewer.test.jsx`
  - `frontend/src/components/workspace/plugins/MarkdownViewer.test.jsx`
- **修复要求**：
  - 由于 `frontend/src/api/client.js` 响应拦截器已执行 `return response.data`，`apiClient.get(url, { responseType: 'blob' })` 返回值本身即为 `Blob`（或测试桩中的响应值）。
  - 在两个 `MarkdownViewer.jsx` 的 `handleArtifactDownload` 中，将返回值解包兼容处理：
    `const blob = response instanceof Blob ? response : (response?.data instanceof Blob ? response.data : new Blob([response?.data ?? response ?? '']));`
    再传入 `URL.createObjectURL(blob)`，并在点击后调用 `URL.revokeObjectURL(blobUrl)`。
  - 保留 `Authorization: Bearer` Header 鉴权，严禁恢复 URL Query `?token=`。
  - 确保 Markdown 普通外链（`target="_blank"`）和锚点链接（`#heading`）行为不受影响。
  - 在 `common/MarkdownViewer.test.jsx` 与 `workspace/plugins/MarkdownViewer.test.jsx` 中补充真实点击下载测试：模拟 `apiClient.get` 返回 `Blob` 实例（而非 `{ data: Blob }`），触发 `fireEvent.click`，断言 `apiClient.get` 参数正确、`URL.createObjectURL` 收到 `Blob` 实例、`URL.revokeObjectURL` 被调用，且普通外链与锚点链接渲染正常。

### 2. P1-02：Webhook 地址安全边界与生产密钥校验 (`backend` & `agent_service_v2` & `deploy`)
- **涉及文件**：
  - `backend/app/core/config.py`
  - `backend/app/core/security.py`
  - `backend/app/api/v1/personalized_resources.py`
  - `backend/app/api/v1/resources.py`
  - `backend/app/api/v1/catalogs.py`
  - `agent_service_v2/src/agent_service_v2/agents/model_provider.py`
  - `agent_service_v2/src/agent_service_v2/api/knowledge.py`
  - `agent_service_v2/src/agent_service_v2/generators/public_resource_flow.py`
  - `deploy_prod.sh`
  - `backend/tests/test_deps_security.py`
  - `agent_service_v2/tests/test_knowledge_api.py`
  - `agent_service_v2/tests/test_public_resource_generation.py`
- **修复要求**：
  1. **Backend 内部回调地址受信生成**：
     - 在 `backend/app/core/config.py::Settings` 中新增 `BACKEND_INTERNAL_BASE_URL: str = "http://127.0.0.1:8001"` 以及属性 `webhook_callback_url -> str`（基于受信任的 `BACKEND_INTERNAL_BASE_URL` 拼接 `/api/v1/webhooks/agent`，绝不使用客户端可控的 `request.base_url` / `Host` 头）；
     - 将 `personalized_resources.py`、`resources.py`、`catalogs.py` 中的 `_webhook_url(request)` 统一改为返回 `settings.webhook_callback_url`（保留 `request: Request | None = None` 签名兼容）。
  2. **Agent Service 回调目标白名单机制**：
     - 在 `agent_service_v2/src/agent_service_v2/agents/model_provider.py::AgentModelSettings` 中设置默认 `BACKEND_INTERNAL_BASE_URL: str = "http://127.0.0.1:8001"` 并支持可选 `WEBHOOK_ALLOWED_ORIGINS: str = ""`（逗号分隔的额外受信 Origin）；
     - 提供统一的 `validate_trusted_webhook_url(url: str, settings: AgentModelSettings | None = None) -> str` 校验函数：
       - 仅允许 `http` 或 `https` 协议且包含非空 `netloc`；
       - 回调路径 `parsed.path` 必须精确为 `/api/v1/webhooks/agent`；
       - 回调 Origin（`scheme://hostname[:port]`）必须命中受信任白名单：由 `settings.BACKEND_INTERNAL_BASE_URL` 解析出的 Origin、本机回环受信地址（`127.0.0.1` / `localhost` 的 `8001` 与 `8000` 端口）以及 `settings.WEBHOOK_ALLOWED_ORIGINS` 中显式配置的 Origin；拒绝一切未授权外部域名、内网探测地址与云元数据地址；
     - 在 `ResourceGenerationRequest.validate_webhook_url`（请求入口）和 `public_resource_flow.py::_post_webhook`（实际发出携带 `X-Webhook-Secret` 的 HTTP 请求前）双层调用 `validate_trusted_webhook_url`。
  3. **生产配置安全护栏（`DEBUG`、`WEBHOOK_SECRET`、`JWT_SECRET_KEY`）**：
     - 在 `backend/app/core/config.py::Settings` 中增加 `validate_production_security()` 方法：当 `not self.DEBUG`（生产模式）时，校验 `JWT_SECRET_KEY`（不得为空、不得为默认值 `"duagent-jwt-secret-change-in-production"`、不得以 `"replace-with-"` 开头且长度 >= 16）以及 `WEBHOOK_SECRET`（不得为空或以 `"replace-with-"` 开头）；
     - 在 `backend/app/core/security.py` 的 `create_token` 与 `decode_token` 中：当 `not settings.DEBUG` 且 `JWT_SECRET_KEY` 为空或仍为默认弱密钥 `"duagent-jwt-secret-change-in-production"` 时，拒绝签发/验签并抛出 HTTP 503；
     - 在 `deploy_prod.sh` 的 `validate_env_placeholders` 中补充校验：生产 `.env` 中 `DEBUG` 必须为 `false`，且 `JWT_SECRET_KEY`、`WEBHOOK_SECRET`、`INTERNAL_AGENT_TOKEN` 均不得为空或等于默认弱密钥 `duagent-jwt-secret-change-in-production`。

### 3. P2-01：题库批量生成部分失败与同名知识点的精确清理边界 (`backend`)
- **涉及文件**：
  - `backend/app/services/catalog_quiz_generation_service.py`
  - `backend/tests/test_admin_catalog_resource_generation.py`
- **修复要求**：
  - 在 `generate_quiz_for_child` 返回字典中增加 `"chapter": chapter`（即同时返回 `"chapter"` 与 `"node_name"`）；
  - 在 `run_quiz_generation_background` 中，收集成功完成节点的组合条件：
    - 若子任务结果包含 `"chapter"` 字段（即使值为空字符串 `""`），构造精确匹配条件 `and_(QuizQuestion.chapter == r["chapter"], QuizQuestion.knowledge_point == r["node_name"])`；
    - 若旧测试桩未提供 `"chapter"` 键（`"chapter" not in r`），回退为 `QuizQuestion.knowledge_point == r["node_name"]` 以保持向后兼容；
    - 使用 `or_(*completed_node_filters)` 限定软删除范围，确保仅清理本次成功重生成的 `(chapter, knowledge_point)` 节点下的旧题；
  - 在多教学班共享 Catalog 场景下，确保清理范围同时覆盖 `QuizQuestion.catalog_id == fanout_catalog_id` 及绑定教学班 `QuizQuestion.course_id.in_(fanout_course_ids)` 下的 `source == "baseline"` 旧题（排除 `inserted_question_ids`），不影响其他 Catalog 或失败节点及不同章节同名知识点的题目；
  - 在 `backend/tests/test_admin_catalog_resource_generation.py` 中新增回归测试：验证第 1 章“概述”节点生成成功、第 2 章同名“概述”节点生成失败（或存在存量题）时，仅第 1 章“概述”的旧基线题被软删除，第 2 章“概述”的存量基线题完好保留（且覆盖多教学班共享 Catalog 的清理契约）。

### 4. P2-02：统一质量门禁增强与 CI 工作流 (`check_all.py` & `.github/workflows/ci.yml`)
- **涉及文件**：
  - `check_all.py`
  - `backend/tests/conftest.py`
  - `.github/workflows/ci.yml`
  - `README.md` / `.trellis/spec/`
- **修复要求**：
  - 在 `check_all.py` 的 `build_checks()` 中新增 `frontend-tests`（`npm run test:unit`，`kind="test"`），使默认完整门禁包含 **7 项检查**（`frontend-lint`, `frontend-build`, `frontend-tests`, `backend-lint`, `backend-tests`, `agent-lint`, `agent-tests`）；
  - `python check_all.py --fast` 保持仅运行 `kind != "test"` 的 4 项静态与构建检查（`frontend-lint`, `frontend-build`, `backend-lint`, `agent-lint`）；同时支持 `--only frontend,backend,agent` 分组别名展开；
  - 在 `backend/tests/conftest.py` 中支持通过环境变量 `TEST_DATABASE_URL` 覆盖默认 MySQL 连接串（未设置时保持现有本地 MySQL 默认值），方便 CI 与不同本地环境注入；
  - 新增 `.github/workflows/ci.yml`：配置 GitHub Actions（Ubuntu + MySQL 8.0 service container `duagent_test` + Python 3.12 + `uv` + Node.js 22），自动执行 `python check_all.py` 全量 7 项门禁；
  - 同步更新 `README.md` 与 `.trellis/spec/` 中的门禁说明与架构约束。

## Acceptance Criteria

- [x] 两个 `MarkdownViewer.jsx` 下载对话文件时正确传递 `Blob` 给 `URL.createObjectURL`，不带 `?token=`，普通外链和锚点不受影响，且新增的模拟点击下载单测通过。
- [x] Backend 回调地址不再受请求 `Host` 头影响；Agent Service 严格按白名单校验 `webhook_url`（必须命中受信 Origin 且路径为 `/api/v1/webhooks/agent`）；生产模式（`DEBUG=False`）下默认/空白 `JWT_SECRET_KEY` 与 `WEBHOOK_SECRET` 被拦截。
- [x] 题库批量生成支持按 `(chapter, knowledge_point)` 精确软删除旧基线题，跨章节同名知识点及失败节点题目不被误删，多教学班共享 Catalog 场景验证通过。
- [x] `python -X utf8 check_all.py` 默认执行全部 7 项检查（含 `frontend-tests` Vitest）并 100% 通过；`--fast` 执行 4 项静态/构建检查；`.github/workflows/ci.yml` 配置完整有效。
