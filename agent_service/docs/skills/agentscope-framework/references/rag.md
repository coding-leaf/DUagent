# RAG

Official page:

- https://docs.agentscope.io/building-blocks/rag.md

## AgentScope RAG Architecture

AgentScope RAG uses:

- `Reader`: reads source data and chunks it into `Document` objects.
- `Knowledge`: stores documents and implements retrieval.
- `Store`: integrates with the vector database.

Important built-ins:

- `TextReader`
- `PDFReader`
- `ImageReader`
- `SimpleKnowledge`
- `QdrantStore`
- `Document`

AgentScope docs state there is no universally optimal chunk size or splitting strategy. For PDF files and domain-specific materials, a custom reader can be appropriate.

## Integration Modes

AgentScope documents two RAG integration modes:

- `Generic`: pass `knowledge` into `ReActAgent`; it retrieves at the start of each reply. Simpler and works with weaker models, but always retrieves.
- `Agentic`: register `knowledge.retrieve_knowledge` as a tool; the model decides when and how to retrieve. More flexible but depends on strong tool-use behavior.

## EDUagent Recommendation

Use Generic-style deterministic retrieval first, but not necessarily by replacing tutoring with `ReActAgent`.

Preferred near-term flow:

```text
knowledge_base folder -> AgentScope Reader -> Document chunks -> Qdrant course_knowledge_v1_1024 -> existing tutoring retrieval -> prompt/chat -> SSE
```

This keeps existing API and SSE behavior stable while gaining AgentScope's document loading and chunking patterns.

## Local Folder Knowledge Base

Recommended folder convention:

```text
knowledge_base/
  course_001/
    meta.yaml
    chapter_01.md
    chapter_02.pdf
  course_002/
    intro.txt
```

Recommended metadata payload:

```json
{
  "course_id": "course_001",
  "course_name": "高等数学",
  "chapter": "第一章",
  "knowledge_point": "函数极限",
  "source_file": "chapter_01.md",
  "source_type": "course_material",
  "content": "...",
  "doc_id": "...",
  "chunk_id": 0,
  "total_chunks": 12
}
```

## Implementation Guidance

- Put ingestion code under `memory/` and CLI entry under `tools/`.
- Do not put file parsing, chunking, or Qdrant writes in `api/`.
- Use stable IDs derived from `course_id`, file path, content hash, and chunk index so repeated imports overwrite logically identical chunks.
- Keep course knowledge collection separate from user memory collection.
- For PDFs, expect imperfect parsing. Keep source file and chunk metadata to debug retrieval quality.

## Tests To Add

- Markdown/text reader path creates expected chunk metadata.
- PDF reader path is optional or mocked if PDF dependencies are unavailable.
- Re-importing same content uses stable point IDs.
- Qdrant write failure does not corrupt existing service behavior.
- Retrieval by `course_id` only returns matching course chunks.
