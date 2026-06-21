# Original User Request

## 2026-06-20T20:12:08Z

Refactor the EDUagent full-stack project (frontend and backend) to clean up complex and redundant code, reorganizing the architecture by functional modules. Execute this in structured phases with mandatory automated code cleanup and quality review after each module, prioritizing functional correctness over strict documentation constraints.

Working directory: /home/yezisama/workspace/workflow/EDUagent
Integrity mode: demo (Strictly maintain existing behavior, no direct copying of external core logic)

## Requirements

### R1. Concrete Module Enumeration & Analysis
Instead of vague exploratory refactoring, explicitly analyze and target the following specific functional modules across the stack:
1. **AI Chat & Tutoring**: Frontend `AIChat`, Backend `tutoring` & `evaluation`, Agent `tutoring`
2. **Resource Generation & Mounting**: Frontend `ResourceDetail` & Catalogs, Backend `resources` & `catalogs`, Agent `resources`
3. **Core Learning**: Frontend `LearningPath` & `Quiz`, Backend `learning-path` & `learning-activities`, Agent `learning_path`
Begin by strictly clarifying the architectural pattern and data flow for a chosen module (e.g., ai-chat) before starting any code changes.

### R2. Boundary-Driven Testing Strategy
Before writing or running tests, first query and establish the test boundaries for the module. Identify equivalence classes (等价类) and edge cases to ensure comprehensive coverage. Only after defining these boundaries should you execute the automated tests to capture the behavioral baseline.

### R3. Automated Quality Review & Cleanup
After completing the functional refactoring of a module, automatically dispatch a dedicated subagent to conduct rigorous code cleanup, deduplication, and code quality review.

### R4. Tooling & Libraries
You may use pre-built libraries/frameworks and run external scripts to assist the refactoring process. However, do not directly copy open-source code for core business logic.

### R5. Proactive Skills Utilization
The subagent team must be aware of and proactively invoke the available `skills` in the environment (e.g., `systematic-debugging`, `test-driven-development`, `subagent-driven-development`) to systematically guide their reasoning and workflows.

## Acceptance Criteria

### Verification & Quality
- [ ] For every refactored module, an automated test suite (unit/integration) is executed before and after the changes, and it passes successfully.
- [ ] A dedicated code quality review agent has inspected the module and confirmed the elimination of complex/redundant code.
- [ ] The core functionality and user-facing behavior of the module remain strictly unchanged.

## Follow-up — 2026-06-20T20:18:18Z

The user has requested a new final deliverable: As you analyze and refactor each module (like ai-chat and resource generation), you must document their internal workflows and data flows. By the end of this project, you must compile and deliver a comprehensive "Architecture & Flow Overview" document that allows the user to understand the complete project structure and the specific data flows of each major module at a glance.
