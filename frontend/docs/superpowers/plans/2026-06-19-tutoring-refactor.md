# Backend Tutoring Route Refactor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 591 行 tutoring 胖路由重构为 Router、Service、Payload Builder、Stream Adapter 和 Presenter，同时保持 Client/Agent API 契约并修复已批准的 SSE 可靠性问题。

**Architecture:** Router 只处理 FastAPI 边界，`TutoringService` 管理 Conversation/Message 事务，`TutoringPayloadBuilder` 白名单组装 Agent DTO，`TutoringStreamAdapter` 适配和持久化 SSE，Presenter 输出 Client DTO。Agent 调用前结束请求级数据库事务；会话列表使用固定 4 次有界查询。

**Tech Stack:** Python 3.12、FastAPI 0.115.6、SQLAlchemy 2.0.36 async、Pydantic 2.10.4、sse-starlette 2.2.1、httpx 0.28.1、pytest、pytest-asyncio、MySQL 8

---

## 实施前提与边界

- 当前分支必须为 `refactor/v2-architecture`，不创建或切换分支。
- 执行前阅读 `backend/AGENTS.md`、设计 Spec 和两个 OpenAPI 契约。
- 不修改前端、Agent Service、数据库 Schema、`.env` 或历史 OpenAPI。
- 保留代码中既有的 `action=chat|edit|regenerate`，即使历史 Client OpenAPI 漏记该字段。
- 不在本任务增加 course enrollment 403；该安全债务另开 Spec。
- 每个 Task 最多触及 5 个文件，完成后独立提交，不 push。
- 所有数据库行为测试使用 MySQL；纯解析/Presenter 测试可以无数据库运行。

## 文件结构锁定

| 文件 | 操作 | 单一职责 |
| --- | --- | --- |
| `backend/app/api/v1/tutoring.py` | 修改 | FastAPI 路由、异常翻译、REST/SSE 响应 |
| `backend/app/services/tutoring_service.py` | 新建 | 会话/消息生命周期、行锁、固定查询 |
| `backend/app/services/tutoring_payload_builder.py` | 新建 | Backend → Agent payload 白名单组装 |
| `backend/app/services/tutoring_stream_adapter.py` | 新建 | Agent SSE 缓冲、转换、累积和落库 |
| `backend/app/services/tutoring_presenters.py` | 新建 | Conversation/Message → Client DTO |
| `backend/tests/test_tutoring_service.py` | 新建 | Service、行锁、查询数量和排序 |
| `backend/tests/test_tutoring_stream_adapter.py` | 新建 | SSE 分片、异常、取消和持久化 |
| `backend/tests/test_tutoring_routes_refactored.py` | 新建 | 薄路由、错误翻译、transaction 释放 |
| `backend/tests/test_tutoring_privacy.py` | 修改 | Payload Builder 隐私、KG、历史上下文 |
| `backend/tests/test_agent_integration.py` | 修改 | patch 路径和 Client API/SSE 回归 |
| `WORKFLOW.md` | 修改 | 阶段状态、验证和接口漂移记录 |
| `frontend/docs/requirements-coverage.md` | 修改 | tutoring 接口实现覆盖记录 |

## 统一验证环境

从仓库根目录运行；若测试库尚不存在，先执行：

```bash
docker exec eduagent-mysql mysql -uroot -p123456 -e "CREATE DATABASE IF NOT EXISTS tutoring_refactor_test CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"
```

后端测试统一前缀：

```bash
TEST_DATABASE_URL='mysql+aiomysql://root:123456@127.0.0.1:3306/tutoring_refactor_test?charset=utf8mb4' ../.venv/bin/python -m pytest
```

---

### Task 1: 锁定重构前 Client/SSE 行为

**Files:**
- Modify: `backend/tests/test_agent_integration.py`

- [ ] **Step 1: 为既有 action 字段补充特征测试**

在 `TestTutoringChatIntegration` 中增加测试，复用该类的 `_setup_tutoring`，用可控 Agent 流先创建对话，再分别发送 edit 和 regenerate：

```python
@pytest.mark.asyncio
async def test_tutoring_action_field_remains_supported(self):
    async def fake_stream_sse(path, payload):
        yield b'data: {"type":"chunk","content":"ok"}\n\n'
        yield b'data: {"type":"done","message_id":"agent-id"}\n\n'

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        headers, course_id = await self._setup_tutoring(client)
        with patch("app.api.v1.tutoring.agent_client.stream_sse", fake_stream_sse):
            created = await client.post(
                "/api/v1/tutoring/chat",
                headers=headers,
                json={"message": "first", "scope": "course", "course_id": course_id},
            )
            done = next(
                json.loads(line.removeprefix("data: "))
                for line in created.text.splitlines()
                if line.startswith("data: ") and '"type":"done"' in line.replace(" ", "")
            )
            conversation_id = done["conversation_id"]

            edited = await client.post(
                "/api/v1/tutoring/chat",
                headers=headers,
                json={
                    "message": "edited",
                    "action": "edit",
                    "scope": "course",
                    "course_id": course_id,
                    "conversation_id": conversation_id,
                },
            )
            regenerated = await client.post(
                "/api/v1/tutoring/chat",
                headers=headers,
                json={
                    "message": "edited",
                    "action": "regenerate",
                    "scope": "course",
                    "course_id": course_id,
                    "conversation_id": conversation_id,
                },
            )

    assert edited.status_code == 200
    assert regenerated.status_code == 200
```

- [ ] **Step 2: 在 action 测试中锁定最终历史内容**

在 Step 1 测试的同一个 client 生命周期中，在 regenerate 后读取历史并增加：

```python
history = await client.get(
    f"/api/v1/tutoring/conversations/{conversation_id}",
    headers=headers,
)
assert history.status_code == 200
assert [item["role"] for item in history.json()["data"]["messages"]] == ["user", "assistant"]
assert history.json()["data"]["messages"][0]["content"] == "edited"
assert history.json()["data"]["messages"][1]["content"] == "ok"
```

- [ ] **Step 3: 运行特征测试并确认当前差异**

Run:

```bash
cd backend && TEST_DATABASE_URL='mysql+aiomysql://root:123456@127.0.0.1:3306/tutoring_refactor_test?charset=utf8mb4' ../.venv/bin/python -m pytest tests/test_agent_integration.py::TestTutoringChatIntegration -q
```

Expected: 全部 PASS；这是当前代码行为特征，不允许以修改期望值掩盖失败。

- [ ] **Step 4: 提交测试基线**

```bash
git add backend/tests/test_agent_integration.py
git commit -m "test(tutoring): 锁定会话动作与排序契约"
```

---

### Task 2: 提取 TutoringService 与会话事务

**Files:**
- Create: `backend/app/services/tutoring_service.py`
- Create: `backend/tests/test_tutoring_service.py`

- [ ] **Step 1: 写 Service RED 测试**

测试至少覆盖内部 DTO、三种 action、所有权、`FOR UPDATE` 和现有异常区分：

```python
from app.services.tutoring_service import (
    ConversationNotFoundError,
    EditConversationRequiredError,
    EditUserMessageRequiredError,
    PreparedTutoringTurn,
    RegenerateConversationRequiredError,
    RegenerateUserMessageRequiredError,
    TutoringService,
)


@pytest.mark.asyncio
async def test_prepare_edit_locks_conversation_and_reuses_message_ids(mysql_session, conversation_with_pair):
    service = TutoringService(mysql_session)
    turn = await service.prepare_edit_turn(
        user_id=conversation_with_pair.user_id,
        conversation_id=conversation_with_pair.id,
        message="edited",
        scope="course",
        course_id=conversation_with_pair.course_id,
    )

    assert isinstance(turn, PreparedTutoringTurn)
    assert turn.conversation_id == conversation_with_pair.id
    assert turn.message == "edited"
    assert turn.user_message_id
    assert turn.assistant_message_id
```

在同一文件提供 `mysql_session` 与 `conversation_with_pair` async fixtures；fixture 使用 `async_session_factory` 创建唯一 user/course/conversation 数据，并在测试后按 ID 删除，不能依赖 SQLite 文件清理。

- [ ] **Step 2: 运行 Service 测试确认 RED**

Run:

```bash
cd backend && TEST_DATABASE_URL='mysql+aiomysql://root:123456@127.0.0.1:3306/tutoring_refactor_test?charset=utf8mb4' ../.venv/bin/python -m pytest tests/test_tutoring_service.py -q
```

Expected: collection FAIL，提示 `app.services.tutoring_service` 不存在。

- [ ] **Step 3: 实现领域异常、DTO 和消息排序**

创建：

```python
from dataclasses import dataclass
from datetime import datetime


class ConversationNotFoundError(Exception):
    pass


class EditConversationRequiredError(Exception):
    pass


class RegenerateConversationRequiredError(Exception):
    pass


class EditUserMessageRequiredError(Exception):
    pass


class RegenerateUserMessageRequiredError(Exception):
    pass


@dataclass(frozen=True, slots=True)
class PreparedTutoringTurn:
    conversation_id: str
    user_message_id: str
    assistant_message_id: str
    message: str
    scope: str
    course_id: str | None


def message_order_key(message: Message):
    role_rank = 0 if message.role == "user" else 1
    return (
        message.create_time or datetime.min,
        message.update_time or datetime.min,
        role_rank,
    )
```

- [ ] **Step 4: 实现显式 preparation 方法**

`TutoringService` 使用以下公共方法和私有 helper；edit/regenerate 在持锁后重新读取消息：

```python
class TutoringService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def _owned_conversation(
        self, user_id: str, conversation_id: str, *, for_update: bool,
    ) -> Conversation:
        statement = select(Conversation).where(
            Conversation.id == conversation_id,
            Conversation.user_id == user_id,
            Conversation.is_deleted == False,
        )
        if for_update:
            statement = statement.with_for_update()
        conversation = (await self.db.execute(statement)).scalar_one_or_none()
        if conversation is None:
            raise ConversationNotFoundError
        return conversation

    async def _last_messages(self, conversation_id: str) -> tuple[Message | None, Message | None]:
        result = await self.db.execute(
            select(Message).where(
                Message.conversation_id == conversation_id,
                Message.is_deleted == False,
            ).order_by(Message.create_time.desc(), Message.update_time.desc()).limit(20)
        )
        messages = list(result.scalars().all())
        last_user = next((item for item in messages if item.role == "user"), None)
        last_assistant = next((item for item in messages if item.role == "assistant"), None)
        return last_user, last_assistant

    async def _empty_assistant(
        self, conversation_id: str, scope: str, course_id: str | None,
    ) -> Message:
        message = Message(
            conversation_id=conversation_id,
            role="assistant",
            content="",
            meta_json={"scope": scope, "course_id": course_id},
        )
        self.db.add(message)
        await self.db.flush()
        return message

    async def prepare_chat_turn(
        self, *, user_id: str, conversation_id: str | None,
        message: str, scope: str, course_id: str | None,
    ) -> PreparedTutoringTurn:
        if conversation_id:
            conversation = await self._owned_conversation(user_id, conversation_id, for_update=True)
        else:
            title = message[:50] + ("..." if len(message) > 50 else "")
            conversation = Conversation(
                user_id=user_id, scope=scope, course_id=course_id, title=title,
            )
            self.db.add(conversation)
            await self.db.flush()

        user_message = Message(
            conversation_id=conversation.id,
            role="user",
            content=message,
            meta_json={"scope": scope, "course_id": course_id},
        )
        self.db.add(user_message)
        await self.db.flush()
        assistant = await self._empty_assistant(conversation.id, scope, course_id)
        conversation.update_time = datetime.now(timezone.utc)
        await self.db.flush()
        return PreparedTutoringTurn(
            conversation.id, user_message.id, assistant.id, message, scope, course_id,
        )

    async def prepare_edit_turn(
        self, *, user_id: str, conversation_id: str | None,
        message: str, scope: str, course_id: str | None,
    ) -> PreparedTutoringTurn:
        if not conversation_id:
            raise EditConversationRequiredError
        conversation = await self._owned_conversation(user_id, conversation_id, for_update=True)
        last_user, last_assistant = await self._last_messages(conversation.id)
        if last_user is None:
            raise EditUserMessageRequiredError
        last_user.content = message
        if last_assistant is None:
            last_assistant = await self._empty_assistant(conversation.id, scope, course_id)
        else:
            last_assistant.content = ""
            last_assistant.diagrams = None
            last_assistant.knowledge_points = None
        conversation.update_time = datetime.now(timezone.utc)
        await self.db.flush()
        return PreparedTutoringTurn(
            conversation.id, last_user.id, last_assistant.id, message, scope, course_id,
        )

    async def prepare_regenerate_turn(
        self, *, user_id: str, conversation_id: str | None,
        message: str, scope: str, course_id: str | None,
    ) -> PreparedTutoringTurn:
        if not conversation_id:
            raise RegenerateConversationRequiredError
        conversation = await self._owned_conversation(user_id, conversation_id, for_update=True)
        last_user, last_assistant = await self._last_messages(conversation.id)
        if last_user is None:
            raise RegenerateUserMessageRequiredError
        if last_assistant is None:
            last_assistant = await self._empty_assistant(conversation.id, scope, course_id)
        else:
            last_assistant.content = ""
            last_assistant.diagrams = None
            last_assistant.knowledge_points = None
        conversation.update_time = datetime.now(timezone.utc)
        await self.db.flush()
        return PreparedTutoringTurn(
            conversation.id, last_user.id, last_assistant.id, message, scope, course_id,
        )
```

补充 imports：`datetime, timezone`、SQLAlchemy `select`、`AsyncSession` 以及 Conversation/Message。Service 只做 SQL 读写与 flush，不 commit、不调用 Agent。

- [ ] **Step 5: 运行 Service 测试确认 GREEN**

Run:

```bash
cd backend && TEST_DATABASE_URL='mysql+aiomysql://root:123456@127.0.0.1:3306/tutoring_refactor_test?charset=utf8mb4' ../.venv/bin/python -m pytest tests/test_tutoring_service.py -q
```

Expected: PASS。

- [ ] **Step 6: 提交 Service**

```bash
git add backend/app/services/tutoring_service.py backend/tests/test_tutoring_service.py
git commit -m "refactor(tutoring): 提取会话事务服务"
```

---

### Task 3: 提取隐私白名单 Payload Builder

**Files:**
- Create: `backend/app/services/tutoring_payload_builder.py`
- Modify: `backend/tests/test_tutoring_privacy.py`

- [ ] **Step 1: 将隐私测试切换到目标 Builder 并确认 RED**

替换直接导入路由私有函数：

```python
from app.services.tutoring_payload_builder import TutoringPayloadBuilder
```

测试调用统一改为：

```python
payload = await TutoringPayloadBuilder(db).build(
    user_id=user.id,
    scope="course",
    course_id=course_id,
    conversation_id=conversation.id,
    message="讲一下队列",
    exclude_message_ids=set(),
)
```

保留现有三项断言，并增加：

```python
assert set(payload["user_profile"]) == {
    "guidance_level",
    "modal_preference",
    "knowledge_mastered",
    "knowledge_weak",
    "custom_instruction",
}
assert "real_name" not in json.dumps(payload, ensure_ascii=False)
```

删除测试对路由私有 `_build_learner_context` 的导入与断言；该函数未进入生产 payload，不能为了测试保留无调用方的路由私有 API。

Run:

```bash
cd backend && TEST_DATABASE_URL='mysql+aiomysql://root:123456@127.0.0.1:3306/tutoring_refactor_test?charset=utf8mb4' ../.venv/bin/python -m pytest tests/test_tutoring_privacy.py -q
```

Expected: collection FAIL，Builder 模块不存在。

- [ ] **Step 2: 实现 Builder 公共接口**

```python
class TutoringPayloadBuilder:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def build(
        self, *, user_id: str, scope: str, course_id: str | None,
        conversation_id: str, message: str,
        exclude_message_ids: set[str] | None = None,
    ) -> dict:
        payload = {
            "user_id": user_id,
            "scope": scope,
            "message": message,
            "conversation_id": conversation_id,
            "active_kg_nodes": [],
        }
        if course_id:
            payload["course_id"] = course_id
        await self._add_course_context(payload, scope, course_id)
        await self._add_user_profile(payload, user_id, scope, course_id)
        await self._add_conversation_context(payload, conversation_id, exclude_message_ids or set())
        return payload
```

实现三个私有方法时逐字段迁移当前 `_assemble_tutoring_payload`：

- `_add_course_context`：CourseOffering → catalog_id → CourseCatalog → active KG，只输出 node 的 `id/name/chapter`。
- `_add_user_profile`：只输出五个批准字段；缺失或 global scope 使用 `{"guidance_level": "L2"}`。
- `_add_conversation_context`：summary 可选；最近消息限制 20 条、排除当前轮 IDs，并使用 `message_order_key` 稳定升序。

禁止接受前端 `active_kg_nodes` 作为可信输入，禁止序列化 ORM `__dict__`。

- [ ] **Step 3: 增加 global scope 和 summary 测试**

```python
@pytest.mark.asyncio
async def test_global_payload_uses_default_profile_and_no_course_id():
    payload = await TutoringPayloadBuilder(db).build(
        user_id=user.id,
        scope="global",
        course_id=None,
        conversation_id=conversation.id,
        message="hello",
    )
    assert "course_id" not in payload
    assert payload["user_profile"] == {"guidance_level": "L2"}
    assert payload["active_kg_nodes"] == []
```

- [ ] **Step 4: 运行 Builder 测试确认 GREEN**

Run:

```bash
cd backend && TEST_DATABASE_URL='mysql+aiomysql://root:123456@127.0.0.1:3306/tutoring_refactor_test?charset=utf8mb4' ../.venv/bin/python -m pytest tests/test_tutoring_privacy.py -q
```

Expected: PASS。

- [ ] **Step 5: 提交 Builder**

```bash
git add backend/app/services/tutoring_payload_builder.py backend/tests/test_tutoring_privacy.py
git commit -m "refactor(tutoring): 提取 Agent 请求构建器"
```

---

### Task 4: 提取 SSE Stream Adapter

**Files:**
- Create: `backend/app/services/tutoring_stream_adapter.py`
- Create: `backend/tests/test_tutoring_stream_adapter.py`

- [ ] **Step 1: 写字节分片与 ID 覆盖 RED 测试**

```python
@pytest.mark.asyncio
async def test_stream_adapter_buffers_split_utf8_and_sse_lines():
    async def source(path, payload):
        encoded = 'data: {"type":"chunk","content":"指针"}\n\n'.encode()
        yield encoded[:19]
        yield encoded[19:23]
        yield encoded[23:]
        yield b'data: {"type":"done","message_id":"agent-id"}\n\n'

    persisted = AsyncMock()
    adapter = TutoringStreamAdapter(stream_sse=source, persist_result=persisted)
    events = [event async for event in adapter.stream(
        payload={"message": "x"},
        conversation_id="conv-1",
        assistant_message_id="msg-1",
    )]

    decoded = [json.loads(event["data"]) for event in events]
    assert decoded[0] == {"type": "chunk", "content": "指针"}
    assert decoded[1]["conversation_id"] == "conv-1"
    assert decoded[1]["message_id"] == "msg-1"
    persisted.assert_awaited_once_with("msg-1", "conv-1", "指针", [], [])
```

- [ ] **Step 2: 写取消和 Agent 错误 RED 测试**

```python
@pytest.mark.asyncio
async def test_stream_adapter_persists_partial_content_when_closed():
    async def source(path, payload):
        yield b'data: {"type":"chunk","content":"partial"}\n\n'
        await asyncio.Event().wait()

    persisted = AsyncMock()
    adapter = TutoringStreamAdapter(stream_sse=source, persist_result=persisted)
    stream = adapter.stream(payload={}, conversation_id="c", assistant_message_id="m")
    first = await anext(stream)
    assert json.loads(first["data"])["content"] == "partial"
    await stream.aclose()
    persisted.assert_awaited_once_with("m", "c", "partial", [], [])


@pytest.mark.asyncio
async def test_stream_adapter_emits_existing_done_error_on_agent_failure():
    async def source(path, payload):
        raise AgentServiceError("offline", status_code=503)
        yield b""

    adapter = TutoringStreamAdapter(stream_sse=source, persist_result=AsyncMock())
    events = [event async for event in adapter.stream(payload={}, conversation_id="c", assistant_message_id="m")]
    assert json.loads(events[0]["data"])["error"] == "Agent 服务暂时不可用"
```

Run:

```bash
cd backend && ../.venv/bin/python -m pytest tests/test_tutoring_stream_adapter.py -q
```

Expected: collection FAIL，Adapter 模块不存在。

- [ ] **Step 3: 实现增量 UTF-8/SSE 缓冲器**

使用 `codecs.getincrementaldecoder("utf-8")`，维护 `text_buffer`。每次输入只处理完整 `\n` 行；流结束调用 `decoder.decode(b"", final=True)` 并处理剩余完整行。核心解析规则：

```python
def _adapt_data(self, data_str: str, state: StreamState) -> str:
    try:
        parsed = json.loads(data_str)
    except json.JSONDecodeError:
        return data_str

    event_type = parsed.get("type", "")
    if event_type == "chunk":
        state.chunks.append(parsed.get("content", ""))
    elif event_type == "diagram":
        state.diagrams.append(parsed.get("data", parsed))
    elif event_type == "knowledge_points":
        candidate = parsed.get("points") or parsed.get("knowledge_points") or parsed.get("data")
        if isinstance(candidate, list):
            state.knowledge_points = candidate
    elif event_type == "done":
        state.done_sent = True
        if not state.knowledge_points and isinstance(parsed.get("knowledge_points_used"), list):
            state.knowledge_points = parsed["knowledge_points_used"]
        parsed["conversation_id"] = state.conversation_id
        parsed["message_id"] = state.assistant_message_id
        return json.dumps(parsed, ensure_ascii=False)
    return data_str
```

- [ ] **Step 4: 实现 finally 持久化和生产默认依赖**

构造函数允许测试注入，生产默认使用现有组件：

```python
class TutoringStreamAdapter:
    def __init__(self, stream_sse=None, persist_result=None):
        self._stream_sse = stream_sse or agent_client.stream_sse
        self._persist_result = persist_result or persist_tutoring_result
```

`stream()` 使用 `try/except AgentServiceError/finally`；`finally` 无条件调用 `_persist_result`。生产持久化函数使用 `async_session_factory()`，执行两个 SQL UPDATE 后 commit；失败记录 conversation/message ID，不记录消息正文。

- [ ] **Step 5: 运行 Adapter 测试确认 GREEN**

Run:

```bash
cd backend && ../.venv/bin/python -m pytest tests/test_tutoring_stream_adapter.py -q
```

Expected: PASS。

- [ ] **Step 6: 提交 Adapter**

```bash
git add backend/app/services/tutoring_stream_adapter.py backend/tests/test_tutoring_stream_adapter.py
git commit -m "refactor(tutoring): 提取 SSE 流适配器"
```

---

### Task 5: 提取 Presenter 并实现固定 4 次列表查询

**Files:**
- Create: `backend/app/services/tutoring_presenters.py`
- Modify: `backend/app/services/tutoring_service.py`
- Modify: `backend/tests/test_tutoring_service.py`

- [ ] **Step 1: 写 Presenter 和列表查询 RED 测试**

```python
def test_conversation_item_preserves_client_fields():
    item = conversation_item(conversation, message_count=2, last_message=assistant_message)
    assert item == {
        "id": conversation.id,
        "scope": conversation.scope,
        "course_id": conversation.course_id,
        "title": conversation.title,
        "last_message": "answer",
        "message_count": 2,
        "updated_at": conversation.update_time.isoformat(),
    }


@pytest.mark.asyncio
async def test_list_conversations_executes_four_bounded_queries(counting_session, seeded_conversations):
    page = await TutoringService(counting_session).list_conversations(
        user_id=seeded_conversations.user_id,
        scope="course",
        course_id=seeded_conversations.course_id,
        page=1,
        page_size=20,
    )
    assert counting_session.execute_count == 4
    assert page.total == len(seeded_conversations.items)
    assert all(row.message_count >= 0 for row in page.items)
    assert page.items[0].last_message.content == "answer"


@pytest.mark.asyncio
async def test_list_conversations_uses_assistant_as_last_message_for_same_second_pair(
    mysql_session, same_second_conversation_pair,
):
    page = await TutoringService(mysql_session).list_conversations(
        user_id=same_second_conversation_pair.user_id,
        scope="course",
        course_id=same_second_conversation_pair.course_id,
        page=1,
        page_size=20,
    )
    row = next(item for item in page.items if item.conversation.id == same_second_conversation_pair.id)
    assert row.last_message.role == "assistant"
    assert row.last_message.content == "answer"
```

`counting_session` 包装真实 MySQL AsyncSession，只增加 `execute_count`，不得用返回固定数据的假 session 替代 SQL 行为。

- [ ] **Step 2: 运行测试确认 RED**

Run:

```bash
cd backend && TEST_DATABASE_URL='mysql+aiomysql://root:123456@127.0.0.1:3306/tutoring_refactor_test?charset=utf8mb4' ../.venv/bin/python -m pytest tests/test_tutoring_service.py -q
```

Expected: FAIL，缺少 Presenter 或 `list_conversations`。

- [ ] **Step 3: 实现 Presenter**

```python
def message_item(message: Message) -> dict:
    return {
        "role": message.role,
        "content": message.content or "",
        "diagrams": message.diagrams or [],
        "knowledge_points": message.knowledge_points or [],
        "meta": message.meta_json or {},
        "timestamp": message.create_time.isoformat() if message.create_time else "",
    }


def conversation_item(conversation: Conversation, message_count: int, last_message: Message | None) -> dict:
    return {
        "id": conversation.id,
        "scope": conversation.scope,
        "course_id": conversation.course_id,
        "title": conversation.title,
        "last_message": last_message.content[:50] if last_message and last_message.content else "",
        "message_count": message_count,
        "updated_at": conversation.update_time.isoformat() if conversation.update_time else "",
    }
```

`conversation_detail` 使用 `message_item`，字段必须与当前路由完全一致。

- [ ] **Step 4: 实现 4 次有界查询**

在 Service 中新增 `ConversationListRow`、`ConversationPage` dataclass。查询顺序严格为 count、分页 Conversation、分组 message count、窗口 last message：

```python
role_rank = case((Message.role == "user", 0), else_=1)
ranked = select(
    Message,
    func.row_number().over(
        partition_by=Message.conversation_id,
        order_by=(
            Message.create_time.desc(),
            Message.update_time.desc(),
            role_rank.desc(),
        ),
    ).label("row_number"),
).where(
    Message.conversation_id.in_(conversation_ids),
    Message.is_deleted == False,
).subquery()
ranked_message = aliased(Message, ranked)
last_result = await self.db.execute(
    select(ranked_message).where(ranked.c.row_number == 1)
)
```

空分页仍执行定义清晰的 2 次基础查询后直接返回，不执行无意义 `IN ()`；对应测试应断言空页为 2 次查询。非空页固定 4 次。

- [ ] **Step 5: 实现详情与软删除 Service 方法**

```python
async def get_conversation(self, *, user_id: str, conversation_id: str) -> tuple[Conversation, list[Message]]:
    conversation = await self._get_owned_conversation(user_id, conversation_id)
    result = await self.db.execute(
        select(Message).where(
            Message.conversation_id == conversation_id,
            Message.is_deleted == False,
        ).order_by(Message.create_time.asc(), Message.update_time.asc())
    )
    return conversation, sorted(result.scalars().all(), key=message_order_key)

async def delete_conversation(self, *, user_id: str, conversation_id: str) -> None:
    conversation = await self._get_owned_conversation(user_id, conversation_id, for_update=True)
    conversation.is_deleted = True
    await self.db.flush()
```

- [ ] **Step 6: 运行 Service 与特征测试确认 GREEN**

Run:

```bash
cd backend && TEST_DATABASE_URL='mysql+aiomysql://root:123456@127.0.0.1:3306/tutoring_refactor_test?charset=utf8mb4' ../.venv/bin/python -m pytest tests/test_tutoring_service.py -q
```

Expected: PASS，非空列表查询计数为 4。

- [ ] **Step 7: 提交 Presenter 与查询优化**

```bash
git add backend/app/services/tutoring_presenters.py backend/app/services/tutoring_service.py backend/tests/test_tutoring_service.py
git commit -m "refactor(tutoring): 收口会话查询与响应转换"
```

---

### Task 6: 收口 Router 并证明请求 session 在 SSE 前释放

**Files:**
- Modify: `backend/app/api/v1/tutoring.py`
- Create: `backend/tests/test_tutoring_routes_refactored.py`
- Modify: `backend/tests/test_agent_integration.py`

- [ ] **Step 1: 写薄路由和 transaction RED 测试**

```python
@pytest.mark.asyncio
async def test_chat_ends_request_transaction_before_stream_adapter(
    mysql_session, persisted_user, monkeypatch,
):
    observed = {}

    async def fake_stream(self, *, payload, conversation_id, assistant_message_id):
        observed["db_in_transaction"] = mysql_session.in_transaction()
        yield {"event": "message", "data": json.dumps({
            "type": "done",
            "conversation_id": conversation_id,
            "message_id": assistant_message_id,
        })}

    monkeypatch.setattr(TutoringStreamAdapter, "stream", fake_stream)
    response = await tutoring_chat(
        TutoringChatRequest(message="hello", scope="global"),
        current_user=persisted_user,
        db=mysql_session,
    )
    _ = [chunk async for chunk in response.body_iterator]
    assert observed["db_in_transaction"] is False
```

`mysql_session` 与 `persisted_user` 使用本文件 async fixture 创建真实 MySQL User；测试后按 user ID 删除关联 Conversation/Message 和 User。直接调用路由函数是为了在同一 AsyncSession 上精确观察 transaction 状态，REST 契约由同文件其余 ASGI 测试覆盖。

增加异常翻译参数化测试，分别断言：

- course 缺 ID → 400 包装错误；
- edit 缺 conversation ID → 400 包装错误；
- regenerate 最后 user 缺失 → 保留当前 plain detail；
- 非所有者/不存在 → 404 包装错误。

- [ ] **Step 2: 运行路由测试确认 RED**

Run:

```bash
cd backend && TEST_DATABASE_URL='mysql+aiomysql://root:123456@127.0.0.1:3306/tutoring_refactor_test?charset=utf8mb4' ../.venv/bin/python -m pytest tests/test_tutoring_routes_refactored.py -q
```

Expected: FAIL，当前 Router 尚未使用分层组件，且 Builder 读事务在流开始前未显式结束。

- [ ] **Step 3: 将 chat 路由改为分层编排**

路由只保留以下顺序：

```python
service = TutoringService(db)
try:
    if req.action == "edit":
        turn = await service.prepare_edit_turn(
            user_id=current_user.id,
            conversation_id=req.conversation_id,
            message=req.message,
            scope=req.scope,
            course_id=effective_course_id,
        )
    elif req.action == "regenerate":
        turn = await service.prepare_regenerate_turn(
            user_id=current_user.id,
            conversation_id=req.conversation_id,
            message=req.message,
            scope=req.scope,
            course_id=effective_course_id,
        )
    else:
        turn = await service.prepare_chat_turn(
            user_id=current_user.id,
            conversation_id=req.conversation_id,
            message=req.message,
            scope=req.scope,
            course_id=effective_course_id,
        )
    await db.commit()
except Exception:
    await db.rollback()
    raise

payload = await TutoringPayloadBuilder(db).build(
    user_id=current_user.id,
    scope=turn.scope,
    course_id=turn.course_id,
    conversation_id=turn.conversation_id,
    message=turn.message,
    exclude_message_ids={turn.user_message_id, turn.assistant_message_id},
)
await db.rollback()  # 结束 Builder 的只读 autobegin transaction，释放连接

events = TutoringStreamAdapter().stream(
    payload=payload,
    conversation_id=turn.conversation_id,
    assistant_message_id=turn.assistant_message_id,
)
return EventSourceResponse(events)
```

不得把 request-scoped `db` 传入 Adapter。异常类只在 Router 翻译为当前 HTTP detail 结构。

- [ ] **Step 4: 将 REST 路由改为 Service + Presenter**

- list：调用 `list_conversations`，对每个 row 使用 `conversation_item`。
- detail：调用 `get_conversation`，使用 `conversation_detail`。
- delete：调用 `delete_conversation` 后 commit，返回当前 `{code,message,data}`。

Router 中删除 SQLAlchemy、Conversation、Message、CourseOffering、CourseCatalog、UserProfile、`async_session_factory` 和 JSON SSE 累积相关导入。

- [ ] **Step 5: 更新集成测试 patch 路径**

把：

```python
patch("app.api.v1.tutoring.agent_client.stream_sse", fake_stream_sse)
```

改为：

```python
patch("app.services.tutoring_stream_adapter.agent_client.stream_sse", fake_stream_sse)
```

保留所有现有 SSE done、列表和历史断言。

- [ ] **Step 6: 运行 tutoring 回归确认 GREEN**

Run:

```bash
cd backend && TEST_DATABASE_URL='mysql+aiomysql://root:123456@127.0.0.1:3306/tutoring_refactor_test?charset=utf8mb4' ../.venv/bin/python -m pytest tests/test_tutoring_routes_refactored.py tests/test_tutoring_service.py tests/test_tutoring_privacy.py tests/test_tutoring_stream_adapter.py tests/test_agent_integration.py::TestTutoringChatIntegration -q
```

Expected: 全部 PASS。

- [ ] **Step 7: 语法检查并确认 Router 已收口**

Run:

```bash
python3 -m py_compile backend/app/api/v1/tutoring.py backend/app/services/tutoring_service.py backend/app/services/tutoring_payload_builder.py backend/app/services/tutoring_stream_adapter.py backend/app/services/tutoring_presenters.py
```

Expected: exit 0。

Run:

```bash
rg -n 'select\(|sql_update|async_session_factory|agent_client|json\.loads' backend/app/api/v1/tutoring.py
```

Expected: 无 SQL、独立 session、AgentClient 或 SSE JSON 解析命中。

- [ ] **Step 8: 提交 Router 收口**

```bash
git add backend/app/api/v1/tutoring.py backend/tests/test_tutoring_routes_refactored.py backend/tests/test_agent_integration.py
git commit -m "refactor(tutoring): 收口路由与流式编排"
```

---

### Task 7: 覆盖率、全量回归和进度文档

**Files:**
- Modify: `WORKFLOW.md`
- Modify: `frontend/docs/requirements-coverage.md`

- [ ] **Step 1: 运行 tutoring 定向覆盖率**

Run:

```bash
cd backend && TEST_DATABASE_URL='mysql+aiomysql://root:123456@127.0.0.1:3306/tutoring_refactor_test?charset=utf8mb4' ../.venv/bin/python -m pytest tests/test_tutoring_routes_refactored.py tests/test_tutoring_service.py tests/test_tutoring_privacy.py tests/test_tutoring_stream_adapter.py tests/test_agent_integration.py::TestTutoringChatIntegration --cov=app.api.v1.tutoring --cov=app.services.tutoring_service --cov=app.services.tutoring_payload_builder --cov=app.services.tutoring_stream_adapter --cov=app.services.tutoring_presenters --cov-report=term-missing --cov-fail-under=80 -q
```

Expected: 全部 PASS，总覆盖率 >= 80%。若不足，只补真实未覆盖分支测试，不使用 `# pragma: no cover` 绕过。

- [ ] **Step 2: 运行 Backend 相关回归**

Run:

```bash
cd backend && TEST_DATABASE_URL='mysql+aiomysql://root:123456@127.0.0.1:3306/tutoring_refactor_test?charset=utf8mb4' ../.venv/bin/python -m pytest tests/test_api.py tests/test_agent_integration.py tests/test_tutoring_privacy.py tests/test_tutoring_service.py tests/test_tutoring_stream_adapter.py tests/test_tutoring_routes_refactored.py -q
```

Expected: 全部 PASS。

- [ ] **Step 3: 核对 Client 与 Agent API 契约**

逐项比对：

- Client 路径 `/tutoring/chat`、`/tutoring/conversations`、`/tutoring/conversations/{id}`；
- 请求 `message/scope/course_id/conversation_id`，并保留代码既有 `action`；
- REST response 字段和 nullable；
- SSE `chunk/diagram/knowledge_points/suggestion/done/review`；
- Agent payload `user_id/scope/course_id/catalog_id/conversation_id/message/user_profile/active_kg_nodes/conversation_summary/recent_messages`。

Expected: 无新增、删除或改名；`action` 仅记录为既有文档漂移。

- [ ] **Step 4: 更新进度文档**

在 `WORKFLOW.md` 追加 2026-06-19 记录：

- 修改的五个 tutoring 分层模块和测试；
- Router → Service/Builder/Adapter/Presenter 边界；
- 固定 4 次列表查询；
- SSE 跨字节块和断连持久化修复；
- 实际执行的测试命令和结果；
- Client API 漂移：否；Agent API 漂移：否；既有 Client OpenAPI 漏记 action。

在 `frontend/docs/requirements-coverage.md` 更新 tutoring SSE、会话 CRUD、edit/regenerate、隐私 payload 和流后落库测试覆盖。

- [ ] **Step 5: 检查最终差异和禁止文件**

Run:

```bash
git status --short
git diff --check
git diff --name-only ec9c3af..HEAD
```

Expected: 不包含 `.env`、密钥、volume、上传文件、构建产物、缓存或用户已有无关改动。

- [ ] **Step 6: 提交文档记录**

```bash
git add WORKFLOW.md frontend/docs/requirements-coverage.md
git commit -m "docs: 记录 tutoring 分层重构验证结果"
```

---

## 最终验收清单

- [ ] `backend/app/api/v1/tutoring.py` 不包含 ORM 查询、SSE JSON 解析或独立落库 session。
- [ ] chat/edit/regenerate 均由 `TutoringService` 管理，edit/regenerate 使用 MySQL Conversation 行锁。
- [ ] Agent payload 只由 Builder 白名单生成，不包含身份字段。
- [ ] Builder 查询结束后显式结束请求级 transaction，Adapter 不接收 request DB。
- [ ] SSE 支持 UTF-8 和 data 行跨字节块，done 使用 Backend ID。
- [ ] 客户端取消后只持久化已完整接收内容。
- [ ] 非空会话列表固定 4 次有界查询，空页固定 2 次查询。
- [ ] Client API、Agent API、Schema 和 HTTP 状态码无变化。
- [ ] course enrollment 403 未混入本任务。
- [ ] 定向覆盖率 >= 80%，相关 MySQL 回归全部通过。
- [ ] WORKFLOW 和 requirements coverage 已更新。
