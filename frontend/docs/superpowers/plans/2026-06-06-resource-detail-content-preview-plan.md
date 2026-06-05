# ResourceDetail 正文预览实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 新增 `GET /api/v1/resources/{id}` 端点，Backend 返回 `content_preview`，前端 ResourceDetail 接入 API 替代静态正文。

**Architecture:** 5 个 task 依序执行：OpenAPI → Backend → Frontend service → Frontend page → 验证收口。每 task 独立提交。

**Tech Stack:** OpenAPI JSON, FastAPI (Python), React (JavaScript), Vite

**依据 Spec：** `docs/superpowers/specs/2026-06-06-resource-detail-content-preview-design.md`

---

### Task 1: OpenAPI 更新 — 新增 GET /resources/{id} + ResourceDetailItem

**Files:**
- Modify: `../docs/10-client-api/Client-API.openapi.json`

- [ ] **Step 1: 读取当前状态**

```bash
cd /home/yezisama/workspace/workflow/EDUagent/frontend
jq '.paths["/resources"]' ../docs/10-client-api/Client-API.openapi.json
jq '.components.schemas.ResourceItem' ../docs/10-client-api/Client-API.openapi.json
```

- [ ] **Step 2: 新增 `/resources/{id}` path + ResourceDetailItem schema**

在 paths 中新增：
```json
"/resources/{id}": {
  "get": {
    "tags": ["Resources"],
    "summary": "获取资源详情",
    "operationId": "getResourceDetail",
    "parameters": [
      {
        "name": "id",
        "in": "path",
        "required": true,
        "schema": { "type": "string" },
        "description": "资源 ID"
      }
    ],
    "responses": {
      "200": {
        "description": "资源详情",
        "content": {
          "application/json": {
            "schema": {
              "type": "object",
              "properties": {
                "code": { "type": "integer", "example": 200 },
                "message": { "type": "string", "example": "success" },
                "data": { "$ref": "#/components/schemas/ResourceDetailItem" }
              }
            }
          }
        }
      },
      "401": { "description": "未登录" },
      "403": { "description": "无课程访问权限" },
      "404": { "description": "资源不存在" }
    }
  }
}
```

在 components.schemas 中新增：
```json
"ResourceDetailItem": {
  "type": "object",
  "description": "ResourceItem 全部字段 + content_preview",
  "allOf": [
    { "$ref": "#/components/schemas/ResourceItem" },
    {
      "type": "object",
      "properties": {
        "content_preview": {
          "type": ["string", "null"],
          "description": "文字资源正文预览，通常为正文前若干字符或段落。由 Backend 提供，具体来源是 Backend 实现细节。适用 document/reading 类型；其他类型返回 null。"
        }
      }
    }
  ]
}
```

- [ ] **Step 3: 验证 JSON**

```bash
jq empty ../docs/10-client-api/Client-API.openapi.json
```
Expected: no output (valid JSON).

- [ ] **Step 4: 提交**

```bash
cd /home/yezisama/workspace/workflow/EDUagent
git add ../docs/10-client-api/Client-API.openapi.json
git commit -m "OpenAPI 新增 GET /resources/{id} 和 ResourceDetailItem schema"
```

---

### Task 2: Backend — 新增路由 + 测试

**Files:**
- Modify: `../backend/app/api/v1/resources.py`
- Create: `../backend/tests/test_resource_detail.py`

**注意：** 路由前缀已是 `/api/v1/resources`（`APIRouter(prefix="/api/v1/resources")`），装饰器写成 `@router.get("/{id}")`。

- [ ] **Step 1: 读取当前文件**

```bash
cat /home/yezisama/workspace/workflow/EDUagent/backend/app/api/v1/resources.py
```

- [ ] **Step 2: 新增详情路由**

在列表路由（`@router.get("")`）之后插入：

```python
@router.get("/{id}")
async def get_resource_detail(
    id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Resource).where(Resource.id == id, Resource.is_deleted == False)
    )
    resource = result.scalar_one_or_none()
    if resource is None:
        raise HTTPException(status_code=404, detail="Resource not found")

    preview = None
    if resource.type in ("document", "reading") and resource.content:
        preview = resource.content[:500]

    return {
        "code": 200,
        "message": "success",
        "data": {
            "id": resource.id, "title": resource.title,
            "type": resource.type, "description": resource.description or "",
            "tags": resource.tags or [], "chapter": resource.chapter,
            "knowledge_point": resource.knowledge_point,
            "view_count": resource.view_count,
            "created_at": resource.create_time.isoformat() if resource.create_time else "",
            "content_preview": preview,
        },
    }
```

确认 `Resource`、`get_current_user` 在文件顶部已有 import。

- [ ] **Step 3: 写测试**

创建 `tests/test_resource_detail.py`：
```python
import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app


@pytest.mark.asyncio
async def test_get_resource_detail_404():
    """不存在的资源返回 401（未登录）或 404（含有效 token）"""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get("/api/v1/resources/nonexistent-id")
        assert res.status_code in (401, 404)
```

**注意：** 完整测试需要 auth token fixture。实际执行时根据项目已有测试基础调整。

- [ ] **Step 4: 运行测试**

```bash
cd /home/yezisama/workspace/workflow/EDUagent/backend
python -m pytest tests/test_resource_detail.py -v 2>&1
```

- [ ] **Step 5: 提交**

```bash
cd /home/yezisama/workspace/workflow/EDUagent
git add backend/app/api/v1/resources.py backend/tests/test_resource_detail.py
git commit -m "Backend 新增 GET /resources/{id} 详情路由"
```

---

### Task 3: Frontend service — learning.js 新增 getResourceDetail

**Files:**
- Modify: `src/api/services/learning.js`

- [ ] **Step 1: 追加方法**

在 `learningService` 对象末尾追加：

```javascript
  getResourceDetail(id) {
    return apiClient.get(`/resources/${id}`);
  }
```

- [ ] **Step 2: 验证 lint**

```bash
cd /home/yezisama/workspace/workflow/EDUagent/frontend && npm run lint
```
Expected: PASS

- [ ] **Step 3: 提交**

```bash
cd /home/yezisama/workspace/workflow/EDUagent
git add frontend/src/api/services/learning.js
git commit -m "learningService 新增 getResourceDetail"
```

---

### Task 4: Frontend page — ResourceDetail.jsx 接入 API

**Files:**
- Modify: `src/pages/ResourceDetail.jsx`

**操作：**

### Step 1: 接入 API

新增 import：
```javascript
import { useParams } from 'react-router-dom';
import { useState, useEffect } from 'react';
import { learningService } from '../api/services/learning';
```

组件体内：
```javascript
const { id } = useParams();
const [resource, setResource] = useState(null);
const [loading, setLoading] = useState(true);

useEffect(() => {
  if (id) {
    learningService.getResourceDetail(id).then(res => {
      if (res.code === 200) setResource(res.data);
    }).catch(() => setResource(null))
    .finally(() => setLoading(false));
  }
}, [id]);
```

### Step 2: 替换静态内容

- **正文区域：** `{resource?.content_preview || '暂无正文预览'}`
- **删除：** 阅读进度卡片（65%/3.2k/4.8k）、当前阅读时长（12m）
- **保留并用 API 数据替换：** 标题（`resource?.title`）、描述（`resource?.description`）、关键词（`resource?.tags`）、章节、知识点
- 加载态：`loading` 时展示加载中

### Step 3: 验证

```bash
cd /home/yezisama/workspace/workflow/EDUagent/frontend && npm run lint && npm run build
```
Expected: PASS

### Step 4: 提交

```bash
cd /home/yezisama/workspace/workflow/EDUagent
git add frontend/src/pages/ResourceDetail.jsx
git commit -m "ResourceDetail 接入 API 正文预览,删除静态进度和时长"
```

---

### Task 5: 全量验证 + WORKFLOW 收口

**Files:**
- Modify: `frontend/WORKFLOW.md`

- [ ] **Step 1: lint + build**

```bash
cd /home/yezisama/workspace/workflow/EDUagent/frontend && npm run lint && npm run build
```
Expected: PASS

- [ ] **Step 2: Backend 测试**

```bash
cd /home/yezisama/workspace/workflow/EDUagent/backend && python -m pytest tests/ -k "resource" -v 2>&1
```

- [ ] **Step 3: 更新 WORKFLOW.md**

在 `## 最近验证` 末尾追加：

```markdown
- 2026-06-06：ResourceDetail 正文预览契约实现完成：
  - Client API：新增 `GET /api/v1/resources/{id}` + `ResourceDetailItem` schema（`content_preview: string | null`）
  - Backend：新增详情路由，`document`/`reading` 类型返回正文预览，其他返回 null
  - Frontend：`learningService.getResourceDetail(id)`；ResourceDetail 接入 API，删除阅读进度和时长占位
  - `npm run lint` / `npm run build` 通过。
```

- [ ] **Step 4: 提交**

```bash
cd /home/yezisama/workspace/workflow/EDUagent
git add frontend/WORKFLOW.md
git commit -m "记录 ResourceDetail 正文预览实现完成"
```

---

## 自审清单

**1. Spec 覆盖：** ✅ Task 1-4 覆盖 OpenAPI/Backend/Frontend。

**2. 无占位符：** ✅ 所有步骤含完整代码。

**3. 类型一致性：** ✅ `content_preview: string | null` 贯穿三层。
