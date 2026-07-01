import json

from agentscope.workspace import LocalWorkspace

from agent_service_v2.artifacts.manifest import ArtifactPublisher
from agent_service_v2.workspaces.run_store import WorkbenchRunStore


def test_run_store_exposes_run_and_artifact_dirs(tmp_path):
    store = WorkbenchRunStore(workspace=LocalWorkspace(workdir=str(tmp_path), workspace_id="ws"))

    assert store.run_dir("run/1") == tmp_path / "runs" / "run_1"
    assert store.artifact_dir("run/1") == tmp_path / "runs" / "run_1" / "artifacts"
    assert store.artifact_dir("run/1").exists()


def test_publisher_emits_new_artifact_once_and_writes_manifest(tmp_path):
    artifact_dir = tmp_path / "artifacts"
    artifact_dir.mkdir()
    (artifact_dir / "001-functions.md").write_text(
        "---\ntype: Markdown\ntitle: 函数资料\n---\n\n# 函数资料\n",
        encoding="utf-8",
    )
    publisher = ArtifactPublisher(run_id="run-1", artifact_dir=artifact_dir)

    first = publisher.publish_new(seq_start=7)
    second = publisher.publish_new(seq_start=8)

    assert len(first) == 1
    assert second == []
    assert first[0].id == "artifact_001_functions"
    assert first[0].published_seq == 7
    assert first[0].to_event_payload() == {
        "artifact": {
            "id": "artifact_001_functions",
            "type": "Markdown",
            "props": {"title": "函数资料", "content": "# 函数资料\n"},
        }
    }
    manifest = json.loads((artifact_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["version"] == 1
    assert manifest["run_id"] == "run-1"
    assert manifest["artifacts"][0]["file"] == "001-functions.md"


def test_publisher_reemits_changed_file_with_new_id(tmp_path):
    artifact_dir = tmp_path / "artifacts"
    artifact_dir.mkdir()
    path = artifact_dir / "001-functions.md"
    path.write_text("# v1\n", encoding="utf-8")
    publisher = ArtifactPublisher(run_id="run-1", artifact_dir=artifact_dir)

    first = publisher.publish_new(seq_start=1)
    path.write_text("# v2\n", encoding="utf-8")
    second = publisher.publish_new(seq_start=2)

    assert first[0].id == "artifact_001_functions"
    assert second[0].id == "artifact_001_functions_2"
    assert second[0].props["content"] == "# v2\n"
