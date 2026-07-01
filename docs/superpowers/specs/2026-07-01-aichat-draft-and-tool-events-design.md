# AIChat Draft Conversation And Tool Events Design

## Background

AIChat has two incorrect frontend behaviors:

1. Clicking new conversation clears `activeSession`, but `ChatContext` immediately auto-selects the first historical session when sessions exist. The UI briefly flashes the empty state and then returns to the previous history.
2. The quick action buttons for weak-plan, resources, lesson, and quiz preview call frontend mock helpers. They directly append assistant messages and workspace artifacts from hard-coded data instead of asking the AI through the tutoring SSE path.

## Goal

Keep a user-created blank conversation visible until the user selects history or sends a first message, and ensure quick actions only submit prompts through the real chat stream. The frontend must render `tool_started`, `tool_completed`, and `artifact_created` events returned by the backend; it must not manufacture tool results locally.

## Scope

In scope:

- Add a draft conversation state to `ChatContext`.
- Prevent automatic historical-session selection while the user is intentionally in draft mode.
- Convert quick action buttons to call `sendMessage(prompt)`.
- Remove the real-page dependency on `MOCK_TOOL_DEMOS`, `runMockToolDemo`, and `sendMockArtifact`.
- Keep the existing native EDU v2 event reducer for `tool_started`, `tool_completed`, and `artifact_created`.
- Add focused unit tests.

Out of scope:

- Changing Backend or Agent Service contracts.
- Implementing new Agent tools.
- Adding fake fallback artifacts if Agent does not return artifacts.

## Design

`ChatContext` owns a new boolean state, `isDraftConversation`. `resetConversation()` sets it to true after clearing the active session and messages. The session auto-selection effect only selects `sessions[0]` when the user is not in draft mode. Selecting a historical session through a new context method clears draft mode. Sending a message also clears draft mode so the backend-created conversation can become active when the stream completes.

`ChatArea` replaces mock quick actions with prompt definitions. Clicking a quick action calls the existing send path, so the event flow is:

`button -> sendMessage(prompt) -> chatService.streamChat -> Backend /tutoring/chat -> Agent Service -> SSE events -> ChatContext reducer -> UI render`.

The frontend keeps rendering real stream events:

- `tool_started` and `tool_completed` update `assistant.toolCalls`.
- `artifact_created` appends to `workspaceArtifacts`.
- No frontend component creates completed tool calls or artifacts for these quick actions.

## Testing

- Add a `ChatContext` regression test proving `resetConversation()` remains in a blank draft even when historical sessions exist.
- Add a `ChatArea` regression test proving quick actions call `sendMessage(prompt)` and do not call `runMockToolDemo`.
- Keep the existing `ChatProvider reduces native EDU v2 stream events` test as coverage for rendering backend event output.

## Interface Drift

No API fields, paths, status enums, or event shapes change.
