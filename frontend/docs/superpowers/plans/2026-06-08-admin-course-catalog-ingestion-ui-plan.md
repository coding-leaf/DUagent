# Admin CourseCatalog 入库 UI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add AdminConsole UI for CourseCatalog material upload, manual ingestion triggering, task polling, and material-level ingestion status.

**Architecture:** Keep AdminConsole as the page shell and move catalog detail behavior into a focused right-side drawer component. Add small API and utility modules for task polling and error extraction. Use the existing Backend Client API only; multi-file upload is implemented as repeated calls to the current single-file upload endpoint.

**Tech Stack:** React 19, Vite, Axios, Tailwind utility classes, existing Material Symbols icons, Backend Client API under `/api/v1`.

---

## Source Spec

Implement this plan against:

- `docs/superpowers/specs/2026-06-08-admin-course-catalog-ingestion-ui-design.md`
- `../docs/10-client-api/Client-API.openapi.json`
- `AGENTS.md`

Do not modify `../docs/10-client-api/Client-API.openapi.json` in this implementation.

## File Map

- `src/utils/apiError.js`: shared `getErrorMessage(error, fallback)` helper.
- `src/api/services/task.js`: shared task polling service.
- `src/api/services/admin.js`: CourseCatalog material list, upload, and ingestion endpoint wrappers.
- `src/components/admin/CourseCatalogDrawer.jsx`: right-side drawer, material list, upload queue, ingestion trigger, task polling.
- `src/pages/AdminConsole.jsx`: select catalog, open drawer, import shared error helper, render drawer, refresh list after drawer changes.
- `WORKFLOW.md`: record implementation and verification results after code passes checks.

## Pre-Code Review Output Required

Before editing runtime code, output this review summary to the user per `AGENTS.md`:

```text
问题分析：Phase B1 Backend-Agent 入库链路已闭环，但 AdminConsole 只有资源库列表/创建，缺少真实上传、资料状态、入库触发和任务轮询 UI。
计划修改的文件：src/utils/apiError.js、src/api/services/task.js、src/api/services/admin.js、src/components/admin/CourseCatalogDrawer.jsx、src/pages/AdminConsole.jsx、WORKFLOW.md。
修改方案：新增共享错误工具和 taskService；扩展 adminService；新增右侧 CourseCatalogDrawer；AdminConsole 负责选择资源库和刷新列表。
可能影响的功能：管理员用户/日志 tab 不应改变；课程资源库 tab 会新增详情抽屉和上传入库操作；TeacherConsole 暂不迁移到 taskService。
计划运行的测试命令：npm run lint；npm run build；必要时手工验收 /admin 资源库上传入库流程。
```

## Task 1: API Services And Error Utility

**Files:**

- Create: `src/utils/apiError.js`
- Create: `src/api/services/task.js`
- Modify: `src/api/services/admin.js`

- [ ] **Step 1: Create shared API error helper**

Create `src/utils/apiError.js`:

```js
export const getErrorMessage = (error, fallback = '请求失败') => {
  const detail = error?.response?.data?.detail;
  if (typeof detail === 'string') return detail;
  if (detail?.message) return detail.message;
  return error?.response?.data?.message || error?.message || fallback;
};
```

- [ ] **Step 2: Create task service**

Create `src/api/services/task.js`:

```js
import apiClient from '../client';

export const taskService = {
  getTaskStatus(taskId) {
    return apiClient.get(`/tasks/${taskId}`);
  }
};
```

- [ ] **Step 3: Extend admin service**

Modify `src/api/services/admin.js` to add CourseCatalog B1 methods while keeping existing methods:

```js
  getCourseCatalogMaterials: async (catalogId) => {
    return apiClient.get(`/admin/course-catalogs/${catalogId}/materials`);
  },

  uploadCourseCatalogMaterial: async (catalogId, file) => {
    const formData = new FormData();
    formData.append('file', file);
    return apiClient.post(`/admin/course-catalogs/${catalogId}/materials/upload`, formData, {
      timeout: 60000,
      headers: {
        'Content-Type': 'multipart/form-data'
      }
    });
  },

  startCourseCatalogIngestion: async (catalogId) => {
    return apiClient.post(`/admin/course-catalogs/${catalogId}/ingestions`);
  }
```

Keep `createCourseCatalogMaterial()` for compatibility if current code still references it.

- [ ] **Step 4: Run static check**

Run:

```bash
npm run lint
```

Expected: pass.

- [ ] **Step 5: Commit Task 1**

```bash
git add src/utils/apiError.js src/api/services/task.js src/api/services/admin.js
git commit -m "补齐资源库入库前端服务"
```

## Task 2: CourseCatalog Drawer Component

**Files:**

- Create: `src/components/admin/CourseCatalogDrawer.jsx`

- [ ] **Step 1: Create component shell and constants**

Create `src/components/admin/CourseCatalogDrawer.jsx` with these imports and helpers:

```jsx
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { adminService } from '../../api/services/admin';
import { taskService } from '../../api/services/task';
import { getErrorMessage } from '../../utils/apiError';

const POLL_INTERVAL_MS = 2000;
const ACCEPTED_FILE_TYPES = '.txt,.md,.pdf';

const catalogStatusText = {
  draft: '未入库',
  ingesting: '入库中',
  ready: '可绑定',
  failed: '入库失败'
};

const knowledgeStatusText = {
  draft: '未入库',
  ingesting: '入库中',
  ready: '已同步',
  dirty: '待更新',
  partial: '部分失败',
  failed: '入库失败'
};

const materialStatusText = {
  uploaded: '已上传',
  ingesting: '入库中',
  ingested: '已入库',
  failed: '入库失败'
};

const formatDateTime = (value) => {
  if (!value) return '-';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString();
};

const formatFileSize = (bytes) => {
  if (!Number.isFinite(bytes)) return '-';
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
};

const statusBadgeClass = (status) => {
  if (['ready', 'ingested', 'completed'].includes(status)) return 'bg-emerald-100 text-emerald-700';
  if (['dirty', 'partial', 'processing', 'ingesting'].includes(status)) return 'bg-amber-100 text-amber-700';
  if (status === 'failed') return 'bg-red-100 text-red-700';
  if (status === 'uploaded') return 'bg-cyan-50 text-cyan-700';
  return 'bg-slate-100 text-slate-600';
};
```

- [ ] **Step 2: Implement data loading state**

The component signature must be:

```jsx
export default function CourseCatalogDrawer({ catalog, open, onClose, onChanged }) {
```

State required:

```jsx
const [materials, setMaterials] = useState([]);
const [knowledgeStatus, setKnowledgeStatus] = useState(null);
const [loading, setLoading] = useState(false);
const [error, setError] = useState('');
const [uploadQueue, setUploadQueue] = useState([]);
const [uploading, setUploading] = useState(false);
const [ingesting, setIngesting] = useState(false);
const [activeTask, setActiveTask] = useState(null);
const [taskError, setTaskError] = useState('');
const pollTimerRef = useRef(null);
const requestSeqRef = useRef(0);
```

Add `clearPollTimer()`:

```jsx
const clearPollTimer = useCallback(() => {
  if (pollTimerRef.current) {
    clearInterval(pollTimerRef.current);
    pollTimerRef.current = null;
  }
}, []);
```

Add `loadCatalogDetail()`:

```jsx
const loadCatalogDetail = useCallback(async () => {
  if (!catalog?.id || !open) return;
  const requestSeq = requestSeqRef.current + 1;
  requestSeqRef.current = requestSeq;
  setLoading(true);
  setError('');
  try {
    const [materialsRes, statusRes] = await Promise.all([
      adminService.getCourseCatalogMaterials(catalog.id),
      adminService.getCourseCatalogStatus(catalog.id)
    ]);
    if (requestSeqRef.current !== requestSeq) return;
    setMaterials(materialsRes.data?.materials || []);
    setKnowledgeStatus(statusRes.data || null);
  } catch (err) {
    if (requestSeqRef.current !== requestSeq) return;
    setError(getErrorMessage(err, '课程资源库详情加载失败'));
  } finally {
    if (requestSeqRef.current === requestSeq) {
      setLoading(false);
    }
  }
}, [catalog?.id, open]);
```

Add effects:

```jsx
useEffect(() => {
  if (open) {
    loadCatalogDetail();
  }
}, [open, loadCatalogDetail]);

useEffect(() => {
  return () => {
    requestSeqRef.current += 1;
    clearPollTimer();
  };
}, [clearPollTimer]);

useEffect(() => {
  requestSeqRef.current += 1;
  clearPollTimer();
  setUploadQueue([]);
  setTaskError('');
  setActiveTask(null);
}, [catalog?.id, clearPollTimer]);
```

- [ ] **Step 3: Implement upload behavior**

Add derived flags:

```jsx
const currentStatus = knowledgeStatus || catalog || {};
const isIngesting = currentStatus.status === 'ingesting' || currentStatus.knowledge_status === 'ingesting' || ingesting;
const hasPendingMaterials = useMemo(
  () => materials.some((material) => ['uploaded', 'failed'].includes(material.status)),
  [materials]
);
const canStartIngestion = Boolean(catalog?.id) && !isIngesting && !uploading && hasPendingMaterials && !activeTask;
```

Add upload handler:

```jsx
const handleFileChange = async (event) => {
  const selectedFiles = Array.from(event.target.files || []);
  event.target.value = '';
  if (!catalog?.id || selectedFiles.length === 0 || uploading || isIngesting) return;

  const queue = selectedFiles.map((file, index) => ({
    id: `${Date.now()}-${index}-${file.name}`,
    filename: file.name,
    size: file.size,
    status: 'queued',
    error: ''
  }));

  setUploadQueue(queue);
  setUploading(true);
  setError('');

  const nextQueue = [...queue];
  for (let index = 0; index < selectedFiles.length; index += 1) {
    const file = selectedFiles[index];
    nextQueue[index] = { ...nextQueue[index], status: 'uploading' };
    setUploadQueue([...nextQueue]);
    try {
      await adminService.uploadCourseCatalogMaterial(catalog.id, file);
      nextQueue[index] = { ...nextQueue[index], status: 'uploaded' };
    } catch (err) {
      nextQueue[index] = {
        ...nextQueue[index],
        status: 'failed',
        error: getErrorMessage(err, '资料上传失败')
      };
    }
    setUploadQueue([...nextQueue]);
  }

  setUploading(false);
  await loadCatalogDetail();
  onChanged?.();
};
```

- [ ] **Step 4: Implement ingestion and polling**

Add polling helper:

```jsx
const refreshAfterTask = useCallback(async () => {
  await loadCatalogDetail();
  onChanged?.();
}, [loadCatalogDetail, onChanged]);

const pollTask = useCallback((taskId) => {
  clearPollTimer();
  pollTimerRef.current = setInterval(async () => {
    try {
      const res = await taskService.getTaskStatus(taskId);
      const task = res.data || {};
      setActiveTask(task);
      if (task.status === 'completed' || task.status === 'failed') {
        clearPollTimer();
        setIngesting(false);
        if (task.status === 'failed') {
          setTaskError(task.error_message || task.message || '课程资源库入库失败');
        }
        await refreshAfterTask();
      }
    } catch (err) {
      clearPollTimer();
      setIngesting(false);
      setTaskError(getErrorMessage(err, '任务状态查询失败'));
      await refreshAfterTask();
    }
  }, POLL_INTERVAL_MS);
}, [clearPollTimer, refreshAfterTask]);
```

Add start handler:

```jsx
const handleStartIngestion = async () => {
  if (!canStartIngestion) return;
  setIngesting(true);
  setTaskError('');
  try {
    const res = await adminService.startCourseCatalogIngestion(catalog.id);
    const task = res.data || {};
    setActiveTask({
      task_id: task.task_id,
      id: task.task_id,
      status: task.status || 'processing'
    });
    pollTask(task.task_id);
    await loadCatalogDetail();
    onChanged?.();
  } catch (err) {
    setIngesting(false);
    setTaskError(getErrorMessage(err, '课程资源库入库触发失败'));
  }
};
```

- [ ] **Step 5: Render drawer UI**

The render must return `null` when closed:

```jsx
if (!open || !catalog) return null;
```

Render a fixed overlay with a right panel:

```jsx
return (
  <div className="fixed inset-0 z-50 flex justify-end bg-slate-900/30">
    <button type="button" aria-label="关闭课程资源库详情" className="flex-1 cursor-default" onClick={onClose} />
    <aside className="flex h-full w-full max-w-[520px] flex-col bg-white shadow-2xl">
      {/* Header, summary, upload, materials, task status */}
    </aside>
  </div>
);
```

Minimum UI sections:

- Header: title, catalog id, close button, status badges.
- Summary grid: material count, chunk count, pending count, failed count.
- Upload: file input with `multiple` and `accept={ACCEPTED_FILE_TYPES}`.
- Upload queue: filename, size, queued/uploading/uploaded/failed, error.
- Material list: filename, source_type, file_size, status badge, chunk_count, last_error, ingested_at.
- Ingestion task: start button, current task id/status, task error.

Use `data-testid` attributes for hand-checking selectors:

```jsx
data-testid="catalog-drawer"
data-testid="catalog-upload-input"
data-testid="catalog-start-ingestion"
data-testid="catalog-material-row"
data-testid="catalog-task-status"
```

- [ ] **Step 6: Run static check**

Run:

```bash
npm run lint
```

Expected: pass. If it fails due to hook dependency warnings, fix dependencies explicitly instead of disabling lint.

- [ ] **Step 7: Commit Task 2**

```bash
git add src/components/admin/CourseCatalogDrawer.jsx
git commit -m "新增资源库入库详情抽屉"
```

## Task 3: AdminConsole Integration

**Files:**

- Modify: `src/pages/AdminConsole.jsx`

- [ ] **Step 1: Import drawer and shared error helper**

Replace local `getErrorMessage` helper with imports:

```jsx
import CourseCatalogDrawer from '../components/admin/CourseCatalogDrawer';
import { getErrorMessage } from '../utils/apiError';
```

Remove the local `const getErrorMessage = ...` block from `AdminConsole.jsx`.

- [ ] **Step 2: Add selected catalog state**

Near existing Course Catalog state, add:

```jsx
const [selectedCatalog, setSelectedCatalog] = useState(null);
```

- [ ] **Step 3: Add row open handler**

Add:

```jsx
const handleOpenCatalog = (catalog) => {
  setSelectedCatalog(catalog);
};

const handleCloseCatalog = () => {
  setSelectedCatalog(null);
};
```

- [ ] **Step 4: Refresh selection after list reload**

After `setCatalogs(nextCatalogs)` in `fetchCatalogs`, keep the open drawer in sync:

```jsx
const nextCatalogs = res.data?.catalogs || [];
setCatalogs(nextCatalogs);
setSelectedCatalog((current) => {
  if (!current) return current;
  return nextCatalogs.find((catalog) => catalog.id === current.id) || current;
});
```

- [ ] **Step 5: Add table action and click behavior**

Change catalog table header to include operation column:

```jsx
<th className="px-6 py-4 font-medium text-right">操作</th>
```

Set catalog row click:

```jsx
<tr key={catalog.id} onClick={() => handleOpenCatalog(catalog)} className="cursor-pointer hover:bg-slate-50/50 transition-colors">
```

Add operation cell:

```jsx
<td className="px-6 py-4 text-right">
  <button
    type="button"
    onClick={(event) => {
      event.stopPropagation();
      handleOpenCatalog(catalog);
    }}
    className="inline-flex items-center gap-1 rounded-lg border border-cyan-200 bg-white px-3 py-1.5 text-xs font-medium text-cyan-700 transition-colors hover:bg-cyan-50"
  >
    <span className="material-symbols-outlined text-[16px]">folder_open</span>
    管理资料
  </button>
</td>
```

Update loading/empty `colSpan` from `4` to `5`.

- [ ] **Step 6: Render drawer**

Near the end of `AdminConsole` render, inside the top-level container but outside tab conditionals, render:

```jsx
<CourseCatalogDrawer
  catalog={selectedCatalog}
  open={Boolean(selectedCatalog)}
  onClose={handleCloseCatalog}
  onChanged={fetchCatalogs}
/>
```

- [ ] **Step 7: Run static check**

Run:

```bash
npm run lint
```

Expected: pass.

- [ ] **Step 8: Commit Task 3**

```bash
git add src/pages/AdminConsole.jsx
git commit -m "接入资源库入库管理抽屉"
```

## Task 4: Verification And Workflow

**Files:**

- Modify: `WORKFLOW.md`

- [ ] **Step 1: Run full frontend checks**

Run:

```bash
npm run lint
npm run build
```

Expected:

- `npm run lint` passes.
- `npm run build` passes. Existing Vite chunk size warning is acceptable if unchanged.

- [ ] **Step 2: Optional real smoke if services are running**

If Backend is available at `http://127.0.0.1:8001` and frontend can be run locally, perform manual smoke:

```text
1. Start frontend with VITE_USE_MOCK=false and VITE_API_BASE_URL pointing to Backend.
2. Log in as admin.
3. Open /admin -> 课程资源库.
4. Open a catalog drawer.
5. Upload at least one small .md or .txt file.
6. Trigger ingestion.
7. Confirm task status reaches completed or failed and UI refreshes status.
```

If runtime services are not available, record that manual smoke was not run.

- [ ] **Step 3: Update WORKFLOW.md**

Add a 2026-06-08 entry under 最近验证:

```markdown
- 2026-06-08：AdminConsole 课程资源库入库 UI 接入完成：
  - 新增资源库详情右侧抽屉，支持资料列表、知识库状态、批量选择文件并逐个上传、手动触发入库和 task 轮询。
  - 新增 `taskService` 和共享 `getErrorMessage` 工具；上传请求使用 FormData、单文件接口、60s timeout。
  - 不修改 OpenAPI，不直连 Agent Service，不使用 mock 数据补字段。
  - `npm run lint` 通过；`npm run build` 通过（如有既有 Vite chunk warning，注明）。
```

- [ ] **Step 4: Run diff checks for touched files**

Run:

```bash
git diff --check -- src/utils/apiError.js src/api/services/task.js src/api/services/admin.js src/components/admin/CourseCatalogDrawer.jsx src/pages/AdminConsole.jsx WORKFLOW.md
```

Expected: pass.

- [ ] **Step 5: Commit Task 4**

```bash
git add WORKFLOW.md
git commit -m "记录资源库入库 UI 验证"
```

## Final Review Requirements

After all tasks:

- Run `git status --short`.
- Confirm only intentional files are committed or modified.
- Run final checks if not already fresh:

```bash
npm run lint
npm run build
```

- Review final diff or commits for:
  - No OpenAPI changes.
  - No `.superpowers/` files committed.
  - No upload files or storage files committed.
  - No mock data added for catalog status.
  - No Agent Service direct calls.

## Manual Acceptance Checklist

Use this checklist for the final response:

- Admin can open CourseCatalog drawer.
- Drawer loads `data.materials` and `data` knowledge status.
- Multi-select upload uses repeated single-file upload requests.
- Upload request uses FormData, multipart, and 60s timeout.
- Start ingestion uses `POST /admin/course-catalogs/{catalog_id}/ingestions`.
- Task polling uses `GET /tasks/{task_id}` through `taskService`.
- Completed/failed task refreshes catalog list, material list, and knowledge status.
- `partial` displays as non-blocking incomplete state.
- `npm run lint` passed.
- `npm run build` passed.
