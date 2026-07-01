from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from agentscope.workspace import LocalWorkspace


class WorkbenchRunStore:
    def __init__(self, *, workspace: LocalWorkspace) -> None:
        self._workspace = workspace
        self._root = Path(workspace.workdir).resolve()

    def write_state(self, run_id: str, payload: dict[str, Any]) -> None:
        self._write_json(run_id, "state.json", payload)

    def append_event(self, run_id: str, payload: dict[str, Any]) -> None:
        run_dir = self._run_dir(run_id)
        with (run_dir / "events.jsonl").open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(payload, ensure_ascii=False) + "\n")

    def write_review(self, run_id: str, payload: dict[str, Any]) -> None:
        self._write_json(run_id, "review.json", payload)

    def run_dir(self, run_id: str) -> Path:
        return self._run_dir(run_id)

    def artifact_dir(self, run_id: str) -> Path:
        artifact_dir = self._run_dir(run_id) / "artifacts"
        artifact_dir.mkdir(parents=True, exist_ok=True)
        return artifact_dir

    def _write_json(self, run_id: str, filename: str, payload: dict[str, Any]) -> None:
        path = self._run_dir(run_id) / filename
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def _run_dir(self, run_id: str) -> Path:
        safe_run_id = "".join(ch if ch.isalnum() or ch in "_.-" else "_" for ch in run_id).strip("._-")
        if not safe_run_id:
            safe_run_id = "run"
        run_dir = (self._root / "runs" / safe_run_id).resolve()
        if not run_dir.is_relative_to(self._root):
            raise ValueError("run path escapes workspace")
        run_dir.mkdir(parents=True, exist_ok=True)
        return run_dir
