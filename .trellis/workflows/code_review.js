// DUagent Comprehensive Codebase Review Workflow
// Model: DeepSeek V4.1 Flash via WorkBuddy
const model = "magpie/workbuddy/deepseek-v4.1-flash";

const tasks = [
  {
    key: "backend_review",
    agent: "reviewer",
    model: model,
    output: "reports/review-backend.md",
    task: `[DUagent Codebase Audit - Backend Module]
Review Target: backend/ (FastAPI monolithic business backend, ~15k lines)
Key Subdirectories:
- backend/app/api/v1/ (all REST routers)
- backend/app/services/ (business logic implementations)
- backend/app/models/ & backend/app/db/ (SQLAlchemy 2.0 ORM models and async session management)
- backend/app/exceptions/ & backend/app/core/ (DomainException, error handlers, config, auth)

Core Principles:
1. Code is Truth: Base all findings on real code in backend/app/, not hypothetical ideals.
2. Tech Stack: FastAPI + SQLAlchemy 2.0 async + Pydantic v2. Do not recommend switching frameworks.
3. KISS & Spaghetti Code Detection:
   - Identify over-engineering, unnecessary abstraction layers, and bloated wrappers.
   - Detect fat routers containing direct DB queries or heavy business logic instead of delegating to services.
   - Audit async SQLAlchemy usage: look for N+1 queries, missing eager loading (selectinload/joinedload), improper session commits/rollbacks, and blocking synchronous calls.
   - Check exception handling: are exceptions properly structured under DomainException or swallowed with bare except clauses?
   - Identify dead code, unused endpoints, duplicate functions, or orphaned logic.

Output Structure required in reports/review-backend.md:
# Backend (FastAPI) Codebase Review Report
## 1. Executive Summary & Architecture Health
## 2. P0 Critical Issues (Bugs, data corruption risk, severe async blocking)
## 3. P1 High Tech-Debt & Spaghetti Code (N+1 queries, fat routers, bloated services, poor exception handling)
## 4. P2 KISS Simplification Opportunities (Redundant abstractions, dead code, code duplication)
## 5. Actionable Backend Refactoring Roadmap (Prioritized step-by-step plan)`
  },
  {
    key: "agent_service_review",
    agent: "reviewer",
    model: model,
    output: "reports/review-agent-service-v2.md",
    task: `[DUagent Codebase Audit - Agent Service v2 Module]
Review Target: agent_service_v2/ (AgentScope 2.x AI orchestration microservice, ~8.2k lines)
Key Subdirectories:
- agent_service_v2/src/agent_service_v2/agents/ (AgentScope agent definitions and system prompts)
- agent_service_v2/src/agent_service_v2/runtime/ (agent loop, execution runtime, context)
- agent_service_v2/src/agent_service_v2/tools/ (agent tools, MCP clients, web search)
- agent_service_v2/src/agent_service_v2/api/ (SSE streaming endpoints, workbench, knowledge, evaluation)
- agent_service_v2/src/agent_service_v2/session/, workspaces/, artifacts/ (state & artifact persistence)
- agent_service_v2/src/agent_service_v2/safety/ & observability/ (policy filtering, logging middleware)

Core Principles:
1. Code is Truth: Inspect actual agent code under agent_service_v2/src/agent_service_v2/.
2. Tech Stack: uv + Python 3.12+ + AgentScope 2.x + FastAPI + SSE Starlette + Pydantic v2.
3. KISS & Spaghetti Code Detection:
   - Inspect agent collaboration patterns: are agent prompts, message routing, or team loops overly convoluted?
   - Audit SSE streaming reliability: client disconnect handling, error propagation over SSE, memory leaks in long streams.
   - Audit tool error handling: do tools catch internal exceptions gracefully, or can a tool crash break the whole agent run?
   - Check persistence hygiene: are workspace files, temp files, and session states cleaned up or leaking?
   - Verify service boundaries: verify that agent_service_v2 remains decoupled from backend MySQL and only communicates via API/SSE.

Output Structure required in reports/review-agent-service-v2.md:
# Agent Service v2 Codebase Review Report
## 1. Executive Summary & Architecture Health
## 2. P0 Critical Issues (Runtime crashes, SSE disconnect failures, tool unhandled exceptions)
## 3. P1 High Tech-Debt & Spaghetti Code (Over-complicated agent topologies, memory/workspace leaks, prompt fragility)
## 4. P2 KISS Simplification Opportunities (Unnecessary middleware, redundant abstractions, prompt consolidation)
## 5. Actionable Agent Service Refactoring Roadmap (Prioritized step-by-step plan)`
  },
  {
    key: "frontend_review",
    agent: "reviewer",
    model: model,
    output: "reports/review-frontend.md",
    task: `[DUagent Codebase Audit - Frontend Module]
Review Target: frontend/ (React 19 SPA frontend, ~18.3k lines)
Key Subdirectories:
- frontend/src/pages/ (route views)
- frontend/src/components/ (UI components)
- frontend/src/hooks/ & frontend/src/context/ (custom hooks, SWR fetchers, context state)
- frontend/src/services/ & frontend/src/api/ (Axios client, API endpoints)
- frontend/src/App.jsx, main.jsx

Core Principles:
1. Code is Truth: Inspect actual JSX components and hooks in frontend/src/.
2. Tech Stack: React 19 + Vite + Tailwind CSS v4 + SWR + Axios + pure JSX/JavaScript. (Do NOT recommend TypeScript migration).
3. KISS & Spaghetti Code Detection:
   - Identify "God components" (>300-500 lines) mixing layout, business logic, complex state, and direct API calls.
   - Audit state management: is server data duplicated into Context or local state? Are SWR keys centralized and caching effective?
   - Audit API layer: are network calls consistently routed through services/, or are there ad-hoc Axios calls in components?
   - Error handling & UX: are API errors caught and displayed via Sonner toast/notifications, or silently failing?
   - Dead code: unused components, stale assets, redundant CSS classes, commented-out JSX.

Output Structure required in reports/review-frontend.md:
# Frontend (React 19) Codebase Review Report
## 1. Executive Summary & Architecture Health
## 2. P0 Critical Issues (Render crashes, infinite SWR revalidation loops, broken routing)
## 3. P1 High Tech-Debt & Spaghetti Code (God components, tangled state, inconsistent API calls, poor error handling)
## 4. P2 KISS Simplification Opportunities (Component decomposition, dead code removal, Tailwind cleanup)
## 5. Actionable Frontend Refactoring Roadmap (Prioritized step-by-step plan)`
  },
  {
    key: "integration_review",
    agent: "reviewer",
    model: model,
    output: "reports/review-integration.md",
    task: `[DUagent Codebase Audit - System Integration & Governance]
Review Target: Cross-service contracts, configuration, deployment, and repository governance
Key Files:
- docs/00-overview/README.md (architecture overview)
- bootstrap_ubuntu.sh, deploy_prod.sh, deploy/ directory
- API contract alignment between frontend/src/services/ and backend/app/api/v1/
- API contract alignment between backend/app/api/v1/internal_* and agent_service_v2/src/agent_service_v2/api/
- backend/requirements.txt vs agent_service_v2/pyproject.toml vs frontend/package.json

Core Principles:
1. Code is Truth: Compare actual route definitions and payload structures across frontend, backend, and agent_service_v2.
2. KISS & Monorepo Governance:
   - Identify contract mismatches: are endpoint URLs, request parameters, or response fields out of sync between services?
   - Check environment configuration: .env variables, port consistency, CORS configurations, security tokens.
   - Audit deployment and script hygiene: obsolete bash scripts, hardcoded paths, unmaintained config files.
   - Monorepo boundaries: are types/schemas duplicated? Can we clean up dead files or retired folders (like agent_service/)?

Output Structure required in reports/review-integration.md:
# System Integration & Architecture Governance Review Report
## 1. Executive Summary & Cross-Service Consistency
## 2. P0 Critical Issues (Contract discrepancies breaking features, security/token leaks, port/CORS breakage)
## 3. P1 High Tech-Debt (Schema duplication, fragile deployment scripts, environment variable mismatches)
## 4. P2 KISS Simplification Opportunities (Retired directory cleanups, script consolidation)
## 5. Master Monorepo Refactoring Sequence (End-to-end refactoring strategy)`
  }
];

const results = await runs.all(tasks);

return results.map(r => ({
  key: r.key,
  ok: r.ok,
  runId: r.runId,
  outputReference: r.outputReference || (r.structuredOutput && r.structuredOutput.outputReference)
}));
