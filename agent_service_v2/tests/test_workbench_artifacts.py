from pathlib import Path

from agent_service_v2.workspaces.workbench_artifacts import resolve_workbench_artifact
from agent_service_v2.workspaces.workbench_workspace_manager import (
    WorkbenchWorkspaceManager,
)
from agent_service_v2.main import app


def test_workbench_artifact_route_is_exposed_by_v2_app():
    assert "/agent/v2/workbench/artifacts" in app.openapi()["paths"]


def test_resolve_workbench_artifact_returns_latest_run_file(tmp_path: Path):
    manager = WorkbenchWorkspaceManager(tmp_path)
    workspace = manager.get_workspace(
        user_id="user-1",
        course_id=None,
        conversation_id="conv-1",
    )
    runs = Path(workspace.workdir) / "runs"
    older = runs / "run_001" / "artifacts"
    latest = runs / "run_002" / "artifacts"
    older.mkdir(parents=True)
    latest.mkdir(parents=True)
    (older / "lesson.md").write_text("old", encoding="utf-8")
    expected = latest / "lesson.md"
    expected.write_text("new", encoding="utf-8")

    assert resolve_workbench_artifact(
        manager=manager,
        user_id="user-1",
        course_id=None,
        conversation_id="conv-1",
        filename="lesson.md",
    ) == expected


def test_resolve_workbench_artifact_rejects_path_traversal(tmp_path: Path):
    manager = WorkbenchWorkspaceManager(tmp_path)

    assert resolve_workbench_artifact(
        manager=manager,
        user_id="user-1",
        course_id="course-1",
        conversation_id="conv-1",
        filename="../../secret.txt",
    ) is None
    assert resolve_workbench_artifact(
        manager=manager,
        user_id="user-1",
        course_id="course-1",
        conversation_id="conv-1",
        filename="%252e%252e%252fsecret.txt",
    ) is None
