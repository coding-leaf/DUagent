# BRIEFING — 2026-06-21T13:50:35+08:00

## Mission
Refactor the EDUagent full-stack project functional modules in structured phases.

## 🔒 My Identity
- Archetype: teamwork_preview_orchestrator
- Roles: orchestrator, user_liaison, human_reporter, successor
- Working directory: /home/yezisama/workspace/workflow/EDUagent/.agents/orchestrator
- Original parent: sentinel
- Original parent conversation ID: a42f66a1-4e22-4784-aa56-7e289e6dd6e9

## 🔒 My Workflow
- **Pattern**: Project
- **Scope document**: /home/yezisama/workspace/workflow/EDUagent/PROJECT.md
1. **Decompose**: Decompose the project refactoring into 3 milestone modules corresponding to AI Chat & Tutoring, Resource Generation & Mounting, and Core Learning.
2. **Dispatch & Execute** (pick ONE):
   - **Delegate (sub-orchestrator)**: Spawn a sub-orchestrator for each module milestone.
3. **On failure** (in this order):
   - Retry: nudge stuck agent or re-send task
   - Replace: spawn fresh agent with partial progress
   - Skip: proceed without (only if non-critical)
   - Redistribute: split stuck agent's remaining work
   - Redesign: re-partition decomposition
   - Escalate: report to parent (sub-orchestrators only, last resort)
4. **Succession**: Self-succeed at 16 spawns, write handoff.md, spawn successor.
- **Work items**:
  1. AI Chat & Tutoring Module Refactoring [pending]
  2. Resource Generation & Mounting Module Refactoring [pending]
  3. Core Learning Module Refactoring [pending]
- **Current phase**: 1
- **Current focus**: Decomposition and planning

## 🔒 Key Constraints
- DISPATCH-ONLY orchestrator: MUST delegate ALL work to subagents. Do not write code or run commands directly.
- Strictly maintain existing behavior (demo integrity mode).
- Never reuse a subagent after it has delivered its handoff — always spawn fresh

## Current Parent
- Conversation ID: a42f66a1-4e22-4784-aa56-7e289e6dd6e9
- Updated: not yet

## Key Decisions Made
- Use Project Pattern to delegate each of the 3 modules to sub-orchestrators.

## Team Roster
| Agent | Type | Work Item | Status | Conv ID |
|-------|------|-----------|--------|---------|
| sub_orch_ai_chat | self | AI Chat & Tutoring Module Refactoring | completed | d67cefab-553f-4f69-9acf-01899594be20 |
| sub_orch_resource | self | Resource Generation & Mounting Module Refactoring | in-progress | e661892b-3a1c-4442-b648-d4f645404d06 |

## Succession Status
- Succession required: no
- Spawn count: 4 / 16
- Pending subagents: e661892b-3a1c-4442-b648-d4f645404d06
- Predecessor: de6d8910-4fb8-48da-9dd8-33bb9f982a02
- Successor: not yet spawned

## Active Timers
- Heartbeat cron: 08f70bb2-1c97-4dd5-88b7-91b7eb50b7be/task-35
- Safety timer: none
- On succession: kill all timers before spawning successor
- On context truncation: run `manage_task(Action="list")` — re-create if missing

## Artifact Index
- /home/yezisama/workspace/workflow/EDUagent/.agents/orchestrator/ORIGINAL_REQUEST.md — Verbatim record of user request
