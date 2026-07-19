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
        file_to_idx = {item["file"]: i for i, item in enumerate(manifest["artifacts"])}
        published: list[PublishedArtifact] = []
        for scanned in ArtifactScanner(self._artifact_dir).scan():
            published_seq = None if seq_start is None else seq_start + len(published)
            
            if scanned.file in file_to_idx:
                idx = file_to_idx[scanned.file]
                existing_record = manifest["artifacts"][idx]
                if existing_record["sha256"] == scanned.sha256:
                    continue  # skip if content is identical
                
                # Keep same ID, update content hash and seq
                artifact_id = existing_record["id"]
                existing_record.update({
                    "sha256": scanned.sha256,
                    "published_seq": published_seq,
                    "updated_at": datetime.now(UTC).isoformat(),
                })
            else:
                artifact_id = self._next_artifact_id(scanned.file, manifest["artifacts"])
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
