# EDUagent Integration Guide

This file maps AgentScope official patterns to the current `agent_service` architecture.

## Current Architecture Boundary

- `api/`: FastAPI routes, request/response adaptation, SSE, async task protocol.
- `schemas/`: Pydantic entities aligned with OpenAPI.
- `agents/`: Agent/workflow orchestration and rule-based fallbacks.
- `memory/`: Qdrant read/write, retrieval, fact extraction, RAG adapters.
- `tools/`: diagrams, code execution, external tools.
- `prompts/`: prompts and templates.
- `core/`: config and infrastructure initialization.

## AgentScope Placement

- `ReActAgent` construction and orchestration belongs in `agents/`.
- Reader / Knowledge / Qdrant RAG adapters belong in `memory/`.
- CLI ingestion commands belong in `tools/`.
- Provider config belongs in `core/`.
- Prompt templates belong in `prompts/`.
- AgentScope `Msg` and output conversion should not leak into public `schemas/`.

## Recommended Next Feature

Implement folder-based course knowledge ingestion:

```text
knowledge_base/course_id/*.pdf|*.md|*.txt
  -> AgentScope Reader
  -> Document chunks
  -> embedding
  -> Qdrant course_knowledge_v1_1024
  -> existing tutoring retrieval
```

Why this first:

- The tutoring RAG retrieval path already exists.
- The missing piece is course knowledge ingestion.
- It does not require frontend work.
- It improves real tutoring quality more than additional abstraction.

## Integration Decisions

- Use CLI first, not startup auto-scan.
- Keep ingestion out of live request paths.
- Keep repeated imports idempotent through stable point IDs.
- Keep collection names and dimensions driven by settings.
- Keep rule-based tutoring fallback.

## Avoid For Now

- Full replacement of `tutoring/chat` with `ReActAgent`.
- Agentic RAG tool use as the default first implementation.
- Long-term memory framework migration before fact types are stable.
- Multiple AgentScope serving layers.
- Mirroring official docs into this repository.

## Review Checklist

Before merging AgentScope-related code:

- Does the change respect `api` / `agents` / `memory` / `tools` boundaries?
- Is the public OpenAPI contract unchanged or intentionally updated?
- Does the live request path degrade gracefully if model/Qdrant/AgentScope optional extras fail?
- Are optional dependencies imported lazily or declared clearly?
- Are tests using fakes instead of real model calls?
- Is `WORKFLOW.md` updated with status and test results?
