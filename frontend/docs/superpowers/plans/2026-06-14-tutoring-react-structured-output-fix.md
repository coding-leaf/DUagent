# Tutoring ReAct 结构化输出修复 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 用 AgentScope `structured_model` 让 tutoring ReAct 产出已校验的结构化对象，从源头消灭前端 JSON 块泄露，并为模型调用加上有界超时、修复误导日志、加固兜底解析与前端展示防御。

**Architecture:** ReActAgent 传入 Pydantic `TutoringStructuredOutput` 作为 `structured_model`，结果从 `Msg.metadata` 直接读取干净字段（`model_text/knowledge_points/suggestion/diagram`），不再正则解析自由文本；自由文本解析降为防御性兜底（括号配平，正确跳过嵌套 ```c 围栏）。`OpenAIChatModel` 加 `client_kwargs.timeout` 与 `stream`。前端把两份重复的 `getDisplayText` 抽成共享 util，用括号配平剥离散文中的围栏 JSON。

**Tech Stack:** Python 3.12 / AgentScope 1.0.20 / Pydantic v2 / pytest（`uv run pytest`）；React 19 / Vite 8 / ESLint 10 / Node ESM。

**关键约定（实现者必读）：**
- 后端测试运行器：`cd /home/yezisama/workspace/workflow/EDUagent/agent_service && uv run pytest <path>::<test> -v`。
- 前端检查：`cd /home/yezisama/workspace/workflow/EDUagent/frontend && npm run lint && npm run build`。
- 单仓 git，仓库根 `/home/yezisama/workspace/workflow/EDUagent`；提交用简洁中文，**不要 push**，**只 `git add` 本任务涉及文件**（工作区另有无关在途改动，勿卷入）。
- 不修改 `.env`（超时/流式默认值写在 `config.py`，无需改 `.env`）。不改 `../docs/` 契约。SSE 事件与 OpenAPI 字段不变。

**关联 spec：** `frontend/docs/superpowers/specs/2026-06-14-tutoring-react-structured-output-fix-design.md`

---

## File Structure

后端（`agent_service/`）：
- `core/config.py` — 新增 `LLM_TIMEOUT` / `LLM_STREAM` 设置项。
- `core/ai.py` — `_build_chat_provider_from_settings` 给 `OpenAIChatModel` 应用 `stream` 与 `client_kwargs.timeout`。
- `schemas/tutoring.py` — 新增 `TutoringStructuredOutput`（structured_model 的 schema）。
- `agents/tutoring.py` — 新增 `build_tutoring_response_from_metadata`；加固 `_try_parse_markdown_json_output`（括号配平兜底）。
- `agents/tutoring_react.py` — `generate()` 传 `structured_model`，返回 `dict | str | None`。
- `agents/tutoring_react_flow.py` — 按返回类型分支构建响应；修复误导日志。
- `prompts/tutoring.py` — 删除"只输出 JSON / 不要 markdown 代码块"指令。

前端（`frontend/`）：
- `src/utils/chatContent.js` — 新建共享 `extractModelText`（含括号配平剥离围栏 JSON）。
- `src/components/chat/ChatMessage.jsx` / `src/pages/AIChat.jsx` — 删除各自重复的 `getDisplayText`，改用共享 util。

测试：
- `tests/test_core_config.py` / `tests/test_ai_providers.py` / `tests/test_tutoring_agent.py` / `tests/test_tutoring_react.py` / `tests/test_tutoring_react_flow.py` / `tests/test_tutoring_prompts.py`。
- 前端无单测框架：用一次性 `node` ESM 脚本验证 + `npm run lint && npm run build`。

---

## Task 1: 新增 LLM_TIMEOUT / LLM_STREAM 设置项

**Files:**
- Modify: `agent_service/core/config.py`
- Test: `agent_service/tests/test_core_config.py`

- [ ] **Step 1: 写失败测试**

在 `agent_service/tests/test_core_config.py` 末尾追加：

```python
def test_settings_declares_llm_timeout_and_stream_defaults() -> None:
    from agent_service.core.config import Settings

    assert Settings.model_fields["LLM_TIMEOUT"].default == 60.0
    assert Settings.model_fields["LLM_STREAM"].default is True
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd /home/yezisama/workspace/workflow/EDUagent/agent_service && uv run pytest tests/test_core_config.py::test_settings_declares_llm_timeout_and_stream_defaults -v`
Expected: FAIL，`KeyError: 'LLM_TIMEOUT'`（字段未声明）。

- [ ] **Step 3: 实现最小改动**

在 `agent_service/core/config.py` 的 `Settings` 类中，`LLM_JSON_MODE_ENABLED: bool | None = None` 这一行**之后**插入：

```python
    LLM_TIMEOUT: float = 60.0
    LLM_STREAM: bool = True
```

- [ ] **Step 4: 运行测试确认通过**

Run: `cd /home/yezisama/workspace/workflow/EDUagent/agent_service && uv run pytest tests/test_core_config.py -v`
Expected: PASS。

- [ ] **Step 5: 提交**

```bash
cd /home/yezisama/workspace/workflow/EDUagent
git add agent_service/core/config.py agent_service/tests/test_core_config.py
git commit -m "tutoring: 新增 LLM_TIMEOUT/LLM_STREAM 设置项"
```

---

## Task 2: OpenAIChatModel 应用 timeout 与 stream

**Files:**
- Modify: `agent_service/core/ai.py:160-182`（`_build_chat_provider_from_settings` 内的 `OpenAIChatModel(...)` 构造）
- Test: `agent_service/tests/test_ai_providers.py`

- [ ] **Step 1: 写失败测试**

在 `agent_service/tests/test_ai_providers.py` 末尾追加：

```python
def test_build_chat_provider_applies_timeout_and_stream(monkeypatch) -> None:
    from unittest.mock import patch, MagicMock
    from agent_service.core import ai as ai_module

    monkeypatch.setattr(ai_module.settings, "LLM_PROVIDER", "agentscope_openai")
    monkeypatch.setattr(ai_module.settings, "LLM_BASE_URL", "https://example.com")
    monkeypatch.setattr(ai_module.settings, "LLM_API_KEY", "sk-test")
    monkeypatch.setattr(ai_module.settings, "LLM_MODEL", "test-model")
    monkeypatch.setattr(ai_module.settings, "LLM_TIMEOUT", 42.0)
    monkeypatch.setattr(ai_module.settings, "LLM_STREAM", True)

    captured: dict = {}

    class FakeModel:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    with patch("agentscope.model.OpenAIChatModel", FakeModel), \
         patch("agentscope.formatter.DeepSeekChatFormatter", MagicMock()):
        provider = ai_module._build_chat_provider_from_settings()

    assert provider is not None
    assert captured["stream"] is True
    assert captured["client_kwargs"]["base_url"] == "https://example.com"
    assert captured["client_kwargs"]["timeout"] == 42.0
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd /home/yezisama/workspace/workflow/EDUagent/agent_service && uv run pytest tests/test_ai_providers.py::test_build_chat_provider_applies_timeout_and_stream -v`
Expected: FAIL，`KeyError: 'timeout'`（`client_kwargs` 当前只有 `base_url`），且 `stream` 当前为 `False`。

- [ ] **Step 3: 实现最小改动**

在 `agent_service/core/ai.py` 的 `_build_chat_provider_from_settings` 中，把 `OpenAIChatModel(...)` 构造由：

```python
            model=OpenAIChatModel(
                model_name=settings.LLM_MODEL,
                api_key=settings.LLM_API_KEY,
                stream=False,
                client_kwargs={"base_url": settings.LLM_BASE_URL},
            ),
```

改为：

```python
            model=OpenAIChatModel(
                model_name=settings.LLM_MODEL,
                api_key=settings.LLM_API_KEY,
                stream=settings.LLM_STREAM,
                client_kwargs={
                    "base_url": settings.LLM_BASE_URL,
                    "timeout": settings.LLM_TIMEOUT,
                },
            ),
```

- [ ] **Step 4: 运行测试确认通过**

Run: `cd /home/yezisama/workspace/workflow/EDUagent/agent_service && uv run pytest tests/test_ai_providers.py -v`
Expected: PASS。

- [ ] **Step 5: 提交**

```bash
cd /home/yezisama/workspace/workflow/EDUagent
git add agent_service/core/ai.py agent_service/tests/test_ai_providers.py
git commit -m "tutoring: ReAct 主路径 OpenAIChatModel 应用有界 timeout 与 stream"
```

---

## Task 3: 新增 TutoringStructuredOutput schema

**Files:**
- Modify: `agent_service/schemas/tutoring.py`（在 `TutoringChatRequest` 之后、`ChunkEvent` 之前新增）
- Test: `agent_service/tests/test_schema_contracts.py`

- [ ] **Step 1: 写失败测试**

在 `agent_service/tests/test_schema_contracts.py` 末尾追加：

```python
def test_tutoring_structured_output_schema() -> None:
    from agent_service.schemas.tutoring import TutoringStructuredOutput

    obj = TutoringStructuredOutput(
        model_text="指针是存储地址的变量。",
        knowledge_points=["指针", "解引用"],
        suggestion="练习指针作为函数参数。",
        diagram="flowchart TD\n A-->B",
    )
    assert obj.model_text == "指针是存储地址的变量。"
    assert obj.knowledge_points == ["指针", "解引用"]
    assert obj.suggestion == "练习指针作为函数参数。"
    assert obj.diagram == "flowchart TD\n A-->B"

    # suggestion / diagram 可选，knowledge_points 可空
    minimal = TutoringStructuredOutput(model_text="只有正文")
    assert minimal.knowledge_points == []
    assert minimal.suggestion is None
    assert minimal.diagram is None
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd /home/yezisama/workspace/workflow/EDUagent/agent_service && uv run pytest tests/test_schema_contracts.py::test_tutoring_structured_output_schema -v`
Expected: FAIL，`ImportError: cannot import name 'TutoringStructuredOutput'`。

- [ ] **Step 3: 实现最小改动**

在 `agent_service/schemas/tutoring.py` 中，`TutoringChatRequest` 类（以 `validate_scope` 结束）之后、`class ChunkEvent` 之前插入：

```python
class TutoringStructuredOutput(BaseModel):
    """ReActAgent structured_model 输出契约：由 AgentScope generate_response 工具按此 schema 校验。

    字段直接映射到 SSE 输出，因此 model_text 必须是面向学生的纯文本，不要包裹 JSON 或代码围栏。
    """

    model_text: str = Field(..., description="面向学生的自然语言讲解正文（纯文本，可含 Markdown，不要包 JSON）")
    knowledge_points: list[str] = Field(
        default_factory=list, description="本轮涉及的知识点名称，1 到 3 个；优先取自图谱节点名称"
    )
    suggestion: str | None = Field(None, description="下一步学习建议；无则留空")
    diagram: str | None = Field(
        None, description="可选：涉及数据结构操作流程或复杂逻辑流程时的 Mermaid 语法代码；否则留空"
    )
```

- [ ] **Step 4: 运行测试确认通过**

Run: `cd /home/yezisama/workspace/workflow/EDUagent/agent_service && uv run pytest tests/test_schema_contracts.py -v`
Expected: PASS。

- [ ] **Step 5: 提交**

```bash
cd /home/yezisama/workspace/workflow/EDUagent
git add agent_service/schemas/tutoring.py agent_service/tests/test_schema_contracts.py
git commit -m "tutoring: 新增 TutoringStructuredOutput structured_model 契约"
```

---

## Task 4: tutoring.py 新增 metadata → TutoringModelResponse 映射

**Files:**
- Modify: `agent_service/agents/tutoring.py`（新增公共函数 + 加入 `__all__`）
- Test: `agent_service/tests/test_tutoring_agent.py`

- [ ] **Step 1: 写失败测试**

在 `agent_service/tests/test_tutoring_agent.py` 末尾追加：

```python
def test_build_tutoring_response_from_metadata_maps_and_caps() -> None:
    from agent_service.agents.tutoring import build_tutoring_response_from_metadata

    metadata = {
        "model_text": "  指针是核心概念。  ",
        "knowledge_points": ["指针", "解引用", "地址", "第四个被截断"],
        "suggestion": "  练习指针。  ",
        "diagram": "flowchart TD\n A-->B",
    }

    r = build_tutoring_response_from_metadata(metadata)

    assert r.model_text == "指针是核心概念。"
    assert r.knowledge_point_names == ["指针", "解引用", "地址"]
    assert r.suggestion_text == "练习指针。"
    assert r.diagram == "flowchart TD\n A-->B"


def test_build_tutoring_response_from_metadata_handles_missing_fields() -> None:
    from agent_service.agents.tutoring import build_tutoring_response_from_metadata

    r = build_tutoring_response_from_metadata({"model_text": "只有正文"})

    assert r.model_text == "只有正文"
    assert r.knowledge_point_names == []
    assert r.suggestion_text is None
    assert r.diagram is None
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd /home/yezisama/workspace/workflow/EDUagent/agent_service && uv run pytest tests/test_tutoring_agent.py::test_build_tutoring_response_from_metadata_maps_and_caps -v`
Expected: FAIL，`ImportError: cannot import name 'build_tutoring_response_from_metadata'`。

- [ ] **Step 3: 实现最小改动**

在 `agent_service/agents/tutoring.py` 中，`_build_response_from_payload` 函数定义**之后**新增：

```python
def build_tutoring_response_from_metadata(metadata: dict) -> TutoringModelResponse:
    """把 ReActAgent structured_model 的 metadata dict 映射为 TutoringModelResponse。

    复用 _build_response_from_payload，因此 knowledge_points 截断到 3 个、字段做 strip。
    """
    model_text = metadata.get("model_text")
    clean_text = (
        model_text.strip()
        if isinstance(model_text, str) and model_text.strip()
        else None
    )
    return _build_response_from_payload(clean_text, metadata)
```

并在文件末尾的 `__all__` 列表中加入该函数名。把：

```python
__all__ = [
    "TutoringModelResponse",
    "TutoringGenerationResult",
    "build_tutoring_generation_result",
    "generate_tutoring_sse_events",
    "parse_tutoring_model_response",
]
```

改为：

```python
__all__ = [
    "TutoringModelResponse",
    "TutoringGenerationResult",
    "build_tutoring_generation_result",
    "build_tutoring_response_from_metadata",
    "generate_tutoring_sse_events",
    "parse_tutoring_model_response",
]
```

- [ ] **Step 4: 运行测试确认通过**

Run: `cd /home/yezisama/workspace/workflow/EDUagent/agent_service && uv run pytest tests/test_tutoring_agent.py -v`
Expected: PASS（含原有用例）。

- [ ] **Step 5: 提交**

```bash
cd /home/yezisama/workspace/workflow/EDUagent
git add agent_service/agents/tutoring.py agent_service/tests/test_tutoring_agent.py
git commit -m "tutoring: 新增 metadata→TutoringModelResponse 映射函数"
```

---

## Task 5: tutoring_react.py 启用 structured_model 并返回 metadata

**Files:**
- Modify: `agent_service/agents/tutoring_react.py`
- Test: `agent_service/tests/test_tutoring_react.py`（更新既有 fake + 新增用例）

- [ ] **Step 1: 更新测试（既有 fake 必须先适配新契约）**

把 `agent_service/tests/test_tutoring_react.py` 顶部的 `FakeMsg` 与 `FakeReActAgent` 两个类整体替换为下面版本（`FakeMsg` 增加 `metadata`；`FakeReActAgent.__call__` 接受 `**kwargs` 以兼容 `structured_model=`，并可配置返回的 metadata）：

```python
class FakeMsg:
    """模拟 AgentScope Msg，提供 get_text_content() 与 metadata。"""

    def __init__(self, text: str, metadata: dict | None = None) -> None:
        self._text = text
        self.metadata = metadata or {}

    def get_text_content(self) -> str:
        return self._text


class FakeReActAgent:
    """模拟 AgentScope ReActAgent，记录调用参数并返回预设结果。"""

    def __init__(self, raise_error: bool = False, metadata: dict | None = None) -> None:
        self.calls: list[dict] = []
        self._raise_error = raise_error
        self._metadata = metadata

    async def __call__(self, msg, **kwargs):
        self.calls.append({"msg": msg, "kwargs": kwargs})
        if self._raise_error:
            raise RuntimeError("ReActAgent 调用失败")
        return FakeMsg(
            '{"model_text":"链式法则先看外层函数。","knowledge_points":["链式法则"],"suggestion":"先确认外层函数。"}',
            metadata=self._metadata,
        )
```

再在该文件末尾追加三条新用例：

```python
def test_generate_returns_metadata_dict_when_structured_output_present() -> None:
    model = FakeChatModel()
    formatter = FakeFormatter()
    agent = TutorReActAgent(chat_model=model, formatter=formatter)
    agent._agent = FakeReActAgent(
        metadata={"model_text": "讲解指针", "knowledge_points": ["指针"]}
    )

    result = asyncio.run(agent.generate("讲讲指针"))

    assert isinstance(result, dict)
    assert result["model_text"] == "讲解指针"
    # structured_model 必须被透传给 ReActAgent
    assert "structured_model" in agent._agent.calls[0]["kwargs"]


def test_generate_falls_back_to_text_when_metadata_empty() -> None:
    model = FakeChatModel()
    formatter = FakeFormatter()
    agent = TutorReActAgent(chat_model=model, formatter=formatter)
    agent._agent = FakeReActAgent(metadata=None)

    result = asyncio.run(agent.generate("讲讲指针"))

    assert isinstance(result, str)
    assert "链式法则先看外层函数" in result


def test_generate_returns_none_on_exception_structured() -> None:
    model = FakeChatModel()
    formatter = FakeFormatter()
    agent = TutorReActAgent(chat_model=model, formatter=formatter)
    agent._agent = FakeReActAgent(raise_error=True)

    result = asyncio.run(agent.generate("讲讲指针"))

    assert result is None
```

注意：原有用例 `test_tutor_react_agent_generate_calls_react_agent_and_returns_text` 仍然有效——`FakeReActAgent` 默认 `metadata=None`，`generate()` 会回退到文本，`"链式法则" in result` 依旧成立。

- [ ] **Step 2: 运行测试确认失败**

Run: `cd /home/yezisama/workspace/workflow/EDUagent/agent_service && uv run pytest tests/test_tutoring_react.py -v`
Expected: FAIL——`test_generate_returns_metadata_dict_when_structured_output_present` 失败（当前 `generate()` 返回文本字符串而非 dict，且未透传 `structured_model`）。

- [ ] **Step 3: 实现最小改动**

把 `agent_service/agents/tutoring_react.py` 顶部 import 区加入 schema 引入。把：

```python
from agent_service.core.logging import get_logger
from agent_service.prompts.tutoring import TUTOR_REACT_SYSTEM_PROMPT
```

改为：

```python
from agent_service.core.logging import get_logger
from agent_service.prompts.tutoring import TUTOR_REACT_SYSTEM_PROMPT
from agent_service.schemas.tutoring import TutoringStructuredOutput
```

再把 `generate` 方法整体替换为：

```python
    async def generate(self, user_message: str) -> dict | str | None:
        """调用 ReActAgent 生成回答。

        返回值：
        - dict：成功产出 structured_model（来自 result.metadata），含 model_text 等字段；
        - str：未产出结构化输出时回退到纯文本（交由上游兜底解析）；
        - None：调用异常，走规则兜底。
        """
        try:
            result = await self._agent(
                Msg(name="user", role="user", content=user_message),
                structured_model=TutoringStructuredOutput,
            )
            if result.metadata:
                return result.metadata
            return result.get_text_content()
        except Exception:
            logger.warning("TutorReActAgent.generate 调用失败，降级到规则兜底", exc_info=True)
            return None
```

并把类 docstring 中"输出 generate() 返回模型文本或 None"一句更新为"输出 generate() 返回 structured metadata(dict)/文本(str)/None"（非功能性，保持文档一致）。

- [ ] **Step 4: 运行测试确认通过**

Run: `cd /home/yezisama/workspace/workflow/EDUagent/agent_service && uv run pytest tests/test_tutoring_react.py -v`
Expected: PASS（含更新后的原有用例与三条新用例）。

- [ ] **Step 5: 提交**

```bash
cd /home/yezisama/workspace/workflow/EDUagent
git add agent_service/agents/tutoring_react.py agent_service/tests/test_tutoring_react.py
git commit -m "tutoring: ReActAgent 启用 structured_model，generate 返回 metadata"
```

---

## Task 6: tutoring_react_flow.py 按类型分支构建响应并修复误导日志

**Files:**
- Modify: `agent_service/agents/tutoring_react_flow.py:45-52`
- Test: `agent_service/tests/test_tutoring_react_flow.py`

- [ ] **Step 1: 写失败测试**

在 `agent_service/tests/test_tutoring_react_flow.py` 中：

(a) 把顶部的 `FakeReactAgent` 类整体替换为支持 dict 返回的版本：

```python
class FakeReactAgent:
    """模拟 TutorReActAgent，可配置 generate 的返回值和行为。"""

    def __init__(self, output=None, should_raise: bool = False) -> None:
        self._output = output
        self._should_raise = should_raise
        self.calls = []

    async def generate(self, user_message: str):
        self.calls.append(user_message)
        if self._should_raise:
            raise RuntimeError("agent failure")
        return self._output
```

(b) 在文件末尾追加两条用例：

```python
def test_react_response_builds_from_metadata_dict() -> None:
    request = _make_request()
    context = _make_context()

    class FakeProvider:
        model = object()
        formatter = object()

    fake_agent = FakeReactAgent(
        output={
            "model_text": "链式法则先看外层函数，再乘内层导数。",
            "knowledge_points": ["链式法则", "复合函数"],
            "suggestion": "先确认外层，再检查内层。",
            "diagram": "flowchart TD\n A-->B",
        }
    )

    with patch(
        "agent_service.agents.tutoring_react_flow.TutorReActAgent",
        return_value=fake_agent,
    ):
        result = asyncio.run(
            generate_tutoring_react_response(request, context, FakeProvider())
        )

    assert result is not None
    assert result.model_text == "链式法则先看外层函数，再乘内层导数。"
    assert result.knowledge_point_names == ["链式法则", "复合函数"]
    assert result.suggestion_text == "先确认外层，再检查内层。"
    assert result.diagram == "flowchart TD\n A-->B"


def test_react_response_does_not_log_succeeded_when_none(caplog) -> None:
    import logging

    class FakeProvider:
        model = object()
        formatter = object()

    fake_agent = FakeReactAgent(output=None)

    with patch(
        "agent_service.agents.tutoring_react_flow.TutorReActAgent",
        return_value=fake_agent,
    ):
        with caplog.at_level(logging.INFO, logger="agent_service.agents.tutoring_react_flow"):
            result = asyncio.run(
                generate_tutoring_react_response(
                    _make_request(), _make_context(), FakeProvider()
                )
            )

    assert result is None
    assert "Tutoring ReAct succeeded" not in caplog.text
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd /home/yezisama/workspace/workflow/EDUagent/agent_service && uv run pytest tests/test_tutoring_react_flow.py::test_react_response_builds_from_metadata_dict tests/test_tutoring_react_flow.py::test_react_response_does_not_log_succeeded_when_none -v`
Expected: FAIL——dict 用例当前会把 dict 传给 `parse_tutoring_model_response`（其对 dict 不解析，行为异常）；log 用例当前因无条件记 "succeeded" 而失败。

- [ ] **Step 3: 实现最小改动**

在 `agent_service/agents/tutoring_react_flow.py` 顶部 import 区，把：

```python
from agent_service.agents.tutoring import parse_tutoring_model_response, TutoringModelResponse
```

改为：

```python
from agent_service.agents.tutoring import (
    build_tutoring_response_from_metadata,
    parse_tutoring_model_response,
    TutoringModelResponse,
)
```

再把 `generate_tutoring_react_response` 中这段：

```python
        model_output = await agent.generate(user_message)
        logger.info("Tutoring ReAct succeeded")
        if model_output is None:
            return None
        return parse_tutoring_model_response(model_output)
```

替换为：

```python
        model_output = await agent.generate(user_message)
        if model_output is None:
            logger.info("Tutoring ReAct degraded: no model output, falling back")
            return None
        logger.info("Tutoring ReAct succeeded")
        if isinstance(model_output, dict):
            return build_tutoring_response_from_metadata(model_output)
        return parse_tutoring_model_response(model_output)
```

- [ ] **Step 4: 运行测试确认通过**

Run: `cd /home/yezisama/workspace/workflow/EDUagent/agent_service && uv run pytest tests/test_tutoring_react_flow.py -v`
Expected: PASS（含原有 str 路径用例与两条新用例）。

- [ ] **Step 5: 提交**

```bash
cd /home/yezisama/workspace/workflow/EDUagent
git add agent_service/agents/tutoring_react_flow.py agent_service/tests/test_tutoring_react_flow.py
git commit -m "tutoring: flow 按 metadata/文本分支构建响应并修复误导成功日志"
```

---

## Task 7: 加固兜底解析器（括号配平，跳过嵌套 ```c 围栏）

**Files:**
- Modify: `agent_service/agents/tutoring.py`（重写 `_try_parse_markdown_json_output`，新增 `_iter_json_objects` / `_scan_balanced_object_end`，移除不再使用的 `_MARKDOWN_JSON_PATTERN`）
- Test: `agent_service/tests/test_tutoring_agent.py`

- [ ] **Step 1: 写失败测试（复现真实泄露样例）**

在 `agent_service/tests/test_tutoring_agent.py` 末尾追加：

```python
def test_parse_tutoring_model_response_strips_fenced_json_with_nested_code_fence() -> None:
    # 真实泄露形态：散文前缀 + ```json 围栏，且 model_text 内部嵌 ```c 代码块（含花括号）
    model_output = (
        "根据策略要求，我为用户讲解指针。\n\n```json\n"
        "{\"model_text\": \"指针是核心概念。\\n\\n```c\\nint main() {int a=10; int *p=&a; return 0;}\\n```\\n完。\", "
        "\"knowledge_points\": [\"指针\", \"解引用\"], "
        "\"suggestion\": \"练习指针作为函数参数。\", "
        "\"diagram\": \"flowchart TD\\n A-->B\"}\n```"
    )

    parsed = parse_tutoring_model_response(model_output)

    assert "```json" not in (parsed.model_text or "")
    assert "\"model_text\"" not in (parsed.model_text or "")
    assert parsed.model_text.startswith("指针是核心概念")
    assert "```c" in parsed.model_text  # 内层代码围栏应保留
    assert parsed.knowledge_point_names == ["指针", "解引用"]
    assert parsed.suggestion_text == "练习指针作为函数参数。"
    assert parsed.diagram == "flowchart TD\n A-->B"
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd /home/yezisama/workspace/workflow/EDUagent/agent_service && uv run pytest tests/test_tutoring_agent.py::test_parse_tutoring_model_response_strips_fenced_json_with_nested_code_fence -v`
Expected: FAIL——当前非贪婪正则被内层 ```c 截断，`model_text` 仍含整段围栏 JSON。

- [ ] **Step 3: 实现最小改动**

(a) 删除 `agent_service/agents/tutoring.py` 顶部不再使用的正则常量：

```python
_MARKDOWN_JSON_PATTERN = re.compile(r"```(?:json)?\s*\n?(.*?)```", re.DOTALL | re.IGNORECASE)
```

（保留 `_AGENT_RESULT_PATTERN` 与 `import re`、`import json`。）

(b) 把整个 `_try_parse_markdown_json_output` 函数替换为下面三个函数（用括号配平替代非贪婪正则）：

```python
def _try_parse_markdown_json_output(model_output: str) -> TutoringModelResponse | None:
    """从含 Markdown 围栏/散文的输出里提取结构化 JSON，避免泄露到前端正文。

    用括号配平定位首个"含已知字段且能解析"的 JSON object；扫描时跳过字符串字面量内的
    括号与转义，因此 model_text 内嵌的 ```c 代码块或花括号不会截断解析。
    """
    for payload in _iter_json_objects(model_output):
        if not any(
            key in payload for key in ("model_text", "knowledge_points", "suggestion", "diagram")
        ):
            continue
        model_text = payload.get("model_text")
        clean_text = (
            model_text.strip()
            if isinstance(model_text, str) and model_text.strip()
            else None
        )
        return _build_response_from_payload(clean_text, payload)
    return None


def _iter_json_objects(text: str):
    """惰性产出文本中按括号配平、且能 json.loads 成功的 JSON object（dict）。"""
    i = 0
    n = len(text)
    while i < n:
        start = text.find("{", i)
        if start == -1:
            return
        end = _scan_balanced_object_end(text, start)
        if end is None:
            i = start + 1
            continue
        try:
            parsed = json.loads(text[start : end + 1])
        except json.JSONDecodeError:
            parsed = None
        if isinstance(parsed, dict):
            yield parsed
        i = end + 1


def _scan_balanced_object_end(text: str, start: int) -> int | None:
    """从 start 处 '{' 起做括号配平，返回匹配 '}' 的索引；跳过字符串内括号与转义；未配平返回 None。"""
    depth = 0
    in_str = False
    esc = False
    for i in range(start, len(text)):
        ch = text[i]
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return i
    return None
```

- [ ] **Step 4: 运行测试确认通过**

Run: `cd /home/yezisama/workspace/workflow/EDUagent/agent_service && uv run pytest tests/test_tutoring_agent.py -v`
Expected: PASS（新回归用例 + 全部原有解析用例，包括纯 JSON、`<agent_result>`、无效 JSON 兜底）。

- [ ] **Step 5: 提交**

```bash
cd /home/yezisama/workspace/workflow/EDUagent
git add agent_service/agents/tutoring.py agent_service/tests/test_tutoring_agent.py
git commit -m "tutoring: 兜底解析改用括号配平，修复嵌套代码围栏导致的JSON泄露"
```

---

## Task 8: 删除系统提示词中的"只输出 JSON"指令

**Files:**
- Modify: `agent_service/prompts/tutoring.py:5-15`
- Test: `agent_service/tests/test_tutoring_prompts.py`

- [ ] **Step 1: 写失败测试**

在 `agent_service/tests/test_tutoring_prompts.py` 末尾追加：

```python
def test_react_system_prompt_drops_raw_json_instruction() -> None:
    from agent_service.prompts.tutoring import TUTOR_REACT_SYSTEM_PROMPT

    # 不再要求模型直接吐 JSON / markdown 代码块（structured_model 由 generate_response 工具负责）
    assert "JSON 格式输出" not in TUTOR_REACT_SYSTEM_PROMPT
    assert "只输出 JSON" not in TUTOR_REACT_SYSTEM_PROMPT
    assert "markdown 代码块" not in TUTOR_REACT_SYSTEM_PROMPT
    # 仍保留字段语义与教学指引
    assert "knowledge_points" in TUTOR_REACT_SYSTEM_PROMPT
    assert "model_text" in TUTOR_REACT_SYSTEM_PROMPT
    assert "suggestion" in TUTOR_REACT_SYSTEM_PROMPT
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd /home/yezisama/workspace/workflow/EDUagent/agent_service && uv run pytest tests/test_tutoring_prompts.py::test_react_system_prompt_drops_raw_json_instruction -v`
Expected: FAIL——当前 prompt 含"请以 JSON 格式输出…只输出 JSON，不要加 markdown 代码块"。

- [ ] **Step 3: 实现最小改动**

把 `agent_service/prompts/tutoring.py` 中的 `TUTOR_REACT_SYSTEM_PROMPT` 赋值整体替换为：

```python
TUTOR_REACT_SYSTEM_PROMPT = (
    "你是 EDUagent 的智能辅导 Agent，基于 ReActAgent 推理循环。"
    "回答必须贴合用户画像、课程范围和检索上下文，优先引导理解。"
    "如果提供了图谱节点，knowledge_points 应优先从这些节点名称中选择；"
    "回答应围绕最相关节点展开，不要机械覆盖所有节点。"
    "需要课程知识时调用 retrieve_course_knowledge 工具检索后再作答。"
    "完成时，把面向学生的讲解放入 model_text，本轮知识点放入 knowledge_points，"
    "下一步学习建议放入 suggestion；涉及数据结构操作或复杂逻辑流程时，"
    "diagram 给出 Mermaid 语法代码，否则留空。"
)
```

说明：保留了 `model_text` / `knowledge_points` / `suggestion` / `diagram` 字段语义（供模型调用 generate_response 时填对位置），但移除了"直接输出 JSON / markdown 代码块"的诱导性指令——结构化输出由 AgentScope 的 generate_response 工具按 schema 强制完成。

- [ ] **Step 4: 运行测试确认通过**

Run: `cd /home/yezisama/workspace/workflow/EDUagent/agent_service && uv run pytest tests/test_tutoring_prompts.py tests/test_tutoring_react.py -v`
Expected: PASS（含 `test_tutoring_react.py::test_tutor_react_system_prompt_contains_tutoring_conventions`，它要求 prompt 仍含 model_text/knowledge_points/suggestion）。

- [ ] **Step 5: 提交**

```bash
cd /home/yezisama/workspace/workflow/EDUagent
git add agent_service/prompts/tutoring.py agent_service/tests/test_tutoring_prompts.py
git commit -m "tutoring: 删除系统提示词中诱导原始JSON输出的指令"
```

---

## Task 9: 前端共享 util chatContent.js（括号配平剥离围栏 JSON）

**Files:**
- Create: `frontend/src/utils/chatContent.js`
- Verify: 一次性 Node ESM 脚本 + `npm run lint`

- [ ] **Step 1: 创建工具模块**

创建 `frontend/src/utils/chatContent.js`，内容如下：

```javascript
// 聊天正文展示工具：把模型可能产出的结构化输出（纯 JSON / 散文 + ```json 围栏 / 对象）
// 归一化为面向学生的纯文本，避免 JSON 块泄露到正文。
// 提取用括号配平而非非贪婪正则，因此 model_text 内嵌的 ```c 代码块/花括号不会截断解析。

function scanBalancedObjectEnd(text, start) {
  let depth = 0;
  let inStr = false;
  let esc = false;
  for (let i = start; i < text.length; i++) {
    const ch = text[i];
    if (inStr) {
      if (esc) esc = false;
      else if (ch === '\\') esc = true;
      else if (ch === '"') inStr = false;
      continue;
    }
    if (ch === '"') inStr = true;
    else if (ch === '{') depth++;
    else if (ch === '}') {
      depth--;
      if (depth === 0) return i;
    }
  }
  return -1;
}

// 扫描文本，返回首个"能解析且含 model_text/content"的 JSON object；找不到返回 null。
function extractEnvelope(text) {
  let i = 0;
  while (i < text.length) {
    const start = text.indexOf('{', i);
    if (start === -1) return null;
    const end = scanBalancedObjectEnd(text, start);
    if (end === -1) {
      i = start + 1;
      continue;
    }
    try {
      const obj = JSON.parse(text.slice(start, end + 1));
      if (obj && typeof obj === 'object' && (obj.model_text || obj.content)) {
        return obj;
      }
    } catch {
      // 此处不是合法 JSON，继续向后扫描
    }
    i = end + 1;
  }
  return null;
}

export function extractModelText(value) {
  if (value === null || value === undefined) return '';
  if (typeof value === 'number' || typeof value === 'boolean') return String(value);
  if (typeof value === 'object') {
    return value.model_text
      || value.code
      || value.name
      || value.title
      || value.knowledge_point
      || value.label
      || value.content
      || value.id
      || JSON.stringify(value);
  }
  if (typeof value !== 'string') return String(value);

  const str = value;

  // 1. 整串就是 JSON object
  const trimmed = str.trim();
  if (trimmed.startsWith('{')) {
    try {
      const obj = JSON.parse(trimmed);
      if (obj && typeof obj === 'object' && (obj.model_text || obj.content)) {
        return obj.model_text || obj.content;
      }
    } catch {
      // 非完整 JSON（如流式中途），继续走下面的逻辑
    }
  }

  // 2. 散文 + ```json 围栏：括号配平提取后取 model_text（正确跳过嵌套 ```c）
  const envelope = extractEnvelope(str);
  if (envelope) {
    return envelope.model_text || envelope.content;
  }

  // 3. 普通文本
  return str;
}
```

- [ ] **Step 2: 写一次性验证脚本并运行（预期先通过——这是纯逻辑模块，无需先失败）**

创建临时文件 `frontend/tmp_verify_chat.mjs`：

```javascript
import { extractModelText } from './src/utils/chatContent.js';

const cases = [];
function check(name, cond) {
  cases.push([name, !!cond]);
}

// 真实泄露形态：散文 + ```json 围栏 + 内嵌 ```c（含花括号）
const leak =
  '根据策略要求，讲解指针。\n\n```json\n' +
  '{"model_text": "指针是核心概念。\\n```c\\nint main(){int a=10; return 0;}\\n```\\n完。", ' +
  '"knowledge_points": ["指针"]}\n```';
const out1 = extractModelText(leak);
check('no ```json leak', !out1.includes('```json'));
check('no model_text key leak', !out1.includes('"model_text"'));
check('starts with content', out1.startsWith('指针是核心概念'));
check('inner ```c preserved', out1.includes('```c'));

// 纯 JSON
const out2 = extractModelText('{"model_text":"纯JSON正文","knowledge_points":[]}');
check('pure json -> model_text', out2 === '纯JSON正文');

// 普通文本原样返回
const out3 = extractModelText('这只是一句普通回答。');
check('plain text passthrough', out3 === '这只是一句普通回答。');

// 对象输入
const out4 = extractModelText({ model_text: '对象正文' });
check('object -> model_text', out4 === '对象正文');

let ok = true;
for (const [name, pass] of cases) {
  console.log((pass ? 'PASS ' : 'FAIL ') + name);
  if (!pass) ok = false;
}
process.exit(ok ? 0 : 1);
```

Run: `cd /home/yezisama/workspace/workflow/EDUagent/frontend && node tmp_verify_chat.mjs`
Expected: 全部 `PASS`，退出码 0。若某条 FAIL，回到 Step 1 修正 `chatContent.js` 再跑。

- [ ] **Step 3: 删除临时验证脚本并跑 lint**

```bash
cd /home/yezisama/workspace/workflow/EDUagent/frontend
rm tmp_verify_chat.mjs
npm run lint
```
Expected: lint 通过（无新增报错）。

- [ ] **Step 4: 提交**

```bash
cd /home/yezisama/workspace/workflow/EDUagent
git add frontend/src/utils/chatContent.js
git commit -m "前端: 新增 chatContent 共享工具，括号配平剥离围栏JSON"
```

---

## Task 10: 接入共享 util，移除两处重复的 getDisplayText

**Files:**
- Modify: `frontend/src/components/chat/ChatMessage.jsx`（删除本地 `getDisplayText`，import 共享 util）
- Modify: `frontend/src/pages/AIChat.jsx`（删除本地 `getDisplayText`，import 共享 util）
- Verify: `npm run lint && npm run build`

- [ ] **Step 1: 改 ChatMessage.jsx**

(a) 在 `frontend/src/components/chat/ChatMessage.jsx` 顶部 import 区，`import ToolCallCard from './ToolCallCard';` 之后新增：

```javascript
import { extractModelText } from '../../utils/chatContent';
```

(b) 删除文件中本地定义的 `getDisplayText` 函数（即 `const getDisplayText = (value) => { ... };` 整段，原 167-187 行）。

(c) 把组件内两处调用从 `getDisplayText(...)` 改为 `extractModelText(...)`：
- `{getDisplayText(message.content)}` → `{extractModelText(message.content)}`
- `<MermaidDiagram content={getDisplayText(diag)} />` → `<MermaidDiagram content={extractModelText(diag)} />`

- [ ] **Step 2: 改 AIChat.jsx**

(a) 在 `frontend/src/pages/AIChat.jsx` 顶部 import 区，`import ChatEmptyState from '../components/chat/ChatEmptyState';` 之后新增：

```javascript
import { extractModelText } from '../utils/chatContent';
```

(b) 删除文件中本地定义的 `getDisplayText` 函数（原 10-37 行整段）。

(c) 把其余引用改为共享函数：
- `normalizeTextList` 内 `.map(getDisplayText)` → `.map(extractModelText)`
- `normalizeMessage` 内 `displayContent = getDisplayText(message?.content);` → `displayContent = extractModelText(message?.content);`

- [ ] **Step 3: 跑 lint 确认无 `getDisplayText` 残留与无未用变量**

```bash
cd /home/yezisama/workspace/workflow/EDUagent/frontend
grep -rn "getDisplayText" src/ ; echo "grep exit: $?"
npm run lint
```
Expected: `grep` 无输出（exit 1，表示已无残留）；`npm run lint` 通过。

- [ ] **Step 4: 构建确认通过**

Run: `cd /home/yezisama/workspace/workflow/EDUagent/frontend && npm run build`
Expected: 构建成功，无报错。

- [ ] **Step 5: 提交**

```bash
cd /home/yezisama/workspace/workflow/EDUagent
git add frontend/src/components/chat/ChatMessage.jsx frontend/src/pages/AIChat.jsx
git commit -m "前端: ChatMessage/AIChat 改用共享 extractModelText 防御层"
```

---

## 收尾验证（全量回归）

- [ ] **后端全量测试**

Run: `cd /home/yezisama/workspace/workflow/EDUagent/agent_service && uv run pytest -q`
Expected: 全绿。若有失败，定位到对应 Task 修复后重跑。

- [ ] **前端检查**

Run: `cd /home/yezisama/workspace/workflow/EDUagent/frontend && npm run lint && npm run build`
Expected: 均通过。

- [ ] **更新施工记录**

按 `frontend/AGENTS.md` 要求，在 `frontend/WORKFLOW.md` 追加本次施工记录（完成状态/修改文件/测试结果/契约是否漂移/commit/剩余风险/下一步），并在功能状态变化时同步 `frontend/docs/feature-ledger.md`。提交：

```bash
cd /home/yezisama/workspace/workflow/EDUagent
git add frontend/WORKFLOW.md frontend/docs/feature-ledger.md
git commit -m "docs: 记录 tutoring ReAct 结构化输出修复施工"
```

---

## 自审记录（Spec 覆盖核对）

- 1.1 JSON 泄露：Task 3（schema）+ Task 5（structured_model 读 metadata）+ Task 6（dict 分支）从源头消灭；Task 7（兜底括号配平）+ Task 9/10（前端防御）兜旧脏数据与偶发不合规。✓
- 1.2 超时/检索失效：Task 1 + Task 2（有界 timeout 落到 ReAct 主路径）；Task 6（修复误导 "succeeded" 日志）。✓
- 1.3 慢：Task 2（`stream=True`，更快 time-to-first-token 与状态反馈）；逐字流式正文不在范围（已确认）。✓
- 历史脏数据"仅前端防御"：Task 9/10，无 DB 迁移。✓
- 契约不变：全程未改 SSE 事件/OpenAPI/`../docs/`。✓
- 类型一致性：`generate()` 返回 `dict | str | None`，flow 用 `isinstance(model_output, dict)` 分支，`build_tutoring_response_from_metadata(dict)` 与 `parse_tutoring_model_response(str)` 签名匹配；前端统一 `extractModelText`。✓
