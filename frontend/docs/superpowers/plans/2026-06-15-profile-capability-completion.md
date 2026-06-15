# Profile Capability Completion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Complete the `/profile` and `/learning-effects` profile capabilities by extending the effective contract, fixing real KG/profile rule calculations, and aligning frontend displays with backend states.

**Architecture:** Keep the backend as the source of truth for profile and KG-derived rule data. Frontend pages translate structured states into user-facing Chinese labels and statistics without mock data or hardcoded learning evidence.

**Tech Stack:** FastAPI, SQLAlchemy async, MySQL-compatible SQL, pytest, React, Vite, ESLint.

---

### Task 1: KG Node Progress State Fixes

**Files:**
- Modify: `../backend/app/services/knowledge_progress.py`
- Modify: `../backend/tests/test_knowledge_progress.py`

- [ ] Add failing tests for latest low-score weakness and `unstarted` summary status.
- [ ] Implement latest-score aggregation from answer/session chronology.
- [ ] Keep node states stable: `mastered`, `weak`, `learning`, `pending_practice`, `unstarted`.
- [ ] Run focused pytest.

### Task 2: Profile Rule Completion

**Files:**
- Modify: `../backend/app/services/profile_rules.py`
- Modify: `../backend/tests/test_profile_rules.py`

- [ ] Add failing tests for real streak days, seven-day practice count, and stable learning habit labels.
- [ ] Implement pure helpers for streak and practice count derivation.
- [ ] Integrate helpers into `compute_profile_fields`.
- [ ] Run focused pytest.

### Task 3: Profile API Shape Stabilization

**Files:**
- Modify: `../backend/app/api/v1/profile.py`

- [ ] Preserve extended profile contract: `learning_habits`, `knowledge_progress_summary`, `kg_quiz_activity`.
- [ ] Ensure default profile and refreshed profile return consistent object shapes.
- [ ] Verify dialogue supplement remains separate from behavior-derived modal preference.

### Task 4: Frontend Profile Display

**Files:**
- Modify: `src/pages/StudentProfile.jsx`

- [ ] Map all backend node states to labels, icons, and colors.
- [ ] Render learning habit labels with deterministic fallbacks.
- [ ] Keep modal preference behavior-based; personal supplement remains in profile dimensions.

### Task 5: Frontend Learning Effects Display

**Files:**
- Modify: `src/pages/LearningEffects.jsx`

- [ ] Count practiced nodes using backend states and attempt counts.
- [ ] Update mastery distribution to recognize `mastered`, `weak`, `learning`, `pending_practice`, and `unstarted`.
- [ ] Keep node table evidence text aligned with backend rows.

### Task 6: Contract Documentation

**Files:**
- Modify: `../docs/10-client-api/API_前端接口规范.md`
- Modify: `../docs/10-client-api/Client-API.openapi.json`
- Modify: `WORKFLOW.md`

- [ ] Document extended profile dimensions and sources.
- [ ] Document expanded knowledge coordinate states.
- [ ] Record implementation and verification in `WORKFLOW.md`.

### Task 7: Verification

**Commands:**
- `PYTHONDONTWRITEBYTECODE=1 TEST_DATABASE_URL=sqlite+aiosqlite:////tmp/profile_capability_completion.db ../.venv/bin/python -m pytest tests/test_profile_rules.py tests/test_knowledge_progress.py -q -p no:cacheprovider`
- `npm run lint`
- `npm run build`

- [ ] Run focused backend tests.
- [ ] Run frontend lint and build.
- [ ] Commit the completed batch with a concise Chinese message.
