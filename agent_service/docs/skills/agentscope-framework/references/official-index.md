# AgentScope Official Documentation Index

This file tracks official AgentScope documentation coverage for EDUagent development. It intentionally does not mirror official documentation content.

## Source Priority

1. Official documentation index: https://docs.agentscope.io/llms.txt
2. Official AgentScope website: https://agentscope.io/
3. Official AgentScope GitHub repository: https://github.com/agentscope-ai/agentscope
4. Installed package introspection in this repo: `./.venv/bin/python`
5. Older docs only when a current page is missing: https://doc.agentscope.io/

## Current Official Coverage

The official `llms.txt` index currently exposes these documentation areas:

- Get Started
  - What is AgentScope: https://docs.agentscope.io/index.md
  - Quickstart: https://docs.agentscope.io/quickstart.md
- Basic Concepts
  - Agent: https://docs.agentscope.io/basic-concepts/agent.md
  - Context and Memory: https://docs.agentscope.io/basic-concepts/context-and-memory.md
  - Model: https://docs.agentscope.io/basic-concepts/model.md
  - Message: https://docs.agentscope.io/basic-concepts/msg.md
  - Tool: https://docs.agentscope.io/basic-concepts/tool.md
- Building Blocks
  - Agent: https://docs.agentscope.io/building-blocks/agent.md
  - Models: https://docs.agentscope.io/building-blocks/models.md
  - Memory: https://docs.agentscope.io/building-blocks/context-and-memory.md
  - RAG: https://docs.agentscope.io/building-blocks/rag.md
  - Tool Capabilities: https://docs.agentscope.io/building-blocks/tool-capabilities.md
  - Hooking Functions: https://docs.agentscope.io/building-blocks/hooking-functions.md
  - Orchestration: https://docs.agentscope.io/building-blocks/orchestration.md
- Deploy and Serve
  - Agent as Service: https://docs.agentscope.io/deploy-and-serve/agent-as-service.md
  - Sandbox and Tool: https://docs.agentscope.io/deploy-and-serve/sandbox-and-tool.md
- Observe and Evaluate
  - Observability: https://docs.agentscope.io/observe-and-evaluate/observability.md
  - Evaluation: https://docs.agentscope.io/observe-and-evaluate/evaluation.md
- Tune Agent
  - Overview: https://docs.agentscope.io/tune-agent/tune-your-first-agent.md
  - Model Selection: https://docs.agentscope.io/tune-agent/model-selection-tuning.md
  - Prompt Tuning: https://docs.agentscope.io/tune-agent/prompt-tuning.md
  - Reinforcement Learning: https://docs.agentscope.io/tune-agent/model-weights-tuning.md
  - Multi-Agent Tuning: https://docs.agentscope.io/tune-agent/tune-multi-agents.md
- Tutorials
  - Personal Research Assistant: https://docs.agentscope.io/tutorial/tutorial_research_agent.md
  - Multi-Agent Customer Support System: https://docs.agentscope.io/tutorial/tutorial_sales_agent.md
- Out-of-box Agents
  - Alias: https://docs.agentscope.io/out-of-box-agents/alias.md
  - Browser-use Agent: https://docs.agentscope.io/out-of-box-agents/browser-use.md
  - Deep Research: https://docs.agentscope.io/out-of-box-agents/deep-research.md
  - Finance Analysis: https://docs.agentscope.io/out-of-box-agents/alias-finance.md
  - Data Science: https://docs.agentscope.io/out-of-box-agents/data-science.md
  - DataJuicer Agent: https://docs.agentscope.io/out-of-box-agents/datajuicer-agent.md
  - EvoTraders: https://docs.agentscope.io/out-of-box-agents/evo-trader.md
- Other
  - FAQ: https://docs.agentscope.io/others/faq.md
  - OpenAPI spec: https://docs.agentscope.io/api-reference/openapi.json
  - Blog: https://agentscope.io/blogs/

## Coverage Status For This Skill

- Fully indexed at navigation level: all official areas above.
- Project-applied details included: concepts, models/embedding, RAG, memory, ReActAgent, tools/MCP, orchestration, observability/evaluation, deploy/serve.
- Not expanded into implementation guidance by default: out-of-box agents, tuning, and tutorials. Read official pages directly when those features become relevant.

## Verification Rule

Before implementing AgentScope-specific behavior, verify the relevant API by either:

```bash
./.venv/bin/python - <<'PY'
import inspect
from agentscope.rag import TextReader, PDFReader, SimpleKnowledge, QdrantStore
print(inspect.signature(TextReader))
print(inspect.signature(PDFReader))
print(inspect.signature(SimpleKnowledge))
print(inspect.signature(QdrantStore))
PY
```

or by checking the current official page. Do not rely on stale examples from older `doc.agentscope.io` pages unless the current docs omit that topic.
