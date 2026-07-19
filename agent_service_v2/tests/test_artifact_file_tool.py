import json

import pytest
from agentscope.workspace import LocalWorkspace

from agent_service_v2.tools.artifact_files import (
    build_create_code_sandbox_card,
    build_write_artifact_file,
)


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
    assert result["outcome"] == "success"
    assert result["status"] == "ok"
    assert result["filename"] == "001-functions.md"
    assert result["bytes_written"] == len(path.read_bytes())
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

    with pytest.raises(ValueError, match="Markdown and Mermaid"):
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


def test_write_artifact_file_rejects_json_cards(tmp_path):
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

    with pytest.raises(ValueError, match="Markdown and Mermaid"):
        tool(
            filename="code-card.json",
            content=content,
            artifact_type="CodeSandboxCard",
            title="代码练习",
        )

    path = tmp_path / "runs" / "run-1" / "artifacts" / "code-card.json"
    assert not path.exists()


def test_create_code_sandbox_card_writes_published_problem_reference(tmp_path):
    tool = build_create_code_sandbox_card(
        workspace=LocalWorkspace(workdir=str(tmp_path), workspace_id="ws"),
        run_id="run-1",
    )

    result = tool(
        problem_id="problem-1",
        language="c",
        title="代码练习",
    )

    path = tmp_path / "runs" / "run-1" / "artifacts" / "code-problem-problem-1.json"
    assert result["status"] == "ok"
    assert result["artifact_type"] == "CodeSandboxCard"
    assert json.loads(path.read_text(encoding="utf-8")) == {
        "type": "CodeSandboxCard",
        "title": "代码练习",
        "props": {
            "problem_id": "problem-1",
            "language": "c",
        },
    }


def test_write_artifact_file_rejects_top_level_json_card(tmp_path):
    tool = build_write_artifact_file(
        workspace=LocalWorkspace(workdir=str(tmp_path), workspace_id="ws"),
        run_id="run-1",
    )
    content = json.dumps(
        {
            "question_text": "补全函数和循环",
            "code": "#include<stdio.h>\\nint main(){return 0;}",
            "language": "c",
            "default_stdin": "1 10\\n-1 0",
        },
        ensure_ascii=False,
    )

    with pytest.raises(ValueError, match="Markdown and Mermaid"):
        tool(
            filename="code-card.json",
            content=content,
            artifact_type="CodeSandboxCard",
            title="函数+循环综合练习：统计与筛选",
        )
