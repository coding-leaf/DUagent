# AIChat Context Injection v1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 AIChat 的上下文注入从扁平 `user_profile` 升级为 Backend 结构化 context snapshot，并在 `agent_service_v2` 按 AgentScope 2.x 边界消费；RAG / Memory 仅以 placeholder tool 形式存在，未启用能力必须显式报告，禁止兜底伪装。

**Architecture:** A+ — Backend 聚合可信学习上下文快照（learner / custom_instructions / course / conversation / runtime_policy）；`agent_service_v2` 把快照分流进 system prompt、history messages 与 placeholder tools；前端展示 placeholder / 未启用状态，不生成假 `source_refs` 或长期记忆。

**Tech Stack:** FastAPI + SQLAlchemy 2.x（Backend）、AgentScope 2.0.3 `Agent` / `Toolkit` / `ToolGroup` / `FunctionTool` / `reply_stream`（agent_service_v2）、React + Vitest + Testing Library（frontend）。

## Global Constraints

- AgentScope 版本固定 `agentscope[full]>=2,<3`，已安装版本 `2.0.3`；不得编造未通过 introspection 的 API。
- v2 运行时只走 `agent_service_v2/`，不把旧 `agent_service/` 的 memory/RAG 实现搬回主线。
- 当前阶段禁止启用真实 `RAGMiddleware` / `Mem0Middleware` / `KnowledgeBase` / `QdrantStore`；RAG / Memory 只做 placeholder tool。
- 禁止兜底伪装：能力未启用、上下文缺失、来源不足时必须显式报告，不得用通用知识冒充课程资料、不得用 recent messages 冒充长期记忆、不得生成假 `source_refs`。
- Backend 不直连 Qdrant；`agent_service_v2` 不写 MySQL；Frontend 不直连 Agent Service。
- 接口变更必须在 `WorkLine.md` 记录漂移；中等/大改提交前附结构化自检（单文件 <300 行、单函数 <50 行、无未声明依赖、Router/Page 不写业务逻辑、注释只写 why）。
- 验证命令：`cd frontend && npm run lint && npm run build`；`cd backend && ../.venv/bin/python -m pytest <test> -q`；`cd agent_service_v2 && ./.venv/bin/pytest <test> -q`。

---

## File Structure

### Backend

- Create: `backend/migrations/2026-07-02-add-users-custom-instruction.sql` — 给 `users` 加 `custom_instruction` 列的幂等迁移。
- Modify: `backend/schema.sql` — 在 `users` 建表语句里同步新增列，保持 schema 与迁移一致。
- Modify: `backend/app/models/user.py:13-31` — `User` 模型新增 `custom_instruction` 映射列。
- Modify: `backend/app/schemas/user.py:5-10` — `UpdateUserRequest` 新增可选 `custom_instruction`。
- Modify: `backend/app/api/v1/users.py:10-53` — `_user_info` 输出新字段；`update_my_info` 支持写入。
- Create: `backend/app/services/tutoring_context_snapshot.py` — 纯函数模块，把 `user_profile`/`course`/`conversation` 聚合成结构化 snapshot。
- Create: `backend/tests/test_tutoring_context_snapshot.py` — snapshot 聚合的单测。
- Modify: `backend/app/services/tutoring_payload_builder.py:12-176` — `build()` 输出 `context_version` + 五个分区，保留旧字段兼容。
- Create: `backend/tests/test_tutoring_payload_builder.py` — payload 输出测试。
- Create: `backend/tests/test_users_me_custom_instruction.py` — `/users/me` 读写新字段。

### agent_service_v2

- Create: `agent_service_v2/src/agent_service_v2/session/context_snapshot.py` — 解析 Backend snapshot 的 dataclass 与降级策略。
- Create: `agent_service_v2/tests/test_context_snapshot.py` — 解析与降级测试。
- Modify: `agent_service_v2/src/agent_service_v2/agents/prompts.py:1-16` — `WORKBENCH_SYSTEM_PROMPT` 增加能力边界与禁止兜底条款；新增 `build_workbench_system_prompt(snapshot)`。
- Create: `agent_service_v2/tests/test_workbench_system_prompt.py` — system prompt 测试。
- Modify: `agent_service_v2/src/agent_service_v2/session/workbench_input.py:1-80` — 不再把 learner/profile 拼成伪 `UserMsg`；只产出 conversation history + current message。
- Modify: `agent_service_v2/tests/test_workbench_input.py` — 对齐新签名。
- Modify: `agent_service_v2/src/agent_service_v2/tools/workbench_placeholders.py:1-26` — `read_learning_state` 改为读取 snapshot 摘要；新增 `search_course_knowledge`、`search_memory`、`add_memory` placeholder。
- Modify: `agent_service_v2/src/agent_service_v2/tools/workbench_toolkit.py:14-57` — 新增 `knowledge` / `memory` placeholder ToolGroup；`learning_state` 传入 snapshot。
- Modify: `agent_service_v2/src/agent_service_v2/agents/permissions.py:4-13` — `SAFE_WORKBENCH_TOOLS` 增加 placeholder 工具名。
- Modify: `agent_service_v2/src/agent_service_v2/agents/workbench_factory.py:21-84` — 接收 snapshot，用 `build_workbench_system_prompt(snapshot)` 构造 system prompt；toolkit 注入 placeholder 工具。
- Modify: `agent_service_v2/src/agent_service_v2/session/workbench_session.py:157-288` — 把 context 解析成 snapshot 后传给 factory；`_run_agent` 透传 snapshot；发布 `context.attached` debug_log。
- Modify: `agent_service_v2/src/agent_service_v2/api/workbench.py:21-44` — 透传 `req.context` 给 session（session 内部解析）。
- Modify: `agent_service_v2/src/agent_service_v2/runtime/protocol_adapter.py:118-122` — `TOOL_COMPLETED` 透传 placeholder 工具的 `kind/status/output_summary`。
- Modify: 对应测试 `test_workbench_toolkit.py` / `test_workbench_factory.py` / `test_workbench_session.py` / `test_workbench_api.py` / `test_protocol_adapter.py`。

### Frontend

- Modify: `frontend/src/utils/chatStreamEvents.js:95-175` — `reduceAssistantMessageForEvent` 支持 placeholder tool 的 `status=not_configured`、`kind=rag|memory`，以及 `critic_completed.status=not_applicable`。
- Modify: `frontend/src/utils/__tests__/chatStreamEvents.test.js` — 新增 placeholder / not_applicable 用例。
- Modify: `frontend/src/components/chat/ToolCallCard.jsx:1-80` — 支持 `not_configured` 状态与 `kind` 标签。
- Modify: `frontend/src/components/chat/ToolCallCard.test.jsx` — 新增 placeholder 展示用例。
- Modify: `frontend/src/components/chat/ChatMessage.jsx:60-230` — 渲染 grounding `not_applicable` 提示；不渲染空 source refs。
- Modify: `frontend/src/components/chat/ChatMessage.test.jsx` — 新增 grounding not_applicable 用例。

---

## Task 1: Backend users.custom_instruction 迁移与模型

**Files:**
- Create: `backend/migrations/2026-07-02-add-users-custom-instruction.sql`
- Modify: `backend/schema.sql:6-26`
- Modify: `backend/app/models/user.py:13-31`
- Test: `backend/tests/test_users_me_custom_instruction.py`

**Interfaces:**
- Consumes: 无（首个任务，建立数据库列与 ORM 映射）。
- Produces: `User.custom_instruction: Mapped[str | None]`；MySQL 列 `users.custom_instruction TEXT NULLABLE`。

- [ ] **Step 1: 写失败测试（模型层 + /users/me 读写）**

```python
# backend/tests/test_users_me_custom_instruction.py
import pytest
from app.models.user import User


def test_user_model_has_custom_instruction_column():
    assert "custom_instruction" in User.__table__.columns
    col = User.__table__.columns["custom_instruction"]
    assert col.nullable is True


@pytest.mark.asyncio
async def test_update_my_info_persists_custom_instruction(async_client, db_session):
    # async_client / db_session 复用项目现有 fixture；若项目无 async_client，
    # 改为直接调用 update_my_info 路由函数的等价测试。
    user = await _create_user(db_session, custom_instruction="")
    resp = await async_client.put(
        "/api/v1/users/me",
        json={"custom_instruction": "讲解时先给直觉"},
        headers=await _auth_headers(user),
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["custom_instruction"] == "讲解时先给直觉"
```

> 若项目 `/users/me` 没有现成 `async_client` fixture，把第二个用例替换为直接调用 `update_my_info` 路由函数的最小等价测试，断言 `current_user.custom_instruction` 被写入。

- [ ] **Step 2: 运行测试确认失败**

Run: `cd backend && ../.venv/bin/python -m pytest tests/test_users_me_custom_instruction.py -q`
Expected: FAIL — `AttributeError: custom_instruction` 或列不存在。

- [ ] **Step 3: 写迁移 SQL**

```sql
-- backend/migrations/2026-07-02-add-users-custom-instruction.sql
-- 给 users 增加账号级全局自定义提示词列，nullable，幂等。
ALTER TABLE `users`
  ADD COLUMN IF NOT EXISTS `custom_instruction` TEXT NULL DEFAULT NULL
  COMMENT '账号级全局学习偏好，由用户在个人中心维护';
```

- [ ] **Step 4: 同步 schema.sql**

在 `backend/schema.sql` 的 `users` 建表语句中、`guidance_level` 行之后加入：

```sql
  `custom_instruction` TEXT NULL DEFAULT NULL COMMENT '账号级全局学习偏好',
```

- [ ] **Step 5: 更新 ORM 模型**

在 `backend/app/models/user.py` 的 `User` 类中、`guidance_level` 之后加入：

```python
    custom_instruction: Mapped[str | None] = mapped_column(Text, nullable=True)
```

确认顶部已 `from sqlalchemy import ... Text`（当前文件已导入 `Text`，无需新增 import）。

- [ ] **Step 6: 运行测试确认通过**

Run: `cd backend && ../.venv/bin/python -m pytest tests/test_users_me_custom_instruction.py -q`
Expected: PASS。

- [ ] **Step 7: 提交**

```bash
git add backend/migrations/2026-07-02-add-users-custom-instruction.sql \
        backend/schema.sql \
        backend/app/models/user.py \
        backend/tests/test_users_me_custom_instruction.py
git commit -m "feat: users 表新增 custom_instruction 列"
```

---

## Task 2: /users/me 读写 custom_instruction

**Files:**
- Modify: `backend/app/schemas/user.py:5-10`
- Modify: `backend/app/api/v1/users.py:10-53`
- Test: `backend/tests/test_users_me_custom_instruction.py`（续写）

**Interfaces:**
- Consumes: `User.custom_instruction`（Task 1 产出）。
- Produces: `GET /api/v1/users/me` 返回 `data.custom_instruction`；`PUT /api/v1/users/me` 接受 `custom_instruction` 并持久化。

- [ ] **Step 1: 续写失败测试**

在 `backend/tests/test_users_me_custom_instruction.py` 末尾追加：

```python
@pytest.mark.asyncio
async def test_get_users_me_returns_custom_instruction(async_client, db_session):
    user = await _create_user(db_session, custom_instruction="讲解时先给直觉")
    resp = await async_client.get("/api/v1/users/me", headers=await _auth_headers(user))
    assert resp.json()["data"]["custom_instruction"] == "讲解时先给直觉"


@pytest.mark.asyncio
async def test_update_users_me_rejects_overlong_custom_instruction(async_client, db_session):
    user = await _create_user(db_session, custom_instruction="")
    resp = await async_client.put(
        "/api/v1/users/me",
        json={"custom_instruction": "x" * 2001},
        headers=await _auth_headers(user),
    )
    assert resp.status_code == 400
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd backend && ../.venv/bin/python -m pytest tests/test_users_me_custom_instruction.py -q`
Expected: FAIL — `_user_info` 没有 `custom_instruction` 键；无长度校验。

- [ ] **Step 3: 更新 schema**

`backend/app/schemas/user.py`：

```python
from typing import Optional

from pydantic import BaseModel, Field


class UpdateUserRequest(BaseModel):
    real_name: Optional[str] = None
    student_id: Optional[str] = None
    major: Optional[str] = None
    grade: Optional[str] = None
    guidance_level: Optional[str] = None
    custom_instruction: Optional[str] = Field(default=None, max_length=2000)
```

- [ ] **Step 4: 更新 _user_info 与 update_my_info**

`backend/app/api/v1/users.py` 的 `_user_info` 在 `guidance_level` 之后加入：

```python
        "custom_instruction": u.custom_instruction or "",
```

`update_my_info` 在 `guidance_level` 分支之后加入：

```python
    if req.custom_instruction is not None:
        if len(req.custom_instruction) > 2000:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"code": 40001, "message": "自定义提示词过长（上限 2000 字符）", "data": None},
            )
        current_user.custom_instruction = req.custom_instruction
```

- [ ] **Step 5: 运行测试确认通过**

Run: `cd backend && ../.venv/bin/python -m pytest tests/test_users_me_custom_instruction.py -q`
Expected: PASS。

- [ ] **Step 6: 提交**

```bash
git add backend/app/schemas/user.py backend/app/api/v1/users.py \
        backend/tests/test_users_me_custom_instruction.py
git commit -m "feat: /users/me 支持读写 custom_instruction"
```

---

## Task 3: Backend Context Snapshot 聚合器

**Files:**
- Create: `backend/app/services/tutoring_context_snapshot.py`
- Create: `backend/tests/test_tutoring_context_snapshot.py`

**Interfaces:**
- Consumes: `User`、`UserProfile`、`CourseOffering`、`CourseCatalog`、`Conversation`、`Message`、`get_active_knowledge_graph`。
- Produces: `build_context_snapshot(*, user, profile, offering, catalog, active_graph, conversation, recent_messages, scope="course") -> dict`，输出 `context_version` + `learner_context` + `custom_instructions` + `course_context` + `conversation_context` + `runtime_policy`。

- [ ] **Step 1: 写失败测试**

```python
# backend/tests/test_tutoring_context_snapshot.py
from app.services.tutoring_context_snapshot import build_context_snapshot


def _profile():
    return {
        "guidance_level_current": "L2",
        "modal_preference": {"visual": 0.7, "text": 0.5, "practice": 0.8},
        "knowledge_coordinates": [
            {"name": "AVL 树旋转", "status": "weak", "mastery": 0.42, "chapter": "树与二叉树"},
            {"name": "二叉树遍历", "status": "mastered", "mastery": 0.86, "chapter": "树与二叉树"},
        ],
        "cognitive_blindspots": [{"label": "概念迁移困难", "evidence": "左旋右旋混淆"}],
        "drive_intent": {"custom_instruction": "多给代码例子", "type": "exam_prep"},
        "discipline_badge": {"label": "连续学习型", "confidence": 0.74},
    }


def test_snapshot_structures_weak_points_with_source_and_mastery():
    snap = build_context_snapshot(
        user={"id": "u1", "real_name": "张三", "guidance_level": "L2", "custom_instruction": "先给直觉"},
        profile=_profile(),
        offering={"id": "course-1", "catalog_id": "catalog-1"},
        catalog={"id": "catalog-1", "title": "数据结构", "kg_host_course_id": "host-1"},
        active_graph={"nodes": [{"id": "kg-1", "name": "AVL 树", "chapter": "树"}]},
        conversation={"id": "conv-1", "summary": "之前问过 AVL"},
        recent_messages=[{"role": "user", "content": "AVL 是什么"}],
    )

    assert snap["context_version"] == "ai_chat_context_v1"
    weak = snap["learner_context"]["weak_points"]
    assert weak[0]["name"] == "AVL 树旋转"
    assert weak[0]["mastery"] == 0.42
    assert weak[0]["source"] == "user_profile.knowledge_coordinates"
    assert snap["custom_instructions"]["user_global"] == "先给直觉"
    assert snap["custom_instructions"]["course_local"] == "多给代码例子"
    assert snap["course_context"]["catalog_id"] == "catalog-1"
    assert snap["runtime_policy"]["rag"]["enabled"] is False
    assert snap["runtime_policy"]["memory"]["enabled"] is False


def test_snapshot_reports_missing_profile_without_fabricating_weak_points():
    snap = build_context_snapshot(
        user={"id": "u1", "real_name": "", "guidance_level": "L2", "custom_instruction": ""},
        profile=None,
        offering=None,
        catalog=None,
        active_graph=None,
        conversation=None,
        recent_messages=[],
    )
    assert snap["learner_context"]["weak_points"] == []
    assert snap["learner_context"]["mastered_points"] == []
    assert snap["custom_instructions"]["course_local"] == ""
    assert snap["course_context"]["scope"] == "global"


def test_snapshot_global_scope_does_not_inject_course_local_profile():
    snap = build_context_snapshot(
        user={"id": "u1", "real_name": "", "guidance_level": "L2", "custom_instruction": "全局偏好"},
        profile=_profile(),
        offering=None,
        catalog=None,
        active_graph=None,
        conversation=None,
        recent_messages=[],
        scope="global",
    )
    assert snap["course_context"]["scope"] == "global"
    assert snap["custom_instructions"]["course_local"] == ""
    assert snap["custom_instructions"]["user_global"] == "全局偏好"
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd backend && ../.venv/bin/python -m pytest tests/test_tutoring_context_snapshot.py -q`
Expected: FAIL — `ModuleNotFoundError: app.services.tutoring_context_snapshot`。

- [ ] **Step 3: 实现聚合器**

```python
# backend/app/services/tutoring_context_snapshot.py
"""把 Backend 可信业务事实聚合成结构化 context snapshot。"""

from __future__ import annotations

from typing import Any, Mapping

CONTEXT_VERSION = "ai_chat_context_v1"


def build_context_snapshot(
    *,
    user: Mapping[str, Any] | None,
    profile: Mapping[str, Any] | None,
    offering: Mapping[str, Any] | None,
    catalog: Mapping[str, Any] | None,
    active_graph: Mapping[str, Any] | None,
    conversation: Mapping[str, Any] | None,
    recent_messages: list[Mapping[str, Any]] | None,
    scope: str = "course",
) -> dict:
    user = user or {}
    scope = scope if scope in ("course", "global") else "global"
    course_scoped = scope == "course"

    learner = _learner_context(user, profile if course_scoped else None)
    custom = _custom_instructions(user, profile if course_scoped else None)
    course = _course_context(scope, offering, catalog, active_graph)
    convo = _conversation_context(conversation, recent_messages)
    policy = _runtime_policy(course_scoped)

    return {
        "context_version": CONTEXT_VERSION,
        "learner_context": learner,
        "custom_instructions": custom,
        "course_context": course,
        "conversation_context": convo,
        "runtime_policy": policy,
    }


def _learner_context(user: Mapping[str, Any], profile: Mapping[str, Any] | None) -> dict:
    coordinates = _safe_list(profile.get("knowledge_coordinates")) if profile else []
    weak = [
        {
            "name": item.get("name"),
            "chapter": item.get("chapter"),
            "mastery": item.get("mastery"),
            "source": "user_profile.knowledge_coordinates",
        }
        for item in coordinates
        if isinstance(item, Mapping) and item.get("status") != "mastered" and item.get("name")
    ]
    mastered = [
        {
            "name": item.get("name"),
            "chapter": item.get("chapter"),
            "mastery": item.get("mastery"),
            "source": "user_profile.knowledge_coordinates",
        }
        for item in coordinates
        if isinstance(item, Mapping) and item.get("status") == "mastered" and item.get("name")
    ]
    blindspots = [
        {
            "label": item.get("label"),
            "evidence": item.get("evidence"),
            "source": "user_profile.cognitive_blindspots",
        }
        for item in _safe_list(profile.get("cognitive_blindspots")) if profile
        if isinstance(item, Mapping)
    ]
    drive = profile.get("drive_intent") if profile else None
    return {
        "user_id": user.get("id", ""),
        "display_name": user.get("real_name") or "",
        "guidance_level": (profile or {}).get("guidance_level_current") or user.get("guidance_level") or "L2",
        "modal_preference": (profile or {}).get("modal_preference") or {},
        "weak_points": weak,
        "mastered_points": mastered,
        "cognitive_blindspots": blindspots,
        "learning_goal": (drive or {}).get("type") if isinstance(drive, Mapping) else "",
        "discipline_badge": (profile or {}).get("discipline_badge") or {},
    }


def _custom_instructions(user: Mapping[str, Any], profile: Mapping[str, Any] | None) -> dict:
    user_global = (user.get("custom_instruction") or "").strip()
    course_local = ""
    if profile:
        course_local = ((profile.get("drive_intent") or {}).get("custom_instruction") or "").strip()
    return {
        "user_global": user_global,
        "course_local": course_local,
        "effective_order": ["user_global", "course_local"],
    }


def _course_context(
    scope: str,
    offering: Mapping[str, Any] | None,
    catalog: Mapping[str, Any] | None,
    active_graph: Mapping[str, Any] | None,
) -> dict:
    if scope != "course":
        return {"scope": "global"}
    nodes = _safe_list(active_graph.get("nodes")) if active_graph else []
    preview = [
        {"id": n.get("id"), "name": n.get("name"), "chapter": n.get("chapter")}
        for n in nodes
        if isinstance(n, Mapping)
    ][:20]
    return {
        "scope": "course",
        "course_id": (offering or {}).get("id"),
        "catalog_id": (offering or {}).get("catalog_id") if offering else (catalog or {}).get("id"),
        "course_title": (catalog or {}).get("title"),
        "kg_host_course_id": (catalog or {}).get("kg_host_course_id"),
        "active_kg_nodes_preview": preview,
    }


def _conversation_context(
    conversation: Mapping[str, Any] | None,
    recent_messages: list[Mapping[str, Any]] | None,
) -> dict:
    return {
        "conversation_id": (conversation or {}).get("id"),
        "summary": (conversation or {}).get("summary") or "",
        "recent_messages": [
            {"role": m.get("role"), "content": m.get("content") or "", "meta": m.get("meta") or {}}
            for m in (recent_messages or [])
            if isinstance(m, Mapping) and (m.get("content") or "").strip()
        ][:20],
    }


def _runtime_policy(course_scoped: bool) -> dict:
    return {
        "rag": {
            "enabled": False,
            "status": "placeholder",
            "reason": "rag_architecture_pending",
            "course_scoped": course_scoped,
            "require_source_refs_for_course_facts": False,
        },
        "memory": {
            "enabled": False,
            "status": "placeholder",
            "scope_plan": "user_global_and_user_course",
            "reason": "memory_architecture_pending",
            "search_order": ["user_course", "user_global"],
            "write_policy": "whitelist_pending",
        },
        "safety": {
            "content_safety_review": True,
            "grounding_review": "not_applicable_until_rag_enabled",
        },
    }


def _safe_list(value: Any) -> list:
    return value if isinstance(value, list) else []
```

- [ ] **Step 4: 运行测试确认通过**

Run: `cd backend && ../.venv/bin/python -m pytest tests/test_tutoring_context_snapshot.py -q`
Expected: PASS。

- [ ] **Step 5: 提交**

```bash
git add backend/app/services/tutoring_context_snapshot.py \
        backend/tests/test_tutoring_context_snapshot.py
git commit -m "feat: 新增 Backend context snapshot 聚合器"
```

---

## Task 4: TutoringPayloadBuilder 输出 snapshot（保留旧字段兼容）

**Files:**
- Modify: `backend/app/services/tutoring_payload_builder.py:12-176`
- Create: `backend/tests/test_tutoring_payload_builder.py`

**Interfaces:**
- Consumes: `build_context_snapshot`（Task 3）。
- Produces: `TutoringPayloadBuilder.build()` 返回的 dict 新增 `context_version` / `learner_context` / `custom_instructions` / `course_context` / `conversation_context` / `runtime_policy`，并保留旧 `user_profile` / `active_kg_nodes` / `recent_messages` / `conversation_summary` 一段兼容期。

- [ ] **Step 1: 写失败测试**

```python
# backend/tests/test_tutoring_payload_builder.py
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.tutoring_payload_builder import TutoringPayloadBuilder


@pytest.mark.asyncio
async def test_payload_includes_context_snapshot_and_legacy_fields(db_session: AsyncSession):
    await _seed_full_course_fixture(db_session)
    payload = await TutoringPayloadBuilder(db_session).build(
        user_id="u1",
        scope="course",
        course_id="course-1",
        conversation_id="conv-1",
        message="AVL 旋转怎么理解？",
        exclude_message_ids=set(),
    )
    assert payload["context_version"] == "ai_chat_context_v1"
    assert payload["learner_context"]["weak_points"][0]["name"] == "AVL 树旋转"
    assert payload["custom_instructions"]["user_global"] == "先给直觉"
    assert payload["custom_instructions"]["course_local"] == "多给代码例子"
    assert payload["runtime_policy"]["rag"]["enabled"] is False
    assert "user_profile" in payload
    assert "recent_messages" in payload
    assert "active_kg_nodes" in payload


@pytest.mark.asyncio
async def test_payload_global_scope_has_no_course_local_profile(db_session: AsyncSession):
    await _seed_global_only_user(db_session)
    payload = await TutoringPayloadBuilder(db_session).build(
        user_id="u1",
        scope="global",
        course_id=None,
        conversation_id="conv-1",
        message="你好",
        exclude_message_ids=set(),
    )
    assert payload["course_context"]["scope"] == "global"
    assert payload["custom_instructions"]["course_local"] == ""
    assert payload["learner_context"]["weak_points"] == []
```

`_seed_full_course_fixture` / `_seed_global_only_user` 复用项目已有 fixture 工厂；若没有，按现有 `test_tutoring_routes_refactored.py` 的 seed 模式最小构造。

- [ ] **Step 2: 运行测试确认失败**

Run: `cd backend && ../.venv/bin/python -m pytest tests/test_tutoring_payload_builder.py -q`
Expected: FAIL — `KeyError: context_version`。

- [ ] **Step 3: 重构 build() 调用 snapshot**

把 `TutoringPayloadBuilder.build()` 改为：先按现有逻辑取 `user / profile / offering / catalog / active_graph / conversation / recent_messages`，再调用 `build_context_snapshot(...)`，最后把 snapshot 顶层字段合并进 payload，并保留旧字段。

```python
# backend/app/services/tutoring_payload_builder.py 顶部新增 import
from app.services.tutoring_context_snapshot import build_context_snapshot
```

`build()` 主体改为：

```python
    async def build(
        self,
        *,
        user_id: str,
        scope: str,
        course_id: str | None,
        conversation_id: str,
        message: str,
        exclude_message_ids: set[str] | None = None,
    ) -> dict:
        user = await self._load_user(user_id)
        offering, catalog, active_graph = await self._load_course(scope, course_id)
        profile = await self._load_profile(user_id, scope, course_id)
        conversation, recent = await self._load_conversation(
            conversation_id, exclude_message_ids or set()
        )

        snapshot = build_context_snapshot(
            user=_user_mapping(user),
            profile=_profile_mapping(profile),
            offering=_offering_mapping(offering),
            catalog=_catalog_mapping(catalog),
            active_graph=_graph_mapping(active_graph),
            conversation=_conversation_mapping(conversation),
            recent_messages=_recent_mappings(recent),
            scope=scope,
        )

        payload: dict = {
            "user_id": user_id,
            "scope": scope,
            "message": message,
            "conversation_id": conversation_id,
        }
        if course_id:
            payload["course_id"] = course_id

        payload["context_version"] = snapshot["context_version"]
        payload["learner_context"] = snapshot["learner_context"]
        payload["custom_instructions"] = snapshot["custom_instructions"]
        payload["course_context"] = snapshot["course_context"]
        payload["conversation_context"] = snapshot["conversation_context"]
        payload["runtime_policy"] = snapshot["runtime_policy"]

        # 旧字段兼容：保留一段过渡期，供未升级的 v2 消费者使用
        payload["user_profile"] = _legacy_user_profile(profile, user)
        payload["active_kg_nodes"] = snapshot["course_context"].get("active_kg_nodes_preview", [])
        if snapshot["conversation_context"].get("summary"):
            payload["conversation_summary"] = snapshot["conversation_context"]["summary"]
        payload["recent_messages"] = snapshot["conversation_context"]["recent_messages"]
        return payload
```

`_load_*` / `_*_mapping` 是把原来 `_add_*` 里的 SQL 查询抽出来的薄函数；保持 SQL 不变，只把“查询”和“聚合”分开。`_legacy_user_profile(profile, user)` 复用原 `_add_user_profile` 的字段形状（`guidance_level / modal_preference / knowledge_mastered / knowledge_weak / custom_instruction`），保证旧消费者不破。

- [ ] **Step 4: 运行测试确认通过**

Run: `cd backend && ../.venv/bin/python -m pytest tests/test_tutoring_payload_builder.py tests/test_tutoring_stream_adapter.py -q`
Expected: PASS（stream adapter 测试不应受影响，因为它只依赖 `context` 透传）。

- [ ] **Step 5: 提交**

```bash
git add backend/app/services/tutoring_payload_builder.py \
        backend/tests/test_tutoring_payload_builder.py
git commit -m "feat: TutoringPayloadBuilder 输出结构化 context snapshot"
```

---

## Task 5: agent_service_v2 context snapshot 解析模型

**Files:**
- Create: `agent_service_v2/src/agent_service_v2/session/context_snapshot.py`
- Create: `agent_service_v2/tests/test_context_snapshot.py`

**Interfaces:**
- Consumes: Backend `context` dict（Task 4 输出）。
- Produces: `parse_context_snapshot(context: dict) -> ContextSnapshot`，含 `learner_context` / `custom_instructions` / `course_context` / `conversation_context` / `runtime_policy` / `warnings`；缺字段安全降级，但**不编造**弱点 / 课程 / 记忆。

- [ ] **Step 1: 写失败测试**

```python
# agent_service_v2/tests/test_context_snapshot.py
from agent_service_v2.session.context_snapshot import parse_context_snapshot


def test_parse_full_snapshot_exposes_structured_fields():
    snap = parse_context_snapshot({
        "context_version": "ai_chat_context_v1",
        "learner_context": {"user_id": "u1", "weak_points": [{"name": "AVL"}]},
        "custom_instructions": {"user_global": "先给直觉", "course_local": "多给代码"},
        "course_context": {"scope": "course", "catalog_id": "catalog-1"},
        "conversation_context": {"summary": "之前问过 AVL", "recent_messages": []},
        "runtime_policy": {"rag": {"enabled": False}, "memory": {"enabled": False}},
    })
    assert snap.context_version == "ai_chat_context_v1"
    assert snap.learner_context["weak_points"][0]["name"] == "AVL"
    assert snap.custom_instructions["user_global"] == "先给直觉"
    assert snap.course_context["scope"] == "course"
    assert snap.runtime_policy["rag"]["enabled"] is False


def test_parse_missing_profile_does_not_fabricate_weak_points():
    snap = parse_context_snapshot({})
    assert snap.context_version == "ai_chat_context_v1"
    assert snap.learner_context["weak_points"] == []
    assert snap.custom_instructions["user_global"] == ""
    assert snap.course_context["scope"] == "global"
    assert snap.runtime_policy["rag"]["enabled"] is False


def test_parse_reports_partial_context_warning():
    snap = parse_context_snapshot({"learner_context": {}})
    assert snap.warnings == ["learner_context.empty"]
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd agent_service_v2 && ./.venv/bin/pytest tests/test_context_snapshot.py -q`
Expected: FAIL — `ModuleNotFoundError`。

- [ ] **Step 3: 实现解析模型**

```python
# agent_service_v2/src/agent_service_v2/session/context_snapshot.py
"""解析 Backend 上下文快照，缺字段安全降级且不编造事实。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

DEFAULT_CONTEXT_VERSION = "ai_chat_context_v1"


@dataclass(slots=True)
class ContextSnapshot:
    context_version: str
    learner_context: dict[str, Any]
    custom_instructions: dict[str, Any]
    course_context: dict[str, Any]
    conversation_context: dict[str, Any]
    runtime_policy: dict[str, Any]
    warnings: list[str] = field(default_factory=list)


def parse_context_snapshot(context: Mapping[str, Any] | None) -> ContextSnapshot:
    context = context or {}
    warnings: list[str] = []

    learner = context.get("learner_context")
    if not isinstance(learner, Mapping) or not learner:
        learner = {"user_id": "", "weak_points": [], "mastered_points": []}
        warnings.append("learner_context.empty")

    custom = context.get("custom_instructions")
    if not isinstance(custom, Mapping):
        custom = {"user_global": "", "course_local": "", "effective_order": ["user_global", "course_local"]}

    course = context.get("course_context")
    if not isinstance(course, Mapping):
        course = {"scope": "global"}

    convo = context.get("conversation_context")
    if not isinstance(convo, Mapping):
        convo = {"summary": "", "recent_messages": []}

    policy = context.get("runtime_policy")
    if not isinstance(policy, Mapping):
        policy = {
            "rag": {"enabled": False, "status": "placeholder", "reason": "rag_architecture_pending"},
            "memory": {"enabled": False, "status": "placeholder", "reason": "memory_architecture_pending"},
            "safety": {"content_safety_review": True, "grounding_review": "not_applicable_until_rag_enabled"},
        }

    return ContextSnapshot(
        context_version=str(context.get("context_version") or DEFAULT_CONTEXT_VERSION),
        learner_context=dict(learner),
        custom_instructions=dict(custom),
        course_context=dict(course),
        conversation_context=dict(convo),
        runtime_policy=dict(policy),
        warnings=warnings,
    )
```

- [ ] **Step 4: 运行测试确认通过**

Run: `cd agent_service_v2 && ./.venv/bin/pytest tests/test_context_snapshot.py -q`
Expected: PASS。

- [ ] **Step 5: 提交**

```bash
git add agent_service_v2/src/agent_service_v2/session/context_snapshot.py \
        agent_service_v2/tests/test_context_snapshot.py
git commit -m "feat: agent_service_v2 新增 context snapshot 解析"
```

---

## Task 6: workbench_input 只产 history + current，不再拼伪 system_context

**Files:**
- Modify: `agent_service_v2/src/agent_service_v2/session/workbench_input.py:1-80`
- Modify: `agent_service_v2/tests/test_workbench_input.py`

**Interfaces:**
- Consumes: `ContextSnapshot`（Task 5）。
- Produces: `build_workbench_agent_input(*, message: str, snapshot: ContextSnapshot) -> list[Msg]`，只返回 conversation history + current `UserMsg(name="student")`；不再生成 `system_context` UserMsg。

- [ ] **Step 1: 改写失败测试**

```python
# agent_service_v2/tests/test_workbench_input.py
from agent_service_v2.session.context_snapshot import ContextSnapshot
from agent_service_v2.session.workbench_input import build_workbench_agent_input


def _snapshot(recent_messages=None, summary=""):
    return ContextSnapshot(
        context_version="ai_chat_context_v1",
        learner_context={"user_id": "u1", "weak_points": [{"name": "AVL"}]},
        custom_instructions={"user_global": "先给直觉", "course_local": "多给代码"},
        course_context={"scope": "course", "catalog_id": "catalog-1"},
        conversation_context={"summary": summary, "recent_messages": recent_messages or []},
        runtime_policy={"rag": {"enabled": False}, "memory": {"enabled": False}},
    )


def test_build_input_only_emits_history_and_current_message():
    messages = build_workbench_agent_input(
        message="继续讲",
        snapshot=_snapshot(recent_messages=[
            {"role": "user", "content": "AVL 是什么"},
            {"role": "assistant", "content": "自平衡二叉搜索树"},
        ]),
    )
    assert [m.role for m in messages] == ["user", "assistant", "user"]
    assert messages[-1].get_text_content() == "继续讲"
    assert "本轮可用上下文" not in messages[0].get_text_content()


def test_build_input_filters_empty_history_placeholders():
    messages = build_workbench_agent_input(
        message="继续",
        snapshot=_snapshot(recent_messages=[
            {"role": "assistant", "content": ""},
            {"role": "user", "content": "   "},
            {"role": "assistant", "content": "有效回答"},
        ]),
    )
    assert [m.role for m in messages] == ["assistant", "user"]
    assert [m.get_text_content() for m in messages] == ["有效回答", "继续"]
```

> 同时删除旧 `test_build_workbench_agent_input_includes_context_history_and_current_message` 中对“AVL 旋转出现在第一条 UserMsg”的断言（该断言依赖已废弃的 `system_context` 拼接行为）。

- [ ] **Step 2: 运行测试确认失败**

Run: `cd agent_service_v2 && ./.venv/bin/pytest tests/test_workbench_input.py -q`
Expected: FAIL — 旧函数签名 `context: dict` 不再匹配 `snapshot: ContextSnapshot`。

- [ ] **Step 3: 重写 workbench_input**

```python
# agent_service_v2/src/agent_service_v2/session/workbench_input.py
from __future__ import annotations

from agentscope.message import AssistantMsg, Msg, UserMsg

from agent_service_v2.session.context_snapshot import ContextSnapshot


def build_workbench_agent_input(*, message: str, snapshot: ContextSnapshot) -> list[Msg]:
    inputs: list[Msg] = []
    for item in snapshot.conversation_context.get("recent_messages") or []:
        msg = _history_message(item)
        if msg is not None:
            inputs.append(msg)
    inputs.append(UserMsg(name="student", content=message))
    return inputs


def _history_message(item) -> Msg | None:
    if not isinstance(item, dict):
        return None
    content = str(item.get("content") or "").strip()
    if not content:
        return None
    role = item.get("role")
    if role == "user":
        return UserMsg(name="student", content=content)
    if role == "assistant":
        return AssistantMsg(name="assistant", content=content)
    return None
```

- [ ] **Step 4: 运行测试确认通过**

Run: `cd agent_service_v2 && ./.venv/bin/pytest tests/test_workbench_input.py -q`
Expected: PASS。

- [ ] **Step 5: 提交**

```bash
git add agent_service_v2/src/agent_service_v2/session/workbench_input.py \
        agent_service_v2/tests/test_workbench_input.py
git commit -m "refactor: workbench_input 只产 history + current，不再拼伪 system_context"
```

---

## Task 7: system prompt 增加能力边界与禁止兜底条款

**Files:**
- Modify: `agent_service_v2/src/agent_service_v2/agents/prompts.py:1-16`
- Create: `agent_service_v2/tests/test_workbench_system_prompt.py`

**Interfaces:**
- Consumes: `ContextSnapshot`（Task 5）。
- Produces: `build_workbench_system_prompt(snapshot: ContextSnapshot) -> str`。

- [ ] **Step 1: 写失败测试**

```python
# agent_service_v2/tests/test_workbench_system_prompt.py
from agent_service_v2.agents.prompts import build_workbench_system_prompt
from agent_service_v2.session.context_snapshot import ContextSnapshot


def _snapshot(**over):
    base = dict(
        context_version="ai_chat_context_v1",
        learner_context={"user_id": "u1", "guidance_level": "L2", "weak_points": [{"name": "AVL"}]},
        custom_instructions={"user_global": "先给直觉", "course_local": "多给代码"},
        course_context={"scope": "course", "course_id": "c1", "course_title": "数据结构"},
        conversation_context={"summary": "", "recent_messages": []},
        runtime_policy={"rag": {"enabled": False}, "memory": {"enabled": False}},
    )
    base.update(over)
    return ContextSnapshot(**base)


def test_prompt_states_rag_and_memory_not_enabled():
    prompt = build_workbench_system_prompt(_snapshot())
    assert "课程 RAG 尚未启用" in prompt
    assert "长期记忆尚未启用" in prompt
    assert "不得用通用知识冒充课程资料" in prompt


def test_prompt_includes_custom_instructions_in_effective_order():
    prompt = build_workbench_system_prompt(_snapshot())
    assert "先给直觉" in prompt
    assert "多给代码" in prompt


def test_prompt_warns_when_learner_context_empty():
    snap = _snapshot(learner_context={"user_id": "", "weak_points": []})
    snap.warnings = ["learner_context.empty"]
    prompt = build_workbench_system_prompt(snap)
    assert "学习画像缺失" in prompt
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd agent_service_v2 && ./.venv/bin/pytest tests/test_workbench_system_prompt.py -q`
Expected: FAIL — `build_workbench_system_prompt` 不存在。

- [ ] **Step 3: 实现 prompt builder**

```python
# agent_service_v2/src/agent_service_v2/agents/prompts.py
from __future__ import annotations

from agent_service_v2.session.context_snapshot import ContextSnapshot

WORKBENCH_SYSTEM_PROMPT = """You are EDUagent's AIChat learning workbench agent.

Use planning tools only for genuinely complex multi-step work. Keep tool use
bounded, prefer course-grounded context, and expose uncertainty when context is
missing.

Workspace artifact rules:
- When the user asks for saveable learning material, lesson pages, worksheets,
  diagrams, study plans, or resource recommendation documents, call
  write_artifact_file with the complete artifact body.
- Do not stream the full artifact body in chat after writing the file.
- After writing artifact files, reply in chat with the artifact title,
  one-sentence summary, and one suggested next action.
- Use Markdown files for reading materials, Mermaid files for diagrams, and JSON
  files only for supported workspace plugin cards.

Capability honesty (mandatory):
- 课程 RAG 尚未启用时，不得用通用知识冒充课程资料，不得生成 source_refs，不得说"根据课程资料"。
- 长期记忆尚未启用时，不得用 recent messages 冒充跨会话长期记忆，不得说"我记得你之前……"。
- 学习画像缺失时，必须明确报告缺失，不得编造学生弱点或掌握点。
- 能力未启用或上下文不足时，必须显式报告，禁止兜底伪装。
"""


def build_workbench_system_prompt(snapshot: ContextSnapshot) -> str:
    learner = snapshot.learner_context
    custom = snapshot.custom_instructions
    course = snapshot.course_context
    policy = snapshot.runtime_policy

    parts: list[str] = [WORKBENCH_SYSTEM_PROMPT]

    parts.append(f"Current user_id: {learner.get('user_id') or 'unknown'}")
    parts.append(f"Current course_scope: {course.get('scope') or 'global'}")
    if course.get("scope") == "course":
        parts.append(f"Current course_id: {course.get('course_id') or 'unknown'}")
        if course.get("course_title"):
            parts.append(f"Current course_title: {course['course_title']}")

    parts.append(f"Guidance level: {learner.get('guidance_level') or 'L2'}")

    weak = ", ".join(w.get("name", "") for w in learner.get("weak_points") or [] if w.get("name"))
    if weak:
        parts.append(f"Known weak points (from backend snapshot): {weak}")
    elif "learner_context.empty" in snapshot.warnings:
        parts.append("学习画像缺失：后端未提供学习画像，回答中不得编造弱点。")

    user_global = (custom.get("user_global") or "").strip()
    course_local = (custom.get("course_local") or "").strip()
    if user_global:
        parts.append(f"用户全局偏好：{user_global}")
    if course_local:
        parts.append(f"课程内偏好：{course_local}")

    rag_enabled = bool(policy.get("rag", {}).get("enabled"))
    memory_enabled = bool(policy.get("memory", {}).get("enabled"))
    parts.append(f"课程 RAG 已启用: {rag_enabled}")
    parts.append(f"长期记忆已启用: {memory_enabled}")
    if not rag_enabled:
        parts.append("课程 RAG 尚未启用：不得引用课程资料，不得生成 source_refs。")
    if not memory_enabled:
        parts.append("长期记忆尚未启用：不得声称读取或写入跨会话长期记忆。")

    return "\n".join(parts)
```

- [ ] **Step 4: 运行测试确认通过**

Run: `cd agent_service_v2 && ./.venv/bin/pytest tests/test_workbench_system_prompt.py -q`
Expected: PASS。

- [ ] **Step 5: 提交**

```bash
git add agent_service_v2/src/agent_service_v2/agents/prompts.py \
        agent_service_v2/tests/test_workbench_system_prompt.py
git commit -m "feat: workbench system prompt 增加能力边界与禁止兜底条款"
```

---

## Task 8: placeholder tools（read_learning_state 读 snapshot + RAG/Memory placeholder）

**Files:**
- Modify: `agent_service_v2/src/agent_service_v2/tools/workbench_placeholders.py:1-26`
- Modify: `agent_service_v2/tests/test_workbench_toolkit.py`

**Interfaces:**
- Consumes: `ContextSnapshot`（Task 5）。
- Produces:
  - `make_read_learning_state(snapshot)` 返回闭包 tool，输出 snapshot 摘要。
  - `search_course_knowledge(query: str) -> dict`、`search_memory(query: str) -> dict`、`add_memory(fact: str) -> dict` 三个 placeholder，固定返回 `not_configured / architecture_pending`。

- [ ] **Step 1: 改写失败测试**

在 `agent_service_v2/tests/test_workbench_toolkit.py` 末尾追加：

```python
from agent_service_v2.session.context_snapshot import ContextSnapshot
from agent_service_v2.tools.workbench_placeholders import (
    add_memory,
    make_read_learning_state,
    search_course_knowledge,
    search_memory,
)


def _snapshot(**over):
    base = dict(
        context_version="ai_chat_context_v1",
        learner_context={"user_id": "u1", "guidance_level": "L2", "weak_points": [{"name": "AVL"}], "mastered_points": []},
        custom_instructions={"user_global": "先给直觉", "course_local": "多给代码"},
        course_context={"scope": "course"},
        conversation_context={"summary": "", "recent_messages": []},
        runtime_policy={"rag": {"enabled": False}, "memory": {"enabled": False}},
    )
    base.update(over)
    return ContextSnapshot(**base)


def test_read_learning_state_returns_snapshot_summary():
    tool = make_read_learning_state(_snapshot())
    result = tool()
    assert result["status"] == "available"
    assert result["source"] == "backend_context_snapshot"
    assert result["weak_points_count"] == 1
    assert result["rag_enabled"] is False
    assert result["memory_enabled"] is False


def test_search_course_knowledge_placeholder_reports_not_configured():
    result = search_course_knowledge(query="AVL 旋转")
    assert result["status"] == "not_configured"
    assert result["kind"] == "rag"
    assert result["reason"] == "rag_architecture_pending"
    assert "sources" not in result


def test_memory_placeholder_tools_report_not_configured():
    assert search_memory(query="AVL")["status"] == "not_configured"
    assert search_memory(query="AVL")["kind"] == "memory"
    assert add_memory(fact="用户混淆 AVL 旋转")["status"] == "not_configured"
    assert add_memory(fact="x")["reason"] == "memory_architecture_pending"
```

同时把旧 `test_placeholder_tools_return_structured_observations` 中 `read_learning_state(user_id=..., course_id=...)` 的断言改为新的 `make_read_learning_state` 形态（旧签名删除）。

- [ ] **Step 2: 运行测试确认失败**

Run: `cd agent_service_v2 && ./.venv/bin/pytest tests/test_workbench_toolkit.py -q`
Expected: FAIL — `make_read_learning_state` / `search_course_knowledge` / `search_memory` / `add_memory` 不存在或签名不匹配。

- [ ] **Step 3: 重写 placeholders**

```python
# agent_service_v2/src/agent_service_v2/tools/workbench_placeholders.py
from __future__ import annotations

from collections.abc import Callable

from agent_service_v2.session.context_snapshot import ContextSnapshot

RAG_NOT_CONFIGURED = {
    "status": "not_configured",
    "kind": "rag",
    "reason": "rag_architecture_pending",
    "message": "课程 RAG 架构尚未启用，当前不能检索课程知识库。",
}

MEMORY_NOT_CONFIGURED_READ = {
    "status": "not_configured",
    "kind": "memory",
    "reason": "memory_architecture_pending",
    "scope_plan": "user_global_and_user_course",
    "message": "长期记忆架构尚未启用，当前不能读取用户长期记忆。",
}

MEMORY_NOT_CONFIGURED_WRITE = {
    "status": "not_configured",
    "kind": "memory",
    "reason": "memory_architecture_pending",
    "message": "长期记忆写入尚未启用，本轮不会写入用户记忆。",
}


def make_read_learning_state(snapshot: ContextSnapshot) -> Callable[[], dict]:
    def read_learning_state() -> dict:
        learner = snapshot.learner_context
        custom = snapshot.custom_instructions
        policy = snapshot.runtime_policy
        return {
            "status": "available",
            "source": "backend_context_snapshot",
            "guidance_level": learner.get("guidance_level") or "L2",
            "weak_points_count": len(learner.get("weak_points") or []),
            "mastered_points_count": len(learner.get("mastered_points") or []),
            "has_user_global_instruction": bool((custom.get("user_global") or "").strip()),
            "has_course_local_instruction": bool((custom.get("course_local") or "").strip()),
            "rag_enabled": bool(policy.get("rag", {}).get("enabled")),
            "memory_enabled": bool(policy.get("memory", {}).get("enabled")),
        }

    return read_learning_state


def search_course_knowledge(query: str = "") -> dict:
    return dict(RAG_NOT_CONFIGURED)


def search_memory(query: str = "") -> dict:
    return dict(MEMORY_NOT_CONFIGURED_READ)


def add_memory(fact: str = "") -> dict:
    return dict(MEMORY_NOT_CONFIGURED_WRITE)


def review_grounding(summary: str) -> dict:
    return {
        "status": "not_applicable",
        "tool": "review_grounding",
        "reason": "rag_not_enabled",
        "summary": summary,
        "message": "课程 RAG 未启用，本轮未进行基于课程来源的 grounding 审查。",
    }
```

- [ ] **Step 4: 运行测试确认通过**

Run: `cd agent_service_v2 && ./.venv/bin/pytest tests/test_workbench_toolkit.py -q`
Expected: PASS。

- [ ] **Step 5: 提交**

```bash
git add agent_service_v2/src/agent_service_v2/tools/workbench_placeholders.py \
        agent_service_v2/tests/test_workbench_toolkit.py
git commit -m "feat: placeholder tools 显式报告 RAG/Memory 未启用"
```

---

## Task 9: toolkit 注入 knowledge / memory placeholder ToolGroup

**Files:**
- Modify: `agent_service_v2/src/agent_service_v2/tools/workbench_toolkit.py:14-57`
- Modify: `agent_service_v2/src/agent_service_v2/agents/permissions.py:4-13`
- Modify: `agent_service_v2/tests/test_workbench_toolkit.py`（续写）
- Modify: `agent_service_v2/tests/test_workbench_factory.py`

**Interfaces:**
- Consumes: `make_read_learning_state` / `search_course_knowledge` / `search_memory` / `add_memory`（Task 8）。
- Produces: `build_workbench_tool_groups(*, snapshot, workspace, run_id)`，返回 `planning / learning_state / knowledge / memory / artifact / review` 六个 group；`SAFE_WORKBENCH_TOOLS` 增加 `search_course_knowledge` / `search_memory` / `add_memory`。

- [ ] **Step 1: 续写失败测试**

在 `test_workbench_toolkit.py` 追加：

```python
def test_tool_groups_include_knowledge_and_memory_placeholders():
    groups = build_workbench_tool_groups(
        snapshot=_snapshot(),
        workspace=LocalWorkspace(workdir="/tmp/eduagent-test-workspace", workspace_id="ws"),
        run_id="run-1",
    )
    names = [g.name for g in groups]
    assert names == ["planning", "learning_state", "knowledge", "memory", "artifact", "review"]
    knowledge = next(g for g in groups if g.name == "knowledge")
    assert {type(t).__name__ for t in knowledge.tools} == {"FunctionTool"}
    memory = next(g for g in groups if g.name == "memory")
    assert len(memory.tools) == 2
```

更新 `test_workbench_factory.py` 的 `test_factory_configures_safe_tool_permission_allow_rules`：增加 `assert "search_course_knowledge" in allow_rules`、`assert "search_memory" in allow_rules`、`assert "add_memory" in allow_rules`。

- [ ] **Step 2: 运行测试确认失败**

Run: `cd agent_service_v2 && ./.venv/bin/pytest tests/test_workbench_toolkit.py tests/test_workbench_factory.py -q`
Expected: FAIL — `build_workbench_tool_groups` 不接受 `snapshot`；group 名单不匹配。

- [ ] **Step 3: 重写 toolkit**

```python
# agent_service_v2/src/agent_service_v2/tools/workbench_toolkit.py
from __future__ import annotations

from agentscope.tool import FunctionTool, ToolGroup
from agentscope.workspace import LocalWorkspace

from agent_service_v2.session.context_snapshot import ContextSnapshot
from agent_service_v2.tools.artifact_files import build_write_artifact_file
from agent_service_v2.tools.planning import build_planning_group
from agent_service_v2.tools.workbench_placeholders import (
    add_memory,
    make_read_learning_state,
    review_grounding,
    search_course_knowledge,
    search_memory,
)


def build_workbench_tool_groups(
    *,
    snapshot: ContextSnapshot,
    workspace: LocalWorkspace,
    run_id: str,
) -> list[ToolGroup]:
    return [
        build_planning_group(),
        ToolGroup(
            name="learning_state",
            description="Read Backend-provided learner state summaries.",
            tools=[FunctionTool(make_read_learning_state(snapshot), is_read_only=True)],
        ),
        ToolGroup(
            name="knowledge",
            description="Course knowledge retrieval (placeholder until RAG architecture lands).",
            tools=[FunctionTool(search_course_knowledge, is_read_only=True)],
        ),
        ToolGroup(
            name="memory",
            description="Long-term learner memory (placeholder until memory architecture lands).",
            tools=[
                FunctionTool(search_memory, is_read_only=True),
                FunctionTool(add_memory),
            ],
        ),
        ToolGroup(
            name="artifact",
            description="Write saveable learning artifacts into the run workspace.",
            tools=[FunctionTool(build_write_artifact_file(workspace=workspace, run_id=run_id))],
        ),
        ToolGroup(
            name="review",
            description="Review generated advice for grounding and safety.",
            tools=[FunctionTool(review_grounding, is_read_only=True)],
        ),
    ]
```

`permissions.py` 的 `SAFE_WORKBENCH_TOOLS` 追加：

```python
    "search_course_knowledge",
    "search_memory",
    "add_memory",
```

- [ ] **Step 4: 运行测试确认通过**

Run: `cd agent_service_v2 && ./.venv/bin/pytest tests/test_workbench_toolkit.py tests/test_workbench_factory.py -q`
Expected: PASS。

- [ ] **Step 5: 提交**

```bash
git add agent_service_v2/src/agent_service_v2/tools/workbench_toolkit.py \
        agent_service_v2/src/agent_service_v2/agents/permissions.py \
        agent_service_v2/tests/test_workbench_toolkit.py \
        agent_service_v2/tests/test_workbench_factory.py
git commit -m "feat: toolkit 注入 knowledge/memory placeholder ToolGroup"
```

---

## Task 10: factory 用 snapshot 构造 system prompt + toolkit

**Files:**
- Modify: `agent_service_v2/src/agent_service_v2/agents/workbench_factory.py:21-84`
- Modify: `agent_service_v2/tests/test_workbench_factory.py`

**Interfaces:**
- Consumes: `ContextSnapshot`、`build_workbench_system_prompt`、`build_workbench_tool_groups`（Task 5/7/9）。
- Produces: `WorkbenchAgentFactory.create_agent(*, snapshot, workspace, run_id, conversation_id, log_sink)`；旧 `user_id` / `course_id` 入参由 `snapshot` 推导。

- [ ] **Step 1: 改写失败测试**

把 `test_workbench_factory.py` 中现有用例的 `create_agent(user_id="u1", course_id="c1", workspace=..., run_id="run-1")` 改为 `create_agent(snapshot=_snapshot(), workspace=..., run_id="run-1")`，其中 `_snapshot()` 用 Task 9 同款 helper。新增：

```python
def test_factory_system_prompt_states_rag_not_enabled(tmp_path):
    class FakeModel: pass
    workspace = WorkbenchWorkspaceManager(root_dir=tmp_path).get_workspace(
        user_id="u1", course_id="c1", conversation_id="conv1",
    )
    factory = WorkbenchAgentFactory(model_provider=lambda: FakeModel())
    agent = factory.create_agent(snapshot=_snapshot(), workspace=workspace, run_id="run-1")
    assert "课程 RAG 尚未启用" in agent.system_prompt
    assert "长期记忆尚未启用" in agent.system_prompt
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd agent_service_v2 && ./.venv/bin/pytest tests/test_workbench_factory.py -q`
Expected: FAIL — `create_agent` 不接受 `snapshot`。

- [ ] **Step 3: 重写 factory**

```python
# agent_service_v2/src/agent_service_v2/agents/workbench_factory.py
from __future__ import annotations

from collections.abc import Callable
from typing import Any

from agentscope.agent import Agent, ContextConfig, ReActConfig
from agentscope.state import AgentState
from agentscope.tool import Toolkit
from agentscope.workspace import LocalWorkspace

from agent_service_v2.agents.permissions import build_workbench_permission_context
from agent_service_v2.agents.prompts import build_workbench_system_prompt
from agent_service_v2.observability.agent_middleware import AgentRunLoggingMiddleware
from agent_service_v2.observability.logging import LogSink
from agent_service_v2.session.context_snapshot import ContextSnapshot
from agent_service_v2.tools.workbench_toolkit import build_workbench_tool_groups


class MissingModelConfigError(RuntimeError):
    pass


class WorkbenchAgentFactory:
    def __init__(self, model_provider: Callable[[], Any]) -> None:
        self._model_provider = model_provider

    def create_agent(
        self,
        *,
        snapshot: ContextSnapshot,
        workspace: LocalWorkspace,
        run_id: str | None = None,
        conversation_id: str | None = None,
        log_sink: LogSink | None = None,
    ) -> Agent:
        model = self._model_provider()
        if model is None:
            raise MissingModelConfigError("model_not_configured")
        if run_id is None:
            raise ValueError("run_id is required for workbench artifact tools")

        learner = snapshot.learner_context
        course = snapshot.course_context
        user_id = learner.get("user_id") or "unknown"
        course_id = course.get("course_id") if course.get("scope") == "course" else None

        toolkit = Toolkit(
            tool_groups=build_workbench_tool_groups(
                snapshot=snapshot,
                workspace=workspace,
                run_id=run_id,
            )
        )
        middlewares = []
        if run_id and log_sink:
            middlewares.append(
                AgentRunLoggingMiddleware(
                    run_id=run_id,
                    conversation_id=conversation_id,
                    user_id=user_id,
                    course_id=course_id,
                    sink=log_sink,
                )
            )

        return Agent(
            name=_agent_name(course_id),
            system_prompt=build_workbench_system_prompt(snapshot),
            model=model,
            toolkit=toolkit,
            middlewares=middlewares,
            state=AgentState(permission_context=build_workbench_permission_context()),
            offloader=workspace,
            context_config=ContextConfig(tool_result_limit=20000),
            react_config=ReActConfig(max_iters=12),
        )


def _agent_name(course_id: str | None) -> str:
    return f"edu_ai_chat_workbench:{course_id or 'global'}"
```

- [ ] **Step 4: 运行测试确认通过**

Run: `cd agent_service_v2 && ./.venv/bin/pytest tests/test_workbench_factory.py -q`
Expected: PASS。

- [ ] **Step 5: 提交**

```bash
git add agent_service_v2/src/agent_service_v2/agents/workbench_factory.py \
        agent_service_v2/tests/test_workbench_factory.py
git commit -m "refactor: factory 用 ContextSnapshot 构造 system prompt 与 toolkit"
```

---

## Task 11: session / api 透传 snapshot

**Files:**
- Modify: `agent_service_v2/src/agent_service_v2/session/workbench_session.py:157-288`
- Modify: `agent_service_v2/src/agent_service_v2/api/workbench.py:21-44`
- Modify: `agent_service_v2/tests/test_workbench_session.py`
- Modify: `agent_service_v2/tests/test_workbench_api.py`

**Interfaces:**
- Consumes: `parse_context_snapshot`（Task 5）、`WorkbenchAgentFactory.create_agent(snapshot=...)`（Task 10）、`build_workbench_agent_input(snapshot=...)`（Task 6）。
- Produces: `WorkbenchSession.start_async(..., context: dict)` 内部解析为 `ContextSnapshot` 并传给 factory 与 input builder；发布 `context.attached` debug_log。

- [ ] **Step 1: 改写失败测试**

在 `test_workbench_session.py` 增加用例：传入带 `learner_context` 的 `context`，断言 run bus 出现 `debug_log` 事件且 `attributes.context_version == "ai_chat_context_v1"`、`attributes.rag_enabled is False`。在 `test_workbench_api.py` 增加用例：`POST /agent/v2/workbench/chat` 的 `context` 含 `runtime_policy.rag.enabled=false`，SSE 流里至少出现一条 `debug_log` 且 `payload.event == "context.attached"`。

- [ ] **Step 2: 运行测试确认失败**

Run: `cd agent_service_v2 && ./.venv/bin/pytest tests/test_workbench_session.py tests/test_workbench_api.py -q`
Expected: FAIL — 旧 session 仍按 `context: dict` 透传，未解析 snapshot，未发 `context.attached`。

- [ ] **Step 3: 改 session**

在 `WorkbenchSession._start_async` 解析 snapshot 并透传：

```python
# 顶部新增 import
from agent_service_v2.session.context_snapshot import parse_context_snapshot
```

`_start_async` 内，在创建 run 之后、`create_agent` 之前：

```python
        snapshot = parse_context_snapshot(context)
        self._run_bus.publish(
            run.run_id,
            EduEventType.DEBUG_LOG,
            {
                "event": "context.attached",
                "level": "info" if not snapshot.warnings else "warning",
                "message": "已装载学习画像和运行策略" if not snapshot.warnings else "上下文部分缺失",
                "attributes": {
                    "context_version": snapshot.context_version,
                    "has_user_global_instruction": bool(snapshot.custom_instructions.get("user_global")),
                    "has_course_local_instruction": bool(snapshot.custom_instructions.get("course_local")),
                    "weak_points_count": len(snapshot.learner_context.get("weak_points") or []),
                    "recent_messages_count": len(snapshot.conversation_context.get("recent_messages") or []),
                    "rag_enabled": bool(snapshot.runtime_policy.get("rag", {}).get("enabled")),
                    "memory_enabled": bool(snapshot.runtime_policy.get("memory", {}).get("enabled")),
                    "warnings": list(snapshot.warnings),
                },
            },
        )
```

`create_agent(...)` 调用改为 `create_agent(snapshot=snapshot, workspace=workspace, run_id=run.run_id, conversation_id=run.conversation_id, log_sink=...)`。

`_run_agent` 内 `build_workbench_agent_input(message=message, context=context)` 改为 `build_workbench_agent_input(message=message, snapshot=snapshot)`；`_run_agent` 增加参数 `snapshot: ContextSnapshot`，并在调用处传入。

- [ ] **Step 4: 改 api**

`api/workbench.py` 的 `create_agent_factory()` 保持不变；`workbench_chat` 把 `req.context` 透传给 `session.start_async(..., context=req.context)`（session 内部解析）。

- [ ] **Step 5: 运行测试确认通过**

Run: `cd agent_service_v2 && ./.venv/bin/pytest tests/test_workbench_session.py tests/test_workbench_api.py tests/test_workbench_input.py tests/test_workbench_factory.py -q`
Expected: PASS。

- [ ] **Step 6: 提交**

```bash
git add agent_service_v2/src/agent_service_v2/session/workbench_session.py \
        agent_service_v2/src/agent_service_v2/api/workbench.py \
        agent_service_v2/tests/test_workbench_session.py \
        agent_service_v2/tests/test_workbench_api.py
git commit -m "feat: session/api 解析 context snapshot 并发布 context.attached"
```

---

## Task 12: protocol_adapter 透传 placeholder 工具的 kind/status

**Files:**
- Modify: `agent_service_v2/src/agent_service_v2/runtime/protocol_adapter.py:118-122`
- Modify: `agent_service_v2/tests/test_protocol_adapter.py`

**Interfaces:**
- Consumes: AgentScope `ToolResultEndEvent`。
- Produces: `TOOL_COMPLETED` payload 在工具结果为 dict 且含 `kind` / `status` / `output_summary` 时透传这些字段，供前端识别 placeholder。

- [ ] **Step 1: 写失败测试**

在 `test_protocol_adapter.py` 增加：构造一个 `ToolResultEndEvent`，其结果文本是 `json.dumps({"status":"not_configured","kind":"rag","reason":"rag_architecture_pending","output_summary":"课程 RAG 尚未启用"})`，断言 `adapter.adapt_many(event)` 产出的 `TOOL_COMPLETED` 事件 payload 含 `kind="rag"`、`status="not_configured"`、`output_summary`。

- [ ] **Step 2: 运行测试确认失败**

Run: `cd agent_service_v2 && ./.venv/bin/pytest tests/test_protocol_adapter.py -q`
Expected: FAIL — 当前 `_map_event` 对 `ToolResultEndEvent` 只输出 `tool_call_id` / `state`。

- [ ] **Step 3: 扩展 _map_event 的 ToolResultEndEvent 分支**

```python
        if isinstance(event, ToolResultEndEvent):
            payload: dict[str, Any] = {
                "tool_call_id": event.tool_call_id,
                "state": getattr(event.state, "value", event.state),
            }
            parsed = _parse_json_object(self._tool_result_text.get(event.tool_call_id, ""))
            if parsed:
                for key in ("kind", "status", "reason", "output_summary", "message"):
                    if key in parsed:
                        payload[key] = parsed[key]
            return EduEventType.TOOL_COMPLETED, payload
```

- [ ] **Step 4: 运行测试确认通过**

Run: `cd agent_service_v2 && ./.venv/bin/pytest tests/test_protocol_adapter.py -q`
Expected: PASS。

- [ ] **Step 5: 提交**

```bash
git add agent_service_v2/src/agent_service_v2/runtime/protocol_adapter.py \
        agent_service_v2/tests/test_protocol_adapter.py
git commit -m "feat: protocol_adapter 透传 placeholder 工具 kind/status"
```

---

## Task 13: Frontend chatStreamEvents 支持 placeholder 与 not_applicable

**Files:**
- Modify: `frontend/src/utils/chatStreamEvents.js:95-175`
- Modify: `frontend/src/utils/__tests__/chatStreamEvents.test.js`

**Interfaces:**
- Consumes: SSE 事件 `tool_completed`（含 `kind` / `status` / `output_summary`）、`critic_completed`（含 `status="not_applicable"`）。
- Produces: `reduceAssistantMessageForEvent` 在 `tool_completed` 时透传 `kind` / `status` / `outputSummary`；在 `critic_completed.status==="not_applicable"` 时设置 `groundingNotApplicable=true` 且不设置 `reviewFlagged`。

- [ ] **Step 1: 写失败测试**

在 `chatStreamEvents.test.js` 追加：

```javascript
  it('renders placeholder rag tool as not_configured', () => {
    let message = createEmptyAiMessage();
    message = reduceAssistantMessageForEvent(message, {
      type: 'tool_started',
      payload: { tool_call_id: 't1', tool_name: 'search_course_knowledge' }
    });
    message = reduceAssistantMessageForEvent(message, {
      type: 'tool_completed',
      payload: {
        tool_call_id: 't1',
        state: 'success',
        kind: 'rag',
        status: 'not_configured',
        reason: 'rag_architecture_pending',
        output_summary: '课程 RAG 架构尚未启用，未执行检索。'
      }
    });
    const tool = message.parts.find(p => p.type === 'tool').toolCall;
    expect(tool.kind).toBe('rag');
    expect(tool.status).toBe('not_configured');
    expect(tool.outputSummary).toContain('尚未启用');
  });

  it('marks grounding as not_applicable without flagging the answer', () => {
    let message = createEmptyAiMessage();
    message = reduceAssistantMessageForEvent(message, {
      type: 'critic_completed',
      payload: { critic_type: 'grounding', status: 'not_applicable', reason: 'rag_not_enabled' }
    });
    expect(message.groundingNotApplicable).toBe(true);
    expect(message.reviewFlagged).toBeUndefined();
  });
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd frontend && npm run test:unit -- src/utils/__tests__/chatStreamEvents.test.js`
Expected: FAIL — `tool.kind` undefined；`groundingNotApplicable` 未设置。

- [ ] **Step 3: 扩展 reducer**

`tool_completed` 分支改为：

```javascript
    case 'tool_completed':
      {
        const toolCall = {
          id: event.payload?.tool_call_id || 'unknown',
          name: event.payload?.tool_name || message.toolCalls?.find(tc => tc.id === event.payload?.tool_call_id)?.name,
          status: event.payload?.status || (event.payload?.state === 'error' ? 'error' : 'completed'),
          kind: event.payload?.kind,
          reason: event.payload?.reason,
          outputSummary: event.payload?.output_summary || event.payload?.summary
        };
        return {
          ...message,
          toolCalls: upsertToolCall(message.toolCalls, toolCall),
          parts: upsertToolPart(message.parts, toolCall)
        };
      }
```

`critic_completed` 分支改为：

```javascript
    case 'critic_completed':
      {
        const status = event.payload?.status;
        if (status === 'not_applicable') {
          return {
            ...message,
            groundingNotApplicable: true,
            groundingReason: event.payload?.reason || 'rag_not_enabled'
          };
        }
        return {
          ...message,
          reviewFlagged: event.payload?.passed === false,
          reviewReason: event.payload?.reason || message.reviewReason
        };
      }
```

- [ ] **Step 4: 运行测试确认通过**

Run: `cd frontend && npm run test:unit -- src/utils/__tests__/chatStreamEvents.test.js`
Expected: PASS。

- [ ] **Step 5: 提交**

```bash
git add frontend/src/utils/chatStreamEvents.js \
        frontend/src/utils/__tests__/chatStreamEvents.test.js
git commit -m "feat: chatStreamEvents 支持 placeholder tool 与 grounding not_applicable"
```

---

## Task 14: ToolCallCard 展示 placeholder 状态

**Files:**
- Modify: `frontend/src/components/chat/ToolCallCard.jsx:1-80`
- Modify: `frontend/src/components/chat/ToolCallCard.test.jsx`

**Interfaces:**
- Consumes: `toolCall.kind` / `toolCall.status="not_configured"` / `toolCall.outputSummary`（Task 13）。
- Produces: 当 `status==="not_configured"` 且 `kind==="rag"` 时显示“课程 RAG 尚未启用”；`kind==="memory"` 时显示“长期记忆尚未启用”；状态样式用 neutral（slate）。

- [ ] **Step 1: 写失败测试**

在 `ToolCallCard.test.jsx` 追加：

```javascript
  it('shows 课程 RAG 尚未启用 for placeholder rag tool', () => {
    render(
      <ToolCallCard
        name="search_course_knowledge"
        status="not_configured"
        kind="rag"
        outputSummary="课程 RAG 架构尚未启用，未执行检索。"
      />
    );
    expect(screen.getByText('课程 RAG 尚未启用')).toBeDefined();
    expect(screen.queryByText('完成')).toBeNull();
  });

  it('shows 长期记忆尚未启用 for placeholder memory tool', () => {
    render(
      <ToolCallCard
        name="search_memory"
        status="not_configured"
        kind="memory"
        outputSummary="长期记忆架构尚未启用，未读取跨会话记忆。"
      />
    );
    expect(screen.getByText('长期记忆尚未启用')).toBeDefined();
  });
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd frontend && npm run test:unit -- src/components/chat/ToolCallCard.test.jsx`
Expected: FAIL — 无“课程 RAG 尚未启用”文本。

- [ ] **Step 3: 扩展 ToolCallCard**

在 `STATUS_META` 增加 `not_configured`：

```javascript
  not_configured: {
    label: '未启用',
    icon: 'lock',
    shell: 'border-slate-200 bg-slate-50/70 text-slate-600',
    dot: 'border-slate-300'
  },
```

在 `TOOL_TITLE_MAP` 增加：

```javascript
  search_course_knowledge: '课程知识库检索',
  search_memory: '长期记忆检索',
  add_memory: '更新长期记忆',
```

组件内，在 `const meta = ...` 之后：

```javascript
  const isNotConfigured = status === 'not_configured';
  const placeholderTitle = isNotConfigured && kind === 'rag'
    ? '课程 RAG 尚未启用'
    : isNotConfigured && kind === 'memory'
    ? '长期记忆尚未启用'
    : null;
  const displayTitle = placeholderTitle || title || mappedTitle || name || '工具调用';
  const effectiveMeta = isNotConfigured ? STATUS_META.not_configured : (STATUS_META[status] || STATUS_META.running);
```

并把后续用到 `meta` 的地方改为 `effectiveMeta`。

- [ ] **Step 4: 运行测试确认通过**

Run: `cd frontend && npm run test:unit -- src/components/chat/ToolCallCard.test.jsx`
Expected: PASS。

- [ ] **Step 5: 提交**

```bash
git add frontend/src/components/chat/ToolCallCard.jsx \
        frontend/src/components/chat/ToolCallCard.test.jsx
git commit -m "feat: ToolCallCard 展示 RAG/Memory placeholder 未启用状态"
```

---

## Task 15: ChatMessage 渲染 grounding not_applicable，不渲染空 source refs

**Files:**
- Modify: `frontend/src/components/chat/ChatMessage.jsx:60-230`
- Modify: `frontend/src/components/chat/ChatMessage.test.jsx`

**Interfaces:**
- Consumes: `message.groundingNotApplicable` / `message.groundingReason` / `message.sourceRefs`（Task 13）。
- Produces: 当 `groundingNotApplicable===true` 时在 assistant 内容尾部渲染“未进行课程来源 grounding 审查”；当 `sourceRefs` 为空数组或 undefined 时不渲染引用区。

- [ ] **Step 1: 写失败测试**

在 `ChatMessage.test.jsx` 追加：

```javascript
  it('shows grounding not applicable notice when RAG is disabled', () => {
    render(
      <ChatMessage
        message={{
          id: 'ai-1',
          role: 'assistant',
          content: '通用解释',
          loading: false,
          groundingNotApplicable: true,
          groundingReason: 'rag_not_enabled',
          parts: [{ type: 'text', content: '通用解释' }]
        }}
        onSendMessage={vi.fn()}
        onRegenerate={vi.fn()}
      />
    );
    expect(screen.getByText('未进行课程来源 grounding 审查')).toBeDefined();
  });

  it('does not render empty source refs area', () => {
    render(
      <ChatMessage
        message={{
          id: 'ai-1',
          role: 'assistant',
          content: '通用解释',
          loading: false,
          sourceRefs: [],
          parts: [{ type: 'text', content: '通用解释' }]
        }}
        onSendMessage={vi.fn()}
        onRegenerate={vi.fn()}
      />
    );
    expect(screen.queryByText('参考来源')).toBeNull();
  });
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd frontend && npm run test:unit -- src/components/chat/ChatMessage.test.jsx`
Expected: FAIL — 无“未进行课程来源 grounding 审查”文本。

- [ ] **Step 3: 扩展 ChatMessage**

在 `hasOrderedParts` 区块内、`parts.map` 之后追加 grounding 提示：

```jsx
        {message.groundingNotApplicable && (
          <div className="mt-2 rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-[11px] text-slate-600">
            未进行课程来源 grounding 审查（课程 RAG 未启用）
          </div>
        )}
```

`sourceRefs` 渲染仅当 `Array.isArray(message.sourceRefs) && message.sourceRefs.length > 0` 时显示“参考来源”区。

- [ ] **Step 4: 运行测试确认通过**

Run: `cd frontend && npm run test:unit -- src/components/chat/ChatMessage.test.jsx`
Expected: PASS。

- [ ] **Step 5: 提交**

```bash
git add frontend/src/components/chat/ChatMessage.jsx \
        frontend/src/components/chat/ChatMessage.test.jsx
git commit -m "feat: ChatMessage 展示 grounding not_applicable 并隐藏空 source refs"
```

---

## Task 16: 端到端 lint/build/pytest 与 WorkLine 记录

**Files:**
- Modify: `WorkLine.md`

**Interfaces:**
- Consumes: 所有前置 Task。
- Produces: 全绿验证 + WorkLine 记录 + 接口漂移记录。

- [ ] **Step 1: 前端 lint + build**

Run: `cd frontend && npm run lint && npm run build`
Expected: PASS（仅保留既有 chunk size warning）。

- [ ] **Step 2: 后端 pytest**

Run: `cd backend && ../.venv/bin/python -m pytest tests/test_users_me_custom_instruction.py tests/test_tutoring_context_snapshot.py tests/test_tutoring_payload_builder.py tests/test_tutoring_stream_adapter.py -q`
Expected: PASS。

- [ ] **Step 3: agent_service_v2 pytest**

Run: `cd agent_service_v2 && ./.venv/bin/pytest -q`
Expected: PASS。

- [ ] **Step 4: 在 WorkLine.md 追加记录**

按项目规范追加一条记录：涉及文件、核心改动、验证结果、接口漂移（`/users/me` 新增 `custom_instruction`；`/agent/v2/workbench/chat` 的 `context` 新增结构化 snapshot 字段，旧字段保留兼容）。

- [ ] **Step 5: 提交**

```bash
git add WorkLine.md
git commit -m "docs: 记录 AIChat context injection v1 落地与接口漂移"
```

---

## Self-Review

**1. Spec coverage:**
- §5 Backend Context Snapshot → Task 3（聚合器）+ Task 4（payload 输出）。
- §5.3 双层 custom_instructions → Task 1/2（users.custom_instruction）+ Task 3（`custom_instructions` 分区）。
- §6 AgentScope 2.x 输入分流 → Task 5/6/7/10/11。
- §7 Placeholder Tools → Task 8/9。
- §8 禁止兜底 → Task 7 system prompt 条款 + Task 8 placeholder 返回 `not_configured` + Task 13/15 前端展示未启用。
- §9 SSE 事件 → Task 11 `context.attached` + Task 12 adapter 透传 `kind/status`。
- §10 Frontend 展示 → Task 13/14/15。
- §11 分阶段计划 → Task 1-16 顺序覆盖 Phase 1-4（Phase 5 真实 RAG/Memory 明确不在本计划）。
- §12 验收清单 → 每个 Task 的测试步骤覆盖对应断言。

**2. Placeholder scan:** 已检查，无 “TBD/TODO/实现后续/类似 Task N” 等占位；每个 code step 都给了完整代码或完整 SQL。

**3. Type consistency:**
- `ContextSnapshot` 字段名在 Task 5/6/7/8/10/11 一致：`learner_context` / `custom_instructions` / `course_context` / `conversation_context` / `runtime_policy` / `warnings`。
- `build_workbench_agent_input(*, message, snapshot)` 签名在 Task 6/11 一致。
- `WorkbenchAgentFactory.create_agent(*, snapshot, workspace, run_id, conversation_id, log_sink)` 签名在 Task 10/11 一致。
- `build_workbench_tool_groups(*, snapshot, workspace, run_id)` 签名在 Task 9/10 一致。
- `make_read_learning_state(snapshot) -> Callable[[], dict]` 在 Task 8/9 一致。
- 前端 `toolCall.kind` / `toolCall.status="not_configured"` / `message.groundingNotApplicable` 在 Task 13/14/15 一致。
