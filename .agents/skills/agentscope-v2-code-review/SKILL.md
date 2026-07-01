---
name: agentscope-v2-code-review
description: Use when reviewing AgentScope agent scripts, pull requests, or evaluating framework implementations for bugs, bad practices, or architectural compliance
---

# AgentScope v2 Code Review

## Overview
This skill defines the criteria for reviewing AgentScope code in this project. Standard Python reviews (catching syntax errors or missing try/catch blocks) are insufficient. A proper review must aggressively reject violations of the v2 AgentScope architecture (Events, Workspace, TeamTools).

**Violating the letter of the v2 architecture is violating the spirit of the project.**

## When to Use
- When asked to "review", "check", or "verify" an AgentScope agent script.
- When inspecting a pull request or code diff for an AgentScope implementation.
- When an agent script is failing and you are diagnosing the root cause.

## Red Flags - STOP and Reject

If you see any of the following, the code MUST be rejected and flagged for major refactoring. Do not just suggest "minor improvements" or standard best practices.

### 1. File I/O Violations
- **Red Flag**: Using `with open(...)`, `os.path.abspath`, or hardcoded physical paths (e.g., `/tmp/`, `./data/`).
- **Why**: Breaks multi-tenant safety and containerization.
- **Required Fix**: Code must use `self.workspace` (the `LocalWorkspaceManager`) to read/write files within the isolated `workdir`. Do not accept passing paths via kwargs as a full solution unless the workspace intercepts them.

### 2. Message Parsing Violations
- **Red Flag**: Using `re.search`, `json.loads()`, or string manipulation to extract data from an LLM's response string.
- **Why**: Brittle and violates v2 Event principles.
- **Required Fix**: Code must use `msg.append_event()` to reconstruct structured data emitted during the LLM stream, or yield custom `Event` objects. 

### 3. Workflow and Coordination Violations
- **Red Flag**: Using `while` or `for` loops in main application code to wait for agent interactions or polling states.
- **Why**: Defeats Agent-as-a-Service (AaaS) asynchronous message bus architecture.
- **Required Fix**: Code must use `TeamTools` and the framework's internal `MessageBus` / inbox wake-up patterns.

### 4. Direct Model Invocation
- **Red Flag**: Agents calling `self.model.complete()` or `self.model.format()` directly to process their primary task.
- **Why**: Bypasses memory tracking, token logging, and middleware.
- **Required Fix**: Agents should rely on standard lifecycle methods like `super().reply_stream()` or `self.reply()` yielding `Msg` objects.

## Common Rationalizations to Reject

Agents and developers often try to justify bad patterns. Reject these excuses immediately:

| Excuse | Reality (Reviewer Response) |
|--------|---------|
| "The regex is safe because I strip markdown fences." | Regex parsing is completely forbidden for structural data. Use `Event` reconstruction. |
| "I'm just reading a file, I don't need the overhead of Workspace." | Workspace is mandatory for all file I/O to ensure sandbox isolation. No exceptions. |
| "I'm returning `Msg(content=json_dict)` to wrap the data." | V2 expects structured data to flow via `Event` yields, not just nested in a v1 `Msg` payload. |
| "Calling `self.model()` is faster for this simple task." | Bypassing the agent lifecycle breaks observability. Use `reply()`. |

## How to Format Your Review
1. **Critical Architecture Violations**: List any violations of the Red Flags above first. Be explicit that these are architectural failures, not just "improvements". Quote the specific rules being broken.
2. **Standard Code Quality**: List standard Python issues (error handling, types) second.
3. **Verdict**: Explicitly state if the code is REJECTED or APPROVED based on v2 compliance.
