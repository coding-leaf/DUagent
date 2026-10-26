# 实施执行计划 (Implementation Plan)

## 执行清单 (Ordered Checklist)

### Step 1: 修复 P1-01 前端文件下载回归并补齐交互单测 (`frontend`)
- [x] 1.1 修改 `frontend/src/components/common/MarkdownViewer.jsx` 与 `frontend/src/components/workspace/plugins/MarkdownViewer.jsx` 的 `handleArtifactDownload`：兼容 `apiClient.get` 直接返回 `Blob`（响应拦截器已解包 `response.data`）的情况，正确调用 `URL.createObjectURL(blob)` 与 `URL.revokeObjectURL(blobUrl)`。
- [x] 1.2 在 `frontend/src/components/common/MarkdownViewer.test.jsx` 与 `frontend/src/components/workspace/plugins/MarkdownViewer.test.jsx` 中新增模拟 API 返回 `Blob` 并触发点击下载的单测，同时断言普通外链与锚点链接不受影响。
- [x] 1.3 独立验证：运行 `cd frontend && npm run test:unit` 与 `npm run lint`。

### Step 2: 修复 P1-02 Webhook 安全边界与生产配置校验 (`backend` & `agent_service_v2` & `deploy`)
- [x] 2.1 在 `backend/app/core/config.py::Settings` 中添加 `BACKEND_INTERNAL_BASE_URL: str = "http://127.0.0.1:8001"`、`webhook_callback_url` 属性以及 `validate_production_security()` 校验方法；在 `backend/app/core/security.py` 中拦截生产环境（`DEBUG=False`）下的空/默认弱 `JWT_SECRET_KEY`。
- [x] 2.2 修改 `backend/app/api/v1/personalized_resources.py`、`backend/app/api/v1/resources.py`、`backend/app/api/v1/catalogs.py` 的 `_webhook_url`，使其统一返回 `settings.webhook_callback_url`，不再使用 `request.base_url`。
- [x] 2.3 在 `agent_service_v2/src/agent_service_v2/agents/model_provider.py`、`generators/public_resource_flow.py` 与 `api/knowledge.py` 中实现并接入 `validate_trusted_webhook_url` 白名单校验（要求路径为 `/api/v1/webhooks/agent` 且 Origin 命中受信任 Backend 地址或 `WEBHOOK_ALLOWED_ORIGINS`）。
- [x] 2.4 在 `deploy_prod.sh` 的 `validate_env_placeholders` 中补充 `DEBUG=false` 及 `JWT_SECRET_KEY` / `WEBHOOK_SECRET` / `INTERNAL_AGENT_TOKEN` 非空与非默认弱密钥检查。
- [x] 2.5 更新并补充 `backend/tests/test_deps_security.py`、`agent_service_v2/tests/test_knowledge_api.py`、`agent_service_v2/tests/test_public_resource_generation.py` 中的安全边界单测（覆盖伪造 Host 头不影响回调 URL、非法外部域名/错误路径被拒、合法白名单回调成功、生产模式弱 JWT 密钥拒绝）。

### Step 3: 修复 P2-01 题库批量生成 `(chapter, knowledge_point)` 清理边界 (`backend`)
- [x] 3.1 修改 `backend/app/services/catalog_quiz_generation_service.py`：`generate_quiz_for_child` 返回 `"chapter": chapter`；`run_quiz_generation_background` 按已完成节点的 `(chapter, knowledge_point)` 组合精确过滤软删除范围，并兼容多教学班共享 Catalog 的范围过滤。
- [x] 3.2 在 `backend/tests/test_admin_catalog_resource_generation.py` 中新增跨章节同名知识点（一章成功、一章失败/存量）及多教学班共享 Catalog 的回归测试。

### Step 4: 完善 P2-02 质量门禁 `check_all.py`、CI 与交接文档
- [x] 4.1 修改 `check_all.py`：将 `frontend-tests`（`npm run test:unit`）纳入默认门禁（共 7 项），支持 `--only frontend,backend,agent` 分组别名，保持 `--fast` 仅运行 4 项静态/构建检查。
- [x] 4.2 修改 `backend/tests/conftest.py` 支持 `TEST_DATABASE_URL` 环境变量覆盖默认 MySQL URL，并新增 `.github/workflows/ci.yml`。
- [x] 4.3 若 OpenAPI Schema 因字段描述变化有更新，同步刷新 `docs/10-client-api/Client-API.openapi.json` 与 `docs/20-agent-api/Agent-Service.openapi.json`，并更新 `README.md` 及 `.trellis/spec/`。

---

## 验证门禁 (Validation Gates)

```bash
# 1. 快速静态与构建门禁（4项）
python -X utf8 check_all.py --fast

# 2. 全量 7 大门禁（含前端 Vitest、Backend Pytest、Agent Pytest）
python -X utf8 check_all.py
```
