# 实施执行计划 (Implementation Plan)

## 执行清单 (Ordered Checklist)

### Step 1: 清理过时报告、残留文件与前端 0 引用死代码
- [x] 1.1 删除根目录残留 `test_learning_path_fb.db` 以及 `reports/review-backend.md`、`reports/review-frontend.md`、`reports/review-integration.md`、`reports/review-agent-service-v2.md`。
- [x] 1.2 删除 `frontend/` 根目录下的 9 个临时文件：`fix_aichat.py`、`patch_aichat.py`、`update_icons.py`、`update_teacher_console.cjs`、`test_mermaid.cjs`、`test_mermaid2.cjs`、`test_regex.js`、`test_regex2.js`、`前端页面字段与布局结构数据报告.md`，删除 `frontend/.superpowers/` 并在 `frontend/.gitignore` 添加 `.superpowers/`。
- [x] 1.3 删除 `frontend/src/services/catalogService.js` 与 `frontend/src/services/catalogService.test.js`（以及空的 `frontend/src/services/` 目录）。
- [x] 1.4 删除 4 个零引用死组件：`frontend/src/components/personalized/GenerateModal.jsx`、`frontend/src/components/effects/EffectsSuggestionsCard.jsx`、`frontend/src/components/chat/SidebarResources.jsx`、`frontend/src/components/quiz/CodingQuestionCard.jsx`。
- [x] 1.5 删除 4 个零引用静态文件：`frontend/src/assets/react.svg`、`frontend/src/assets/vite.svg`、`frontend/public/icons.svg`、`frontend/public/test.html`。

### Step 2: 前端图标映射补齐、错误工具合并与无 Token 泄露下载
- [x] 2.1 在 `frontend/src/components/Icon.jsx` 中补齐 23 个缺失的 Material -> Lucide 图标映射。
- [x] 2.2 将 `frontend/src/api/error.js` 的 422 校验错误格式化逻辑合并到 `frontend/src/utils/apiError.js`（同时导出 `getErrorMessage` 和 `getApiErrorMessage`），修改 `Login.jsx` 和 `Register.jsx` 的导入路径，删除 `frontend/src/api/error.js`，并更新 `frontend/src/utils/__tests__/apiError.test.js`。
- [x] 2.3 修改 `frontend/src/components/common/MarkdownViewer.jsx` 与 `frontend/src/components/workspace/plugins/MarkdownViewer.jsx`：移除 `downloadUrl` 上的 `?token=...` 拼接，改为点击时通过 `apiClient.get(..., { responseType: 'blob' })` 下载文件；同步更新 `frontend/src/components/workspace/plugins/MarkdownViewer.test.jsx` 断言 `href` 不含 `token=`。
- [x] 2.4 在 `frontend/vite.config.js` 的 `server` 中添加 `strictPort: true`，并在 `start_all.sh` 的 `start()` 中添加 `ensure_port_free "$FRONTEND_PORT" "Frontend"`。

### Step 3: 后端与 Agent Service 安全与健壮性收尾
- [x] 3.1 修改 `backend/app/api/deps.py`：
  - `get_download_user` 移除 `token: str | None = Query(None)`，仅通过 `get_current_user`（Bearer Header）鉴权；
  - `verify_webhook_secret` 在 `not settings.WEBHOOK_SECRET` 且 `not getattr(settings, "DEBUG", False)` 时抛出 503 `HTTPException`。
- [x] 3.2 修改 `agent_service_v2/src/agent_service_v2/api/knowledge.py`：为 `ResourceGenerationRequest.webhook_url` 添加 `@field_validator("webhook_url")`，校验 `http/https` 协议、非空 `netloc`，并拒绝 `169.254.169.254` / `metadata.google.internal`。
- [x] 3.3 修改 `agent_service_v2/src/agent_service_v2/tools/backend_learning_client.py`：`post_json` 捕获全部 `httpx.TransportError` 与 `response.json()` 的 `ValueError`，并在 `agent_service_v2/tests/test_backend_learning_client.py` 中补充对应单测。

### Step 4: 自动刷新双端 OpenAPI 契约并更新 `README.md`
- [x] 4.1 运行 Python 脚本从 `backend` (`app.main:app.openapi()`) 和 `agent_service_v2` (`agent_service_v2.main:app.openapi()`) 导出最新 OpenAPI JSON 至 `docs/10-client-api/Client-API.openapi.json` 和 `docs/20-agent-api/Agent-Service.openapi.json`。
- [x] 4.2 在 `README.md` 补充简洁的《开发者交接与架构规范导览（Trellis 工作流）》章节。

---

## 验证门禁 (Validation Gates)

```bash
# 1. 全仓统一门禁（Frontend ESLint + Build, Backend & Agent Ruff, Backend & Agent Pytest）
python -X utf8 check_all.py

# 2. 前端单元测试
cd frontend && npm run test:unit
```
