# 交接前全仓死代码清理、跨层安全收尾与 OpenAPI 契约刷新

## Goal

在项目移交下一位开发者前，彻底清理仓库中已过时的审计报告、本地测试残留数据库、前端 0 引用的死代码/死组件与一次性补丁脚本；修复前端图标问号退化、双套错误解析函数分裂、文件下载 URL 泄露 JWT、Webhook 空密钥放行与 SSRF、Agent 传输层异常逃逸及本地 Vite 端口漂移隐患；最后基于最新代码自动导出双端 OpenAPI 契约文档并补充 `README.md` 开发者与 Trellis 规范交接导览。

## Requirements

### 1. 过时报告、残留文件与前端 0 引用死代码清理 (`repo` & `frontend`)
- **清理根目录与历史审查报告**：
  - 删除本地残留未跟踪的 SQLite 文件：`test_learning_path_fb.db`；
  - 删除已过时的 4 份代码审查报告（核心问题已修复并沉淀至 `.trellis/spec/`）：
    - `reports/review-backend.md`
    - `reports/review-frontend.md`
    - `reports/review-integration.md`
    - `reports/review-agent-service-v2.md`
- **清理 `frontend/` 根目录一次性临时脚本与报告**：
  - 删除 `frontend/fix_aichat.py`、`frontend/patch_aichat.py`、`frontend/update_icons.py`、`frontend/update_teacher_console.cjs`、`frontend/test_mermaid.cjs`、`frontend/test_mermaid2.cjs`、`frontend/test_regex.js`、`frontend/test_regex2.js`、`frontend/前端页面字段与布局结构数据报告.md`；
  - 删除 `frontend/.superpowers/` 目录，并在 `frontend/.gitignore` 中追加 `.superpowers/`。
- **清理 `frontend/src/` 与 `frontend/public/` 下 100% 零引用的死代码与静态资源**：
  - 删除重复且无任何业务引用的服务层：`frontend/src/services/catalogService.js` 及 `frontend/src/services/catalogService.test.js`（真实业务统一使用 `frontend/src/api/services/catalog.js`）；
  - 删除 4 个零引用死组件：
    - `frontend/src/components/personalized/GenerateModal.jsx`
    - `frontend/src/components/effects/EffectsSuggestionsCard.jsx`
    - `frontend/src/components/chat/SidebarResources.jsx`
    - `frontend/src/components/quiz/CodingQuestionCard.jsx`
  - 删除 4 个零引用静态文件：
    - `frontend/src/assets/react.svg`
    - `frontend/src/assets/vite.svg`
    - `frontend/public/icons.svg`
    - `frontend/public/test.html`

### 2. 前端图标映射补齐与错误解析工具合并 (`frontend`)
- **补齐 `frontend/src/components/Icon.jsx` 缺失的图标映射 (`Frontend P1-3`)**：
  - 在 `materialToLucide` 字典中补齐页面实际使用但此前退化为问号 `HelpCircle` 的全部图标：
    - `'chevron_left': 'ChevronLeft'`
    - `'folder_open': 'FolderOpen'`
    - `'download': 'Download'`
    - `'person': 'User'`
    - `'edit': 'Edit'`
    - `'chat_bubble_outline': 'MessageCircle'`
    - `'groups': 'Users'`
    - `'upload_file': 'FileUp'`
    - `'verified': 'BadgeCheck'`
    - `'check_circle_outline': 'CheckCircle2'`
    - `'schedule': 'Clock'`
    - `'explore': 'Compass'`
    - `'sync': 'RefreshCw'`
    - `'help': 'HelpCircle'`
    - `'radio_button_unchecked': 'Circle'`
    - `'radio_button_checked': 'CheckCircle2'`
    - `'check_box': 'CheckSquare'`
    - `'code_blocks': 'Code2'`
    - `'calendar_month': 'Calendar'`
    - `'video_library': 'Video'`
    - `'speed': 'Gauge'`
    - `'fact_check': 'ClipboardCheck'`
    - `'warning_amber': 'AlertTriangle'`
- **合并双套错误消息解析函数 (`Frontend P1-8`)**：
  - 将 `frontend/src/api/error.js` 中的 FastAPI 422 校验数组格式化逻辑（`formatValidationError`、`fieldLabels`）完整合并进 `frontend/src/utils/apiError.js`，并在 `frontend/src/utils/apiError.js` 中同时导出 `getErrorMessage` 与别名 `getApiErrorMessage`；
  - 将 `frontend/src/pages/Login.jsx` 与 `frontend/src/pages/Register.jsx` 的导入路径改为 `../utils/apiError`；
  - 物理删除 `frontend/src/api/error.js`，并在 `frontend/src/utils/__tests__/apiError.test.js` 中补充对 FastAPI 422 数组详情格式化与别名导出的单测覆盖。

### 3. 跨层安全与网络健壮性收尾 (`frontend` ↔ `backend` ↔ `agent_service_v2`)
- **消除会话文件下载 URL 中的 JWT 泄露 (`Integration P0-3`)**：
  - 在 `backend/app/api/deps.py` 的 `get_download_user` 中移除 `token: str | None = Query(None)` 查询参数（直接委托或等同于 `get_current_user`，仅接受 `Authorization: Bearer <token>` 请求头）；
  - 在 `frontend/src/components/common/MarkdownViewer.jsx` 与 `frontend/src/components/workspace/plugins/MarkdownViewer.jsx` 中：
    - 移除在 `downloadUrl` 后拼接 `?token=...` 的逻辑（保留纯粹的 `${apiBaseUrl}/tutoring/conversations/${activeSession}/files/${encodeURIComponent(filename)}` 作为 `href`）；
    - 为该 `<a href={downloadUrl} download={filename} ...>` 绑定 `onClick` 处理器：`e.preventDefault()` 后通过 `apiClient.get(\`/tutoring/conversations/\${activeSession}/files/\${encodeURIComponent(filename)}\`, { responseType: 'blob' })` 发起带 Bearer Header 的请求，再用 `URL.createObjectURL(blob)` 触发浏览器下载并释放 URL；
    - 更新 `frontend/src/components/workspace/plugins/MarkdownViewer.test.jsx`，断言下载链接 `href` 包含 `/tutoring/conversations/conversation-1/files/` 且**不包含** `token=`。
- **Webhook 鉴权防空密钥放行与 SSRF 校验 (`Integration P0-2` & `Agent P0-3`)**：
  - 在 `backend/app/api/deps.py` 的 `verify_webhook_secret` 中：当 `not settings.WEBHOOK_SECRET` 且 `not getattr(settings, "DEBUG", False)`（生产模式）时，抛出 `HTTPException(status_code=503, detail={"code": 50300, "message": "Webhook secret 未配置", "data": None})`；`DEBUG=True` 时保持开发/单测兼容；
  - 在 `agent_service_v2/src/agent_service_v2/api/knowledge.py` 的 `ResourceGenerationRequest` 中为 `webhook_url` 增加 `@field_validator("webhook_url")`：校验 URL 必须为合法的 `http` 或 `https` 协议且包含非空 `netloc`，并且禁止访问云元数据地址 `169.254.169.254`。
- **Agent 调用 Backend 客户端传输异常与非 JSON 响应兜底 (`Agent P0-2`)**：
  - 在 `agent_service_v2/src/agent_service_v2/tools/backend_learning_client.py` 的 `BackendLearningClient.post_json` 中：
    - 捕获 `httpx.TransportError`（当 `isinstance(exc, httpx.TimeoutException)` 时抛出 `BackendLearningClientError("backend_timeout")`，其余如 `ConnectError`、`ReadError`、`RemoteProtocolError` 统一抛出 `BackendLearningClientError("backend_unavailable")`）；
    - 对 `response.json()` 用 `try ... except ValueError as exc:` 包裹，非 JSON 响应时抛出 `BackendLearningClientError("backend_bad_response", status_code=response.status_code)`；
    - 在 `agent_service_v2/tests/test_backend_learning_client.py` 中新增对 `httpx.ReadError` 与非 JSON HTML 响应（如 200 OK 但 body 为 `<html>...`）的单元测试。
- **本地开发端口锁定防漂移 (`Integration P0-4`)**：
  - 在 `frontend/vite.config.js` 的 `server` 配置中增加 `strictPort: true`；
  - 在 `start_all.sh` 的 `start()` 函数中增加 `ensure_port_free "$FRONTEND_PORT" "Frontend"`。

### 4. OpenAPI 契约自动同步与 README 开发者交接导览 (`docs` & `README.md`)
- **自动重新导出双端 OpenAPI 契约文档**：
  - 从 `backend` 的 `app.main:app.openapi()` 导出最新 JSON（`indent=2, ensure_ascii=False`）写入 `docs/10-client-api/Client-API.openapi.json`；
  - 从 `agent_service_v2` 的 `agent_service_v2.main:app.openapi()` 导出最新 JSON（`indent=2, ensure_ascii=False`）写入 `docs/20-agent-api/Agent-Service.openapi.json`。
- **在 `README.md` 补充《开发者交接与 Trellis 规范导览》章节**：
  - 简明扼要说明仓库三大模块目录（`backend/`、`agent_service_v2/`、`frontend/`）、`.trellis/spec/` 架构红线与规范体系、全仓唯一门禁命令 `python check_all.py` 以及如何通过 Trellis 开启新开发任务。

## Acceptance Criteria

- [x] 根目录 `test_learning_path_fb.db`、`reports/review-*.md`、`frontend/` 下全部 9 个临时脚本/旧报告、`.superpowers/`、4 个死组件、重复的 `src/services/catalogService*` 与 4 个无引用静态文件全部清除。
- [x] `Icon.jsx` 包含全部 22 个新增图标映射，且所有映射到 `lucide-react` 真实存在的导出组件。
- [x] `frontend/src/api/error.js` 已删除，`Login.jsx` 与 `Register.jsx` 统一使用 `utils/apiError.js`，且 422 校验错误格式化单测通过。
- [x] 会话文件下载不再通过 URL Query 暴露 `?token=`，后端 `get_download_user` 不再接收 `Query` token 参数。
- [x] 生产环境（`DEBUG=False`）下空白 `WEBHOOK_SECRET` 请求 `/api/v1/webhooks/agent` 返回 503；`ResourceGenerationRequest.webhook_url` 拒绝非法协议与 `169.254.169.254`；`BackendLearningClient.post_json` 完整捕获 `TransportError` 与 JSON `ValueError`。
- [x] `docs/10-client-api/Client-API.openapi.json` 与 `docs/20-agent-api/Agent-Service.openapi.json` 与当前代码路由 100% 同步。
- [x] `python check_all.py`（6 大门禁）与 `cd frontend && npm run test:unit` 100% 通过。
