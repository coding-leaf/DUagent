# AIChat Guarded Workspace Artifacts Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make AIChat saveable learning outputs appear as Agent workspace artifacts by writing guarded files under the AgentScope workspace, scanning them into a manifest, and emitting the existing `artifact_created` SSE event.

**Architecture:** The workspace file is the source of truth. AgentScope receives one bounded domain tool, `write_artifact_file`, which writes only inside `runs/<run_id>/artifacts/`; EDUagent scans that directory, records published files in `manifest.json`, and maps new files to stable EDU SSE v2 `artifact_created` events. Backend remains a proxy/persistence owner, and frontend keeps rendering artifacts through the existing `PluginRegistry`.

**Tech Stack:** Python 3.12, AgentScope 2.0.3 from `agent_service_v2/.venv`, FastAPI SSE facade, pytest, React/Vitest, existing EDU SSE v2 event types.

---

## Preconditions

- Use `/home/yezisama/workspace/workflow/EDUagent/agent_service_v2/.venv`, not the root `.venv`, for AgentScope v2 implementation and tests.
- Verified local AgentScope surface in `agent_service_v2/.venv`: `Agent`, `ContextConfig`, `ReActConfig`, `Toolkit`, `ToolGroup`, `FunctionTool`, `Write`, `Read`, `Edit`, `Grep`, `Glob`, and `LocalWorkspace` exist; `agentscope.service` is absent.
- Keep direct AgentScope built-in file tools out of AIChat in this first pass. Only expose the guarded EDU domain tool.
- Do not change `.env`, secrets, MySQL volumes, uploaded files, or old `agent_service/`.

## File Structure

- Create: `agent_service_v2/src/agent_service_v2/artifacts/__init__.py`
  - Package marker and exports for artifact scanning helpers.
- Create: `agent_service_v2/src/agent_service_v2/artifacts/schemas.py`
  - Constants, dataclasses, validation errors, filename/type/size limits.
- Create: `agent_service_v2/src/agent_service_v2/artifacts/scanner.py`
  - Parse `.md`, `.mmd`, `.json` files into frontend artifact payloads.
- Create: `agent_service_v2/src/agent_service_v2/artifacts/manifest.py`
  - Read/write `manifest.json`, publish new artifacts once, assign stable IDs.
- Create: `agent_service_v2/src/agent_service_v2/tools/artifact_files.py`
  - Build the AgentScope `write_artifact_file` callable bound to a workspace and run id.
- Modify: `agent_service_v2/src/agent_service_v2/tools/workbench_toolkit.py`
  - Accept workspace/run id and register the guarded artifact tool.
- Modify: `agent_service_v2/src/agent_service_v2/agents/workbench_factory.py`
  - Pass workspace/run id into toolkit construction.
- Modify: `agent_service_v2/src/agent_service_v2/agents/permissions.py`
  - Allow `write_artifact_file`, remove `draft_study_artifact` from safe tool list once toolkit no longer exposes it.
- Modify: `agent_service_v2/src/agent_service_v2/agents/prompts.py`
  - Instruct the model to write saveable material via `write_artifact_file` and keep chat replies short.
- Modify: `agent_service_v2/src/agent_service_v2/runtime/protocol_adapter.py`
  - Accept an optional artifact publisher and emit `artifact_created` after successful artifact tool completion and before workflow completion.
- Modify: `agent_service_v2/src/agent_service_v2/session/workbench_session.py`
  - Construct `ArtifactPublisher` from `WorkbenchRunStore` run directory and pass it to `EDUProtocolAdapter`.
- Modify: `agent_service_v2/src/agent_service_v2/workspaces/run_store.py`
  - Add public `run_dir(run_id)` and `artifact_dir(run_id)` helpers.
- Modify: `agent_service_v2/tests/test_workbench_toolkit.py`
  - Update toolkit and permission expectations.
- Create: `agent_service_v2/tests/test_artifact_scanner.py`
- Create: `agent_service_v2/tests/test_artifact_manifest.py`
- Create: `agent_service_v2/tests/test_artifact_file_tool.py`
- Modify: `agent_service_v2/tests/test_protocol_adapter.py`
  - Add artifact event emission tests.
- Modify: `agent_service_v2/tests/test_workbench_session.py`
  - Add one session-level test for final safety scan if adapter-only coverage is not enough.
- Modify: `backend/tests/test_tutoring_stream_adapter.py`
  - Keep existing passthrough test; add title assertion for artifact payload.
- Modify: `frontend/src/components/workspace/plugins/MarkdownViewer.jsx`
  - Render `title` prop above content and reduce nested-card feeling if needed.
- Modify: `frontend/src/components/workspace/AgentWorkspace.test.jsx`
  - Add Markdown artifact rendering and unknown-type coverage with real registry or explicit mock.
- Modify: `WorkLine.md`
  - Append implementation and verification record at the end.

---

### Task 1: Artifact Schemas And Scanner

**Files:**
- Create: `agent_service_v2/src/agent_service_v2/artifacts/__init__.py`
- Create: `agent_service_v2/src/agent_service_v2/artifacts/schemas.py`
- Create: `agent_service_v2/src/agent_service_v2/artifacts/scanner.py`
- Create: `agent_service_v2/tests/test_artifact_scanner.py`

- [ ] **Step 1: Write scanner tests**

Create `agent_service_v2/tests/test_artifact_scanner.py`:

```python
import json

import pytest

from agent_service_v2.artifacts.scanner import ArtifactScanner
from agent_service_v2.artifacts.schemas import ArtifactValidationError


def test_scanner_parses_markdown_with_frontmatter(tmp_path):
    artifact_dir = tmp_path / "artifacts"
    artifact_dir.mkdir()
    (artifact_dir / "001-functions.md").write_text(
        "---\n"
        "type: Markdown\n"
        "title: C语言函数核心概念\n"
        "---\n\n"
        "# C语言函数核心概念\n\n"
        "函数用于把可复用逻辑封装成命名代码块。\n",
        encoding="utf-8",
    )

    artifacts = ArtifactScanner(artifact_dir).scan()

    assert len(artifacts) == 1
    artifact = artifacts[0]
    assert artifact.file == "001-functions.md"
    assert artifact.type == "Markdown"
    assert artifact.title == "C语言函数核心概念"
    assert artifact.props == {
        "title": "C语言函数核心概念",
        "content": "# C语言函数核心概念\n\n函数用于把可复用逻辑封装成命名代码块。\n",
    }


def test_scanner_parses_mermaid_with_default_type(tmp_path):
    artifact_dir = tmp_path / "artifacts"
    artifact_dir.mkdir()
    (artifact_dir / "002-flow.mmd").write_text(
        "flowchart TD\n  A[main] --> B[add]\n",
        encoding="utf-8",
    )

    artifacts = ArtifactScanner(artifact_dir).scan()

    assert artifacts[0].type == "Mermaid"
    assert artifacts[0].props == {"chart": "flowchart TD\n  A[main] --> B[add]\n"}


def test_scanner_parses_json_plugin_artifact(tmp_path):
    artifact_dir = tmp_path / "artifacts"
    artifact_dir.mkdir()
    (artifact_dir / "003-plan.json").write_text(
        json.dumps(
            {
                "type": "StudyPlanCard",
                "title": "两周补弱计划",
                "props": {"weeks": [{"label": "第1周", "goals": ["复习函数"]}]},
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    artifacts = ArtifactScanner(artifact_dir).scan()
    assert artifacts[0].type == "StudyPlanCard"
    assert artifacts[0].title == "两周补弱计划"
    assert artifacts[0].props == {"weeks": [{"label": "第1周", "goals": ["复习函数"]}]}


def test_scanner_rejects_invalid_json(tmp_path):
    artifact_dir = tmp_path / "artifacts"
    artifact_dir.mkdir()
    (artifact_dir / "bad.json").write_text("{bad", encoding="utf-8")

    with pytest.raises(ArtifactValidationError, match="invalid json"):
        ArtifactScanner(artifact_dir).scan()


def test_scanner_rejects_unsupported_type(tmp_path):
    artifact_dir = tmp_path / "artifacts"
    artifact_dir.mkdir()
    (artifact_dir / "bad.md").write_text(
        "---\ntype: UnknownType\n---\n\n# Bad\n",
        encoding="utf-8",
    )

    with pytest.raises(ArtifactValidationError, match="unsupported artifact type"):
        ArtifactScanner(artifact_dir).scan()


def test_scanner_ignores_manifest_and_rejects_hidden_or_nested_files(tmp_path):
    artifact_dir = tmp_path / "artifacts"
    artifact_dir.mkdir()
    (artifact_dir / "manifest.json").write_text('{"version":1}', encoding="utf-8")
    (artifact_dir / ".secret.md").write_text("# Secret", encoding="utf-8")

    with pytest.raises(ArtifactValidationError, match="hidden artifact file"):
        ArtifactScanner(artifact_dir).scan()
```

- [ ] **Step 2: Run scanner tests and verify they fail**

Run:

```bash
cd agent_service_v2 && ./.venv/bin/python -m pytest tests/test_artifact_scanner.py -q
```

Expected: FAIL with `ModuleNotFoundError: No module named 'agent_service_v2.artifacts'`.

- [ ] **Step 3: Create schema module**

Create `agent_service_v2/src/agent_service_v2/artifacts/__init__.py`:

```python
from agent_service_v2.artifacts.scanner import ArtifactScanner

__all__ = ["ArtifactScanner"]
```

Create `agent_service_v2/src/agent_service_v2/artifacts/schemas.py`:

```python
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

SUPPORTED_ARTIFACT_TYPES = {
    "Markdown",
    "Mermaid",
    "StudyPlanCard",
    "WeakPointsCard",
    "PathRecommendationCard",
    "QuizCard",
}
SUPPORTED_EXTENSIONS = {".md", ".mmd", ".json"}
MAX_ARTIFACT_BYTES = 200 * 1024
MAX_ARTIFACTS_PER_RUN = 10
MANIFEST_FILENAME = "manifest.json"


class ArtifactValidationError(ValueError):
    pass


@dataclass(frozen=True)
class ScannedArtifact:
    file: str
    path: Path
    type: str
    title: str | None
    props: dict[str, Any]
    sha256: str


@dataclass(frozen=True)
class PublishedArtifact:
    id: str
    file: str
    type: str
    title: str | None
    sha256: str
    props: dict[str, Any]
    published_seq: int | None = None

    def to_event_payload(self) -> dict[str, Any]:
        return {
            "artifact": {
                "id": self.id,
                "type": self.type,
                "props": self.props,
            }
        }
```

- [ ] **Step 4: Create scanner implementation**

Create `agent_service_v2/src/agent_service_v2/artifacts/scanner.py`:

```python
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from agent_service_v2.artifacts.schemas import (
    MANIFEST_FILENAME,
    MAX_ARTIFACT_BYTES,
    SUPPORTED_ARTIFACT_TYPES,
    SUPPORTED_EXTENSIONS,
    ArtifactValidationError,
    ScannedArtifact,
)


class ArtifactScanner:
    def __init__(self, artifact_dir: str | Path) -> None:
        self._artifact_dir = Path(artifact_dir).resolve()

    def scan(self) -> list[ScannedArtifact]:
        if not self._artifact_dir.exists():
            return []
        artifacts: list[ScannedArtifact] = []
        for path in sorted(self._artifact_dir.iterdir(), key=lambda item: item.name):
            if path.name == MANIFEST_FILENAME:
                continue
            artifacts.append(self._scan_file(path))
        return artifacts

    def _scan_file(self, path: Path) -> ScannedArtifact:
        if path.name.startswith("."):
            raise ArtifactValidationError(f"hidden artifact file is not allowed: {path.name}")
        if path.is_dir():
            raise ArtifactValidationError(f"nested artifact directory is not allowed: {path.name}")
        if path.suffix not in SUPPORTED_EXTENSIONS:
            raise ArtifactValidationError(f"unsupported artifact extension: {path.suffix}")
        size = path.stat().st_size
        if size > MAX_ARTIFACT_BYTES:
            raise ArtifactValidationError(f"artifact file exceeds {MAX_ARTIFACT_BYTES} bytes: {path.name}")

        raw = path.read_text(encoding="utf-8")
        digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()
        if path.suffix == ".json":
            artifact_type, title, props = _parse_json_artifact(raw, path.name)
        else:
            meta, body = _split_frontmatter(raw)
            default_type = "Mermaid" if path.suffix == ".mmd" else "Markdown"
            artifact_type = str(meta.get("type") or default_type)
            title = str(meta["title"]) if meta.get("title") else None
            props = {"chart": body} if artifact_type == "Mermaid" else {"content": body}
            if title:
                props["title"] = title

        if artifact_type not in SUPPORTED_ARTIFACT_TYPES:
            raise ArtifactValidationError(f"unsupported artifact type: {artifact_type}")
        return ScannedArtifact(
            file=path.name,
            path=path,
            type=artifact_type,
            title=title,
            props=props,
            sha256=digest,
        )


def _split_frontmatter(raw: str) -> tuple[dict[str, str], str]:
    if not raw.startswith("---\n"):
        return {}, raw
    marker = raw.find("\n---\n", 4)
    if marker == -1:
        return {}, raw
    header = raw[4:marker]
    body = raw[marker + len("\n---\n") :]
    meta: dict[str, str] = {}
    for line in header.splitlines():
        key, sep, value = line.partition(":")
        if sep:
            meta[key.strip()] = value.strip().strip('"').strip("'")
    return meta, body


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
    if title and "title" not in props:
        props = {"title": title, **props}
    return artifact_type, title, props
```

- [ ] **Step 5: Run scanner tests and verify they pass**

Run:

```bash
cd agent_service_v2 && ./.venv/bin/python -m pytest tests/test_artifact_scanner.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit scanner task**

```bash
git add agent_service_v2/src/agent_service_v2/artifacts agent_service_v2/tests/test_artifact_scanner.py
git commit -m "添加AIChat工作区产物扫描器"
```

---

### Task 2: Artifact Manifest Publisher

**Files:**
- Create: `agent_service_v2/src/agent_service_v2/artifacts/manifest.py`
- Create: `agent_service_v2/tests/test_artifact_manifest.py`
- Modify: `agent_service_v2/src/agent_service_v2/workspaces/run_store.py`

- [ ] **Step 1: Write manifest tests**

Create `agent_service_v2/tests/test_artifact_manifest.py`:

```python
import json

from agentscope.workspace import LocalWorkspace

from agent_service_v2.artifacts.manifest import ArtifactPublisher
from agent_service_v2.workspaces.run_store import WorkbenchRunStore


def test_run_store_exposes_run_and_artifact_dirs(tmp_path):
    store = WorkbenchRunStore(workspace=LocalWorkspace(workdir=str(tmp_path), workspace_id="ws"))

    assert store.run_dir("run/1") == tmp_path / "runs" / "run_1"
    assert store.artifact_dir("run/1") == tmp_path / "runs" / "run_1" / "artifacts"
    assert store.artifact_dir("run/1").exists()


def test_publisher_emits_new_artifact_once_and_writes_manifest(tmp_path):
    artifact_dir = tmp_path / "artifacts"
    artifact_dir.mkdir()
    (artifact_dir / "001-functions.md").write_text(
        "---\ntype: Markdown\ntitle: 函数资料\n---\n\n# 函数资料\n",
        encoding="utf-8",
    )
    publisher = ArtifactPublisher(run_id="run-1", artifact_dir=artifact_dir)

    first = publisher.publish_new(seq_start=7)
    second = publisher.publish_new(seq_start=8)

    assert len(first) == 1
    assert second == []
    assert first[0].id == "artifact_001_functions"
    assert first[0].published_seq == 7
    assert first[0].to_event_payload() == {
        "artifact": {
            "id": "artifact_001_functions",
            "type": "Markdown",
            "props": {"title": "函数资料", "content": "# 函数资料\n"},
        }
    }
    manifest = json.loads((artifact_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["version"] == 1
    assert manifest["run_id"] == "run-1"
    assert manifest["artifacts"][0]["file"] == "001-functions.md"


def test_publisher_reemits_changed_file_with_new_id(tmp_path):
    artifact_dir = tmp_path / "artifacts"
    artifact_dir.mkdir()
    path = artifact_dir / "001-functions.md"
    path.write_text("# v1\n", encoding="utf-8")
    publisher = ArtifactPublisher(run_id="run-1", artifact_dir=artifact_dir)

    first = publisher.publish_new(seq_start=1)
    path.write_text("# v2\n", encoding="utf-8")
    second = publisher.publish_new(seq_start=2)

    assert first[0].id == "artifact_001_functions"
    assert second[0].id == "artifact_001_functions_2"
    assert second[0].props["content"] == "# v2\n"
```

- [ ] **Step 2: Run manifest tests and verify they fail**

Run:

```bash
cd agent_service_v2 && ./.venv/bin/python -m pytest tests/test_artifact_manifest.py -q
```

Expected: FAIL because `manifest.py`, `run_dir`, and `artifact_dir` are missing.

- [ ] **Step 3: Add run directory helpers**

Modify `agent_service_v2/src/agent_service_v2/workspaces/run_store.py` so the class has public helpers and existing methods call them:

```python
    def run_dir(self, run_id: str) -> Path:
        return self._run_dir(run_id)

    def artifact_dir(self, run_id: str) -> Path:
        artifact_dir = self._run_dir(run_id) / "artifacts"
        artifact_dir.mkdir(parents=True, exist_ok=True)
        return artifact_dir
```

- [ ] **Step 4: Add manifest publisher implementation**

Create `agent_service_v2/src/agent_service_v2/artifacts/manifest.py`:

```python
from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from agent_service_v2.artifacts.scanner import ArtifactScanner
from agent_service_v2.artifacts.schemas import MANIFEST_FILENAME, PublishedArtifact


class ArtifactPublisher:
    def __init__(self, *, run_id: str, artifact_dir: str | Path) -> None:
        self._run_id = run_id
        self._artifact_dir = Path(artifact_dir).resolve()
        self._artifact_dir.mkdir(parents=True, exist_ok=True)
        self._manifest_path = self._artifact_dir / MANIFEST_FILENAME

    def publish_new(self, *, seq_start: int | None = None) -> list[PublishedArtifact]:
        manifest = self._read_manifest()
        existing = {(item["file"], item["sha256"]) for item in manifest["artifacts"]}
        published: list[PublishedArtifact] = []
        for scanned in ArtifactScanner(self._artifact_dir).scan():
            if (scanned.file, scanned.sha256) in existing:
                continue
            artifact_id = self._next_artifact_id(scanned.file, manifest["artifacts"])
            published_seq = None if seq_start is None else seq_start + len(published)
            record = {
                "id": artifact_id,
                "file": scanned.file,
                "type": scanned.type,
                "title": scanned.title,
                "sha256": scanned.sha256,
                "created_at": datetime.now(UTC).isoformat(),
                "published_seq": published_seq,
                "status": "published",
            }
            manifest["artifacts"].append(record)
            published.append(
                PublishedArtifact(
                    id=artifact_id,
                    file=scanned.file,
                    type=scanned.type,
                    title=scanned.title,
                    sha256=scanned.sha256,
                    props=scanned.props,
                    published_seq=published_seq,
                )
            )
        if published:
            self._write_manifest(manifest)
        return published

    def _read_manifest(self) -> dict[str, Any]:
        if not self._manifest_path.exists():
            return {"version": 1, "run_id": self._run_id, "artifacts": []}
        parsed = json.loads(self._manifest_path.read_text(encoding="utf-8"))
        if not isinstance(parsed, dict) or not isinstance(parsed.get("artifacts"), list):
            return {"version": 1, "run_id": self._run_id, "artifacts": []}
        parsed["version"] = 1
        parsed["run_id"] = self._run_id
        return parsed

    def _write_manifest(self, manifest: dict[str, Any]) -> None:
        self._manifest_path.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def _next_artifact_id(self, filename: str, records: list[dict[str, Any]]) -> str:
        stem = Path(filename).stem
        slug = re.sub(r"[^A-Za-z0-9]+", "_", stem).strip("_").lower() or "artifact"
        base = f"artifact_{slug}"
        used = {str(record.get("id")) for record in records}
        if base not in used:
            return base
        suffix = 2
        while f"{base}_{suffix}" in used:
            suffix += 1
        return f"{base}_{suffix}"
```

Update `agent_service_v2/src/agent_service_v2/artifacts/__init__.py` now that `manifest.py` exists:

```python
from agent_service_v2.artifacts.manifest import ArtifactPublisher
from agent_service_v2.artifacts.scanner import ArtifactScanner

__all__ = ["ArtifactPublisher", "ArtifactScanner"]
```

- [ ] **Step 5: Run manifest and scanner tests**

Run:

```bash
cd agent_service_v2 && ./.venv/bin/python -m pytest tests/test_artifact_scanner.py tests/test_artifact_manifest.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit manifest task**

```bash
git add agent_service_v2/src/agent_service_v2/artifacts/manifest.py agent_service_v2/src/agent_service_v2/workspaces/run_store.py agent_service_v2/tests/test_artifact_manifest.py
git commit -m "添加AIChat产物发布清单"
```

---

### Task 3: Guarded Artifact File Tool

**Files:**
- Create: `agent_service_v2/src/agent_service_v2/tools/artifact_files.py`
- Create: `agent_service_v2/tests/test_artifact_file_tool.py`

- [ ] **Step 1: Write guarded tool tests**

Create `agent_service_v2/tests/test_artifact_file_tool.py`:

```python
import pytest
from agentscope.workspace import LocalWorkspace

from agent_service_v2.tools.artifact_files import build_write_artifact_file


def test_write_artifact_file_writes_markdown_with_frontmatter(tmp_path):
    tool = build_write_artifact_file(
        workspace=LocalWorkspace(workdir=str(tmp_path), workspace_id="ws"),
        run_id="run-1",
    )

    result = tool(
        filename="001-functions.md",
        content="# 函数资料\n",
        artifact_type="Markdown",
        title="函数资料",
    )

    path = tmp_path / "runs" / "run-1" / "artifacts" / "001-functions.md"
    assert result == {
        "status": "ok",
        "tool": "write_artifact_file",
        "filename": "001-functions.md",
        "artifact_type": "Markdown",
        "title": "函数资料",
        "bytes_written": len(path.read_bytes()),
        "summary": "artifact file written: 001-functions.md",
    }
    assert path.read_text(encoding="utf-8") == (
        "---\n"
        "type: Markdown\n"
        "title: 函数资料\n"
        "---\n\n"
        "# 函数资料\n"
    )


@pytest.mark.parametrize(
    "filename",
    ["/tmp/x.md", "../x.md", ".hidden.md", "nested/x.md", "bad.exe"],
)
def test_write_artifact_file_rejects_unsafe_filename(tmp_path, filename):
    tool = build_write_artifact_file(
        workspace=LocalWorkspace(workdir=str(tmp_path), workspace_id="ws"),
        run_id="run-1",
    )

    with pytest.raises(ValueError):
        tool(filename=filename, content="# x\n", artifact_type="Markdown", title="x")


def test_write_artifact_file_rejects_unsupported_type(tmp_path):
    tool = build_write_artifact_file(
        workspace=LocalWorkspace(workdir=str(tmp_path), workspace_id="ws"),
        run_id="run-1",
    )

    with pytest.raises(ValueError, match="unsupported artifact type"):
        tool(filename="x.md", content="# x\n", artifact_type="UnknownType", title="x")


def test_write_artifact_file_rejects_more_than_ten_artifacts(tmp_path):
    artifact_dir = tmp_path / "runs" / "run-1" / "artifacts"
    artifact_dir.mkdir(parents=True)
    for index in range(10):
        (artifact_dir / f"{index}.md").write_text("# x\n", encoding="utf-8")
    tool = build_write_artifact_file(
        workspace=LocalWorkspace(workdir=str(tmp_path), workspace_id="ws"),
        run_id="run-1",
    )

    with pytest.raises(ValueError, match="artifact count limit"):
        tool(filename="overflow.md", content="# x\n", artifact_type="Markdown", title="x")
```

- [ ] **Step 2: Run tool tests and verify they fail**

Run:

```bash
cd agent_service_v2 && ./.venv/bin/python -m pytest tests/test_artifact_file_tool.py -q
```

Expected: FAIL because `agent_service_v2.tools.artifact_files` is missing.

- [ ] **Step 3: Implement guarded tool**

Create `agent_service_v2/src/agent_service_v2/tools/artifact_files.py`:

```python
from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from agentscope.workspace import LocalWorkspace

from agent_service_v2.artifacts.schemas import (
    MAX_ARTIFACTS_PER_RUN,
    MAX_ARTIFACT_BYTES,
    SUPPORTED_ARTIFACT_TYPES,
    SUPPORTED_EXTENSIONS,
    ArtifactValidationError,
)
from agent_service_v2.workspaces.run_store import WorkbenchRunStore


def build_write_artifact_file(*, workspace: LocalWorkspace, run_id: str) -> Callable[..., dict]:
    store = WorkbenchRunStore(workspace=workspace)
    artifact_dir = store.artifact_dir(run_id)

    def write_artifact_file(
        filename: str,
        content: str,
        artifact_type: str = "Markdown",
        title: str = "",
    ) -> dict:
        safe_filename = _validate_filename(filename)
        if artifact_type not in SUPPORTED_ARTIFACT_TYPES:
            raise ArtifactValidationError(f"unsupported artifact type: {artifact_type}")
        encoded_body = content.encode("utf-8")
        if len(encoded_body) > MAX_ARTIFACT_BYTES:
            raise ArtifactValidationError(f"artifact content exceeds {MAX_ARTIFACT_BYTES} bytes")
        existing_files = [path for path in artifact_dir.iterdir() if path.is_file() and path.name != "manifest.json"]
        if len(existing_files) >= MAX_ARTIFACTS_PER_RUN and not (artifact_dir / safe_filename).exists():
            raise ArtifactValidationError("artifact count limit exceeded")

        body = _with_frontmatter(
            content=content,
            artifact_type=artifact_type,
            title=title,
            extension=Path(safe_filename).suffix,
        )
        target = (artifact_dir / safe_filename).resolve()
        if not target.is_relative_to(artifact_dir):
            raise ArtifactValidationError("artifact path escapes run artifact directory")
        target.write_text(body, encoding="utf-8")
        return {
            "status": "ok",
            "tool": "write_artifact_file",
            "filename": safe_filename,
            "artifact_type": artifact_type,
            "title": title,
            "bytes_written": len(target.read_bytes()),
            "summary": f"artifact file written: {safe_filename}",
        }

    return write_artifact_file


def _validate_filename(filename: str) -> str:
    path = Path(filename)
    if path.is_absolute() or path.name != filename or ".." in path.parts:
        raise ArtifactValidationError("artifact filename must be a non-nested relative basename")
    if filename.startswith("."):
        raise ArtifactValidationError("hidden artifact filename is not allowed")
    if path.suffix not in SUPPORTED_EXTENSIONS:
        raise ArtifactValidationError(f"unsupported artifact extension: {path.suffix}")
    return filename


def _with_frontmatter(*, content: str, artifact_type: str, title: str, extension: str) -> str:
    if extension == ".json":
        return content
    if content.startswith("---\n"):
        return content
    lines = ["---", f"type: {artifact_type}"]
    if title:
        lines.append(f"title: {title}")
    lines.append("---")
    return "\n".join(lines) + "\n\n" + content
```

- [ ] **Step 4: Run tool tests**

Run:

```bash
cd agent_service_v2 && ./.venv/bin/python -m pytest tests/test_artifact_file_tool.py tests/test_artifact_scanner.py tests/test_artifact_manifest.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit guarded tool task**

```bash
git add agent_service_v2/src/agent_service_v2/tools/artifact_files.py agent_service_v2/tests/test_artifact_file_tool.py
git commit -m "添加AIChat受保护产物写入工具"
```

---

### Task 4: Toolkit, Permission, And Prompt Wiring

**Files:**
- Modify: `agent_service_v2/src/agent_service_v2/tools/workbench_toolkit.py`
- Modify: `agent_service_v2/src/agent_service_v2/agents/workbench_factory.py`
- Modify: `agent_service_v2/src/agent_service_v2/agents/permissions.py`
- Modify: `agent_service_v2/src/agent_service_v2/agents/prompts.py`
- Modify: `agent_service_v2/tests/test_workbench_toolkit.py`
- Modify: `agent_service_v2/tests/test_workbench_factory.py`

- [ ] **Step 1: Update toolkit tests first**

Modify `agent_service_v2/tests/test_workbench_toolkit.py` so toolkit construction passes a workspace/run id and no longer expects `draft_study_artifact` in the artifact group:

```python
from agentscope.tool import ToolGroup
from agentscope.workspace import LocalWorkspace

from agent_service_v2.tools.planning import build_planning_group
from agent_service_v2.tools.workbench_placeholders import read_learning_state, review_grounding
from agent_service_v2.tools.workbench_toolkit import build_workbench_tool_groups


def test_workbench_tool_groups_include_guarded_artifact_tool(tmp_path):
    groups = build_workbench_tool_groups(
        memory_tools=[],
        rag_tools=[],
        workspace=LocalWorkspace(workdir=str(tmp_path), workspace_id="ws"),
        run_id="run-1",
    )

    assert [group.name for group in groups] == [
        "planning",
        "learning_state",
        "artifact",
        "review",
    ]
    artifact_group = next(group for group in groups if group.name == "artifact")
    assert [getattr(tool, "name", type(tool).__name__) for tool in artifact_group.tools] == ["write_artifact_file"]
```

Keep the existing planning and placeholder tests for `read_learning_state` and `review_grounding`, but remove the `draft_study_artifact` assertion.

- [ ] **Step 2: Update factory permission test first**

Modify successful `factory.create_agent(...)` calls in `agent_service_v2/tests/test_workbench_factory.py` to pass `run_id="run-1"`, because the guarded artifact tool is run-scoped:

```python
agent = factory.create_agent(
    user_id="u1",
    course_id="c1",
    workspace=workspace,
    run_id="run-1",
)
```

Keep `test_factory_raises_clear_error_without_model` without `run_id`; missing model config should still raise `MissingModelConfigError` before toolkit construction.

Update `test_factory_configures_safe_tool_permission_allow_rules` assertions:

```python
allow_rules = agent.state.permission_context.allow_rules

assert "reset_tools" in allow_rules
assert "read_learning_state" in allow_rules
assert "write_artifact_file" in allow_rules
assert "draft_study_artifact" not in allow_rules
assert "TaskCreate" in allow_rules
```

- [ ] **Step 3: Run toolkit/factory tests and verify they fail**

Run:

```bash
cd agent_service_v2 && ./.venv/bin/python -m pytest tests/test_workbench_toolkit.py tests/test_workbench_factory.py -q
```

Expected: FAIL because `build_workbench_tool_groups` does not accept `workspace`/`run_id` and permissions still allow `draft_study_artifact`.

- [ ] **Step 4: Wire the guarded tool into toolkit**

Modify `agent_service_v2/src/agent_service_v2/tools/workbench_toolkit.py`:

```python
from __future__ import annotations

from agentscope.tool import FunctionTool, ToolBase, ToolGroup
from agentscope.workspace import LocalWorkspace

from agent_service_v2.tools.artifact_files import build_write_artifact_file
from agent_service_v2.tools.planning import build_planning_group
from agent_service_v2.tools.workbench_placeholders import read_learning_state, review_grounding


def build_workbench_tool_groups(
    *,
    memory_tools: list[ToolBase] | None,
    rag_tools: list[ToolBase] | None,
    workspace: LocalWorkspace,
    run_id: str,
) -> list[ToolGroup]:
    groups = [build_planning_group()]
    if memory_tools:
        groups.append(
            ToolGroup(
                name="memory",
                description="Search and update long-term learner memory.",
                tools=memory_tools,
            )
        )
    if rag_tools:
        groups.append(
            ToolGroup(
                name="rag",
                description="Retrieve course-grounded learning context.",
                tools=rag_tools,
            )
        )
    groups.extend(
        [
            ToolGroup(
                name="learning_state",
                description="Read Backend-provided learner state summaries.",
                tools=[FunctionTool(read_learning_state, is_read_only=True)],
            ),
            ToolGroup(
                name="artifact",
                description="Write saveable learning artifacts into the run workspace.",
                tools=[FunctionTool(build_write_artifact_file(workspace=workspace, run_id=run_id))],
            ),
            ToolGroup(
                name="review",
                description="Review generated advice for grounding and safety.",
                tools=[FunctionTool(review_grounding, is_read_only=True)],
            ),
        ]
    )
    return groups
```

- [ ] **Step 5: Pass workspace and run id from factory**

Modify the `Toolkit` construction in `agent_service_v2/src/agent_service_v2/agents/workbench_factory.py`:

```python
        if run_id is None:
            raise ValueError("run_id is required for workbench artifact tools")

        toolkit = Toolkit(
            tool_groups=build_workbench_tool_groups(
                memory_tools=[],
                rag_tools=[],
                workspace=workspace,
                run_id=run_id,
            )
        )
```

- [ ] **Step 6: Update permissions**

Modify `SAFE_WORKBENCH_TOOLS` in `agent_service_v2/src/agent_service_v2/agents/permissions.py`:

```python
SAFE_WORKBENCH_TOOLS = [
    "reset_tools",
    "TaskCreate",
    "TaskGet",
    "TaskList",
    "TaskUpdate",
    "read_learning_state",
    "write_artifact_file",
    "review_grounding",
]
```

- [ ] **Step 7: Update prompt contract**

Modify `agent_service_v2/src/agent_service_v2/agents/prompts.py` so `WORKBENCH_SYSTEM_PROMPT` includes this instruction block:

```text
Workspace artifact rules:
- When the user asks for saveable learning material, lesson pages, worksheets, diagrams, study plans, or resource recommendation documents, call write_artifact_file with the complete artifact body.
- Do not stream the full artifact body in chat after writing the file.
- After writing artifact files, reply in chat with the artifact title, one-sentence summary, and one suggested next action.
- Use Markdown files for reading materials, Mermaid files for diagrams, and JSON files only for supported workspace plugin cards.
```

- [ ] **Step 8: Run toolkit/factory tests**

Run:

```bash
cd agent_service_v2 && ./.venv/bin/python -m pytest tests/test_workbench_toolkit.py tests/test_workbench_factory.py tests/test_artifact_file_tool.py -q
```

Expected: PASS.

- [ ] **Step 9: Commit toolkit wiring**

```bash
git add agent_service_v2/src/agent_service_v2/tools/workbench_toolkit.py agent_service_v2/src/agent_service_v2/agents/workbench_factory.py agent_service_v2/src/agent_service_v2/agents/permissions.py agent_service_v2/src/agent_service_v2/agents/prompts.py agent_service_v2/tests/test_workbench_toolkit.py agent_service_v2/tests/test_workbench_factory.py
git commit -m "接入AIChat工作区产物工具"
```

---

### Task 5: Protocol Adapter Artifact Events

**Files:**
- Modify: `agent_service_v2/src/agent_service_v2/runtime/protocol_adapter.py`
- Modify: `agent_service_v2/src/agent_service_v2/session/workbench_session.py`
- Modify: `agent_service_v2/tests/test_protocol_adapter.py`
- Modify: `agent_service_v2/tests/test_workbench_session.py`

- [ ] **Step 1: Write adapter artifact tests**

Append to `agent_service_v2/tests/test_protocol_adapter.py`:

```python
from agent_service_v2.artifacts.schemas import PublishedArtifact


class FakeArtifactPublisher:
    def __init__(self):
        self.calls = []

    def publish_new(self, *, seq_start=None):
        self.calls.append(seq_start)
        if len(self.calls) == 1:
            return [
                PublishedArtifact(
                    id="artifact_001_functions",
                    file="001-functions.md",
                    type="Markdown",
                    title="函数资料",
                    sha256="abc",
                    props={"title": "函数资料", "content": "# 函数资料\n"},
                    published_seq=seq_start,
                )
            ]
        return []


def test_protocol_adapter_emits_artifact_after_artifact_tool_success():
    publisher = FakeArtifactPublisher()
    adapter = EDUProtocolAdapter(
        run_id="run-1",
        conversation_id="conv-1",
        agent="workbench",
        artifact_publisher=publisher,
    )

    raw_events = [
        ToolCallStartEvent(reply_id="reply-1", tool_call_id="tool-1", tool_call_name="write_artifact_file"),
        ToolResultEndEvent(reply_id="reply-1", tool_call_id="tool-1", state=ToolResultState.SUCCESS),
    ]

    events = [event for raw_event in raw_events for event in adapter.adapt_many(raw_event)]

    assert [event.type for event in events] == [
        EduEventType.TOOL_STARTED,
        EduEventType.TOOL_COMPLETED,
        EduEventType.ARTIFACT_CREATED,
    ]
    assert events[2].payload == {
        "artifact": {
            "id": "artifact_001_functions",
            "type": "Markdown",
            "props": {"title": "函数资料", "content": "# 函数资料\n"},
        }
    }


def test_protocol_adapter_scans_before_workflow_completed():
    publisher = FakeArtifactPublisher()
    adapter = EDUProtocolAdapter(
        run_id="run-1",
        conversation_id="conv-1",
        agent="workbench",
        artifact_publisher=publisher,
    )

    events = adapter.adapt_many(ReplyEndEvent(session_id="conv-1", reply_id="reply-1"))

    assert [event.type for event in events] == [
        EduEventType.ARTIFACT_CREATED,
        EduEventType.WORKFLOW_COMPLETED,
    ]
```

- [ ] **Step 2: Run adapter tests and verify they fail**

Run:

```bash
cd agent_service_v2 && ./.venv/bin/python -m pytest tests/test_protocol_adapter.py -q
```

Expected: FAIL because `EDUProtocolAdapter` does not accept `artifact_publisher`.

- [ ] **Step 3: Update adapter implementation**

Modify `agent_service_v2/src/agent_service_v2/runtime/protocol_adapter.py`:

```python
from agent_service_v2.artifacts.manifest import ArtifactPublisher
```

Update `__init__`:

```python
        artifact_publisher: ArtifactPublisher | None = None,
```

Set:

```python
        self._artifact_publisher = artifact_publisher
```

Replace `adapt_many` with this shape:

```python
    def adapt_many(self, event: Any) -> list[EduEvent]:
        self._capture_event_context(event)
        events: list[EduEvent] = []
        mapped = self._map_event(event)
        if mapped is not None:
            event_type, payload = mapped
            if isinstance(event, ReplyEndEvent):
                events.extend(self._build_artifact_events())
            events.append(self._build_event(event_type, payload))
        if isinstance(event, ToolResultEndEvent):
            plan_payload = self._build_plan_payload_for_tool_result(event)
            if plan_payload is not None:
                events.append(self._build_event(EduEventType.PLAN_UPDATED, plan_payload))
            if self._is_successful_artifact_tool_result(event):
                events.extend(self._build_artifact_events())
        return events
```

Add helper methods:

```python
    def _is_successful_artifact_tool_result(self, event: ToolResultEndEvent) -> bool:
        state = getattr(event.state, "value", event.state)
        return state != "error" and self._tool_names.get(event.tool_call_id) == "write_artifact_file"

    def _build_artifact_events(self) -> list[EduEvent]:
        if self._artifact_publisher is None:
            return []
        seq_start = self._seq + 1
        return [
            self._build_event(EduEventType.ARTIFACT_CREATED, artifact.to_event_payload())
            for artifact in self._artifact_publisher.publish_new(seq_start=seq_start)
        ]
```

- [ ] **Step 4: Wire publisher into session**

Modify `agent_service_v2/src/agent_service_v2/session/workbench_session.py` imports:

```python
from agent_service_v2.artifacts.manifest import ArtifactPublisher
```

Update adapter construction:

```python
        adapter = EDUProtocolAdapter(
            run_id=run.run_id,
            conversation_id=run.conversation_id,
            agent=run.agent,
            artifact_publisher=ArtifactPublisher(
                run_id=run.run_id,
                artifact_dir=run_store.artifact_dir(run.run_id),
            ),
        )
```

- [ ] **Step 5: Run adapter and session tests**

Run:

```bash
cd agent_service_v2 && ./.venv/bin/python -m pytest tests/test_protocol_adapter.py tests/test_workbench_session.py -q
```

Expected: PASS. If `test_workbench_session.py` has strict constructor or event count assertions, update those assertions only where they account for the optional artifact publisher and empty artifact scan.

- [ ] **Step 6: Commit adapter task**

```bash
git add agent_service_v2/src/agent_service_v2/runtime/protocol_adapter.py agent_service_v2/src/agent_service_v2/session/workbench_session.py agent_service_v2/tests/test_protocol_adapter.py agent_service_v2/tests/test_workbench_session.py
git commit -m "从工作区文件发布AIChat产物事件"
```

---

### Task 6: Backend And Frontend Compatibility Polish

**Files:**
- Modify: `backend/tests/test_tutoring_stream_adapter.py`
- Modify: `frontend/src/components/workspace/plugins/MarkdownViewer.jsx`
- Create: `frontend/src/components/workspace/plugins/MarkdownViewer.test.jsx`
- Modify: `frontend/src/components/workspace/AgentWorkspace.test.jsx`

- [ ] **Step 1: Strengthen backend passthrough assertion**

Modify the artifact event fixture in `backend/tests/test_tutoring_stream_adapter.py` to include title:

```python
yield b'data: {"type":"artifact_created","run_id":"run-1","seq":4,"timestamp":"t4","agent":"workbench","payload":{"artifact":{"id":"a1","type":"Markdown","props":{"title":"函数资料","content":"# Plan"}}}}\n\n'
```

Add assertion:

```python
assert decoded[3]["payload"]["artifact"]["props"]["title"] == "函数资料"
```

- [ ] **Step 2: Add frontend Markdown title tests**

Modify `frontend/src/components/workspace/AgentWorkspace.test.jsx` to include Markdown in the existing `PluginRegistry` mock so workspace routing covers Markdown artifact props:

```jsx
vi.mock('./PluginRegistry', () => ({
  PluginRegistry: {
    QuizCard: ({ question }) => <div data-testid="quiz-card">{question}</div>,
    Markdown: ({ title, content }) => (
      <article data-testid="markdown-artifact">
        <h1>{title}</h1>
        <div>{content}</div>
      </article>
    ),
  },
}));

test('renders markdown artifact title and content', () => {
  useChat.mockReturnValue({
    workspaceArtifacts: [
      {
        id: 'artifact_001_functions',
        type: 'Markdown',
        props: { title: '函数资料', content: '# 函数资料' },
      },
    ],
  });

  render(<AgentWorkspace />);

  expect(screen.getByTestId('markdown-artifact')).toBeDefined();
  expect(screen.getByText('函数资料')).toBeDefined();
  expect(screen.getByText('# 函数资料')).toBeDefined();
});
```

Create `frontend/src/components/workspace/plugins/MarkdownViewer.test.jsx` to test the real Markdown plugin title support:

```jsx
import { render, screen } from '@testing-library/react';
import { expect, test } from 'vitest';
import MarkdownViewer from './MarkdownViewer';

test('renders workspace markdown title and content', () => {
  render(<MarkdownViewer title="函数资料" content="# 函数资料\n\n正文" />);

  expect(screen.getByText('函数资料')).toBeDefined();
  expect(screen.getByRole('heading', { name: '函数资料' })).toBeDefined();
  expect(screen.getByText('正文')).toBeDefined();
});
```

- [ ] **Step 3: Run compatibility tests and verify frontend title test fails if component lacks title support**

Run:

```bash
cd backend && ../.venv/bin/python -m pytest tests/test_tutoring_stream_adapter.py -q
cd frontend && npm run test:unit -- src/components/workspace/AgentWorkspace.test.jsx src/components/workspace/plugins/MarkdownViewer.test.jsx
```

Expected: backend PASS; `AgentWorkspace.test.jsx` PASS with the mock; `MarkdownViewer.test.jsx` FAIL until the real `MarkdownViewer` accepts `title`.

- [ ] **Step 4: Add title prop to workspace Markdown viewer**

Modify `frontend/src/components/workspace/plugins/MarkdownViewer.jsx`:

```jsx
export default function MarkdownViewer({ title, content }) {
  return (
    <div className="bg-white border border-slate-200 rounded-lg p-6 shadow-sm w-full">
      {title ? (
        <div className="mb-5 border-b border-slate-100 pb-3">
          <h1 className="text-xl font-semibold text-slate-900">{title}</h1>
        </div>
      ) : null}
      <ReactMarkdown remarkPlugins={[remarkGfm]} components={COMPONENTS}>
        {content}
      </ReactMarkdown>
    </div>
  );
}
```

- [ ] **Step 5: Run frontend/backend compatibility tests**

Run:

```bash
cd backend && ../.venv/bin/python -m pytest tests/test_tutoring_stream_adapter.py -q
cd frontend && npm run test:unit -- src/components/workspace/AgentWorkspace.test.jsx src/components/workspace/plugins/MarkdownViewer.test.jsx src/context/ChatContext.test.jsx
```

Expected: PASS.

- [ ] **Step 6: Commit compatibility task**

```bash
git add backend/tests/test_tutoring_stream_adapter.py frontend/src/components/workspace/plugins/MarkdownViewer.jsx frontend/src/components/workspace/plugins/MarkdownViewer.test.jsx frontend/src/components/workspace/AgentWorkspace.test.jsx
git commit -m "完善AIChat产物前后端兼容测试"
```

---

### Task 7: Full Verification, WorkLine, And Final Commit

**Files:**
- Modify: `WorkLine.md`

- [ ] **Step 1: Run Agent Service focused tests**

Run:

```bash
cd agent_service_v2 && ./.venv/bin/python -m pytest tests/test_artifact_scanner.py tests/test_artifact_manifest.py tests/test_artifact_file_tool.py tests/test_workbench_toolkit.py tests/test_workbench_factory.py tests/test_protocol_adapter.py tests/test_workbench_session.py -q
```

Expected: PASS.

- [ ] **Step 2: Run Agent Service syntax check**

Run:

```bash
cd agent_service_v2 && ./.venv/bin/python -m py_compile \
  src/agent_service_v2/artifacts/schemas.py \
  src/agent_service_v2/artifacts/scanner.py \
  src/agent_service_v2/artifacts/manifest.py \
  src/agent_service_v2/tools/artifact_files.py \
  src/agent_service_v2/tools/workbench_toolkit.py \
  src/agent_service_v2/runtime/protocol_adapter.py \
  src/agent_service_v2/session/workbench_session.py
```

Expected: no output and exit code 0.

- [ ] **Step 3: Run Backend focused tests**

Run:

```bash
cd backend && ../.venv/bin/python -m pytest tests/test_tutoring_stream_adapter.py -q
```

Expected: PASS.

- [ ] **Step 4: Run Frontend focused tests, lint, and build**

Run:

```bash
cd frontend && npm run test:unit -- src/components/workspace/AgentWorkspace.test.jsx src/components/workspace/plugins/MarkdownViewer.test.jsx src/context/ChatContext.test.jsx
cd frontend && npm run lint
cd frontend && npm run build
```

Expected: tests PASS, lint PASS, build PASS. Existing chunk-size warnings can remain if they match the current baseline.

- [ ] **Step 5: Append WorkLine record**

Append this entry to `WorkLine.md` and replace the verification lines with actual command results:

```markdown
### 2026-07-01 — 实现 AIChat 工作区文件产物链路

**涉及文件：**
- `agent_service_v2/src/agent_service_v2/artifacts/`
- `agent_service_v2/src/agent_service_v2/tools/artifact_files.py`
- `agent_service_v2/src/agent_service_v2/tools/workbench_toolkit.py`
- `agent_service_v2/src/agent_service_v2/agents/workbench_factory.py`
- `agent_service_v2/src/agent_service_v2/agents/permissions.py`
- `agent_service_v2/src/agent_service_v2/agents/prompts.py`
- `agent_service_v2/src/agent_service_v2/runtime/protocol_adapter.py`
- `agent_service_v2/src/agent_service_v2/session/workbench_session.py`
- `agent_service_v2/src/agent_service_v2/workspaces/run_store.py`
- `backend/tests/test_tutoring_stream_adapter.py`
- `frontend/src/components/workspace/plugins/MarkdownViewer.jsx`
- `frontend/src/components/workspace/plugins/MarkdownViewer.test.jsx`
- `frontend/src/components/workspace/AgentWorkspace.test.jsx`

**核心改动：**
将 AIChat 的 saveable 内容从占位 `draft_study_artifact` 改为受保护的 `write_artifact_file` 工作区写入链路。Agent Service 在 run 级 `artifacts/` 目录扫描 Markdown、Mermaid 和 JSON plugin 文件，通过 `manifest.json` 去重并发布 `artifact_created`，让前端 Agent 工作区成为学习资料的展示位置。Backend 保持 SSE 透传和文本持久化边界，不直接持久化 artifact body。

**验证结果：**
- 前端 lint / build：通过 `npm run lint`、`npm run build`
- 后端 py_compile / pytest：通过 `../.venv/bin/python -m pytest tests/test_tutoring_stream_adapter.py -q`
- Agent pytest：通过 focused artifact/toolkit/adapter/session tests

**接口漂移：** 无。复用既有 `artifact_created` SSE 类型和 `payload.artifact.{id,type,props}` 结构。
```

- [ ] **Step 6: Check git diff and file sizes**

Run:

```bash
git status --short
git diff --stat
wc -l agent_service_v2/src/agent_service_v2/artifacts/scanner.py agent_service_v2/src/agent_service_v2/artifacts/manifest.py agent_service_v2/src/agent_service_v2/tools/artifact_files.py
```

Expected: only intended files are modified; new Python files stay focused and near or below the project guidance threshold.

- [ ] **Step 7: Commit final WorkLine update if it was not included earlier**

```bash
git add WorkLine.md
git commit -m "记录AIChat工作区产物链路验证"
```

If Task 1-6 commits already included all code and Task 7 only changes `WorkLine.md`, keep this documentation commit. If the implementation was intentionally batched into fewer commits, make one final commit containing the remaining intended files with message `实现AIChat工作区文件产物链路`.

---

## Self-Review

- Spec coverage: The plan covers guarded writing, scanner, manifest, artifact event mapping, backend forwarding, frontend Markdown rendering, prompt rules, safety guardrails, tests, WorkLine, and no new SSE event type.
- Type consistency: The plan uses `write_artifact_file(filename, content, artifact_type='Markdown', title='')`, `ArtifactPublisher.publish_new(seq_start=...)`, and `PublishedArtifact.to_event_payload()` consistently across tool, scanner, manifest, and adapter tasks.
- Boundary check: Agent Service writes only inside AgentScope workspace files; Backend does not import Agent Service modules; Agent Service does not write MySQL; frontend does not call Agent Service directly.
- Execution order: Each task has a failing test step, implementation step, verification step, and commit step.
