from __future__ import annotations

import json
import re
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
from agent_service_v2.tools.contracts import edu_tool_result


def build_write_artifact_file(*, workspace: LocalWorkspace, run_id: str) -> Callable[..., dict]:
    store = WorkbenchRunStore(workspace=workspace)
    artifact_dir = store.artifact_dir(run_id)

    def write_artifact_file(
        filename: str,
        content: str,
        artifact_type: str = "Markdown",
        title: str = "",
    ) -> dict:
        """Write one Markdown lesson or Mermaid diagram into the run workspace.

        Args:
            filename: A basename ending in .md for Markdown or .mmd for Mermaid.
            content: The complete learning material or Mermaid source.
            artifact_type: Either Markdown or Mermaid and matching the extension.
            title: A short student-facing artifact title.
        """
        expected = {"Markdown": ".md", "Mermaid": ".mmd"}
        if artifact_type not in expected or Path(filename).suffix != expected[artifact_type]:
            raise ArtifactValidationError(
                "write_artifact_file only supports Markdown and Mermaid with matching extensions"
            )
        result = _persist_artifact(
            artifact_dir=artifact_dir,
            filename=filename,
            content=content,
            artifact_type=artifact_type,
            title=title,
        )
        return edu_tool_result(
            status="ok",
            summary=result["summary"],
            data={key: value for key, value in result.items() if key not in {"status", "summary"}},
        )

    return write_artifact_file


def build_create_code_sandbox_card(
    *, workspace: LocalWorkspace, run_id: str
) -> Callable[..., dict]:
    artifact_dir = WorkbenchRunStore(workspace=workspace).artifact_dir(run_id)

    def create_code_sandbox_card(problem_id: str, language: str, title: str) -> dict:
        """Create a practice card for an already published private code problem.

        Args:
            problem_id: The non-empty problem_id returned with status published.
            language: One of c, cpp, python, java, go, or javascript.
            title: A short student-facing title for the practice tab.
        """
        if not re.fullmatch(r"[A-Za-z0-9_-]+", problem_id):
            raise ArtifactValidationError("problem_id contains unsupported characters")
        if language not in {"c", "cpp", "python", "java", "go", "javascript"}:
            raise ArtifactValidationError("unsupported CodeSandboxCard language")
        content = json.dumps(
            {
                "type": "CodeSandboxCard",
                "title": title,
                "props": {"problem_id": problem_id, "language": language},
            },
            ensure_ascii=False,
        )
        return _persist_artifact(
            artifact_dir=artifact_dir,
            filename=f"code-problem-{problem_id}.json",
            content=content,
            artifact_type="CodeSandboxCard",
            title=title,
        )

    return create_code_sandbox_card


def build_create_quiz_practice_card(
    *, workspace: LocalWorkspace, run_id: str
) -> Callable[..., dict]:
    artifact_dir = WorkbenchRunStore(workspace=workspace).artifact_dir(run_id)

    def create_quiz_practice_card(
        course_id: str, question_ids: list[str], title: str
    ) -> dict:
        if not re.fullmatch(r"[A-Za-z0-9_-]+", course_id):
            raise ArtifactValidationError("course_id contains unsupported characters")
        if (
            not 1 <= len(question_ids) <= 8
            or any(not re.fullmatch(r"[A-Za-z0-9_-]+", item) for item in question_ids)
        ):
            raise ArtifactValidationError("question_ids must contain 1 to 8 safe IDs")
        content = json.dumps(
            {
                "type": "QuizCard",
                "title": title,
                "props": {"course_id": course_id, "question_ids": question_ids},
            },
            ensure_ascii=False,
        )
        return _persist_artifact(
            artifact_dir=artifact_dir,
            filename=f"choice-quiz-{question_ids[0]}.json",
            content=content,
            artifact_type="QuizCard",
            title=title,
        )

    return create_quiz_practice_card


def _persist_artifact(
    *, artifact_dir: Path, filename: str, content: str, artifact_type: str, title: str
) -> dict:
    safe_filename = _validate_filename(filename)
    if artifact_type not in SUPPORTED_ARTIFACT_TYPES:
        raise ArtifactValidationError(f"unsupported artifact type: {artifact_type}")
    content = _normalize_json_content_for_write(
        filename=safe_filename,
        content=content,
        artifact_type=artifact_type,
        title=title,
    )
    if len(content.encode("utf-8")) > MAX_ARTIFACT_BYTES:
        raise ArtifactValidationError(f"artifact content exceeds {MAX_ARTIFACT_BYTES} bytes")
    existing = [path for path in artifact_dir.iterdir() if path.is_file() and path.name != "manifest.json"]
    if len(existing) >= MAX_ARTIFACTS_PER_RUN and not (artifact_dir / safe_filename).exists():
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


def _normalize_json_content_for_write(
    *,
    filename: str,
    content: str,
    artifact_type: str,
    title: str,
) -> str:
    if Path(filename).suffix != ".json":
        return content
    try:
        payload = json.loads(content)
    except json.JSONDecodeError as exc:
        raise ArtifactValidationError(f"invalid json artifact: {filename}") from exc
    if not isinstance(payload, dict):
        raise ArtifactValidationError(f"json artifact must be an object: {filename}")
    normalized = validate_json_artifact_payload(
        payload,
        filename,
        artifact_type_hint=artifact_type,
        title_hint=title or None,
    )
    if normalized.get("type") == "CodeSandboxCard":
        return json.dumps(normalized, ensure_ascii=False)
    return content


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
