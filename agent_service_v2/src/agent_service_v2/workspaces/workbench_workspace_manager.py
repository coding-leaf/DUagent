from __future__ import annotations

import re
from pathlib import Path

from agentscope.workspace import LocalWorkspace


_SAFE_PART_RE = re.compile(r"[^A-Za-z0-9_.-]+")


class WorkbenchWorkspaceManager:
    def __init__(self, root_dir: str | Path) -> None:
        self.root_dir = Path(root_dir).resolve()

    def get_workspace(
        self,
        *,
        user_id: str,
        course_id: str | None,
        conversation_id: str,
    ) -> LocalWorkspace:
        safe_user = _safe_part(user_id, prefix="u")
        safe_course = _safe_part(course_id or "global", prefix="c")
        safe_conversation = _safe_part(conversation_id, prefix="conv")
        workspace_id = "__".join(["ai-chat", safe_user, safe_course, safe_conversation])
        workdir = (self.root_dir / "ai-chat" / safe_user / safe_course / safe_conversation).resolve()

        if not workdir.is_relative_to(self.root_dir):
            raise ValueError("workspace path escapes root_dir")

        return LocalWorkspace(workdir=str(workdir), workspace_id=workspace_id)


def _safe_part(value: str, *, prefix: str) -> str:
    cleaned = _SAFE_PART_RE.sub("_", value).strip("._-")
    if not cleaned:
        cleaned = "empty"
    return f"{prefix}_{cleaned}"
