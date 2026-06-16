# 个性化资源功能 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为学生提供两条个性化资源生成路径——①答题正确率<60%时触发错题针对性题目生成，②个性化资源页手动引导式表单生成任意类型资源，所有结果独立归属于用户并在"个性化资源"独立页面展示。

**Architecture:** 新建 `user_personalized_resources` 关联表存储 `(user_id, course_id)` 归属关系；新增后端路由 `personalized_resources.py`（GET 列表 + POST 触发生成）；前端新增独立页面 `PersonalizedResources.jsx`、三步引导 Modal 和 Sidebar 导航入口；PracticeResult 页面在正确率 <60% 时展示横幅入口。Agent 侧无需改动，复用现有 `/assessment/generate-questions` 和 `/resources/generate`。

**Tech Stack:** FastAPI + SQLAlchemy (async) + MySQL / React + Vite + Tailwind CSS / Google Material Symbols

---

## 文件清单

| 操作 | 路径 |
|------|------|
| 追加 | `backend/app/models/others.py` |
| 新建 | `backend/app/schemas/personalized.py` |
| 新建 | `backend/app/api/v1/personalized_resources.py` |
| 修改 | `backend/app/main.py`（import + include_router） |
| 修改 | `backend/app/api/v1/webhooks.py` |
| 执行 | DB migration（CREATE TABLE） |
| 新建 | `frontend/src/api/services/personalizedResources.js` |
| 新建 | `frontend/src/pages/PersonalizedResources.jsx` |
| 新建 | `frontend/src/components/personalized/GenerateModal.jsx` |
| 修改 | `frontend/src/pages/PracticeResult.jsx` |
| 修改 | `frontend/src/components/Sidebar.jsx` |
| 修改 | `frontend/src/App.jsx` |

---

## Task 1: DB Model + 建表

**Files:**
- Modify: `backend/app/models/others.py`（在文件末尾追加）

- [ ] **Step 1: 追加 UserPersonalizedResource Model**

在 `backend/app/models/others.py` 末尾（当前 `is_deleted` 最后一行之后）追加：

```python
class UserPersonalizedResource(Base):
    __tablename__ = "user_personalized_resources"
    __table_args__ = (
        Index("idx_upr_user_course", "user_id", "course_id", "is_deleted"),
        Index("idx_upr_task", "task_id"),
    )

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=gen_id)
    user_id: Mapped[str] = mapped_column(String(32), ForeignKey("users.id"), nullable=False)
    course_id: Mapped[str] = mapped_column(String(32), ForeignKey("courses.id"), nullable=False)
    resource_id: Mapped[str | None] = mapped_column(String(32), ForeignKey("resources.id"), nullable=True)
    question_id: Mapped[str | None] = mapped_column(String(32), ForeignKey("quiz_questions.id"), nullable=True)
    source_type: Mapped[str] = mapped_column(String(30), nullable=False)
    task_id: Mapped[str | None] = mapped_column(String(32), ForeignKey("async_tasks.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False)
```

- [ ] **Step 2: 校验语法**

```bash
cd /home/yezisama/workspace/workflow/EDUagent
python3 -m py_compile backend/app/models/others.py && echo "OK"
```

Expected: `OK`

- [ ] **Step 3: 执行建表 DDL**

连接到 MySQL（使用 backend/.env 中的数据库连接信息）并执行：

```sql
CREATE TABLE IF NOT EXISTS user_personalized_resources (
    id          VARCHAR(32)  NOT NULL,
    user_id     VARCHAR(32)  NOT NULL,
    course_id   VARCHAR(32)  NOT NULL,
    resource_id VARCHAR(32)  NULL,
    question_id VARCHAR(32)  NULL,
    source_type VARCHAR(30)  NOT NULL,
    task_id     VARCHAR(32)  NULL,
    created_at  DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    is_deleted  TINYINT(1)   NOT NULL DEFAULT 0,
    PRIMARY KEY (id),
    INDEX idx_upr_user_course (user_id, course_id, is_deleted),
    INDEX idx_upr_task (task_id)
);
```

验证建表成功：

```bash
cd /home/yezisama/workspace/workflow/EDUagent
# 读取 .env 中的 DB_URL，连接后执行 SHOW TABLES LIKE 'user_personalized_resources'
# 或直接在 mysql client 中确认
```

- [ ] **Step 4: Commit**

```bash
cd /home/yezisama/workspace/workflow/EDUagent
git add backend/app/models/others.py
git commit -m "feat: 新增 UserPersonalizedResource model 和建表 DDL"
```

---

## Task 2: Schema + 后端路由文件

**Files:**
- Create: `backend/app/schemas/personalized.py`
- Create: `backend/app/api/v1/personalized_resources.py`

- [ ] **Step 1: 创建 Schema 文件**

`backend/app/schemas/personalized.py`:

```python
from typing import Literal, Optional

from pydantic import BaseModel


class PersonalizedResourceGenerateRequest(BaseModel):
    course_id: str
    generate_type: Literal["quiz", "resource"]
    source_type: Literal["quiz_wrong_answer", "manual"]

    chapter: Optional[str] = None
    knowledge_point: Optional[str] = None

    # quiz 专用
    wrong_question_ids: Optional[list[str]] = None
    question_types: Optional[list[str]] = None
    count: int = 5
    difficulty: Optional[str] = None

    # resource 专用
    resource_types: Optional[list[str]] = None
```

- [ ] **Step 2: 校验 Schema 语法**

```bash
cd /home/yezisama/workspace/workflow/EDUagent
python3 -m py_compile backend/app/schemas/personalized.py && echo "OK"
```

Expected: `OK`

- [ ] **Step 3: 创建 API 路由文件（GET 列表接口）**

`backend/app/api/v1/personalized_resources.py`:

```python
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import JSONResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.models.others import AsyncTask, Resource, UserPersonalizedResource
from app.models.quiz import QuizQuestion
from app.models.user import User
from app.schemas.personalized import PersonalizedResourceGenerateRequest
from app.services.agent_client import AgentServiceError, agent_client
from app.services.course_catalog_gate import resolve_generation_catalog
from app.services import quiz_service

router = APIRouter(prefix="/api/v1/personalized-resources", tags=["personalized-resources"])


def _webhook_url(request: Request) -> str:
    base = str(request.base_url).rstrip("/")
    return f"{base}/api/v1/webhooks/agent"


@router.get("")
async def list_personalized_resources(
    course_id: str = Query(...),
    source_type: str = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=50),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    query = select(UserPersonalizedResource).where(
        UserPersonalizedResource.user_id == current_user.id,
        UserPersonalizedResource.course_id == course_id,
        UserPersonalizedResource.is_deleted == False,
    )
    if source_type:
        query = query.where(UserPersonalizedResource.source_type == source_type)

    count_r = await db.execute(select(func.count()).select_from(query.subquery()))
    total = count_r.scalar() or 0

    offset = (page - 1) * page_size
    result = await db.execute(
        query.order_by(UserPersonalizedResource.created_at.desc())
        .offset(offset)
        .limit(page_size)
    )
    uprs = result.scalars().all()

    # Preload related resources and questions
    resource_ids = [u.resource_id for u in uprs if u.resource_id]
    question_ids = [u.question_id for u in uprs if u.question_id]
    task_ids = [u.task_id for u in uprs if u.task_id]

    resources_map: dict = {}
    if resource_ids:
        res_r = await db.execute(
            select(Resource).where(Resource.id.in_(resource_ids), Resource.is_deleted == False)
        )
        resources_map = {r.id: r for r in res_r.scalars().all()}

    questions_map: dict = {}
    if question_ids:
        q_r = await db.execute(
            select(QuizQuestion).where(QuizQuestion.id.in_(question_ids), QuizQuestion.is_deleted == False)
        )
        questions_map = {q.id: q for q in q_r.scalars().all()}

    tasks_map: dict = {}
    if task_ids:
        t_r = await db.execute(
            select(AsyncTask).where(AsyncTask.id.in_(task_ids), AsyncTask.is_deleted == False)
        )
        tasks_map = {t.id: t for t in t_r.scalars().all()}

    # processing_count
    processing_count = sum(
        1 for u in uprs
        if u.task_id and tasks_map.get(u.task_id) and tasks_map[u.task_id].status == "processing"
    )

    items = []
    for u in uprs:
        task = tasks_map.get(u.task_id) if u.task_id else None
        task_status = task.status if task else None

        resource_data = None
        if u.resource_id:
            r = resources_map.get(u.resource_id)
            if r:
                resource_data = {
                    "id": r.id,
                    "title": r.title,
                    "type": r.type,
                    "description": r.description or "",
                    "chapter": r.chapter,
                    "knowledge_point": r.knowledge_point,
                }

        question_data = None
        if u.question_id:
            q = questions_map.get(u.question_id)
            if q:
                question_data = {
                    "id": q.id,
                    "type": q.type,
                    "content": q.content,
                    "options": q.options or [],
                    "knowledge_point": q.knowledge_point,
                    "chapter": q.chapter,
                    "difficulty": q.difficulty,
                }

        items.append({
            "id": u.id,
            "source_type": u.source_type,
            "created_at": u.created_at.isoformat() if u.created_at else "",
            "task_id": u.task_id,
            "task_status": task_status,
            "resource": resource_data,
            "question": question_data,
        })

    return {
        "code": 200,
        "message": "success",
        "data": {
            "items": items,
            "total": total,
            "page": page,
            "page_size": page_size,
            "processing_count": processing_count,
        },
    }
```

- [ ] **Step 4: 校验语法**

```bash
cd /home/yezisama/workspace/workflow/EDUagent
python3 -m py_compile backend/app/api/v1/personalized_resources.py && echo "OK"
```

Expected: `OK`

- [ ] **Step 5: Commit**

```bash
cd /home/yezisama/workspace/workflow/EDUagent
git add backend/app/schemas/personalized.py backend/app/api/v1/personalized_resources.py
git commit -m "feat: 新增 personalized_resources schema 和 GET 列表接口"
```

---

## Task 3: POST 生成接口（quiz 路径）

**Files:**
- Modify: `backend/app/api/v1/personalized_resources.py`（追加 POST 路由，quiz 路径）

- [ ] **Step 1: 追加 POST 路由（quiz 路径）到 personalized_resources.py**

在 `list_personalized_resources` 函数之后追加：

```python
@router.post("/generate")
async def generate_personalized_resource(
    req: PersonalizedResourceGenerateRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    catalog_context = await resolve_generation_catalog(db, req.course_id)

    if req.generate_type == "quiz":
        # ------- Quiz 生成路径（同步，Agent 直接返回题目）-------
        from app.schemas.operations import QuizGenerateRequest
        QQ = QuizQuestion  # alias for clarity below

        # 组装基础 payload（复用 quiz_service.assemble_generate_payload 的 personalization_context）
        quiz_req = QuizGenerateRequest(
            course_id=req.course_id,
            chapter=req.chapter,
            knowledge_point=req.knowledge_point,
            question_types=req.question_types,
            count=req.count,
            difficulty=req.difficulty,
            personalized=True,
        )
        payload = await quiz_service.assemble_generate_payload(
            current_user.id,
            req.course_id,
            catalog_context.catalog_id,
            quiz_req,
            db,
        )

        # 若有错题 ID，查询错题内容并写入 wrong_points（覆盖历史错题）
        if req.wrong_question_ids:
            wrong_r = await db.execute(
                select(QQ.id, QQ.content, QQ.knowledge_point)
                .where(
                    QQ.id.in_(req.wrong_question_ids),
                    QQ.is_deleted == False,
                )
            )
            wrong_points = [
                {"name": row.knowledge_point or "", "content": row.content[:200]}
                for row in wrong_r.all()
            ]
            if wrong_points:
                ctx = payload.get("personalization_context") or {}
                ctx["wrong_points"] = wrong_points
                payload["personalization_context"] = ctx

        try:
            data = await agent_client.post_json("/agent/v1/assessment/generate-questions", payload)
        except AgentServiceError as e:
            return JSONResponse(
                status_code=500,
                content={"code": 500, "message": f"Agent 调用失败: {e.message}", "data": None},
            )

        questions = data.get("questions", [])
        question_ids: list[str] = []
        for q in questions:
            new_q = QQ(
                course_id=req.course_id,
                catalog_id=catalog_context.catalog_id,
                chapter=q.get("chapter", req.chapter or ""),
                knowledge_point=q.get("knowledge_point", req.knowledge_point or ""),
                type=q.get("type", "single_choice"),
                source="personalized",
                personalized=True,
                owner_user_id=current_user.id,
                difficulty=q.get("difficulty", req.difficulty or "medium"),
                content=q.get("content", ""),
                options=q.get("options", []),
                correct_answer=str(q.get("answer", "")),
                explanation=q.get("explanation", ""),
            )
            db.add(new_q)
            await db.flush()
            question_ids.append(new_q.id)

        # 写入 user_personalized_resources（每道题一行）
        for qid in question_ids:
            upr = UserPersonalizedResource(
                user_id=current_user.id,
                course_id=req.course_id,
                question_id=qid,
                source_type=req.source_type,
            )
            db.add(upr)

        await db.flush()
        await db.commit()

        return JSONResponse(
            status_code=202,
            content={
                "code": 202,
                "message": "accepted",
                "data": {"generate_type": "quiz", "question_count": len(question_ids)},
            },
        )

    else:
        # ------- Resource 生成路径（异步 Webhook）-------
        AT = AsyncTask  # alias

        task = AT(
            task_type="resource_generation",
            status="processing",
            user_id=current_user.id,
            course_id=req.course_id,
            result=catalog_context.model_dump(),
        )
        db.add(task)
        await db.flush()
        await db.refresh(task)

        payload: dict = {
            "task_id": task.id,
            "user_id": current_user.id,
            "course_id": catalog_context.catalog_id,
            "webhook_url": _webhook_url(request),
        }
        if req.chapter:
            payload["chapter"] = req.chapter
        if req.knowledge_point:
            payload["knowledge_point"] = req.knowledge_point
        if req.resource_types:
            payload["resource_types"] = req.resource_types

        try:
            await agent_client.post_json("/agent/v1/resources/generate", payload)
        except AgentServiceError as e:
            task.status = "failed"
            task.error_code = str(e.agent_code or "agent_error")
            task.error_message = e.message
            task.completed_at = datetime.now(timezone.utc)
            await db.flush()

        # 写入 user_personalized_resources（task_id 关联，resource_id 等 Webhook 回调补全）
        upr = UserPersonalizedResource(
            user_id=current_user.id,
            course_id=req.course_id,
            source_type=req.source_type,
            task_id=task.id,
        )
        db.add(upr)
        await db.flush()
        await db.commit()

        return JSONResponse(
            status_code=202,
            content={
                "code": 202,
                "message": "accepted",
                "data": {"task_id": task.id, "generate_type": "resource"},
            },
        )
```

- [ ] **Step 2: 校验语法**

```bash
cd /home/yezisama/workspace/workflow/EDUagent
python3 -m py_compile backend/app/api/v1/personalized_resources.py && echo "OK"
```

Expected: `OK`

- [ ] **Step 3: Commit**

```bash
cd /home/yezisama/workspace/workflow/EDUagent
git add backend/app/api/v1/personalized_resources.py
git commit -m "feat: 新增个性化资源 POST 生成接口（quiz + resource 双路径）"
```

---

## Task 4: 注册路由 + Webhook 扩展

**Files:**
- Modify: `backend/app/main.py`
- Modify: `backend/app/api/v1/webhooks.py`

- [ ] **Step 1: 在 main.py 注册新路由**

在 `backend/app/main.py` 中，将 import 行从：

```python
from app.api.v1 import (
    admin, auth, catalogs, courses, evaluation, learning_path,
    learning_activities, profile, quiz, resources, tasks, teaching, tutoring,
    users, webhooks,
)
```

改为：

```python
from app.api.v1 import (
    admin, auth, catalogs, courses, evaluation, learning_path,
    learning_activities, personalized_resources, profile, quiz, resources,
    tasks, teaching, tutoring, users, webhooks,
)
```

在 `app.include_router(resources.router)` 之后（第 111 行附近）追加：

```python
app.include_router(personalized_resources.router)
```

- [ ] **Step 2: 扩展 Webhook 补全 resource_id**

在 `backend/app/api/v1/webhooks.py` 中，在文件顶部 import 中添加：

```python
from app.models.others import AsyncTask, Resource, UserPersonalizedResource
```

（将原有的 `from app.models.others import AsyncTask, Resource` 替换）

在 `agent_webhook` 函数中，找到以下代码段：

```python
        task.status = "completed"
        task.result = {
            **task_result,
            "agent_result": req.result,
            "resource_count": len(resources_data),
        }
        task.progress = 100
        task.completed_at = datetime.now(timezone.utc)
        await _recompute_parent_resource_generation_task(db, task)
```

在 `await _recompute_parent_resource_generation_task(db, task)` 之前插入：

```python
        # 补全 user_personalized_resources.resource_id（若该任务由个性化生成触发）
        upr_result = await db.execute(
            select(UserPersonalizedResource).where(
                UserPersonalizedResource.task_id == task.id,
                UserPersonalizedResource.is_deleted == False,
            )
        )
        upr_row = upr_result.scalar_one_or_none()
        if upr_row and newly_created_resources:
            # 第一个资源更新现有行，多余资源新增行
            upr_row.resource_id = newly_created_resources[0].id
            for extra_resource in newly_created_resources[1:]:
                db.add(UserPersonalizedResource(
                    user_id=upr_row.user_id,
                    course_id=upr_row.course_id,
                    resource_id=extra_resource.id,
                    source_type=upr_row.source_type,
                    task_id=task.id,
                ))
```

注意：需要在 Webhook 中先收集 `newly_created_resources` 列表。将现有的 resource 写入循环改为：

```python
        newly_created_resources = []
        for r in resources_data:
            chapter, knowledge_point, tags = _metadata_for_resource(task, r)
            resource = Resource(
                id=uuid.uuid4().hex[:16],
                course_id=primary_course_id,
                catalog_id=catalog_id,
                title=r["title"],
                type=r["type"],
                description=r["description"],
                tags=tags,
                chapter=chapter,
                knowledge_point=knowledge_point,
                content=r["content"],
                url="",
                create_by=task.user_id,
            )
            db.add(resource)
            newly_created_resources.append(resource)
```

（原代码是 `for r in resources_data: ... resource = Resource(...) db.add(resource)`，改为收集到列表）

- [ ] **Step 3: 校验语法**

```bash
cd /home/yezisama/workspace/workflow/EDUagent
python3 -m py_compile backend/app/main.py && echo "main OK"
python3 -m py_compile backend/app/api/v1/webhooks.py && echo "webhooks OK"
```

Expected: 两行均输出 `OK`

- [ ] **Step 4: Commit**

```bash
cd /home/yezisama/workspace/workflow/EDUagent
git add backend/app/main.py backend/app/api/v1/webhooks.py
git commit -m "feat: 注册个性化资源路由，Webhook 补全 resource_id 关联"
```

---

## Task 5: 前端 API Service + Sidebar + App.jsx 路由

**Files:**
- Create: `frontend/src/api/services/personalizedResources.js`
- Modify: `frontend/src/components/Sidebar.jsx`
- Modify: `frontend/src/App.jsx`

- [ ] **Step 1: 创建前端 API service**

`frontend/src/api/services/personalizedResources.js`:

```js
import apiClient from '../client';

export const personalizedResourcesService = {
  list(courseId, params = {}) {
    return apiClient.get('/personalized-resources', { params: { course_id: courseId, ...params } });
  },
  generate(data) {
    return apiClient.post('/personalized-resources/generate', data);
  },
};
```

- [ ] **Step 2: 修改 Sidebar.jsx 添加导航入口**

在 `frontend/src/components/Sidebar.jsx` 中，在 `<Link to="/dashboard" ...>` 之后，`</div>` 关闭前插入：

```jsx
          <Link to="/personalized-resources" className={`flex items-center space-x-3 px-4 py-3 rounded-lg transition-all duration-200 ease-in-out cursor-pointer hover:pl-5 ${isActive('/personalized-resources') ? 'bg-cyan-50 text-cyan-600 border-r-4 border-cyan-500' : 'text-gray-500 hover:bg-gray-50'}`}>
            <span className="material-symbols-outlined">psychology</span>
            <span className="font-body-md">个性化资源</span>
          </Link>
```

- [ ] **Step 3: 修改 App.jsx 注册路由**

在 `frontend/src/App.jsx` 中：

1. 在 import 区块中（在 `import ResourceDetail` 之后）添加：
```jsx
import PersonalizedResources from './pages/PersonalizedResources';
```

2. 在学生路由区块中（`/learning-effects` 路由之后）添加：
```jsx
            <Route path="/personalized-resources" element={<ProtectedRoute allowedRoles={['student']}><PersonalizedResources /></ProtectedRoute>} />
```

- [ ] **Step 4: 构建校验**

```bash
cd /home/yezisama/workspace/workflow/EDUagent/frontend
npm run lint 2>&1 | tail -5
npm run build 2>&1 | tail -10
```

Expected: lint 无 error，build 成功（PersonalizedResources 不存在会 build 失败，此步骤允许跳过 build，Task 6 完成后再验）

- [ ] **Step 5: Commit**

```bash
cd /home/yezisama/workspace/workflow/EDUagent
git add frontend/src/api/services/personalizedResources.js frontend/src/components/Sidebar.jsx frontend/src/App.jsx
git commit -m "feat: 个性化资源前端 service、Sidebar 入口、路由注册"
```

---

## Task 6: 个性化资源主页面

**Files:**
- Create: `frontend/src/pages/PersonalizedResources.jsx`

- [ ] **Step 1: 创建页面文件**

`frontend/src/pages/PersonalizedResources.jsx`:

```jsx
import { useState, useEffect, useCallback, useRef } from 'react';
import { useLocation, Link } from 'react-router-dom';
import Navbar from '../components/Navbar';
import Sidebar from '../components/Sidebar';
import { useCourse } from '../context/CourseContext';
import { personalizedResourcesService } from '../api/services/personalizedResources';
import GenerateModal from '../components/personalized/GenerateModal';

const TYPE_ICON = {
  document: 'description',
  mindmap: 'account_tree',
  reading: 'menu_book',
  code: 'code',
  video: 'play_circle',
  single_choice: 'radio_button_checked',
  multi_choice: 'check_box',
  short_answer: 'edit_note',
};

const SOURCE_LABEL = {
  quiz_wrong_answer: '错题触发',
  manual: '手动生成',
};

function ResourceCard({ item }) {
  if (item.task_status === 'processing') {
    return (
      <div className="bg-white border border-dashed border-cyan-300 rounded-xl p-md flex items-center gap-md animate-pulse">
        <div className="w-10 h-10 rounded-full bg-cyan-100 flex items-center justify-center">
          <span className="material-symbols-outlined text-cyan-400 animate-spin">progress_activity</span>
        </div>
        <div>
          <p className="text-body-md font-medium text-secondary">正在生成中...</p>
          <p className="text-label-sm text-gray-400">{SOURCE_LABEL[item.source_type] || item.source_type}</p>
        </div>
      </div>
    );
  }

  if (item.task_status === 'failed') {
    return (
      <div className="bg-white border border-error/20 rounded-xl p-md flex items-center gap-md">
        <div className="w-10 h-10 rounded-full bg-error-container flex items-center justify-center text-error">
          <span className="material-symbols-outlined">error</span>
        </div>
        <div>
          <p className="text-body-md font-medium text-error">生成失败</p>
          <p className="text-label-sm text-gray-400">可重新尝试生成</p>
        </div>
      </div>
    );
  }

  if (item.question) {
    const q = item.question;
    return (
      <div className="bg-white border border-outline-variant rounded-xl p-md hover:shadow-sm transition-shadow">
        <div className="flex items-start gap-md">
          <div className="w-10 h-10 rounded-full bg-primary-container/10 flex items-center justify-center text-primary-container flex-shrink-0">
            <span className="material-symbols-outlined">{TYPE_ICON[q.type] || 'quiz'}</span>
          </div>
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-sm mb-xs flex-wrap">
              <span className="text-label-sm text-cyan-600 bg-cyan-50 px-2 py-0.5 rounded-full">{q.knowledge_point}</span>
              <span className="text-label-sm text-gray-400">{q.difficulty}</span>
              <span className="text-label-sm text-orange-500 bg-orange-50 px-2 py-0.5 rounded-full">{SOURCE_LABEL[item.source_type]}</span>
            </div>
            <p className="text-body-md text-on-surface line-clamp-2">{q.content}</p>
          </div>
        </div>
      </div>
    );
  }

  if (item.resource) {
    const r = item.resource;
    return (
      <Link to={`/resource/${r.id}`} className="block bg-white border border-outline-variant rounded-xl p-md hover:shadow-sm transition-shadow">
        <div className="flex items-start gap-md">
          <div className="w-10 h-10 rounded-full bg-surface-container-highest flex items-center justify-center text-secondary flex-shrink-0">
            <span className="material-symbols-outlined">{TYPE_ICON[r.type] || 'article'}</span>
          </div>
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-sm mb-xs flex-wrap">
              <span className="text-label-sm text-cyan-600 bg-cyan-50 px-2 py-0.5 rounded-full">{r.knowledge_point}</span>
              <span className="text-label-sm text-orange-500 bg-orange-50 px-2 py-0.5 rounded-full">{SOURCE_LABEL[item.source_type]}</span>
            </div>
            <h4 className="text-body-md font-medium text-on-surface truncate">{r.title}</h4>
            {r.description && <p className="text-label-sm text-secondary mt-1 line-clamp-1">{r.description}</p>}
          </div>
        </div>
      </Link>
    );
  }

  return null;
}

export default function PersonalizedResources() {
  const { activeCourseId } = useCourse();
  const location = useLocation();
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [processingCount, setProcessingCount] = useState(0);
  const [filterSource, setFilterSource] = useState('all');
  const [showGenerateModal, setShowGenerateModal] = useState(false);
  const [total, setTotal] = useState(0);
  const pollRef = useRef(null);

  const fetchItems = useCallback(async () => {
    if (!activeCourseId) return;
    try {
      const params = {};
      if (filterSource !== 'all') params.source_type = filterSource;
      const res = await personalizedResourcesService.list(activeCourseId, params);
      if (res.code === 200) {
        setItems(res.data.items);
        setTotal(res.data.total);
        setProcessingCount(res.data.processing_count);
      }
    } catch (e) {
      console.error('Failed to fetch personalized resources', e);
    } finally {
      setLoading(false);
    }
  }, [activeCourseId, filterSource]);

  // 初始加载
  useEffect(() => {
    setLoading(true);
    fetchItems();
  }, [fetchItems]);

  // 轮询：processingCount > 0 时每 3 秒刷新一次
  useEffect(() => {
    if (pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }
    if (processingCount > 0) {
      pollRef.current = setInterval(fetchItems, 3000);
    }
    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, [processingCount, fetchItems]);

  const newTaskId = location.state?.newTaskId;
  const showNewTaskBanner = newTaskId && processingCount > 0;

  return (
    <div className="bg-surface min-h-screen">
      <Navbar />
      <Sidebar />
      <main className="ml-0 lg:ml-64 pt-16 min-h-screen">
        <div className="max-w-4xl mx-auto px-6 py-8">
          {/* Header */}
          <div className="flex items-center justify-between mb-6">
            <div>
              <h1 className="font-h2 text-h2 text-on-surface">个性化资源</h1>
              <p className="text-body-md text-secondary mt-1">专属于你的学习材料与练习题，共 {total} 项</p>
            </div>
            <button
              onClick={() => setShowGenerateModal(true)}
              className="flex items-center gap-2 px-4 py-2 bg-primary-container text-white rounded-xl font-bold hover:brightness-110 active:scale-95 transition-all shadow-sm"
            >
              <span className="material-symbols-outlined">add</span>
              生成资源
            </button>
          </div>

          {/* 生成中提示横幅 */}
          {showNewTaskBanner && (
            <div className="mb-4 bg-cyan-50 border border-cyan-200 rounded-xl px-4 py-3 flex items-center gap-3">
              <span className="material-symbols-outlined text-cyan-500 animate-spin">progress_activity</span>
              <p className="text-body-md text-cyan-700">正在为你生成个性化练习，请稍候...</p>
            </div>
          )}

          {/* 筛选栏 */}
          <div className="flex gap-2 mb-6 flex-wrap">
            {[
              { value: 'all', label: '全部' },
              { value: 'quiz_wrong_answer', label: '错题触发' },
              { value: 'manual', label: '手动生成' },
            ].map(opt => (
              <button
                key={opt.value}
                onClick={() => setFilterSource(opt.value)}
                className={`px-3 py-1.5 rounded-full text-label-sm font-medium transition-colors ${
                  filterSource === opt.value
                    ? 'bg-primary-container text-white'
                    : 'bg-surface-container text-secondary hover:bg-surface-container-high'
                }`}
              >
                {opt.label}
              </button>
            ))}
          </div>

          {/* 内容区 */}
          {loading ? (
            <div className="flex items-center justify-center py-20">
              <span className="material-symbols-outlined animate-spin text-4xl text-primary">progress_activity</span>
            </div>
          ) : items.length === 0 ? (
            <div className="text-center py-20 text-secondary">
              <span className="material-symbols-outlined text-6xl mb-4 block text-gray-300">psychology</span>
              <p className="text-body-lg">暂无个性化资源</p>
              <p className="text-body-md mt-2">完成练习后正确率低于 60% 会自动触发生成，或点击"生成资源"手动创建</p>
            </div>
          ) : (
            <div className="space-y-3">
              {items.map(item => (
                <ResourceCard key={item.id} item={item} />
              ))}
            </div>
          )}
        </div>
      </main>

      {showGenerateModal && (
        <GenerateModal
          courseId={activeCourseId}
          onClose={() => setShowGenerateModal(false)}
          onGenerated={() => {
            setShowGenerateModal(false);
            fetchItems();
          }}
        />
      )}
    </div>
  );
}
```

- [ ] **Step 2: 校验构建**

```bash
cd /home/yezisama/workspace/workflow/EDUagent/frontend
npm run lint 2>&1 | tail -5
```

Expected: 无 error（GenerateModal 暂不存在时会有 import 错误，Task 7 完成后消除）

- [ ] **Step 3: Commit**

```bash
cd /home/yezisama/workspace/workflow/EDUagent
git add frontend/src/pages/PersonalizedResources.jsx
git commit -m "feat: 新增个性化资源主页面"
```

---

## Task 7: GenerateModal 三步引导组件

**Files:**
- Create: `frontend/src/components/personalized/GenerateModal.jsx`

- [ ] **Step 1: 创建目录和组件文件**

`frontend/src/components/personalized/GenerateModal.jsx`:

```jsx
import { useState, useEffect } from 'react';
import { learningService } from '../../api/services/learning';
import { personalizedResourcesService } from '../../api/services/personalizedResources';
import { useCourse } from '../../context/CourseContext';

const QUESTION_TYPE_OPTIONS = [
  { value: 'single_choice', label: '单选题', icon: 'radio_button_checked' },
  { value: 'multi_choice', label: '多选题', icon: 'check_box' },
  { value: 'short_answer', label: '问答题', icon: 'edit_note' },
];

const RESOURCE_TYPE_OPTIONS = [
  { value: 'document', label: '文档', icon: 'description' },
  { value: 'mindmap', label: '思维导图', icon: 'account_tree' },
  { value: 'reading', label: '阅读材料', icon: 'menu_book' },
  { value: 'code', label: '代码示例', icon: 'code' },
];

export default function GenerateModal({ courseId, onClose, onGenerated }) {
  const { activeCourseId } = useCourse();
  const cid = courseId || activeCourseId;

  const [step, setStep] = useState(1);
  const [nodes, setNodes] = useState([]);
  const [loadingPath, setLoadingPath] = useState(true);

  const [selectedChapter, setSelectedChapter] = useState(null);
  const [selectedKp, setSelectedKp] = useState(null);
  const [selectedQuestionTypes, setSelectedQuestionTypes] = useState([]);
  const [selectedResourceTypes, setSelectedResourceTypes] = useState([]);

  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!cid) return;
    learningService.getLearningPath(cid).then(res => {
      if (res.code === 200) {
        setNodes(res.data.nodes || []);
      }
    }).catch(() => {}).finally(() => setLoadingPath(false));
  }, [cid]);

  const chapters = [...new Set(nodes.map(n => n.chapter).filter(Boolean))];
  const kpsForChapter = selectedChapter
    ? nodes.filter(n => n.chapter === selectedChapter).map(n => ({ id: n.id, name: n.name }))
    : [];

  const canSubmit = selectedKp && (selectedQuestionTypes.length > 0 || selectedResourceTypes.length > 0);

  const toggleQuestionType = (val) => {
    setSelectedQuestionTypes(prev =>
      prev.includes(val) ? prev.filter(v => v !== val) : [...prev, val]
    );
  };

  const toggleResourceType = (val) => {
    setSelectedResourceTypes(prev =>
      prev.includes(val) ? prev.filter(v => v !== val) : [...prev, val]
    );
  };

  const handleSubmit = async () => {
    if (!canSubmit) return;
    setGenerating(true);
    setError(null);
    const promises = [];

    if (selectedQuestionTypes.length > 0) {
      promises.push(
        personalizedResourcesService.generate({
          course_id: cid,
          generate_type: 'quiz',
          source_type: 'manual',
          chapter: selectedChapter,
          knowledge_point: selectedKp,
          question_types: selectedQuestionTypes,
          count: 5,
        })
      );
    }

    if (selectedResourceTypes.length > 0) {
      promises.push(
        personalizedResourcesService.generate({
          course_id: cid,
          generate_type: 'resource',
          source_type: 'manual',
          chapter: selectedChapter,
          knowledge_point: selectedKp,
          resource_types: selectedResourceTypes,
        })
      );
    }

    const results = await Promise.allSettled(promises);
    const hasError = results.some(r => r.status === 'rejected');
    if (hasError) {
      setError('部分生成请求失败，已提交的任务仍在执行中');
    }
    setGenerating(false);
    onGenerated();
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/40 backdrop-blur-sm">
      <div className="bg-white rounded-2xl shadow-xl w-full max-w-lg overflow-hidden">
        {/* Header */}
        <div className="px-6 pt-5 pb-4 border-b border-surface-container">
          <div className="flex items-center justify-between">
            <h2 className="font-h3 text-on-surface">生成个性化资源</h2>
            <button onClick={onClose} className="text-secondary hover:text-on-surface transition-colors">
              <span className="material-symbols-outlined">close</span>
            </button>
          </div>
          {/* Step indicator */}
          <div className="flex items-center gap-2 mt-3">
            {[1, 2, 3].map(s => (
              <div key={s} className="flex items-center gap-2">
                <div className={`w-6 h-6 rounded-full flex items-center justify-center text-[11px] font-bold transition-colors ${
                  s < step ? 'bg-primary-container text-white' :
                  s === step ? 'bg-cyan-600 text-white' :
                  'bg-surface-container text-secondary'
                }`}>
                  {s < step ? <span className="material-symbols-outlined text-[14px]">check</span> : s}
                </div>
                {s < 3 && <div className={`h-px w-8 ${s < step ? 'bg-primary-container' : 'bg-surface-container-high'}`} />}
              </div>
            ))}
            <span className="text-label-sm text-secondary ml-2">
              {step === 1 ? '选择章节' : step === 2 ? '选择知识点' : '选择资源类型'}
            </span>
          </div>
        </div>

        {/* Body */}
        <div className="px-6 py-5 min-h-[200px]">
          {loadingPath ? (
            <div className="flex items-center justify-center py-10">
              <span className="material-symbols-outlined animate-spin text-3xl text-primary">progress_activity</span>
            </div>
          ) : step === 1 ? (
            <div>
              <p className="text-body-md text-secondary mb-4">请选择要生成资源的章节：</p>
              {chapters.length === 0 ? (
                <p className="text-secondary text-center py-6">暂无章节数据，请先确认学习路径已加载</p>
              ) : (
                <div className="flex flex-wrap gap-2">
                  {chapters.map(ch => (
                    <button
                      key={ch}
                      onClick={() => { setSelectedChapter(ch); setSelectedKp(null); setStep(2); }}
                      className="px-4 py-2 rounded-xl border border-outline-variant text-body-md hover:bg-cyan-50 hover:border-cyan-300 hover:text-cyan-700 transition-colors"
                    >
                      {ch}
                    </button>
                  ))}
                </div>
              )}
            </div>
          ) : step === 2 ? (
            <div>
              <p className="text-body-md text-secondary mb-4">
                章节：<span className="text-on-surface font-medium">{selectedChapter}</span> — 请选择知识点：
              </p>
              <div className="flex flex-wrap gap-2">
                {kpsForChapter.map(kp => (
                  <button
                    key={kp.id}
                    onClick={() => { setSelectedKp(kp.name); setStep(3); }}
                    className={`px-4 py-2 rounded-xl border text-body-md transition-colors ${
                      selectedKp === kp.name
                        ? 'border-cyan-500 bg-cyan-50 text-cyan-700'
                        : 'border-outline-variant hover:bg-cyan-50 hover:border-cyan-300 hover:text-cyan-700'
                    }`}
                  >
                    {kp.name}
                  </button>
                ))}
              </div>
            </div>
          ) : (
            <div>
              <p className="text-body-md text-secondary mb-4">
                知识点：<span className="text-on-surface font-medium">{selectedKp}</span> — 请选择资源类型（可多选）：
              </p>
              <div className="mb-4">
                <p className="text-label-sm text-secondary uppercase tracking-wider mb-2">练习题</p>
                <div className="flex flex-wrap gap-2">
                  {QUESTION_TYPE_OPTIONS.map(opt => (
                    <button
                      key={opt.value}
                      onClick={() => toggleQuestionType(opt.value)}
                      className={`flex items-center gap-1.5 px-3 py-2 rounded-xl border text-body-md transition-colors ${
                        selectedQuestionTypes.includes(opt.value)
                          ? 'border-primary-container bg-primary-container/10 text-primary-container'
                          : 'border-outline-variant hover:bg-surface-container'
                      }`}
                    >
                      <span className="material-symbols-outlined text-[16px]">{opt.icon}</span>
                      {opt.label}
                    </button>
                  ))}
                </div>
              </div>
              <div>
                <p className="text-label-sm text-secondary uppercase tracking-wider mb-2">学习资源</p>
                <div className="flex flex-wrap gap-2">
                  {RESOURCE_TYPE_OPTIONS.map(opt => (
                    <button
                      key={opt.value}
                      onClick={() => toggleResourceType(opt.value)}
                      className={`flex items-center gap-1.5 px-3 py-2 rounded-xl border text-body-md transition-colors ${
                        selectedResourceTypes.includes(opt.value)
                          ? 'border-primary-container bg-primary-container/10 text-primary-container'
                          : 'border-outline-variant hover:bg-surface-container'
                      }`}
                    >
                      <span className="material-symbols-outlined text-[16px]">{opt.icon}</span>
                      {opt.label}
                    </button>
                  ))}
                </div>
              </div>
              {error && <p className="text-error text-label-sm mt-3">{error}</p>}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="px-6 py-4 border-t border-surface-container flex items-center justify-between">
          <button
            onClick={() => step > 1 ? setStep(step - 1) : onClose()}
            className="text-secondary hover:text-on-surface transition-colors text-body-md"
          >
            {step > 1 ? '上一步' : '取消'}
          </button>
          {step === 3 && (
            <button
              onClick={handleSubmit}
              disabled={!canSubmit || generating}
              className="flex items-center gap-2 px-5 py-2 bg-primary-container text-white rounded-xl font-bold hover:brightness-110 active:scale-95 transition-all disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {generating ? (
                <span className="material-symbols-outlined animate-spin text-[16px]">progress_activity</span>
              ) : (
                <span className="material-symbols-outlined text-[16px]">auto_awesome</span>
              )}
              {generating ? '生成中...' : '确认生成'}
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: 校验构建**

```bash
cd /home/yezisama/workspace/workflow/EDUagent/frontend
npm run lint 2>&1 | tail -5
npm run build 2>&1 | tail -10
```

Expected: lint 无 error，build 成功

- [ ] **Step 3: Commit**

```bash
cd /home/yezisama/workspace/workflow/EDUagent
git add frontend/src/components/personalized/GenerateModal.jsx
git commit -m "feat: 个性化资源三步引导 Modal 组件"
```

---

## Task 8: PracticeResult 错题触发横幅

**Files:**
- Modify: `frontend/src/pages/PracticeResult.jsx`

- [ ] **Step 1: 在 PracticeResult.jsx 中添加导入和横幅逻辑**

在文件顶部 import 区块中（`useNavigate`、`useLocation` 已存在），追加以下两行（`useState` 若已在 react import 中则无需重复）：

```jsx
import { personalizedResourcesService } from '../api/services/personalizedResources';
import { useCourse } from '../context/CourseContext';
```

注意：检查文件顶部是否已有 `useState` 导入，若无则在 react import 中补充。`useNavigate`、`useLocation` 已存在。

在 `PracticeResult` 组件函数体内（`const accuracy = ...` 计算行之后）添加：

```jsx
  const { activeCourseId } = useCourse();
  const [generating, setGenerating] = useState(false);
  const [generateError, setGenerateError] = useState(null);

  const wrongQuestionIds = resultData?.per_question_results
    ?.filter(q => !q.is_correct)
    .map(q => q.question_id)
    .filter(Boolean) || [];

  const handleGenerateWrongAnswerQuiz = async () => {
    if (!wrongQuestionIds.length || !activeCourseId) return;
    setGenerating(true);
    setGenerateError(null);
    try {
      await personalizedResourcesService.generate({
        course_id: activeCourseId,
        generate_type: 'quiz',
        source_type: 'quiz_wrong_answer',
        wrong_question_ids: wrongQuestionIds,
        count: 5,
      });
      navigate('/personalized-resources', { state: { newTaskId: 'triggered' } });
    } catch (e) {
      setGenerateError('生成失败，请稍后重试');
      setGenerating(false);
    }
  };
```

- [ ] **Step 2: 在 Modal Footer 中插入横幅（条件渲染）**

在 `frontend/src/pages/PracticeResult.jsx` 中找到 Modal Footer div（包含"返回主页"和"下一组练习"按钮的部分），在该 div 之前插入（作为 flex col 的一部分）：

找到：
```jsx
          {/* Modal Footer (Actions) */}
          <div className="px-xl py-lg bg-surface-container-low border-t border-surface-container flex gap-md justify-center">
```

将整个 Modal Footer 区域替换为：

```jsx
          {/* Modal Footer (Actions) */}
          <div className="px-xl py-lg bg-surface-container-low border-t border-surface-container flex flex-col gap-md">
            {accuracy < 60 && wrongQuestionIds.length > 0 && (
              <div className="bg-amber-50 border border-amber-200 rounded-xl px-4 py-3 flex items-start gap-3">
                <span className="material-symbols-outlined text-amber-500 flex-shrink-0 mt-0.5">warning</span>
                <div className="flex-1">
                  <p className="text-body-md font-medium text-amber-800">本次正确率较低（{accuracy}%）</p>
                  <p className="text-label-sm text-amber-600 mt-0.5">是否生成针对错题的个性化练习，帮助你巩固薄弱知识点？</p>
                  {generateError && <p className="text-error text-label-sm mt-1">{generateError}</p>}
                </div>
                <button
                  onClick={handleGenerateWrongAnswerQuiz}
                  disabled={generating}
                  className="flex-shrink-0 flex items-center gap-1.5 px-3 py-2 bg-amber-500 text-white rounded-lg text-label-sm font-bold hover:bg-amber-600 active:scale-95 transition-all disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {generating
                    ? <span className="material-symbols-outlined text-[14px] animate-spin">progress_activity</span>
                    : <span className="material-symbols-outlined text-[14px]">auto_awesome</span>
                  }
                  {generating ? '生成中...' : '生成针对性练习'}
                </button>
              </div>
            )}
            <div className="flex gap-md justify-center">
              <button 
                onClick={() => navigate('/dashboard')}
                className="flex-1 max-w-[200px] h-12 rounded-xl border-2 border-primary-container text-primary font-bold hover:bg-primary-container/5 active:scale-95 transition-all flex items-center justify-center gap-2 cursor-pointer"
              >
                <span className="material-symbols-outlined">home</span>
                返回主页
              </button>
              <button 
                onClick={() => navigate('/quiz')}
                className="flex-1 max-w-[200px] h-12 rounded-xl bg-primary-container text-white font-bold shadow-lg shadow-primary-container/20 hover:brightness-110 active:scale-95 transition-all flex items-center justify-center gap-2 cursor-pointer"
              >
                下一组练习
                <span className="material-symbols-outlined">arrow_forward</span>
              </button>
            </div>
          </div>
```

- [ ] **Step 3: 校验构建**

```bash
cd /home/yezisama/workspace/workflow/EDUagent/frontend
npm run lint 2>&1 | tail -5
npm run build 2>&1 | tail -10
```

Expected: lint 无 error，build 成功

- [ ] **Step 4: Commit**

```bash
cd /home/yezisama/workspace/workflow/EDUagent
git add frontend/src/pages/PracticeResult.jsx
git commit -m "feat: PracticeResult 低正确率横幅，触发个性化错题练习生成"
```

---

## Task 9: 端到端验收 + WORKFLOW.md 记录

- [ ] **Step 1: 后端全量语法校验**

```bash
cd /home/yezisama/workspace/workflow/EDUagent
python3 -m py_compile backend/app/models/others.py && echo "models OK"
python3 -m py_compile backend/app/schemas/personalized.py && echo "schema OK"
python3 -m py_compile backend/app/api/v1/personalized_resources.py && echo "route OK"
python3 -m py_compile backend/app/api/v1/webhooks.py && echo "webhooks OK"
python3 -m py_compile backend/app/main.py && echo "main OK"
```

Expected: 5 行均输出 `OK`

- [ ] **Step 2: 前端完整构建**

```bash
cd /home/yezisama/workspace/workflow/EDUagent/frontend
npm run lint 2>&1 | tail -5
npm run build 2>&1 | tail -10
```

Expected: lint 无 error，build 成功

- [ ] **Step 3: 手动 E2E 验收**

按以下顺序逐一验证（需要后端服务运行中）：

1. **Sidebar 入口**：登录学生账号，确认 Sidebar 出现"个性化资源"菜单项，点击跳转 `/personalized-resources`
2. **空状态页面**：首次进入显示空状态文案和"生成资源"按钮
3. **GenerateModal 三步流程**：点击"生成资源" → Step1 选章节 → Step2 选知识点 → Step3 选单选题 → 确认生成 → Modal 关闭，列表刷新出现 processing 卡片
4. **轮询过渡**：等待约 10-30 秒，processing 卡转变为具体题目卡（需 Agent 正常运行）
5. **错题触发**：在 Quiz 页故意答错所有题（或至少 40%），提交，进入 PracticeResult 页面，确认出现黄色横幅
6. **点击生成并跳转**：点击"生成针对性练习"，触发后自动跳转至个性化资源页，顶部出现生成中横幅

- [ ] **Step 4: 更新 WORKFLOW.md**

在 `WORKFLOW.md` 末尾追加：

```markdown
### 2026-06-16

- 个性化资源功能（spec：`docs/superpowers/specs/2026-06-16-personalized-resources-design.md`）：
  - 新建表 `user_personalized_resources`（DDL 已执行），新增 `UserPersonalizedResource` SQLAlchemy model（`backend/app/models/others.py`）
  - 新建 `backend/app/schemas/personalized.py`：`PersonalizedResourceGenerateRequest`
  - 新建 `backend/app/api/v1/personalized_resources.py`：`GET /api/v1/personalized-resources`（列表）、`POST /api/v1/personalized-resources/generate`（quiz + resource 双路径）
  - 修改 `backend/app/main.py`：注册 `personalized_resources.router`
  - 修改 `backend/app/api/v1/webhooks.py`：resource_generation 回调补全 `user_personalized_resources.resource_id`
  - 新建 `frontend/src/api/services/personalizedResources.js`
  - 新建 `frontend/src/pages/PersonalizedResources.jsx`：独立页面，含轮询（processingCount>0 每 3s 刷新）
  - 新建 `frontend/src/components/personalized/GenerateModal.jsx`：三步引导（章节→知识点→资源类型）
  - 修改 `frontend/src/pages/PracticeResult.jsx`：accuracy<60 显示黄色横幅，点击触发错题 quiz 生成并跳转
  - 修改 `frontend/src/components/Sidebar.jsx`：添加"个性化资源"导航入口
  - 修改 `frontend/src/App.jsx`：注册 `/personalized-resources` 路由
  - 接口漂移：新增 `/api/v1/personalized-resources` 接口族（学生可用），`personalization_context.wrong_points` 新增 `content` 字段
  - 验证：`py_compile` 全通过；`npm run build` 通过
```

- [ ] **Step 5: 最终 Commit**

```bash
cd /home/yezisama/workspace/workflow/EDUagent
git add WORKFLOW.md
git commit -m "docs: 记录个性化资源功能实现至 WORKFLOW.md"
```
