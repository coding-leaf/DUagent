import json
from pathlib import Path

from agent_service_v2.workspaces.run_store import WorkbenchRunStore
from agent_service_v2.workspaces.workbench_workspace_manager import WorkbenchWorkspaceManager


def test_run_store_writes_state_events_and_review_inside_workspace(tmp_path: Path):
    workspace = WorkbenchWorkspaceManager(root_dir=tmp_path).get_workspace(
        user_id="u1",
        course_id="c1",
        conversation_id="conv1",
    )
    store = WorkbenchRunStore(workspace=workspace)

    store.write_state("run-1", {"status": "running"})
    store.append_event("run-1", {"type": "workflow_started"})
    store.append_event("run-1", {"type": "workflow_completed"})
    store.write_review("run-1", {"action": "allow"})

    run_dir = Path(workspace.workdir) / "runs" / "run-1"
    assert json.loads((run_dir / "state.json").read_text()) == {"status": "running"}
    assert [
        json.loads(line)["type"]
        for line in (run_dir / "events.jsonl").read_text().splitlines()
    ] == ["workflow_started", "workflow_completed"]
    assert json.loads((run_dir / "review.json").read_text()) == {"action": "allow"}
    assert run_dir.resolve().is_relative_to(Path(workspace.workdir).resolve())
