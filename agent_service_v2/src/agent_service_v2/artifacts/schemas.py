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
    "CodeSandboxCard",
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
                "title": self.title,
                "props": self.props,
            }
        }
