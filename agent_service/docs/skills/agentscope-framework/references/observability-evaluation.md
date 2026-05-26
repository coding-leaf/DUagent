# Observability And Evaluation

Official pages:

- Observability: https://docs.agentscope.io/observe-and-evaluate/observability.md
- Evaluation: https://docs.agentscope.io/observe-and-evaluate/evaluation.md

## Why It Matters

Agent behavior failures are often not simple exceptions. They may be:

- wrong retrieval
- wrong tool choice
- malformed structured output
- unstable reasoning path
- excessive latency
- missing fallback

AgentScope observability and evaluation features should be considered when model-driven behavior becomes the primary path.

## EDUagent Current Baseline

The project currently uses:

- standard Python logging
- unit tests
- contract alignment tests
- rule-based fallbacks

This is appropriate for the current phase.

## Future Additions

Add observability when:

- AgentScope ReActAgent becomes active in request paths
- tool calls are model-controlled
- RAG quality needs debugging
- multi-agent orchestration is introduced

Add evaluations when:

- generated questions must meet quality criteria
- tutoring answers need rubric-based checks
- learning path outputs need stability checks

## Minimum Trace Fields

Even before full tracing, log:

- endpoint
- user/course identifiers where safe
- retrieval collection
- retrieved chunk count
- model provider configured/not configured
- fallback reason
- latency per stage

Avoid logging raw student messages if privacy requirements are unclear.
