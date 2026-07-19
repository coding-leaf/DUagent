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
from agent_service_v2.artifacts.validation import validate_json_artifact_payload


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
    if body.startswith("\n"):
        body = body[1:]
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
    parsed = validate_json_artifact_payload(parsed, filename)
    artifact_type = parsed.get("type")
    if not isinstance(artifact_type, str):
        raise ArtifactValidationError(f"json artifact type is required: {filename}")
    props = parsed.get("props", {})
    if not isinstance(props, dict):
        raise ArtifactValidationError(f"json artifact props must be an object: {filename}")
    title = parsed.get("title")
    if title is not None and not isinstance(title, str):
        raise ArtifactValidationError(f"json artifact title must be a string: {filename}")
    return artifact_type, title, props
