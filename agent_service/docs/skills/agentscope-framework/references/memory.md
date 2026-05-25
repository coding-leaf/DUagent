# Memory

Official pages:

- Basic context and memory: https://docs.agentscope.io/basic-concepts/context-and-memory.md
- Building-block memory: https://docs.agentscope.io/building-blocks/context-and-memory.md

## AgentScope Memory Layers

AgentScope separates memory into:

- Short-term memory: session/conversation state, typically `MemoryBase` implementations.
- Long-term memory: cross-session persistence and retrieval, typically `LongTermMemoryBase` implementations.

Short-term memory stores `Msg` objects and can use marks such as `hint`, `summary`, or `tool_result`.

Documented short-term memory implementations include:

- `InMemoryMemory`
- `AsyncSQLAlchemyMemory`
- `RedisMemory`

Documented long-term memory implementations include:

- `Mem0LongTermMemory`
- `ReMePersonalLongTermMemory`

`ReActAgent` long-term memory modes:

- `agent_control`: agent uses memory tools autonomously.
- `static_control`: developer calls memory APIs explicitly.
- `both`: enables both patterns.

## EDUagent Current State

Current `memory/compress` behavior:

- builds a summary
- extracts learning facts
- writes facts to `user_memory_v1_1024` best-effort
- does not write raw Backend SQL
- does not store full raw conversations as primary vector content

## Recommendation

Keep the current explicit memory compression path for now. It is predictable and fits the existing API contract.

Consider AgentScope long-term memory later when:

- tutoring needs autonomous retrieval of personal preferences
- profile generation needs cross-session user traits
- model tool-calling reliability has been validated

When adopting AgentScope long-term memory, prefer `static_control` first for API-backed services. Use `agent_control` only after prompts and tool behavior are tested.

## Separation Rule

- Course knowledge: facts about course materials, stored in `course_knowledge_v1_1024`.
- User memory: facts about a learner, stored in `user_memory_v1_1024`.
- Short-term memory: per-session conversation state, not a replacement for either vector collection.

## Candidate Memory Fact Types

Future extracted facts may include:

- `blind_spot`
- `mastered_point`
- `cognitive_preference`
- `common_error`
- `learning_goal`
- `pace_preference`

Do not add new public fact types unless they are allowed by current schemas or the OpenAPI contract is updated.
