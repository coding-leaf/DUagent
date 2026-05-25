# Orchestration

Official page:

- https://docs.agentscope.io/building-blocks/orchestration.md

## Scope

AgentScope orchestration covers multi-agent collaboration and control flow patterns. Use it when a task genuinely needs multiple roles, routing, or staged agent execution.

## EDUagent Fit

Potential future orchestration candidates:

- tutoring agent + assessment agent + resource agent coordination
- evaluation agent using profile and learning path agents
- resource generation that searches, ranks, and explains material choices
- teacher-facing diagnosis workflows

Do not introduce multi-agent orchestration for a single deterministic transform.

## Initial Pattern

Prefer a coordinator function in `agents/` that calls small capability functions. Introduce AgentScope orchestration only when:

- multiple LLM-driven roles are needed
- role separation improves correctness
- intermediate outputs need validation
- tests can isolate each role

## Testing Rule

Multi-agent orchestration must include tests for:

- missing sub-agent output
- malformed sub-agent output
- timeout or cancellation
- fallback to simpler rule path
- stable conversion to public schemas
