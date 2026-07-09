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
