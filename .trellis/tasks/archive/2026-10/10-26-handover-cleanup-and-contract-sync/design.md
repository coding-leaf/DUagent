# 技术架构与设计方案 (Technical Design)

## 1. 死代码与过时文件清理边界

### 1.1 全量引用核验
- `frontend/src/services/catalogService.js`：全仓仅 `frontend/src/services/catalogService.test.js` 引用，真实业务代码（`useCatalog.js` 等）全部引用 `frontend/src/api/services/catalog.js`。删除 `frontend/src/services/` 整个目录零副作用。
- 4 个死组件（`GenerateModal.jsx`、`EffectsSuggestionsCard.jsx`、`SidebarResources.jsx`、`CodingQuestionCard.jsx`）：全仓无任何 `import` 引用。
- `reports/review-*.md`：4 份静态审计报告已由前序 5 个 Trellis 任务消化完毕，核心规范已沉淀进 `.trellis/spec/*/architecture-guardrails.md`，删除 `reports/` 下的旧报告避免误导接手人。

## 2. 前端图标补齐与错误处理统一 (`frontend`)

### 2.1 `Icon.jsx` 映射表扩展
在 `frontend/src/components/Icon.jsx` 的 `materialToLucide` 中补充以下 23 个键（全部对应 `lucide-react` 有效导出名）：
```javascript
    'chevron_left': 'ChevronLeft',
    'folder_open': 'FolderOpen',
    'download': 'Download',
    'person': 'User',
    'edit': 'Edit',
    'chat_bubble_outline': 'MessageCircle',
    'groups': 'Users',
    'upload_file': 'FileUp',
    'verified': 'BadgeCheck',
    'check_circle_outline': 'CheckCircle2',
    'schedule': 'Clock',
    'explore': 'Compass',
    'sync': 'RefreshCw',
    'help': 'HelpCircle',
    'radio_button_unchecked': 'Circle',
    'radio_button_checked': 'CheckCircle2',
    'check_box': 'CheckSquare',
    'code_blocks': 'Code2',
    'calendar_month': 'Calendar',
    'video_library': 'Video',
    'speed': 'Gauge',
    'fact_check': 'ClipboardCheck',
    'warning_amber': 'AlertTriangle',
```

### 2.2 `utils/apiError.js` 统一错误提取契约
- 将 `frontend/src/api/error.js` 中的 `fieldLabels` 与 `formatValidationError` 移入 `frontend/src/utils/apiError.js`。
- `getErrorMessage(error, fallback = '请求失败')` 逻辑：
  1. 若 `!error?.response?.data`，返回 `error?.message || fallback`；
  2. 先检查 `detail = data.detail`：
     - 若 `typeof detail === 'string' && detail.trim()`，返回 `detail`；
     - 若 `typeof detail?.message === 'string' && detail.message.trim()`，返回 `detail.message`；
     - 若 `Array.isArray(detail)`，映射 `formatValidationError(item)` 返回第一个非空字符串；
  3. 再检查 `typeof data.message === 'string' && data.message.trim()`，返回 `data.message`；
  4. 最后返回 `error?.message || fallback`。
- 同时导出 `export const getApiErrorMessage = getErrorMessage;` 保持命名兼容，更新 `Login.jsx` 与 `Register.jsx` 导入自 `../utils/apiError`，并删除 `frontend/src/api/error.js`。

## 3. 跨层安全与网络健壮性设计

### 3.1 会话文件安全下载（消除 URL Query Token）
- **Backend (`backend/app/api/deps.py`)**：
  - `get_download_user` 不再接收 `token: str | None = Query(None)`，直接调用 `return await get_current_user(credentials=credentials, db=db)`，仅允许 `Authorization: Bearer <token>` 请求头鉴权。
- **Frontend (`common/MarkdownViewer.jsx` & `workspace/plugins/MarkdownViewer.jsx`)**：
  - 生成链接时：`const downloadUrl = \`\${apiBaseUrl}/tutoring/conversations/\${activeSession}/files/\${encodeURIComponent(filename)}\`;`（不带 `?token=`）。
  - 点击事件 `handleArtifactDownload(e, filename)`：
    ```javascript
    e.preventDefault();
    try {
      const response = await apiClient.get(
        `/tutoring/conversations/${activeSession}/files/${encodeURIComponent(filename)}`,
        { responseType: 'blob' }
      );
      const blobUrl = URL.createObjectURL(response.data);
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
    ```
  - 这样既保留了 `<a href={downloadUrl} download={filename}>` 的语义与可测试性，又确保真实点击时走 Axios Bearer Header，绝不把 7 天有效期的 JWT 暴露在 URL、浏览器历史或服务器访问日志中。

### 3.2 Webhook 生产环境防空密钥与 SSRF 校验
- **`backend/app/api/deps.py::verify_webhook_secret`**：
  ```python
  if not settings.WEBHOOK_SECRET:
      if getattr(settings, "DEBUG", False):
          return
      raise HTTPException(
          status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
          detail={"code": 50300, "message": "Webhook secret 未配置", "data": None},
      )
  ```
- **`agent_service_v2/src/agent_service_v2/api/knowledge.py::ResourceGenerationRequest`**：
  - 添加 `@field_validator("webhook_url")`：使用 `urllib.parse.urlparse` 校验 `parsed.scheme in ("http", "https")` 且 `bool(parsed.netloc)`，且 `parsed.hostname not in ("169.254.169.254", "metadata.google.internal")`，否则抛出 `ValueError("Invalid or forbidden webhook_url")`。

### 3.3 `BackendLearningClient.post_json` 异常收敛
- 在 `agent_service_v2/src/agent_service_v2/tools/backend_learning_client.py` 中：
  ```python
  except httpx.TimeoutException as exc:
      raise BackendLearningClientError("backend_timeout") from exc
  except httpx.TransportError as exc:
      raise BackendLearningClientError("backend_unavailable") from exc
  ```
  并在解析响应体时：
  ```python
  try:
      body = response.json()
  except ValueError as exc:
      raise BackendLearningClientError(
          "backend_bad_response",
          status_code=response.status_code,
      ) from exc
  ```

## 4. OpenAPI 契约导出与 README 交接导览
- 使用 Python 脚本分别加载 `backend` 的 `app.main:app` 与 `agent_service_v2` 的 `agent_service_v2.main:app`，调用 `.openapi()` 生成 JSON 并格式化写入 `docs/10-client-api/Client-API.openapi.json` 和 `docs/20-agent-api/Agent-Service.openapi.json`。
- 在 `README.md` 中新增简洁的《开发者交接与架构规范导览》章节，指引接手人阅读 `.trellis/spec/` 与运行 `python check_all.py`。
