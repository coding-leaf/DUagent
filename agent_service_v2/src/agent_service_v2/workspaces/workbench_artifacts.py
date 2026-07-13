from pathlib import Path

from agent_service_v2.workspaces.workbench_workspace_manager import (
    WorkbenchWorkspaceManager,
)


def resolve_workbench_artifact(
    *,
    manager: WorkbenchWorkspaceManager,
    user_id: str,
    course_id: str | None,
    conversation_id: str,
    filename: str,
) -> Path | None:
    if not _safe_filename(filename):
        return None

    workspace = manager.get_workspace(
        user_id=user_id,
        course_id=course_id,
        conversation_id=conversation_id,
    )
    runs_dir = Path(workspace.workdir) / "runs"
    if not runs_dir.is_dir():
        return None

    for run_dir in sorted(runs_dir.iterdir(), reverse=True):
        artifacts_dir = (run_dir / "artifacts").resolve()
        candidate = (artifacts_dir / filename).resolve()
        if (
            run_dir.name.startswith("run_")
            and run_dir.is_dir()
            and candidate.is_relative_to(artifacts_dir)
            and candidate.is_file()
        ):
            return candidate
    return None


def _safe_filename(filename: str) -> bool:
    return bool(
        filename
        and filename not in {".", ".."}
        and "/" not in filename
        and "\\" not in filename
        and "%" not in filename
        and "\x00" not in filename
        and all(ord(character) >= 32 for character in filename)
        and Path(filename).name == filename
    )
