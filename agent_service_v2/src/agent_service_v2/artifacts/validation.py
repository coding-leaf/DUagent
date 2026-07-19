from __future__ import annotations

from typing import Any

from agent_service_v2.artifacts.schemas import ArtifactValidationError


CODE_SANDBOX_LANGUAGES = {"c", "cpp", "python", "java", "go", "javascript"}
CODE_SANDBOX_REQUIRED_PROPS = ("question_text", "code", "language", "default_stdin")
CODE_PROBLEM_REQUIRED_PROPS = ("problem_id", "language")
QUIZ_PRACTICE_REQUIRED_PROPS = ("course_id", "question_ids")


def validate_json_artifact_payload(
    payload: dict[str, Any],
    filename: str,
    artifact_type_hint: str | None = None,
    title_hint: str | None = None,
) -> dict[str, Any]:
    artifact_type = payload.get("type") or artifact_type_hint
    if artifact_type is None and _has_top_level_code_sandbox_props(payload):
        artifact_type = "CodeSandboxCard"
    if artifact_type == "CodeSandboxCard":
        return _normalize_code_sandbox_card(payload, filename, title_hint)
    if artifact_type == "QuizCard" and isinstance(payload.get("props"), dict):
        if all(key in payload["props"] for key in QUIZ_PRACTICE_REQUIRED_PROPS):
            return _normalize_quiz_practice_card(payload, filename, title_hint)
    return payload


def _normalize_quiz_practice_card(
    payload: dict[str, Any], filename: str, title_hint: str | None
) -> dict[str, Any]:
    props = payload["props"]
    course_id = props.get("course_id")
    question_ids = props.get("question_ids")
    if not isinstance(course_id, str) or not course_id:
        raise ArtifactValidationError(f"QuizCard props.course_id must be a string: {filename}")
    if (
        not isinstance(question_ids, list)
        or not 1 <= len(question_ids) <= 8
        or any(not isinstance(item, str) or not item for item in question_ids)
    ):
        raise ArtifactValidationError(
            f"QuizCard props.question_ids must contain 1 to 8 strings: {filename}"
        )
    normalized: dict[str, Any] = {
        "type": "QuizCard",
        "props": {"course_id": course_id, "question_ids": question_ids},
    }
    title = payload.get("title") or title_hint
    if title is not None:
        if not isinstance(title, str):
            raise ArtifactValidationError(f"json artifact title must be a string: {filename}")
        normalized["title"] = title
    return normalized


def _has_top_level_code_sandbox_props(payload: dict[str, Any]) -> bool:
    return all(key in payload for key in CODE_SANDBOX_REQUIRED_PROPS)


def _normalize_code_sandbox_card(
    payload: dict[str, Any],
    filename: str,
    title_hint: str | None,
) -> dict[str, Any]:
    raw_props = payload.get("props")
    if isinstance(raw_props, dict):
        source = raw_props
    else:
        source = payload

    if all(key in source for key in CODE_PROBLEM_REQUIRED_PROPS):
        return _normalize_persisted_code_problem_card(payload, source, filename, title_hint)

    props: dict[str, str] = {}
    for key in CODE_SANDBOX_REQUIRED_PROPS:
        value = source.get(key)
        if not isinstance(value, str):
            raise ArtifactValidationError(
                f"CodeSandboxCard props.{key} must be a string: {filename}",
            )
        props[key] = value

    language = props["language"]
    if language not in CODE_SANDBOX_LANGUAGES:
        raise ArtifactValidationError(
            f"unsupported CodeSandboxCard language: {language}",
        )

    normalized: dict[str, Any] = {
        "type": "CodeSandboxCard",
        "props": props,
    }
    title = payload.get("title") or title_hint
    if title is not None:
        if not isinstance(title, str):
            raise ArtifactValidationError(f"json artifact title must be a string: {filename}")
        normalized["title"] = title
    return normalized


def _normalize_persisted_code_problem_card(
    payload: dict[str, Any],
    source: dict[str, Any],
    filename: str,
    title_hint: str | None,
) -> dict[str, Any]:
    problem_id = source.get("problem_id")
    language = source.get("language")
    if not isinstance(problem_id, str) or not problem_id:
        raise ArtifactValidationError(f"CodeSandboxCard props.problem_id must be a string: {filename}")
    if language not in CODE_SANDBOX_LANGUAGES:
        raise ArtifactValidationError(f"unsupported CodeSandboxCard language: {language}")
    normalized: dict[str, Any] = {
        "type": "CodeSandboxCard",
        "props": {"problem_id": problem_id, "language": language},
    }
    title = payload.get("title") or title_hint
    if title is not None:
        if not isinstance(title, str):
            raise ArtifactValidationError(f"json artifact title must be a string: {filename}")
        normalized["title"] = title
    return normalized
