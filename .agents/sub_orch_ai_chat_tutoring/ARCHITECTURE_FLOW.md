# AI Chat & Tutoring: Architecture & Flow Overview

This document describes the internal workflows and data flows of the refactored **AI Chat & Tutoring** and **Evaluation** modules in the EDUagent project.

---

## 1. Evaluation Module Workflow

The Evaluation module provides structured student performance evaluation tracking (knowledge node progress, chapter-level mastery, and resource usage breakdown). It separates concerns using a thin Router, a business Service layer, and a background task worker.

### 1.1 Process Flow Diagram
```
[User/Client]
      │  1. POST /api/v1/evaluation/refresh
      ▼
┌──────────────┐
│  API Router  │
└──────┬───────┘
       │  2. Instantiate & Delegate
       ▼
┌──────────────┐
│  Evaluation  │  3. verify_course_enrollment()
│   Service    ├─────────────────────────────────┐
└──────┬───────┘                                 ▼
       │                                  [CourseEnrollment]
       │  4. _get_processing_refresh_task() (Check if running)
       │  5. _assemble_evaluation_payload() (Sync DB context gathering)
       │  6. create_refresh_task() (Persist AsyncTask with status 'processing')
       │  7. Commit DB Transaction
       │  8. Return HTTP 202 Accepted (with task_id)
       │
       │  9. Dispatch asyncio.create_task()
       ▼
┌──────────────────────────────────────┐
│ run_evaluation_refresh_background()  │ (Isolated DB Session Context)
└──────────────┬───────────────────────┘
               │  10. Call Agent Client POST /agent/v1/evaluation/generate
               ▼
        ┌──────────────┐
        │Agent Service │  (Agent generates tables + LLM enriches summary)
        └──────┬───────┘
               │  11. Return JSON output
               ▼
┌──────────────────────────────────────┐
│ run_evaluation_refresh_background()  │
└──────────────┬───────────────────────┘
               │  12. Acquire named lock: evaluation_lock() (mysql/sqlite compatibility)
               │  13. Soft-delete old Evaluation records (is_deleted = True)
               │  14. Insert new Evaluation record (with mastery/progress tables)
               │  15. Update AsyncTask (status = 'completed')
               │  16. Commit Transaction & Release Lock
               ▼
           [Done/DB]
```

### 1.2 Data Flow Components
1. **Request Payload**: Contains `course_id`.
2. **Context Payload assembled for Agent**:
   - `student_profile`: student's major, grade, and guidance level.
   - `profile_context`: modal preferences, learning coordinates, cognitive blindspots, and intents.
   - `kg_context`: active knowledge graph nodes and student's progress mapping.
   - `learning_activity`: total activities, duration, active days, and timestamps.
   - `learning_progress`: chapter completion rates.
   - `quiz_results`: aggregated correctness scores and personalized quiz trends grouped by knowledge point.
   - `resource_usage`: resource counts grouped by types (video, code, document, etc.).
3. **Agent Output**:
   - `progress_table`: progress rows.
   - `mastery_table`: mastery level classification per knowledge point.
   - `resource_usage_table`: resource counts.
   - `summary_text`: enriched evaluation summary.
4. **Database State**: Saved under `Evaluation` (is_deleted=False) and `AsyncTask` status is updated.

---

## 2. AI Chat & Tutoring Module Workflow

The AI Chat & Tutoring module establishes a real-time conversational tutor using Server-Sent Events (SSE). The frontend utilizes SWR for session lists and resource recommendations, and local React states for high-frequency streaming.

### 2.1 Process Flow Diagram
```
[Frontend View: AIChat.jsx]
      │  1. Send message / trigger chat
      ▼
┌──────────────┐
│ ChatContext  ├───────────────────────────────────┐
└──────┬───────┘                                   ▼
       │  2. POST /api/v1/tutoring/chat     [useRecommendedResources]
       │                                           │ (SWR Cache-first)
       ▼                                           ▼
┌──────────────┐                                 Filter resources by 
│  API Router  │                                 active knowledge points
└──────┬───────┘
       │  3. Forward Payload via SSE
       ▼
┌──────────────┐
│  Tutoring    │  4. Retrieve memory/notes from Vector store
│  Agent (AS)  │  5. Run ReAct reasoning loop (tool execution)
└──────┬───────┘
       │  6. Stream SSE chunks (chunk, diagram, suggestion, done)
       ▼
┌──────────────┐
│Stream Adapter│ (Backend proxy - buffers splits, handles done event)
└──────┬───────┘
       │  7. Forward chunks to Frontend
       ▼
┌──────────────┐
│ ChatContext  │  8. Parse SSE chunks, update messages local state
└──────┬───────┘  9. On 'done' event, mutateSWR(sessions) to pull new sessions
       │
       ▼
[Display View] (Renders Markdown / Mermaid Diagrams / Suggested KPs / Tool Call Cards)
```

### 2.2 MVVM Modularity
- **Model**: Database entities (`TutoringSession`, `Message`, `Resource`, `CourseKnowledgeGraph`).
- **ViewModel**: 
  - `ChatContext.jsx` (handles conversation context, streaming connection state, SWR session list caching, and optimistic deletion updates).
  - `useRecommendedResources.js` (custom SWR hook that fetches course resources, extracts active knowledge points from assistant messages, and matches/filters the recommendations dynamically).
- **View**: 
  - `AIChat.jsx` layout.
  - `SidebarHistory.jsx` (displays history list).
  - `SidebarResources.jsx` (displays recommendations).
  - `ChatArea.jsx` (handles input and scroll actions).
  - `ChatMessage.jsx` (renders Markdown/Mermaid diagrams/Tool calls).
