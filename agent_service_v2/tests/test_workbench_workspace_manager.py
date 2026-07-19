from pathlib import Path

from agentscope.workspace import LocalWorkspace

from agent_service_v2.workspaces.workbench_workspace_manager import (
    WorkbenchWorkspaceManager,
)


def test_workspace_manager_creates_sanitized_local_workspace(tmp_path: Path):
    manager = WorkbenchWorkspaceManager(root_dir=tmp_path)

    workspace = manager.get_workspace(
        user_id="user/1",
        course_id="course:2",
        conversation_id="../conv 3",
    )

    assert isinstance(workspace, LocalWorkspace)
    assert Path(workspace.workdir).is_relative_to(tmp_path)
    assert ".." not in Path(workspace.workdir).parts
    assert "/" not in workspace.workspace_id
    assert workspace.workspace_id.startswith("ai-chat__")


def test_workspace_manager_isolates_different_conversations(tmp_path: Path):
    manager = WorkbenchWorkspaceManager(root_dir=tmp_path)

    first = manager.get_workspace(
        user_id="user-1",
        course_id="course-1",
        conversation_id="conv-1",
    )
    second = manager.get_workspace(
        user_id="user-1",
        course_id="course-1",
        conversation_id="conv-2",
    )

    assert first.workspace_id != second.workspace_id
    assert first.workdir != second.workdir


def test_workspace_manager_uses_global_course_scope_when_course_missing(tmp_path: Path):
    manager = WorkbenchWorkspaceManager(root_dir=tmp_path)

    workspace = manager.get_workspace(
        user_id="user-1",
        course_id=None,
        conversation_id="conv-1",
    )

    assert "global" in workspace.workspace_id
