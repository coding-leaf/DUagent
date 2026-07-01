# AIChat Native EDU v2 Events Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the AIChat `chunk/done` compatibility layer with native EDU v2 SSE events while keeping Backend as a thin transport proxy and envelope wrapper.

**Architecture:** Agent Service v2 remains the only AgentScope semantic adapter: AgentScope events are mapped to EDU v2 events in `agent_service_v2/runtime/protocol_adapter.py`. Backend proxies `/agent/v2/workbench/chat`, adds Backend-owned `conversation_id` and `message_id`, accumulates `text_delta` for persistence, and forwards event names/payloads unchanged. Frontend parses SSE JSON and handles EDU v2 events directly in `ChatContext`.

**Tech Stack:** AgentScope 2.0.3, FastAPI/SSE, React 19, SWR, Vitest, Pytest.

---

## File Structure

- Modify `backend/app/services/tutoring_stream_adapter.py`
  - Responsibility: transport proxy, minimal envelope wrapping, text accumulation for persistence.
- Modify `backend/tests/test_tutoring_stream_adapter.py`
  - Responsibility: prove Backend no longer converts `text_delta/workflow_completed/workflow_failed` to `chunk/done` and no longer filters workbench events.
- Modify `agent_service_v2/src/agent_service_v2/runtime/protocol_adapter.py`
  - Responsibility: safely ignore extra AgentScope delta events so they do not become `workflow_failed`.
- Modify `agent_service_v2/tests/test_protocol_adapter.py`
  - Responsibility: prove extra AgentScope streaming delta events are normal non-failure events.
- Modify `frontend/src/api/services/chat.js`
  - Responsibility: parse SSE and pass complete EDU v2 events to consumers.
- Modify `frontend/src/context/ChatContext.jsx`
  - Responsibility: reduce EDU v2 events into message state, tool call state, source refs, and workspace artifacts.
- Modify `frontend/src/context/ChatContext.test.jsx`
  - Responsibility: prove `text_delta`, `workflow_completed`, `workflow_failed`, tool events, and artifact events update state correctly.
- Update `WorkLine.md`
  - Responsibility: record implementation, verification commands, interface drift.

---

### Task 1: Backend Native EDU v2 Transport Proxy

**Files:**
- Modify: `backend/tests/test_tutoring_stream_adapter.py`
- Modify: `backend/app/services/tutoring_stream_adapter.py`

- [ ] **Step 1: Replace Backend stream adapter tests with native EDU v2 expectations**

In `backend/tests/test_tutoring_stream_adapter.py`, replace the old conversion-specific tests with these tests. Keep imports unchanged.

```python
@pytest.mark.asyncio
async def test_stream_adapter_forwards_v2_events_with_backend_envelope():
    calls = []

    async def source(path, payload):
        calls.append((path, payload))
        yield b'data: {"type":"workflow_started","run_id":"run-1","conversation_id":"agent-conv","seq":1,"timestamp":"t1","agent":"workbench","payload":{"reply_id":"r1"}}\n\n'
        yield b'data: {"type":"text_delta","run_id":"run-1","conversation_id":"agent-conv","seq":2,"timestamp":"t2","agent":"workbench","payload":{"delta":"hello"}}\n\n'
        yield b'data: {"type":"workflow_completed","run_id":"run-1","conversation_id":"agent-conv","seq":3,"timestamp":"t3","agent":"workbench","payload":{"reply_id":"r1"}}\n\n'

    persisted = AsyncMock()
    adapter = TutoringStreamAdapter(stream_sse=source, persist_result=persisted)
    events = [
        event
        async for event in adapter.stream(
            payload={"user_id": "u1", "scope": "course", "course_id": "course-1", "conversation_id": "conv-1", "message": "x"},
            conversation_id="conv-1",
            assistant_message_id="msg-1",
        )
    ]

    decoded = [json.loads(event["data"]) for event in events]
    assert calls[0][0] == "/agent/v2/workbench/chat"
    assert calls[0][1]["context"]["message"] == "x"
    assert [item["type"] for item in decoded] == [
        "workflow_started",
        "text_delta",
        "workflow_completed",
    ]
    assert decoded[1]["payload"] == {"delta": "hello"}
    assert decoded[1]["conversation_id"] == "conv-1"
    assert decoded[1]["message_id"] == "msg-1"
    assert decoded[1]["run_id"] == "run-1"
    persisted.assert_awaited_once_with("msg-1", "conv-1", "hello", [], [])


@pytest.mark.asyncio
async def test_stream_adapter_does_not_filter_tool_source_or_artifact_events():
    async def source(path, payload):
        yield b'data: {"type":"tool_started","run_id":"run-1","seq":1,"timestamp":"t1","agent":"workbench","payload":{"tool_call_id":"tool-1","tool_name":"TaskCreate"}}\n\n'
        yield b'data: {"type":"tool_completed","run_id":"run-1","seq":2,"timestamp":"t2","agent":"workbench","payload":{"tool_call_id":"tool-1","state":"success"}}\n\n'
        yield b'data: {"type":"source_refs","run_id":"run-1","seq":3,"timestamp":"t3","agent":"workbench","payload":{"sources":[{"title":"Array"}]}}\n\n'
        yield b'data: {"type":"artifact_created","run_id":"run-1","seq":4,"timestamp":"t4","agent":"workbench","payload":{"artifact":{"id":"a1","type":"Markdown","props":{"content":"# Plan"}}}}\n\n'

    persisted = AsyncMock()
    adapter = TutoringStreamAdapter(stream_sse=source, persist_result=persisted)
    events = [
        event
        async for event in adapter.stream(
            payload={"message": "x"},
            conversation_id="conv-1",
            assistant_message_id="msg-1",
        )
    ]

    decoded = [json.loads(event["data"]) for event in events]
    assert [item["type"] for item in decoded] == [
        "tool_started",
        "tool_completed",
        "source_refs",
        "artifact_created",
    ]
    assert decoded[0]["payload"]["tool_name"] == "TaskCreate"
    assert decoded[3]["payload"]["artifact"]["type"] == "Markdown"
    persisted.assert_awaited_once_with("msg-1", "conv-1", "", [], [])


@pytest.mark.asyncio
async def test_stream_adapter_emits_workflow_failed_on_agent_service_error():
    async def source(path, payload):
        if False:
            yield b""
        raise AgentServiceError("offline", status_code=503)

    persisted = AsyncMock()
    adapter = TutoringStreamAdapter(stream_sse=source, persist_result=persisted)
    events = [
        event
        async for event in adapter.stream(
            payload={"message": "x"},
            conversation_id="conv-1",
            assistant_message_id="msg-1",
        )
    ]

    decoded = [json.loads(event["data"]) for event in events]
    assert decoded == [
        {
            "type": "workflow_failed",
            "run_id": None,
            "conversation_id": "conv-1",
            "message_id": "msg-1",
            "seq": None,
            "timestamp": decoded[0]["timestamp"],
            "agent": "backend_proxy",
            "payload": {
                "reason": "agent_service_unavailable",
                "message": "Agent 服务暂时不可用",
            },
        }
    ]
    persisted.assert_awaited_once_with("msg-1", "conv-1", "", [], [])
```

- [ ] **Step 2: Run Backend tests and confirm they fail for old compatibility behavior**

Run:

```bash
cd backend && ../.venv/bin/python -m pytest tests/test_tutoring_stream_adapter.py -q
```

Expected: fails because current code still outputs `chunk/done` and filters v2 workbench events.

- [ ] **Step 3: Implement Backend transport proxy behavior**

In `backend/app/services/tutoring_stream_adapter.py`, change `_adapt_data` to preserve event names and payloads. Replace the existing `_adapt_data` method with:

```python
    @staticmethod
    def _adapt_data(data_str: str, state: StreamState) -> str | None:
        try:
            parsed = json.loads(data_str)
        except json.JSONDecodeError:
            return data_str

        event_type = parsed.get("type", "")
        payload = parsed.get("payload") if isinstance(parsed.get("payload"), dict) else {}

        if event_type == "text_delta":
            state.chunks.append(payload.get("delta", ""))
        elif event_type in {"workflow_completed", "workflow_failed"}:
            state.done_sent = True

        parsed["conversation_id"] = state.conversation_id
        parsed["message_id"] = state.assistant_message_id
        return json.dumps(parsed, ensure_ascii=False)
```

Replace the `except AgentServiceError` yielded event with:

```python
                yield {
                    "event": "message",
                    "data": json.dumps(
                        {
                            "type": "workflow_failed",
                            "run_id": None,
                            "conversation_id": conversation_id,
                            "message_id": assistant_message_id,
                            "seq": None,
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                            "agent": "backend_proxy",
                            "payload": {
                                "reason": "agent_service_unavailable",
                                "message": "Agent 服务暂时不可用",
                            },
                        },
                        ensure_ascii=False,
                    ),
                }
```

- [ ] **Step 4: Run Backend stream adapter tests**

Run:

```bash
cd backend && ../.venv/bin/python -m pytest tests/test_tutoring_stream_adapter.py -q
```

Expected: all tests in `test_tutoring_stream_adapter.py` pass.

- [ ] **Step 5: Run Backend syntax check**

Run:

```bash
cd backend && ../.venv/bin/python -m py_compile app/services/tutoring_stream_adapter.py
```

Expected: command exits with code 0 and no output.

- [ ] **Step 6: Commit Backend proxy change**

Run:

```bash
git add backend/app/services/tutoring_stream_adapter.py backend/tests/test_tutoring_stream_adapter.py
git commit -m "feat(backend): 透传AIChat EDU v2事件"
```

---

### Task 2: Agent v2 Delta Event Safety

**Files:**
- Modify: `agent_service_v2/tests/test_protocol_adapter.py`
- Modify: `agent_service_v2/src/agent_service_v2/runtime/protocol_adapter.py`

- [ ] **Step 1: Add failing test for additional AgentScope delta events**

In `agent_service_v2/tests/test_protocol_adapter.py`, extend the event imports:

```python
    DataBlockDeltaEvent,
    ThinkingBlockDeltaEvent,
    ToolCallDeltaEvent,
    ToolResultDataDeltaEvent,
    ToolResultTextDeltaEvent,
```

Add this test:

```python
def test_protocol_adapter_ignores_additional_streaming_delta_events():
    adapter = EDUProtocolAdapter(
        run_id="run-1",
        conversation_id="conv-1",
        agent="workbench",
    )

    events = [
        ToolCallDeltaEvent(reply_id="reply-1", tool_call_id="tool-1", delta='{"kind"'),
        ToolResultTextDeltaEvent(reply_id="reply-1", tool_call_id="tool-1", delta="partial result"),
        ToolResultDataDeltaEvent(
            reply_id="reply-1",
            tool_call_id="tool-1",
            media_type="application/json",
            data='{"ok":true}',
        ),
        DataBlockDeltaEvent(
            reply_id="reply-1",
            block_id="data-1",
            data='{"artifact":true}',
            media_type="application/json",
        ),
        ThinkingBlockDeltaEvent(reply_id="reply-1", block_id="think-1", delta="internal"),
    ]

    assert [adapter.adapt(event) for event in events] == [
        None,
        None,
        None,
        None,
        None,
    ]
```

- [ ] **Step 2: Run Agent adapter test and confirm failure**

Run:

```bash
cd agent_service_v2 && ./.venv/bin/pytest tests/test_protocol_adapter.py -q
```

Expected: fails because these event classes currently become `workflow_failed`.

- [ ] **Step 3: Update protocol adapter imports and ignore list**

In `agent_service_v2/src/agent_service_v2/runtime/protocol_adapter.py`, add imports:

```python
    DataBlockDeltaEvent,
    ThinkingBlockDeltaEvent,
    ToolCallDeltaEvent,
    ToolResultDataDeltaEvent,
    ToolResultTextDeltaEvent,
```

Extend the `isinstance` ignore tuple:

```python
                DataBlockDeltaEvent,
                ThinkingBlockDeltaEvent,
                ToolCallDeltaEvent,
                ToolResultDataDeltaEvent,
                ToolResultTextDeltaEvent,
```

- [ ] **Step 4: Run Agent v2 tests**

Run:

```bash
cd agent_service_v2 && ./.venv/bin/pytest tests -q
```

Expected: all Agent v2 tests pass.

- [ ] **Step 5: Run Agent v2 syntax check**

Run:

```bash
cd agent_service_v2 && ./.venv/bin/python -m py_compile src/agent_service_v2/runtime/protocol_adapter.py
```

Expected: command exits with code 0 and no output.

- [ ] **Step 6: Commit Agent adapter change**

Run:

```bash
git add agent_service_v2/src/agent_service_v2/runtime/protocol_adapter.py agent_service_v2/tests/test_protocol_adapter.py
git commit -m "fix(agent-v2): 忽略正常增量事件"
```

---

### Task 3: Frontend Native EDU v2 Event Reducer

**Files:**
- Modify: `frontend/src/context/ChatContext.test.jsx`
- Modify: `frontend/src/api/services/chat.js`
- Modify: `frontend/src/context/ChatContext.jsx`

- [ ] **Step 1: Expand chat service mock in ChatContext tests**

In `frontend/src/context/ChatContext.test.jsx`, update the mocked `chatService` to include `streamChat`:

```javascript
const streamChatMock = vi.fn();

vi.mock('../api/services/chat', () => ({
  chatService: {
    getSessions: vi.fn().mockResolvedValue({
      code: 200,
      data: { conversations: [] }
    }),
    getHistory: vi.fn().mockResolvedValue({
      code: 200,
      data: { messages: [] }
    }),
    streamChat: (...args) => streamChatMock(...args)
  }
}));
```

- [ ] **Step 2: Add Frontend reducer tests**

In `frontend/src/context/ChatContext.test.jsx`, add this consumer:

```javascript
const StreamConsumer = () => {
  const { messages, workspaceArtifacts, sendMessage, isSending } = useChat();
  return (
    <div>
      <div data-testid="message-count">{messages.length}</div>
      <div data-testid="assistant-content">{messages.find(m => m.role === 'assistant')?.content || ''}</div>
      <div data-testid="assistant-loading">{String(messages.find(m => m.role === 'assistant')?.loading ?? false)}</div>
      <div data-testid="assistant-error">{String(messages.find(m => m.role === 'assistant')?.isError ?? false)}</div>
      <div data-testid="tool-status">{messages.find(m => m.role === 'assistant')?.toolCalls?.[0]?.status || ''}</div>
      <div data-testid="artifact-count">{workspaceArtifacts.length}</div>
      <div data-testid="sending">{String(isSending)}</div>
      <button data-testid="send" onClick={() => sendMessage('hello')}>Send</button>
    </div>
  );
};
```

Add this test:

```javascript
test('ChatProvider reduces native EDU v2 stream events', async () => {
  streamChatMock.mockImplementation((_payload, onMessage, onError) => {
    onMessage({
      type: 'workflow_started',
      run_id: 'run-1',
      conversation_id: 'conv-1',
      message_id: 'msg-1',
      payload: { reply_id: 'reply-1' }
    });
    onMessage({
      type: 'tool_started',
      run_id: 'run-1',
      conversation_id: 'conv-1',
      message_id: 'msg-1',
      payload: { tool_call_id: 'tool-1', tool_name: 'TaskCreate' }
    });
    onMessage({
      type: 'text_delta',
      run_id: 'run-1',
      conversation_id: 'conv-1',
      message_id: 'msg-1',
      payload: { delta: 'hello' }
    });
    onMessage({
      type: 'tool_completed',
      run_id: 'run-1',
      conversation_id: 'conv-1',
      message_id: 'msg-1',
      payload: { tool_call_id: 'tool-1', state: 'success' }
    });
    onMessage({
      type: 'artifact_created',
      run_id: 'run-1',
      conversation_id: 'conv-1',
      message_id: 'msg-1',
      payload: { artifact: { id: 'artifact-1', type: 'Markdown', props: { content: '# Plan' } } }
    });
    onMessage({
      type: 'workflow_completed',
      run_id: 'run-1',
      conversation_id: 'conv-1',
      message_id: 'msg-1',
      payload: { reply_id: 'reply-1' }
    });
    return vi.fn();
  });

  render(
    <CourseProvider>
      <ChatProvider>
        <StreamConsumer />
      </ChatProvider>
    </CourseProvider>
  );

  await act(async () => {
    screen.getByTestId('send').click();
  });

  expect(screen.getByTestId('assistant-content').textContent).toBe('hello');
  expect(screen.getByTestId('assistant-loading').textContent).toBe('false');
  expect(screen.getByTestId('tool-status').textContent).toBe('completed');
  expect(screen.getByTestId('artifact-count').textContent).toBe('1');
  expect(screen.getByTestId('sending').textContent).toBe('false');
});


test('ChatProvider handles workflow_failed as native EDU v2 error event', async () => {
  streamChatMock.mockImplementation((_payload, onMessage, onError) => {
    onMessage({
      type: 'workflow_failed',
      run_id: 'run-1',
      conversation_id: 'conv-1',
      message_id: 'msg-1',
      payload: { reason: 'model_not_configured', message: '模型未配置' }
    });
    return vi.fn();
  });

  render(
    <CourseProvider>
      <ChatProvider>
        <StreamConsumer />
      </ChatProvider>
    </CourseProvider>
  );

  await act(async () => {
    screen.getByTestId('send').click();
  });

  expect(screen.getByTestId('assistant-loading').textContent).toBe('false');
  expect(screen.getByTestId('assistant-error').textContent).toBe('true');
  expect(screen.getByTestId('assistant-content').textContent).toContain('模型未配置');
});
```

- [ ] **Step 3: Run Frontend ChatContext test and confirm failure**

Run:

```bash
cd frontend && npm run test:unit -- src/context/ChatContext.test.jsx
```

Expected: fails because `streamChat` still expects `onDone`, and `ChatContext` does not reduce EDU v2 event names.

- [ ] **Step 4: Simplify chatService stream parsing**

In `frontend/src/api/services/chat.js`, change `streamChat` signature to:

```javascript
  streamChat: (params, onMessage, onError) => {
```

In mock mode, emit EDU v2 events instead of `chunk/done`:

```javascript
          onMessage({
            type: 'text_delta',
            payload: { delta: chunk }
          });
```

Replace the old mock completion call with:

```javascript
          onMessage({
            type: 'workflow_completed',
            conversation_id: conversation_id || 'sess_mock_9527',
            message_id: dummyId,
            payload: { reply_id: dummyId }
          });
```

In the real SSE parser, replace the event-specific branch with:

```javascript
            const parsed = JSON.parse(dataStr);
            onMessage(parsed);
```

Remove all calls to `onDone`.

- [ ] **Step 5: Add EDU v2 reducer helpers in ChatContext**

In `frontend/src/context/ChatContext.jsx`, add these helpers near existing pure helper functions:

```javascript
const upsertToolCall = (toolCalls = [], update) => {
  const id = update.id;
  const existing = toolCalls.find(tc => tc.id === id);
  if (!existing) return [...toolCalls, update];
  return toolCalls.map(tc => tc.id === id ? { ...tc, ...update } : tc);
};

const normalizeArtifact = (event) => {
  const artifact = event.payload?.artifact;
  if (!artifact || !artifact.type) return null;
  return {
    id: artifact.id || `artifact-${crypto.randomUUID()}`,
    type: artifact.type,
    props: artifact.props || {},
    timestamp: event.timestamp || new Date().toISOString()
  };
};

const completionMessageId = (event) => event.message_id || event.payload?.message_id || `ai-${crypto.randomUUID()}`;
```

- [ ] **Step 6: Replace createStreamHandlers with EDU v2 event handling**

In `frontend/src/context/ChatContext.jsx`, update `createStreamHandlers` so `onMessage` handles completion and failure directly:

```javascript
  const createStreamHandlers = (targetId) => {
    const completeMessage = (event, failed = false) => {
      const finalMessageId = completionMessageId(event);
      lastMessageIdRef.current = finalMessageId;
      setMessages(prev => updateTargetMessage(prev, targetId, m => ({
        ...m,
        id: targetId === 'ai-placeholder' ? finalMessageId : m.id,
        content: failed
          ? `${m.content || ''}\n\n[生成失败: ${event.payload?.message || event.payload?.reason || 'agent_failed'}]`
          : m.content,
        loading: false,
        isError: failed || m.isError,
        toolCalls: completeRunningToolCalls(m.toolCalls),
      })));
      setIsSending(false);
      abortControllerRef.current = null;

      if (!activeSession && event.conversation_id) {
        setActiveSession(event.conversation_id);
        mutateSessions();
      }
    };

    return {
      onMessage: (event) => {
        if (event.type === 'artifact_created') {
          const artifact = normalizeArtifact(event);
          if (artifact) setWorkspaceArtifacts(prev => [...prev, artifact]);
        }

        if (event.type === 'workflow_completed') {
          completeMessage(event, false);
          return;
        }

        if (event.type === 'workflow_failed') {
          completeMessage(event, true);
          return;
        }

        setMessages(prev => updateTargetMessage(prev, targetId, m => {
          switch (event.type) {
            case 'workflow_started':
              return { ...m, runId: event.run_id || m.runId };
            case 'text_delta':
              return { ...m, content: m.content + (event.payload?.delta || '') };
            case 'tool_started':
              return {
                ...m,
                toolCalls: upsertToolCall(m.toolCalls, {
                  id: event.payload?.tool_call_id || `tool-${crypto.randomUUID()}`,
                  name: event.payload?.tool_name || '工具调用',
                  status: 'running',
                }),
              };
            case 'tool_completed':
              return {
                ...m,
                toolCalls: upsertToolCall(m.toolCalls, {
                  id: event.payload?.tool_call_id || 'unknown',
                  status: event.payload?.state === 'error' ? 'error' : 'completed',
                  outputSummary: event.payload?.summary,
                }),
              };
            case 'tool_failed':
              return {
                ...m,
                toolCalls: upsertToolCall(m.toolCalls, {
                  id: event.payload?.tool_call_id || 'unknown',
                  name: event.payload?.tool_name || '工具调用',
                  status: 'error',
                  outputSummary: event.payload?.reason || event.payload?.message,
                }),
              };
            case 'source_refs':
              return { ...m, sourceRefs: event.payload?.sources || [] };
            case 'critic_completed':
              return {
                ...m,
                reviewFlagged: event.payload?.passed === false,
                reviewReason: event.payload?.reason || m.reviewReason,
              };
            default:
              return m;
          }
        }));
      },
      onError: (err) => {
        console.error('Chat stream error:', err);
        completeMessage(
          {
            type: 'workflow_failed',
            payload: { message: err.message || '网络连接故障' },
          },
          true,
        );
      },
    };
  };
```

- [ ] **Step 7: Update startStream to call the new streamChat signature**

In `frontend/src/context/ChatContext.jsx`, replace the `chatService.streamChat` call with:

```javascript
    abortControllerRef.current = chatService.streamChat(
      { ...requestPayload, scope: 'course', course_id: activeCourseId, conversation_id: activeSession },
      handlers.onMessage,
      handlers.onError
    );
```

- [ ] **Step 8: Run Frontend ChatContext test**

Run:

```bash
cd frontend && npm run test:unit -- src/context/ChatContext.test.jsx
```

Expected: `ChatContext.test.jsx` passes.

- [ ] **Step 9: Run Frontend unit tests affected by chat UI**

Run:

```bash
cd frontend && npm run test:unit -- src/context/ChatContext.test.jsx src/components/workspace/AgentWorkspace.test.jsx src/components/chat/ToolCallCard.test.jsx
```

Expected: all selected tests pass.

- [ ] **Step 10: Commit Frontend native EDU v2 reducer**

Run:

```bash
git add frontend/src/api/services/chat.js frontend/src/context/ChatContext.jsx frontend/src/context/ChatContext.test.jsx
git commit -m "feat(frontend): 原生消费AIChat EDU v2事件"
```

---

### Task 4: Cross-Layer Verification and Documentation

**Files:**
- Modify: `WorkLine.md`

- [ ] **Step 1: Run Agent v2 full tests**

Run:

```bash
cd agent_service_v2 && ./.venv/bin/pytest tests -q
```

Expected: all Agent v2 tests pass.

- [ ] **Step 2: Run Backend relevant tests**

Run:

```bash
cd backend && ../.venv/bin/python -m pytest tests/test_tutoring_stream_adapter.py tests/test_tutoring_routes_refactored.py -q
```

Expected: all relevant Backend tests pass, with the existing route skip unchanged if present.

- [ ] **Step 3: Run Frontend lint and build**

Run:

```bash
cd frontend && npm run lint && npm run build
```

Expected: lint exits with code 0 and build exits with code 0.

- [ ] **Step 4: Check no old compatibility assertions remain in active AIChat code**

Run:

```bash
rg "type === 'chunk'|type === 'done'|onDone|text_delta.*chunk|workflow_completed.*done" frontend/src backend/app backend/tests frontend/src/context frontend/src/api
```

Expected: no active implementation references to old `chunk/done` conversion. Test names may include historical context only when asserting absence.

- [ ] **Step 5: Update WorkLine**

Append a new `WorkLine.md` entry:

```markdown
### 2026-07-01 — AIChat 原生消费 EDU v2 事件

**涉及文件：**
- `backend/app/services/tutoring_stream_adapter.py`
- `backend/tests/test_tutoring_stream_adapter.py`
- `agent_service_v2/src/agent_service_v2/runtime/protocol_adapter.py`
- `agent_service_v2/tests/test_protocol_adapter.py`
- `frontend/src/api/services/chat.js`
- `frontend/src/context/ChatContext.jsx`
- `frontend/src/context/ChatContext.test.jsx`
- `WorkLine.md`

**核心改动：**
移除 Backend 的 `chunk/done` 兼容转换。Backend 现在仅作为 `/agent/v2/workbench/chat` 的 transport proxy 和最小 envelope wrapper，原样透传 EDU v2 事件并补 `conversation_id/message_id`，继续累积 `text_delta` 用于 assistant message 持久化。前端 `chatService` 改为 SSE JSON 透传，`ChatContext` 原生处理 `workflow_started/text_delta/tool_started/tool_completed/tool_failed/source_refs/artifact_created/critic_completed/workflow_completed/workflow_failed`。Agent v2 adapter 对正常增量事件补安全忽略，避免误报失败。

**验证结果：**
- Agent pytest：`cd agent_service_v2 && ./.venv/bin/pytest tests -q`
- Backend pytest：`cd backend && ../.venv/bin/python -m pytest tests/test_tutoring_stream_adapter.py tests/test_tutoring_routes_refactored.py -q`
- Frontend tests：`cd frontend && npm run test:unit -- src/context/ChatContext.test.jsx src/components/workspace/AgentWorkspace.test.jsx src/components/chat/ToolCallCard.test.jsx`
- Frontend lint/build：`cd frontend && npm run lint && npm run build`

**接口漂移：**
Backend 对前端的 tutoring SSE event 类型从旧 `chunk/done` 切换为 EDU v2 原生事件。前端已同步适配；Backend 到 Agent Service 仍为 `/agent/v2/workbench/chat`。
```

- [ ] **Step 6: Commit final verification record**

Run:

```bash
git add WorkLine.md
git commit -m "docs: 记录AIChat原生EDU事件落地"
```

---

## Self-Review Checklist

- Spec coverage:
  - Backend transport proxy and envelope wrapper: Task 1.
  - Frontend native EDU v2 reducer: Task 3.
  - Agent v2 delta event safety: Task 2.
  - Testing and verification: Task 4.
- No old compatibility layer:
  - Task 1 removes `text_delta -> chunk`, `workflow_completed -> done`, and filtered tool/artifact/source events.
  - Task 3 removes `onDone` business semantics and old event branching in `chatService`.
- Boundary discipline:
  - Frontend still calls Backend `/api/v1/tutoring/chat`.
  - Backend still calls Agent Service v2 `/agent/v2/workbench/chat`.
  - Backend does not generate artifact or tool semantics.
