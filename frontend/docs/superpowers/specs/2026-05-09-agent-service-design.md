# Agent Service Design Specification

## 1. Overview
This document outlines the architecture and data flow for the `agent_service` (Port 8002) of the EduAgent project. The service is responsible for intelligent tutoring, memory compression, assessment evaluation, and asynchronous resource generation, utilizing AgentScope for multi-agent orchestration and Qdrant for vector retrieval.

## 2. Architecture & Directory Structure
The service uses **AgentScope Native** architecture. FastAPI acts as a thin HTTP wrapper to receive requests, parse them using Pydantic, and trigger the corresponding AgentScope pipelines.

### Directory Structure (`agent_service/`)
```text
agent_service/
├── main.py                 # FastAPI entrypoint (Port 8002)
├── config.py               # Environment variables (Spark API keys, Qdrant host)
├── api/
│   └── routes.py           # FastAPI endpoints (/chat, /memory/compress, etc.)
├── agents/
│   ├── chat_agent.py       # Single Agent with Tool Calling (SSE)
│   ├── memory_agent.py     # Pipeline for compression & fact extraction
│   ├── assess_agent.py     # Pipeline for quiz evaluation
│   └── resource_agents.py  # Manager & Worker agents for parallel generation
├── tools/
│   ├── qdrant_tools.py     # RAG retrieval (course_knowledge, user_memory)
│   ├── code_sandbox.py     # Tool for running code
│   └── diagram_tool.py     # Tool for generating Mermaid diagrams
├── memory/
│   └── custom_memory.py    # AgentScope memory extensions for Qdrant integration
├── prompts/
│   └── templates.py        # Centralized prompt templates
└── models/
    └── schemas.py          # Pydantic models matching the API spec
```

## 3. Data Flow & API Mapping

### 3.1 Chat & Tutoring (`POST /agent/v1/chat`)
- **Flow:** FastAPI receives request -> `qdrant_tools` fetches user facts & course chunks -> `chat_agent` (Tool-calling Agent) is invoked.
- **Output:** AgentScope's streaming capabilities are piped directly into a FastAPI `StreamingResponse` (SSE).

### 3.2 Memory Compression (`POST /agent/v1/memory/compress`)
- **Trigger:** Threshold reached (e.g., 10 turns).
- **Flow:** AgentScope Sequential Pipeline.
  - **Node 1 (Summarizer Agent):** Merges old summary with new dialogues.
  - **Node 2 (Extractor Agent):** Extracts new unstructured facts.
  - **Node 3 (Tool Node):** Embeds and saves facts to Qdrant.
- **Output:** Synchronous JSON response.

### 3.3 Assessment & Evaluation (`POST /agent/v1/assessment/evaluate`)
- **Flow:** AgentScope Mixed Pipeline (Python logic + LLM).
  - **Node 1 (Python):** Calculates objective score.
  - **Node 2 (Evaluator Agent):** Analyzes wrong answers and writes feedback.
  - **Node 3 (Recommender Agent):** Determines next learning nodes based on static graph logic.
- **Output:** Synchronous JSON response.

### 3.4 Resource Generation (`POST /agent/v1/resource/generate`)
- **Flow:** AgentScope Manager-Worker (Parallel) Pipeline.
- **Trigger:** FastAPI returns 200 OK immediately and spawns a background task.
- **Execution:** Manager Agent receives the request and dispatches tasks to specific Worker Agents (e.g., MindmapWorker, QuizWorker) in parallel.
- **Callback:** Manager aggregates results and sends a POST request to the Backend Webhook.

## 4. Qdrant Memory & Tools

### 4.1 Strict Separation of Concerns
- **SQL (Backend):** Absolute source of truth for structured data (User Profile, Mastery, Knowledge Coordinates).
- **Qdrant (Agent):** Only stores unstructured, semantic facts and course materials.

### 4.2 Qdrant Collections
- **Collection 1: `user_memory`**
  - Stores *only* unstructured behavioral facts extracted from conversations (e.g., "User prefers visual explanations for pointers").
  - **Metadata:** `user_id`, `timestamp`, `fact_type`.
  - **Retrieval:** Enhanced filtering. Must filter by `user_id` and use `timestamp` to prioritize recent facts. The Agent will be instructed to *always* trust the SQL `user_profile` over old Qdrant facts if there's a conflict regarding mastery.
- **Collection 2: `course_knowledge`**
  - Stores course materials.
  - **Metadata:** `chapter`, `difficulty`, `knowledge_point_id`.
  - **Retrieval:** Hybrid search with strict metadata filtering (e.g., only search within the current `knowledge_point_id` if specified).

### 4.3 Tools & Prompts
- **Tools:** `search_knowledge`, `draw_diagram`, `run_code`.
- **Prompts:** Centralized in `prompts/templates.py`. The prompt will explicitly state: "Use the provided `user_profile` as the absolute truth for the user's current knowledge state. Use `recalled_facts` only for behavioral context."
