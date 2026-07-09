# CodeSandboxCard Artifact Validation Design

## Background

The frontend sandbox request failed with HTTP 422 because the rendered
`CodeSandboxCard` submitted `{ code, stdin }` without `language`. Backend
validation is correct: `/api/v1/sandbox/execute` requires `code` and
`language`.

The deeper issue is upstream. AgentScope normalizes tool return values into
tool result chunks, but it does not validate EDUagent-specific artifact JSON.
`write_artifact_file` currently accepts JSON content as a string, and the
artifact scanner only checks that JSON artifacts contain a string `type` and an
object `props`. A malformed `CodeSandboxCard` can therefore be published to the
frontend workspace.

## Goal

Reject malformed `CodeSandboxCard` artifacts before they reach the frontend
workspace.

## Non-Goals

- Do not change `/api/v1/sandbox/execute`.
- Do not change EDU SSE event names or artifact payload shape.
- Do not introduce a dedicated `write_code_sandbox_card` tool in this fix.
- Do not add frontend-only fallbacks as the primary fix.

## Design

Use two validation boundaries.

First, validate before writing JSON plugin artifacts. In
`write_artifact_file`, when `artifact_type == "CodeSandboxCard"` and the target
file is `.json`, parse `content` and reject invalid card payloads before the
file is written. This keeps bad artifacts out of the run workspace.

Second, validate during artifact scanning. `ArtifactScanner` remains the
publication boundary from workspace files to `artifact_created` events. It
should reject any existing or manually introduced malformed `CodeSandboxCard`
JSON file, even if it bypassed the write tool.

## CodeSandboxCard Contract

A valid JSON artifact must have:

```json
{
  "type": "CodeSandboxCard",
  "props": {
    "question_text": "string",
    "code": "string",
    "language": "c | cpp | python | java | go | javascript",
    "default_stdin": "string"
  }
}
```

All four props are required and must be strings. `language` must be one of:
`c`, `cpp`, `python`, `java`, `go`, `javascript`.

Strict rejection is intentional. Auto-filling `default_stdin` would hide
contract drift in model-produced artifacts, and the current incident shows that
soft prompt guidance is not enough.

## Error Behavior

If the model writes an invalid `CodeSandboxCard`, `write_artifact_file` should
fail before writing the file. The agent can then correct the artifact in the
same reasoning loop or report that artifact creation failed.

If an invalid file already exists in the artifact directory, scanner validation
should raise `ArtifactValidationError`, preventing publication of that artifact.

## Testing

Add focused tests:

- `write_artifact_file` rejects a `CodeSandboxCard` missing `language`.
- Rejected `CodeSandboxCard` content is not written to disk.
- `ArtifactScanner` rejects an existing `CodeSandboxCard` missing `language`.
- A valid `CodeSandboxCard` scans successfully.
- An unsupported language is rejected.

## Contract Impact

Client API contract: no change.

Agent API contract: no path or event shape change. This enforces the existing
documented artifact contract for `CodeSandboxCard`.
