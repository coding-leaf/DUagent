# ReActAgent And Agent Behavior

Official pages:

- Basic agent concept: https://docs.agentscope.io/basic-concepts/agent.md
- Building-block agent guide: https://docs.agentscope.io/building-blocks/agent.md

## ReActAgent Capabilities

The official AgentScope agent guide describes `ReActAgent` as the primary built-in agent for:

- reasoning and acting
- tool use
- realtime steering
- memory compression
- parallel tool calls
- structured output
- MCP control
- long-term memory
- planning
- state/session management
- A2A agents
- realtime agents

## EDUagent Adoption Strategy

Do not replace all `agents/` modules with `ReActAgent` directly.

Recommended adoption sequence:

1. Keep existing rule-based agent functions as fallback.
2. Introduce endpoint-specific AgentScope adapter functions.
3. Convert Backend request models into AgentScope `Msg` internally.
4. Convert AgentScope output into existing Pydantic schemas and SSE events.
5. Add tests for degraded mode before enabling model/tool paths by default.

## Structured Output

AgentScope supports structured output at the agent/model layer. This matters because current tutoring structured metadata still uses a prompt tag convention:

```text
<agent_result>{...}</agent_result>
```

Future improvement path:

- Keep current parser until a verified AgentScope structured-output implementation is introduced.
- Add an internal result object as the stable project contract.
- Only then replace tag parsing with model/AgentScope structured output.

## Planning

AgentScope planning is useful for multi-step autonomous tasks. Do not use it for deterministic API transformations where a normal function is clearer.

Good candidates:

- multi-step resource generation
- complex assessment generation
- multi-agent tutoring workflows

Poor candidates:

- health checks
- schema conversion
- simple Qdrant upsert
- static rule-based score calculation

## State And Session

If AgentScope state/session management is adopted, it must not become a hidden second database for Backend-owned business state. Agent Service may keep agent runtime state, but the Backend remains owner of product data.
