from __future__ import annotations

import json
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
from agent_service_v2.artifacts.validation import validate_json_artifact_payload
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
        _validate_json_content_for_write(
            filename=safe_filename,
            content=content,
        )
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
