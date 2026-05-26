# Models And Embedding

Official pages:

- Basic model concepts: https://docs.agentscope.io/basic-concepts/model.md
- Model details: https://docs.agentscope.io/building-blocks/models.md

## Model Layer

AgentScope provides unified async abstractions for:

- Chat models
- Embedding models
- TTS models
- Realtime models

Chat models use provider-specific formatters. For example, DashScope chat models pair with DashScope formatters. OpenAI-compatible models are supported through OpenAI model classes.

## Embedding Layer

Embedding models expose an async call interface that accepts text or content blocks and returns embedding vectors plus usage metadata.

Official provider families include:

- OpenAI text embeddings
- DashScope text embeddings
- DashScope multimodal embeddings
- Gemini text embeddings
- Ollama text embeddings

## EDUagent Current State

The project already has `core.ai` provider protocols and OpenAI-compatible HTTP providers for:

- embedding
- reranking
- chat

Do not remove those boundaries just to use AgentScope. Instead:

- For course knowledge ingestion, it is acceptable to use AgentScope embedding models if configured.
- For current tutoring runtime, keep `core.ai` as the provider-neutral boundary unless replacing it clearly reduces complexity.
- If AgentScope embedding is added, wrap it behind the existing `EmbeddingProvider` protocol or keep it isolated in the ingestion path.

## Recommended Choice

For the next local knowledge-base feature:

- Keep BGE-M3 `1024` dimension and `course_knowledge_v1_1024` unless the user explicitly changes embedding model.
- Use batching where possible.
- Use a cache if AgentScope's embedding cache fits the selected provider.
- Verify vector dimension before writing to Qdrant.

## Anti-Patterns

- Do not mix embeddings from different dimensions in the same collection.
- Do not hardcode provider API keys.
- Do not block FastAPI request paths on large document embedding jobs.
- Do not introduce AgentScope model objects into Pydantic response schemas.
