# AgentScope Concepts

Official pages:

- Agent: https://docs.agentscope.io/basic-concepts/agent.md
- Message: https://docs.agentscope.io/basic-concepts/msg.md
- Model: https://docs.agentscope.io/basic-concepts/model.md
- Context and Memory: https://docs.agentscope.io/basic-concepts/context-and-memory.md
- Tool: https://docs.agentscope.io/basic-concepts/tool.md

## Core Mapping

AgentScope's core concepts should be mapped carefully to EDUagent:

- `Agent`: an entity that receives external information, reasons, and acts. It exposes `reply` for responding and `observe` for state updates without response generation.
- `Msg`: the message exchange object among users, agents, and tools. It includes sender name, role, content, timestamp, metadata, and can carry multimodal or tool-use blocks.
- `Model`: provider-specific chat, embedding, realtime, and TTS model abstractions behind unified async interfaces.
- `Memory`: short-term session state and long-term cross-session memory. Storage is separate from algorithmic behavior.
- `Tool`: native Python functions, MCP servers, and AgentScope skills wrapped through `Toolkit`.

## EDUagent Interpretation

- Backend request payloads are not AgentScope `Msg` objects. Convert them at the agent boundary, not in `api/`.
- SSE event schemas are not AgentScope response schemas. Convert AgentScope output into existing `schemas/` events before streaming.
- Course material RAG is not user long-term memory. Keep these stores separate.
- Do not leak AgentScope classes into public API schemas unless the OpenAPI contract explicitly changes.

## Development Rule

When introducing AgentScope into an existing endpoint:

1. Keep the public request/response schema unchanged.
2. Add a small adapter in `agents/` or `memory/`.
3. Preserve rule-based fallback behavior.
4. Add tests for unavailable model, unavailable Qdrant, and malformed AgentScope output.
