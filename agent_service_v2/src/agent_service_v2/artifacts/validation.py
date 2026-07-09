from __future__ import annotations

from typing import Any

from agent_service_v2.artifacts.schemas import ArtifactValidationError


CODE_SANDBOX_LANGUAGES = {"c", "cpp", "python", "java", "go", "javascript"}
CODE_SANDBOX_REQUIRED_PROPS = ("question_text", "code", "language", "default_stdin")


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
    return payload


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
