# CodeSandboxCard Artifact Validation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reject malformed `CodeSandboxCard` artifacts before they can be published to the frontend workspace or submitted to `/api/v1/sandbox/execute`.

**Architecture:** Add one shared artifact validation module used by both the write tool and scanner. `write_artifact_file` blocks bad JSON before writing to disk; `ArtifactScanner` enforces the same contract at publication time for existing or manually introduced files.

**Tech Stack:** Python 3.12, AgentScope 2.0.3, pytest 9.x, existing `agent_service_v2` artifact pipeline.

## Global Constraints

- Do not change `/api/v1/sandbox/execute`.
- Do not change EDU SSE event names or artifact payload shape.
- Do not introduce a dedicated `write_code_sandbox_card` tool in this fix.
- Do not add frontend-only fallbacks as the primary fix.
- Valid `CodeSandboxCard.props` requires string `question_text`, `code`, `language`, and `default_stdin`.
- Valid `language` values are exactly `c`, `cpp`, `python`, `java`, `go`, `javascript`.
- Client API contract: no change.
- Agent API contract: no path or event shape change.

---

## File Structure

- Create `agent_service_v2/src/agent_service_v2/artifacts/validation.py`
  - Owns JSON artifact business-contract validation.
  - Exposes `validate_json_artifact_payload(payload: dict[str, Any], filename: str) -> dict[str, Any]`.
  - Raises existing `ArtifactValidationError`.
- Modify `agent_service_v2/src/agent_service_v2/tools/artifact_files.py`
  - Calls validation before writing `.json` artifact content.
- Modify `agent_service_v2/src/agent_service_v2/artifacts/scanner.py`
  - Calls validation after parsing JSON and before returning scanned props.
- Modify `agent_service_v2/tests/test_artifact_file_tool.py`
  - Adds write-time rejection tests.
- Modify `agent_service_v2/tests/test_artifact_scanner.py`
  - Adds scan-time rejection and valid card tests.
- Modify `WorkLine.md`
  - Records the fix, verification, and no API drift.

### Task 1: Add Shared CodeSandboxCard Artifact Validation

**Files:**
- Create: `agent_service_v2/src/agent_service_v2/artifacts/validation.py`
- Modify: `agent_service_v2/src/agent_service_v2/artifacts/scanner.py`
- Test: `agent_service_v2/tests/test_artifact_scanner.py`

**Interfaces:**
- Consumes: `ArtifactValidationError` from `agent_service_v2.artifacts.schemas`.
- Produces: `validate_json_artifact_payload(payload: dict[str, Any], filename: str) -> dict[str, Any]`.

- [ ] **Step 1: Write failing scanner tests**

Append these tests to `agent_service_v2/tests/test_artifact_scanner.py`:

```python
def test_scanner_rejects_code_sandbox_card_missing_language(tmp_path):
    artifact_dir = tmp_path / "artifacts"
    artifact_dir.mkdir()
    (artifact_dir / "bad-code-card.json").write_text(
        json.dumps(
            {
                "type": "CodeSandboxCard",
                "props": {
                    "question_text": "修复这段 C 代码",
                    "code": "#include<stdio.h>\\nint main(){return 0;}",
                    "default_stdin": "",
                },
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    with pytest.raises(ArtifactValidationError, match="language"):
        ArtifactScanner(artifact_dir).scan()


def test_scanner_rejects_code_sandbox_card_unsupported_language(tmp_path):
    artifact_dir = tmp_path / "artifacts"
    artifact_dir.mkdir()
    (artifact_dir / "bad-code-card.json").write_text(
        json.dumps(
            {
                "type": "CodeSandboxCard",
                "props": {
                    "question_text": "运行 Python 代码",
                    "code": "print('hello')",
                    "language": "python3",
                    "default_stdin": "",
                },
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    with pytest.raises(ArtifactValidationError, match="unsupported CodeSandboxCard language"):
        ArtifactScanner(artifact_dir).scan()


def test_scanner_accepts_valid_code_sandbox_card(tmp_path):
    artifact_dir = tmp_path / "artifacts"
    artifact_dir.mkdir()
    (artifact_dir / "code-card.json").write_text(
        json.dumps(
            {
                "type": "CodeSandboxCard",
                "props": {
                    "question_text": "修复这段 C 代码",
                    "code": "#include<stdio.h>\\nint main(){return 0;}",
                    "language": "c",
                    "default_stdin": "",
                },
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    artifacts = ArtifactScanner(artifact_dir).scan()

    assert len(artifacts) == 1
    assert artifacts[0].type == "CodeSandboxCard"
    assert artifacts[0].props == {
        "question_text": "修复这段 C 代码",
        "code": "#include<stdio.h>\\nint main(){return 0;}",
        "language": "c",
        "default_stdin": "",
    }
```

- [ ] **Step 2: Run scanner tests to verify RED**

Run:

```bash
cd agent_service_v2 && ./.venv/bin/python -m pytest tests/test_artifact_scanner.py -q
```

Expected: the new missing-language and unsupported-language tests fail because scanner does not yet validate `CodeSandboxCard.props`.

- [ ] **Step 3: Add validation module**

Create `agent_service_v2/src/agent_service_v2/artifacts/validation.py`:

```python
from __future__ import annotations

from typing import Any

from agent_service_v2.artifacts.schemas import ArtifactValidationError


CODE_SANDBOX_LANGUAGES = {"c", "cpp", "python", "java", "go", "javascript"}
CODE_SANDBOX_REQUIRED_PROPS = ("question_text", "code", "language", "default_stdin")


def validate_json_artifact_payload(payload: dict[str, Any], filename: str) -> dict[str, Any]:
    artifact_type = payload.get("type")
    if artifact_type == "CodeSandboxCard":
        _validate_code_sandbox_card(payload, filename)
    return payload


def _validate_code_sandbox_card(payload: dict[str, Any], filename: str) -> None:
    props = payload.get("props")
    if not isinstance(props, dict):
        raise ArtifactValidationError(f"CodeSandboxCard props must be an object: {filename}")

    for key in CODE_SANDBOX_REQUIRED_PROPS:
        value = props.get(key)
        if not isinstance(value, str):
            raise ArtifactValidationError(
                f"CodeSandboxCard props.{key} must be a string: {filename}",
            )

    language = props["language"]
    if language not in CODE_SANDBOX_LANGUAGES:
        raise ArtifactValidationError(
            f"unsupported CodeSandboxCard language: {language}",
        )
```

- [ ] **Step 4: Wire scanner validation**

Modify `agent_service_v2/src/agent_service_v2/artifacts/scanner.py`.

Add import:

```python
from agent_service_v2.artifacts.validation import validate_json_artifact_payload
```

Replace `_parse_json_artifact` body after `title` validation with this exact return path:

```python
    validate_json_artifact_payload(parsed, filename)
    return artifact_type, title, props
```

The complete `_parse_json_artifact` should end as:

```python
def _parse_json_artifact(raw: str, filename: str) -> tuple[str, str | None, dict[str, Any]]:
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ArtifactValidationError(f"invalid json artifact: {filename}") from exc
    if not isinstance(parsed, dict):
        raise ArtifactValidationError(f"json artifact must be an object: {filename}")
    artifact_type = parsed.get("type")
    if not isinstance(artifact_type, str):
        raise ArtifactValidationError(f"json artifact type is required: {filename}")
    props = parsed.get("props", {})
    if not isinstance(props, dict):
        raise ArtifactValidationError(f"json artifact props must be an object: {filename}")
    title = parsed.get("title")
    if title is not None and not isinstance(title, str):
        raise ArtifactValidationError(f"json artifact title must be a string: {filename}")
    validate_json_artifact_payload(parsed, filename)
    return artifact_type, title, props
```

- [ ] **Step 5: Run scanner tests to verify GREEN**

Run:

```bash
cd agent_service_v2 && ./.venv/bin/python -m pytest tests/test_artifact_scanner.py -q
```

Expected: all tests in `test_artifact_scanner.py` pass.

- [ ] **Step 6: Commit Task 1**

Run:

```bash
git add agent_service_v2/src/agent_service_v2/artifacts/validation.py agent_service_v2/src/agent_service_v2/artifacts/scanner.py agent_service_v2/tests/test_artifact_scanner.py
git commit -m "校验代码沙箱工件扫描契约"
```

### Task 2: Block Invalid CodeSandboxCard Files Before Write

**Files:**
- Modify: `agent_service_v2/src/agent_service_v2/tools/artifact_files.py`
- Test: `agent_service_v2/tests/test_artifact_file_tool.py`

**Interfaces:**
- Consumes: `validate_json_artifact_payload(payload: dict[str, Any], filename: str) -> dict[str, Any]` from Task 1.
- Produces: write-time rejection of invalid `CodeSandboxCard` JSON content before filesystem write.

- [ ] **Step 1: Write failing write-tool tests**

Add imports to `agent_service_v2/tests/test_artifact_file_tool.py`:

```python
import json
```

Append these tests:

```python
def test_write_artifact_file_rejects_code_sandbox_card_missing_language_before_write(tmp_path):
    tool = build_write_artifact_file(
        workspace=LocalWorkspace(workdir=str(tmp_path), workspace_id="ws"),
        run_id="run-1",
    )
    content = json.dumps(
        {
            "type": "CodeSandboxCard",
            "props": {
                "question_text": "修复这段 C 代码",
                "code": "#include<stdio.h>\\nint main(){return 0;}",
                "default_stdin": "",
            },
        },
        ensure_ascii=False,
    )

    with pytest.raises(ValueError, match="language"):
        tool(
            filename="code-card.json",
            content=content,
            artifact_type="CodeSandboxCard",
            title="代码练习",
        )

    path = tmp_path / "runs" / "run-1" / "artifacts" / "code-card.json"
    assert not path.exists()


def test_write_artifact_file_accepts_valid_code_sandbox_card(tmp_path):
    tool = build_write_artifact_file(
        workspace=LocalWorkspace(workdir=str(tmp_path), workspace_id="ws"),
        run_id="run-1",
    )
    content = json.dumps(
        {
            "type": "CodeSandboxCard",
            "props": {
                "question_text": "修复这段 C 代码",
                "code": "#include<stdio.h>\\nint main(){return 0;}",
                "language": "c",
                "default_stdin": "",
            },
        },
        ensure_ascii=False,
    )

    result = tool(
        filename="code-card.json",
        content=content,
        artifact_type="CodeSandboxCard",
        title="代码练习",
    )

    path = tmp_path / "runs" / "run-1" / "artifacts" / "code-card.json"
    assert result["status"] == "ok"
    assert result["artifact_type"] == "CodeSandboxCard"
    assert path.read_text(encoding="utf-8") == content
```

- [ ] **Step 2: Run write-tool tests to verify RED**

Run:

```bash
cd agent_service_v2 && ./.venv/bin/python -m pytest tests/test_artifact_file_tool.py -q
```

Expected: `test_write_artifact_file_rejects_code_sandbox_card_missing_language_before_write` fails because invalid JSON is still written.

- [ ] **Step 3: Implement write-time validation**

Modify `agent_service_v2/src/agent_service_v2/tools/artifact_files.py`.

Add import:

```python
import json
```

Add import:

```python
from agent_service_v2.artifacts.validation import validate_json_artifact_payload
```

Add this helper below `build_write_artifact_file`:

```python
def _validate_json_content_for_write(*, filename: str, content: str) -> None:
    if Path(filename).suffix != ".json":
        return
    try:
        payload = json.loads(content)
    except json.JSONDecodeError as exc:
        raise ArtifactValidationError(f"invalid json artifact: {filename}") from exc
    if not isinstance(payload, dict):
        raise ArtifactValidationError(f"json artifact must be an object: {filename}")
    validate_json_artifact_payload(payload, filename)
```

Call it after the size check and before artifact count checking:

```python
        _validate_json_content_for_write(
            filename=safe_filename,
            content=content,
        )
```

The ordering must remain before `target.write_text(...)` so invalid content does not reach disk.

- [ ] **Step 4: Run write-tool tests to verify GREEN**

Run:

```bash
cd agent_service_v2 && ./.venv/bin/python -m pytest tests/test_artifact_file_tool.py -q
```

Expected: all tests in `test_artifact_file_tool.py` pass.

- [ ] **Step 5: Run combined artifact tests**

Run:

```bash
cd agent_service_v2 && ./.venv/bin/python -m pytest tests/test_artifact_file_tool.py tests/test_artifact_scanner.py -q
```

Expected: both files pass.

- [ ] **Step 6: Commit Task 2**

Run:

```bash
git add agent_service_v2/src/agent_service_v2/tools/artifact_files.py agent_service_v2/tests/test_artifact_file_tool.py
git commit -m "写入前拒绝无效代码沙箱工件"
```

### Task 3: Verification and WorkLine Record

**Files:**
- Modify: `WorkLine.md`

**Interfaces:**
- Consumes: passing tests from Tasks 1 and 2.
- Produces: project work record with verification commands and no API drift.

- [ ] **Step 1: Run focused tests**

Run:

```bash
cd agent_service_v2 && ./.venv/bin/python -m pytest tests/test_artifact_file_tool.py tests/test_artifact_scanner.py -q
```

Expected: tests pass.

- [ ] **Step 2: Run import compile check**

Run:

```bash
python3 -m py_compile agent_service_v2/src/agent_service_v2/artifacts/validation.py agent_service_v2/src/agent_service_v2/artifacts/scanner.py agent_service_v2/src/agent_service_v2/tools/artifact_files.py
```

Expected: command exits with status 0 and no output.

- [ ] **Step 3: Append WorkLine entry**

Append this entry near the top of `WorkLine.md`:

```markdown
### 2026-07-10 — CodeSandboxCard artifact contract validation

当前完成：
在 Agent Service v2 artifact 写入和扫描边界增加 `CodeSandboxCard` 强契约校验，缺少 `question_text` / `code` / `language` / `default_stdin` 或语言枚举非法的 JSON 工件会被拒绝，避免前端渲染缺 `language` 的代码沙箱卡片后提交 `/api/v1/sandbox/execute` 触发 422。

修改文件：
- `agent_service_v2/src/agent_service_v2/artifacts/validation.py`
- `agent_service_v2/src/agent_service_v2/artifacts/scanner.py`
- `agent_service_v2/src/agent_service_v2/tools/artifact_files.py`
- `agent_service_v2/tests/test_artifact_scanner.py`
- `agent_service_v2/tests/test_artifact_file_tool.py`

测试结果：
- `cd agent_service_v2 && ./.venv/bin/python -m pytest tests/test_artifact_file_tool.py tests/test_artifact_scanner.py -q`
- `python3 -m py_compile agent_service_v2/src/agent_service_v2/artifacts/validation.py agent_service_v2/src/agent_service_v2/artifacts/scanner.py agent_service_v2/src/agent_service_v2/tools/artifact_files.py`

接口是否漂移：
无。未修改 Client API、Agent API 路径、SSE 事件类型或 artifact payload 形状，仅强制执行既有 `CodeSandboxCard` 工件契约。

下一步建议：
后续如继续增强代码练习产物，可新增专用 `write_code_sandbox_card` 工具，把卡片字段从自由 JSON 字符串升级为 typed tool 参数。
```

- [ ] **Step 4: Review final diff**

Run:

```bash
git diff -- agent_service_v2/src/agent_service_v2/artifacts/validation.py agent_service_v2/src/agent_service_v2/artifacts/scanner.py agent_service_v2/src/agent_service_v2/tools/artifact_files.py agent_service_v2/tests/test_artifact_scanner.py agent_service_v2/tests/test_artifact_file_tool.py WorkLine.md
```

Expected: diff only contains CodeSandboxCard validation, tests, and WorkLine entry.

- [ ] **Step 5: Commit Task 3**

Run:

```bash
git add WorkLine.md
git commit -m "记录代码沙箱工件校验进展"
```
