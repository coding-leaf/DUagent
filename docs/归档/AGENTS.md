# Repository Guidelines

## Project Structure & Module Organization
This repository contains multiple product areas, but this branch only develops `agent_service/`. Keep changes scoped there unless explicitly requested. Core files live under `agent_service/main.py` (FastAPI entry), `agent_service/api/` (versioned routes), `agent_service/core/` (settings and Qdrant wiring), and `agent_service/agents/` (agent logic). Reference specs and OpenAPI files live in `agent_service/docs/`. Treat `agent_service/qdrant_data/` as runtime data, not hand-edited source.

## Build, Test, and Development Commands
Install dependencies with `pip install -r agent_service/requirements.txt`.
Run the service locally with `cd agent_service && uvicorn main:app --reload --host 0.0.0.0 --port 8002`.
You can also use `cd agent_service && python main.py` for the same FastAPI app.
Verify the service with `curl http://127.0.0.1:8002/agent/v1/health`.

## Coding Style & Naming Conventions
Use Python with 4-space indentation, type hints on new public functions, and concise docstrings only where behavior is not obvious. Prefer `snake_case` for modules, functions, and variables; `PascalCase` for classes; `UPPER_SNAKE_CASE` for settings constants. Keep routers thin and move reusable logic into `agents/` or `core/`. Follow the existing versioned API layout under `api/v1/`.

## Testing Guidelines
There is no committed test suite yet. Add new tests under `agent_service/tests/` and use `pytest` with files named `test_<module>.py`. For API work, cover both JSON responses and SSE behavior where applicable. When adding nontrivial agent logic, include at least one focused unit test plus one route-level test.

## Commit & Pull Request Guidelines
Follow the existing Conventional Commit style seen in history: `feat(agent): ...`, `fix(agent): ...`, `docs(api): ...`, `chore: ...`. Keep commit scopes specific to the module you changed. PRs should state the affected endpoint or subsystem, summarize behavior changes, list verification steps, and include sample request/response payloads for API changes.

## Architecture & Boundary Notes
`agent_service` is the AI-facing FastAPI service on port `8002`. Backend owns SQL, auth, and orchestration; this service owns AI workflows, Qdrant retrieval, SSE streaming, and internal agent APIs. Do not modify `frontend/`, `backend/`, or `dataset/` from this branch unless the task explicitly expands scope.
