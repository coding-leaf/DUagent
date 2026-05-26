---
name: agentscope-framework
description: Use when developing EDUagent agent_service features with AgentScope, including ReActAgent orchestration, Msg/model/formatter usage, RAG over PDF/Markdown folders, embeddings, Qdrant-backed knowledge stores, long-term memory, tools, MCP, hooks, observability, evaluation, deployment, and project integration boundaries.
---

# AgentScope Framework Skill

Use this skill before implementing or reviewing AgentScope-related changes in `agent_service`.

This skill is a navigation layer, not a mirror of the official documentation. Treat AgentScope official docs as the source of truth and this directory as the project-specific guide for applying those docs to EDUagent.

## Official Sources

Start with [references/official-index.md](references/official-index.md) when you need to confirm documentation coverage or locate the correct official page.

Primary official entry points:

- AgentScope home: https://agentscope.io/
- Documentation index: https://docs.agentscope.io/llms.txt
- Python package in this repo: `agentscope==1.0.20` in `uv.lock`

## Read By Task

- **Core concepts**: read [references/concepts.md](references/concepts.md) before mapping `Msg`, agent, model, memory, or tool concepts.
- **Models and embeddings**: read [references/models-and-embedding.md](references/models-and-embedding.md) before adding or replacing chat / embedding providers.
- **RAG / local files / Qdrant**: read [references/rag.md](references/rag.md) before building PDF, Markdown, text, image, or Qdrant knowledge features.
- **Memory**: read [references/memory.md](references/memory.md) before changing short-term memory, compression, or long-term user memory.
- **ReActAgent and agent behavior**: read [references/react-agent.md](references/react-agent.md) before introducing ReActAgent, structured output, planning, hooks, state, A2A, or realtime behavior.
- **Tools and MCP**: read [references/tools-and-mcp.md](references/tools-and-mcp.md) before adding tool calls, MCP servers, or AgentScope skills.
- **Orchestration**: read [references/orchestration.md](references/orchestration.md) before adding multi-agent flows or routing.
- **Observability and evaluation**: read [references/observability-evaluation.md](references/observability-evaluation.md) before adding traces, studio integration, or agent evaluations.
- **Deployment**: read [references/deploy-and-serve.md](references/deploy-and-serve.md) before serving AgentScope agents or sandboxed tools.
- **EDUagent integration**: always read [references/eduagent-integration.md](references/eduagent-integration.md) before modifying this repo based on AgentScope.
- **AGENTS.md suggestion**: see [references/agents-md-recommendation.md](references/agents-md-recommendation.md) for a proposed project instruction update.

## Project Rules

- Do not invent AgentScope APIs. If a class, method, parameter, or package extra is not confirmed in official docs or local installed package introspection, stop and verify.
- Do not copy official docs wholesale into this repo. Keep links, summaries, project decisions, and small code sketches only.
- Keep `api/` thin. AgentScope orchestration belongs in `agents/`; RAG and vector-store adapters belong in `memory/`; tools belong in `tools/`; prompts belong in `prompts/`; config belongs in `core/`.
- Do not replace stable rule-based endpoints with ReActAgent in one step. Add an adapter boundary first, keep fallback behavior, and test request-path regressions.
- Keep course knowledge and user memory separate. Course documents belong to `course_knowledge`; personal learning facts belong to `user_memory`.
- Prefer Generic RAG for deterministic tutoring retrieval first. Consider Agentic RAG only after model/tool reliability is proven.

## First Implementation Target

For the next AgentScope-backed project feature, prefer a local knowledge ingestion CLI:

```bash
./.venv/bin/python -m agent_service.tools.ingest_knowledge ./knowledge_base/course_001
```

Target flow:

```text
folder PDF/MD/TXT -> AgentScope Reader -> Document chunks -> embedding -> Qdrant course_knowledge_v1_1024 -> tutoring retrieval
```

Avoid building a frontend for knowledge ingestion unless a future product requirement explicitly needs it.
