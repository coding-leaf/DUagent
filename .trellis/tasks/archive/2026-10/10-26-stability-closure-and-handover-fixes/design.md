# 技术方案设计 (Technical Design)

## 1. P1-01：前端文件下载回归修复 (`frontend`)

### 1.1 根因分析
- `frontend/src/api/client.js` 第 25-27 行定义了响应拦截器：
  ```javascript
  apiClient.interceptors.response.use((response) => response.data, ...);
  ```
- 因此 `await apiClient.get(url, { responseType: 'blob' })` 在运行时直接返回 `Blob` 对象，而非 `AxiosResponse`。
- `common/MarkdownViewer.jsx` 与 `workspace/plugins/MarkdownViewer.jsx` 中调用 `URL.createObjectURL(response.data)` 传入了 `undefined`，导致浏览器抛出 `TypeError`。

### 1.2 最小修复设计
在两个 `MarkdownViewer.jsx` 的 `handleArtifactDownload` 中：
```javascript
const handleArtifactDownload = useCallback(async (e, filename) => {
  e.preventDefault();
  try {
    const response = await apiClient.get(
      `/tutoring/conversations/${activeSession}/files/${encodeURIComponent(filename)}`,
      { responseType: 'blob' }
    );
    const blob =
      response instanceof Blob
        ? response
        : response?.data instanceof Blob
          ? response.data
          : new Blob([response?.data ?? response ?? '']);
    const blobUrl = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = blobUrl;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(blobUrl);
  } catch (err) {
    console.error('Download failed:', err);
  }
}, [activeSession]);
```

---

## 2. P1-02：Webhook 安全边界与生产配置校验 (`backend` & `agent_service_v2`)

### 2.1 根因分析
1. **Backend 侧**：`personalized_resources.py`、`resources.py`、`catalogs.py` 中的 `_webhook_url(request)` 使用 `str(request.base_url).rstrip("/")`。`request.base_url` 取自 HTTP 请求的 `Host` 头，若反向代理或直连端口未严格重写 `Host`，攻击者可通过伪造 `Host: evil.example.com` 诱导 Agent Service 向外部地址发送带 `X-Webhook-Secret` 的回调请求。
2. **Agent Service 侧**：`ResourceGenerationRequest.validate_webhook_url` 仅拉黑了 `169.254.169.254` 和 `metadata.google.internal`，未限制回调目标必须是受信任的 Backend 实例；且 `public_resource_flow.py::_post_webhook` 在发送请求前未做二次校验。
3. **生产配置侧**：`backend/app/core/config.py` 中 `JWT_SECRET_KEY` 有硬编码默认值 `"duagent-jwt-secret-change-in-production"`，若生产环境（`DEBUG=False`）漏配或保留默认值，存在伪造 Token 风险。

### 2.2 最小修复设计
1. **Backend 固定使用受信任内部地址**：
   - 在 `backend/app/core/config.py::Settings` 中新增：
     ```python
     BACKEND_INTERNAL_BASE_URL: str = "http://127.0.0.1:8001"

     @property
     def webhook_callback_url(self) -> str:
         base = (self.BACKEND_INTERNAL_BASE_URL or "").strip().rstrip("/")
         if not base:
             host = "127.0.0.1" if self.HOST in ("0.0.0.0", "::", "") else self.HOST
             base = f"http://{host}:{self.PORT}"
         return f"{base}/api/v1/webhooks/agent"
     ```
   - `catalogs.py`、`resources.py`、`personalized_resources.py` 中的 `_webhook_url(request: Request | None = None) -> str` 直接返回 `settings.webhook_callback_url`（忽略 `request.base_url`）。
2. **Agent Service 严格白名单校验**：
   - 在 `AgentModelSettings` (`agent_service_v2/src/agent_service_v2/agents/model_provider.py`) 中设置：
     ```python
     BACKEND_INTERNAL_BASE_URL: str | None = "http://127.0.0.1:8001"
     WEBHOOK_ALLOWED_ORIGINS: str = ""
     ```
   - 在 `agent_service_v2/src/agent_service_v2/generators/public_resource_flow.py`（或公共辅助函数）中定义 `validate_trusted_webhook_url(url: str, settings: AgentModelSettings | None = None) -> str`：
     - 解析 `urlparse(url)`，要求 `scheme in ("http", "https")` 且 `bool(netloc)`；
     - 要求 `parsed.path == "/api/v1/webhooks/agent"`；
     - 构造受信任 Origin 集合 `allowed_origins`：
       - 默认包含 `{"http://127.0.0.1:8001", "http://localhost:8001", "http://127.0.0.1:8000", "http://localhost:8000"}`；
       - 若 `settings.BACKEND_INTERNAL_BASE_URL` 非空，解析其 `f"{p.scheme}://{p.netloc}".lower()` 加入白名单；
       - 若 `settings.WEBHOOK_ALLOWED_ORIGINS` 非空，按逗号分割解析加入白名单；
     - 若 `f"{parsed.scheme}://{parsed.netloc}".lower() not in allowed_origins`，抛出 `ValueError("Invalid or forbidden webhook_url")`；
   - 在 `ResourceGenerationRequest.validate_webhook_url` 与 `_post_webhook` 中均调用 `validate_trusted_webhook_url`。
3. **生产环境密钥与 DEBUG 校验**：
   - 在 `backend/app/core/config.py::Settings` 中新增 `is_weak_jwt_secret` / `validate_production_security()`；
   - 在 `backend/app/core/security.py` 的 `create_token` 与 `decode_token` 中，若 `not settings.DEBUG` 且 `settings.JWT_SECRET_KEY` 为空、等于 `"duagent-jwt-secret-change-in-production"` 或以 `"replace-with-"` 开头，抛出 `HTTPException(status_code=503, detail={"code": 50300, "message": "JWT secret 未安全配置", "data": None})`；
   - 在 `deploy_prod.sh` 的 `validate_env_placeholders` 中校验 `DEBUG=false` 且 `JWT_SECRET_KEY`、`WEBHOOK_SECRET`、`INTERNAL_AGENT_TOKEN` 非空且不为默认弱密钥。

---

## 3. P2-01：题库批量生成 `(chapter, knowledge_point)` 精确清理边界 (`backend`)

### 3.1 根因分析
- `QuizQuestion` 表具有 `chapter` 和 `knowledge_point` 两个字段。
- 在 `catalog_quiz_generation_service.py` 中，每个 KG 节点子任务生成题目时写入了 `chapter=chapter` 与 `knowledge_point=node_name`，但 `generate_quiz_for_child` 返回的字典只带了 `"node_name": node_name`，漏掉了 `"chapter": chapter`。
- `run_quiz_generation_background` 在软删除旧基线题时仅按 `QuizQuestion.knowledge_point.in_(completed_node_names)` 过滤，导致不同章节下的同名知识点（如“第一章 / 概述”成功、“第二章 / 概述”失败）被一并软删除。

### 3.2 最小修复设计
1. 在 `generate_quiz_for_child` 的成功和失败返回字典中均附带 `"chapter": chapter` 与 `"node_name": node_name`。
2. 在 `run_quiz_generation_background` 中构造已完成节点的精确过滤谓词列表 `completed_predicates`：
   ```python
   completed_predicates = []
   for r in results:
       if isinstance(r, dict) and r.get("status") == "completed" and r.get("node_name"):
           if "chapter" in r and r["chapter"] is not None:
               completed_predicates.append(
                   and_(
                       QuizQuestion.chapter == r["chapter"],
                       QuizQuestion.knowledge_point == r["node_name"],
                   )
               )
           else:
               completed_predicates.append(
                   QuizQuestion.knowledge_point == r["node_name"]
               )
   ```
3. 当 `inserted_question_ids and (completed_predicates or failed == 0)` 时：
   - 课程/目录归属范围：若同时存在 `fanout_catalog_id` 与 `fanout_course_ids`，使用 `or_(QuizQuestion.catalog_id == fanout_catalog_id, QuizQuestion.course_id.in_(fanout_course_ids))`（兼容存量 `catalog_id IS NULL` 但绑定在 `fanout_course_ids` 上的基线题，同时不波及其他 Catalog）；
   - 节点范围：若 `completed_predicates` 非空，附加 `.where(or_(*completed_predicates))`。

---

## 4. P2-02：统一质量门禁 `check_all.py` 与 GitHub Actions CI

1. 在 `check_all.py` 的 `build_checks()` 中（在 `frontend-build` 之后）插入：
   ```python
   Check(
       name="frontend-tests",
       description="frontend: npm run test:unit (Vitest)",
       command=[_npm(), "run", "test:unit"],
       cwd=FRONTEND,
       hint="cd frontend && npm install",
       kind="test",
   ),
   ```
2. 支持 `--only` / `--skip` 传入模块前缀别名（`frontend` -> `frontend-lint,frontend-build,frontend-tests`，`backend` -> `backend-lint,backend-tests`，`agent` -> `agent-lint,agent-tests`），与文件顶部 docstring 中的示例 `python check_all.py --only frontend,backend` 完全一致。
3. 新增 `.github/workflows/ci.yml`，在 push / pull_request 到 `main` 或 `dev` 时自动运行门禁。
