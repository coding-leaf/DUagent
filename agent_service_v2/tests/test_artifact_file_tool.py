import json

import pytest
from agentscope.workspace import LocalWorkspace

from agent_service_v2.tools.artifact_files import build_write_artifact_file


def test_write_artifact_file_writes_markdown_with_frontmatter(tmp_path):
    tool = build_write_artifact_file(
        workspace=LocalWorkspace(workdir=str(tmp_path), workspace_id="ws"),
        run_id="run-1",
    )

    result = tool(
        filename="001-functions.md",
        content="# 函数资料\n",
        artifact_type="Markdown",
        title="函数资料",
    )

    path = tmp_path / "runs" / "run-1" / "artifacts" / "001-functions.md"
    assert result == {
        "status": "ok",
        "tool": "write_artifact_file",
        "filename": "001-functions.md",
        "artifact_type": "Markdown",
        "title": "函数资料",
        "bytes_written": len(path.read_bytes()),
        "summary": "artifact file written: 001-functions.md",
    }
    assert path.read_text(encoding="utf-8") == (
        "---\n"
        "type: Markdown\n"
        "title: 函数资料\n"
        "---\n\n"
        "# 函数资料\n"
    )


@pytest.mark.parametrize(
    "filename",
    ["/tmp/x.md", "../x.md", ".hidden.md", "nested/x.md", "bad.exe"],
)
def test_write_artifact_file_rejects_unsafe_filename(tmp_path, filename):
    tool = build_write_artifact_file(
        workspace=LocalWorkspace(workdir=str(tmp_path), workspace_id="ws"),
        run_id="run-1",
    )

    with pytest.raises(ValueError):
        tool(filename=filename, content="# x\n", artifact_type="Markdown", title="x")


def test_write_artifact_file_rejects_unsupported_type(tmp_path):
    tool = build_write_artifact_file(
        workspace=LocalWorkspace(workdir=str(tmp_path), workspace_id="ws"),
        run_id="run-1",
    )

    with pytest.raises(ValueError, match="unsupported artifact type"):
        tool(filename="x.md", content="# x\n", artifact_type="UnknownType", title="x")


def test_write_artifact_file_rejects_more_than_ten_artifacts(tmp_path):
    artifact_dir = tmp_path / "runs" / "run-1" / "artifacts"
    artifact_dir.mkdir(parents=True)
    for index in range(10):
        (artifact_dir / f"{index}.md").write_text("# x\n", encoding="utf-8")
    tool = build_write_artifact_file(
        workspace=LocalWorkspace(workdir=str(tmp_path), workspace_id="ws"),
        run_id="run-1",
    )

    with pytest.raises(ValueError, match="artifact count limit"):
        tool(filename="overflow.md", content="# x\n", artifact_type="Markdown", title="x")


def test_write_artifact_file_rejects_code_sandbox_card_missing_language_before_write(tmp_path):
    tool = build_write_artifact_file(
        workspace=LocalWorkspace(workdir=str(tmp_path), workspace_id="ws"),
        run_id="run-1",
    )
    content = json.dumps(
        {
            "type": "CodeSandboxCard",
            "props": {
                "question_text": "修复这段 C 代码",
                "code": "#include<stdio.h>\\nint main(){return 0;}",
                "default_stdin": "",
            },
        },
        ensure_ascii=False,
    )

    with pytest.raises(ValueError, match="language"):
        tool(
            filename="code-card.json",
            content=content,
            artifact_type="CodeSandboxCard",
            title="代码练习",
        )

    path = tmp_path / "runs" / "run-1" / "artifacts" / "code-card.json"
    assert not path.exists()


def test_write_artifact_file_accepts_valid_code_sandbox_card(tmp_path):
    tool = build_write_artifact_file(
        workspace=LocalWorkspace(workdir=str(tmp_path), workspace_id="ws"),
        run_id="run-1",
    )
    content = json.dumps(
        {
            "type": "CodeSandboxCard",
            "props": {
                "question_text": "修复这段 C 代码",
                "code": "#include<stdio.h>\\nint main(){return 0;}",
                "language": "c",
                "default_stdin": "",
            },
        },
        ensure_ascii=False,
    )

    result = tool(
        filename="code-card.json",
        content=content,
        artifact_type="CodeSandboxCard",
        title="代码练习",
    )

    path = tmp_path / "runs" / "run-1" / "artifacts" / "code-card.json"
    assert result["status"] == "ok"
    assert result["artifact_type"] == "CodeSandboxCard"
    assert path.read_text(encoding="utf-8") == content
