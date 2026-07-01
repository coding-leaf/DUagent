# AIChat Guarded Workspace Artifacts Design

## Background

AIChat AgentScope v2 can call `draft_study_artifact`, but the tool is currently a placeholder. Recent runs show the model calls the tool and then streams the full learning material through `text_delta`, so the content appears in the chat area instead of the Agent workspace. The frontend already supports `artifact_created` events and has workspace plugins for `Markdown`, `Mermaid`, `StudyPlanCard`, `WeakPointsCard`, `PathRecommendationCard`, and `QuizCard`; the missing piece is the Agent-side artifact pipeline.

AgentScope 2.0.3 is installed in `agent_service_v2/.venv`. Introspection there confirms `Agent.reply_stream`, `Toolkit`, `ToolGroup`, `FunctionTool`, `Write`, `Read`, `Edit`, `Grep`, `Glob`, and `LocalWorkspace` are available, while `agentscope.service` is not installed. The root `.venv` has a different/incomplete AgentScope import surface and must not be used as the implementation truth for v2 runtime work. EDUagent should therefore keep the current `agent_service_v2` FastAPI service facade and use AgentScope workspace/runtime primitives behind EDU SSE v2 events.

## Goal

Make saveable AIChat outputs first-class workspace artifacts. When the user asks for learning materials, lesson pages, worksheets, diagrams, study plans, or resource recommendation documents, the Agent writes a bounded workspace file. EDUagent scans that file, records it in a manifest, emits `artifact_created`, and renders it in the frontend workspace. The chat area should receive only a short confirmation and summary.

## Scope

In scope:

- Add a guarded artifact file writing tool for AgentScope v2 AIChat.
- Add an Agent workspace artifact scanner and run-level manifest.
- Emit `artifact_created` after artifact files are written and after final reply as a safety scan.
- Support first-stage artifact types: `Markdown`, `Mermaid`, `StudyPlanCard`, `WeakPointsCard`, `PathRecommendationCard`, and `QuizCard`.
- Update prompt/tool instructions so artifact content goes to workspace files, not long chat text.
- Keep Backend as SSE proxy and persistence owner; Agent Service still does not write MySQL.
- Add tests across Agent Service, Backend forwarding, and frontend workspace rendering.

Out of scope for the first implementation:

- Directly exposing unrestricted AgentScope `Write`, `Edit`, `Bash`, `Grep`, or `Glob` tools.
- Persisting artifact bodies in MySQL.
- A full artifact editor or artifact version chain.
- Recovering all historical conversation artifacts through a new API.
- Knowledge correctness review for artifact contents.

## Architecture

The selected architecture is **C-Guarded Native Workspace Artifact Pipeline**:

```text
AgentScope Agent.reply_stream()
  -> model selects a bounded artifact file tool
  -> tool writes runs/<run_id>/artifacts/<file>
  -> ArtifactScanner scans artifacts directory
  -> ArtifactManifest records published files and hashes
  -> EDUProtocolAdapter emits artifact_created
  -> Backend forwards SSE unchanged
  -> Frontend ChatContext stores workspaceArtifacts
  -> AgentWorkspace renders PluginRegistry[type]
```

The file is the source of truth. `artifact_created` is a product event derived from workspace files; it is not an AgentScope-native object and should not expose AgentScope internals directly.

## Workspace Layout

Artifacts are isolated per run under the existing `WorkbenchRunStore` boundary:

```text
agent_service_v2/workspaces/
  ai-chat/
    u_<user_id>/
      c_<course_id_or_global>/
        conv_<conversation_id>/
          runs/
            run_<run_id>/
              state.json
              events.jsonl
              review.json
              artifacts/
                manifest.json
                001-c-functions.md
                002-function-call-flow.mmd
                003-study-plan.json
```

Run-level isolation keeps debug and replay simple. Conversation-level artifact aggregation can be added later by reading manifests across runs.

## Artifact File Formats

Markdown artifacts use frontmatter when a title or explicit type is available:

```markdown
---
type: Markdown
title: C语言函数核心概念学习资料
---

# C语言函数核心概念学习资料

...
```

Mermaid artifacts use `.mmd` and can also include frontmatter:

```markdown
---
type: Mermaid
title: 函数调用流程图
---

flowchart TD
  A[main] --> B[add]
```

Structured plugin artifacts use JSON:

```json
{
  "type": "StudyPlanCard",
  "title": "C语言薄弱点补强计划",
  "props": {
    "weeks": []
  }
}
```

Scanner rules:

- `.md`: parse frontmatter, default `type` to `Markdown`, set `props.content` to body content.
- `.mmd`: parse optional frontmatter, default `type` to `Mermaid`, set `props.chart` to body content.
- `.json`: parse object, require `type`, require `props` to be an object when present.
- Reject unsupported extensions, unsupported types, invalid JSON, hidden files, directories, oversized files, and files outside the run artifact directory.

## Manifest

Each run artifact directory owns `manifest.json`:

```json
{
  "version": 1,
  "run_id": "run_xxx",
  "artifacts": [
    {
      "id": "artifact_001_c_functions",
      "file": "001-c-functions.md",
      "type": "Markdown",
      "title": "C语言函数核心概念学习资料",
      "sha256": "...",
      "created_at": "2026-07-01T15:00:00Z",
      "published_seq": 42,
      "status": "published"
    }
  ]
}
```

The manifest prevents duplicate `artifact_created` events. First implementation handles new artifacts only. If the same file path changes content, it should be emitted with a new artifact id rather than introducing `artifact_updated` in the first pass.

## Tool Strategy

First implementation should use a bounded domain tool, not unrestricted AgentScope `Write`:

```python
write_artifact_file(
    filename: str,
    content: str,
    artifact_type: str = "Markdown",
    title: str = "",
) -> dict
```

The tool writes to `runs/<run_id>/artifacts/` and returns a structured observation containing filename, artifact type, title, bytes written, and a short summary. This preserves the selected方案 C because files remain the source of truth, while reducing path and permission risk.

The tool must reject:

- absolute paths
- `..` path traversal
- hidden filenames
- nested directories in the first implementation
- unsupported extensions
- unsupported artifact types
- content larger than 200 KB
- more than 10 artifact files in one run

Direct AgentScope `Write`, `Read`, `Edit`, `Bash`, `Grep`, and `Glob` remain out of the AIChat toolkit until the guarded pipeline is verified. A later phase may allow `Read` and `Write` only inside the same artifact directory.

## Prompt Rules

`WORKBENCH_SYSTEM_PROMPT` should tell the model:

- Use planning tools only for genuinely multi-step work.
- For saveable materials, lesson pages, worksheets, diagrams, study plans, and resource recommendation documents, call the artifact file tool with the complete content.
- Do not stream the full artifact body in chat.
- After creating artifact files, reply with artifact title, one-sentence summary, and one suggested next action.

This prompt rule is part of the product contract. Without it, the model may create a placeholder tool trace and still stream a long final answer into chat.

## Event Mapping

`EDUProtocolAdapter.adapt_many()` should scan for new artifacts in two places:

1. After a successful artifact file tool `ToolResultEndEvent`.
2. After `ReplyEndEvent`, before `workflow_completed`, as a final safety scan.

Recommended order for successful artifact generation:

```text
tool_started
tool_completed
artifact_created
text_delta short confirmation
workflow_completed
content_safety_reviewed
```

`artifact_created.payload.artifact` should match existing frontend expectations:

```json
{
  "id": "artifact_001_c_functions",
  "type": "Markdown",
  "props": {
    "title": "C语言函数核心概念学习资料",
    "content": "# C语言函数核心概念学习资料\n..."
  }
}
```

## Backend Boundary

Backend remains an SSE adapter and persistence owner. It forwards `artifact_created` events and persists assistant text exactly as streamed. Agent Service does not write MySQL. No new Backend API is required in the first implementation.

Future artifact replay may add a Backend-proxied query endpoint, but that is outside this first artifact pipeline.

## Frontend Boundary

Frontend already consumes `artifact_created` into `workspaceArtifacts` and renders `PluginRegistry[type]`. First implementation should only add small compatibility polish if needed:

- Markdown workspace plugin should display `props.title` when provided.
- Workspace should continue to show unknown-type errors for unsupported artifact types.
- Chat message should not duplicate artifact body because artifact body should not arrive as `text_delta`.

## Security And Guardrails

Required guardrails:

- Path whitelist: run artifact directory only.
- Filename whitelist: non-hidden basename only, no path separator in first implementation.
- Extension whitelist: `.md`, `.mmd`, `.json`.
- Type whitelist: frontend-supported artifact types.
- Size limit: 200 KB per artifact file.
- Count limit: 10 artifact files per run.
- Manifest de-duplication by path and hash.
- JSON parse validation for structured artifacts.
- No `Bash`, unrestricted `Write`, unrestricted `Read`, `Edit`, `Grep`, or `Glob` in the first toolkit.

## Testing Strategy

Agent Service tests:

- artifact file tool rejects path traversal and unsupported extensions.
- artifact file tool writes Markdown with frontmatter.
- scanner parses Markdown, Mermaid, and JSON plugin files.
- scanner rejects invalid JSON and unsupported types.
- manifest prevents duplicate publishes.
- protocol adapter emits `artifact_created` after artifact file tool success.
- final reply scan emits missed artifacts before `workflow_completed`.

Backend tests:

- tutoring stream adapter forwards `artifact_created` unchanged.
- persisted assistant content remains short when the agent streams only confirmation text.

Frontend tests:

- `ChatContext` stores artifact from `artifact_created`.
- `AgentWorkspace` renders a Markdown artifact with title and content.
- unknown artifact types still render an explicit error.

## Rollout

Phase 1 implements Markdown artifacts only end-to-end, while scanner supports Mermaid and JSON parsing tests. Phase 2 lets the model generate Mermaid and structured JSON plugin files. Phase 3 adds artifact replay across historical runs. Phase 4 adds artifact edits and version events.

## Interface Drift

No new SSE event type is introduced. This design makes the existing `artifact_created` event real in Agent Service v2. Payload follows the existing frontend shape: `payload.artifact.id`, `payload.artifact.type`, and `payload.artifact.props`.
