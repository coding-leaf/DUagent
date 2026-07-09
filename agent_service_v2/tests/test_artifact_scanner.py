import json

import pytest

from agent_service_v2.artifacts.scanner import ArtifactScanner
from agent_service_v2.artifacts.schemas import ArtifactValidationError


def test_scanner_parses_markdown_with_frontmatter(tmp_path):
    artifact_dir = tmp_path / "artifacts"
    artifact_dir.mkdir()
    (artifact_dir / "001-functions.md").write_text(
        "---\n"
        "type: Markdown\n"
        "title: C语言函数核心概念\n"
        "---\n\n"
        "# C语言函数核心概念\n\n"
        "函数用于把可复用逻辑封装成命名代码块。\n",
        encoding="utf-8",
    )

    artifacts = ArtifactScanner(artifact_dir).scan()

    assert len(artifacts) == 1
    artifact = artifacts[0]
    assert artifact.file == "001-functions.md"
    assert artifact.type == "Markdown"
    assert artifact.title == "C语言函数核心概念"
    assert artifact.props == {
        "title": "C语言函数核心概念",
        "content": "# C语言函数核心概念\n\n函数用于把可复用逻辑封装成命名代码块。\n",
    }


def test_scanner_parses_mermaid_with_default_type(tmp_path):
    artifact_dir = tmp_path / "artifacts"
    artifact_dir.mkdir()
    (artifact_dir / "002-flow.mmd").write_text(
        "flowchart TD\n  A[main] --> B[add]\n",
        encoding="utf-8",
    )

    artifacts = ArtifactScanner(artifact_dir).scan()

    assert artifacts[0].type == "Mermaid"
    assert artifacts[0].props == {"chart": "flowchart TD\n  A[main] --> B[add]\n"}


def test_scanner_parses_json_plugin_artifact(tmp_path):
    artifact_dir = tmp_path / "artifacts"
    artifact_dir.mkdir()
    (artifact_dir / "003-plan.json").write_text(
        json.dumps(
            {
                "type": "StudyPlanCard",
                "title": "两周补弱计划",
                "props": {"weeks": [{"label": "第1周", "goals": ["复习函数"]}]},
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    artifacts = ArtifactScanner(artifact_dir).scan()

    assert artifacts[0].type == "StudyPlanCard"
    assert artifacts[0].title == "两周补弱计划"
    assert artifacts[0].props == {"weeks": [{"label": "第1周", "goals": ["复习函数"]}]}


def test_scanner_rejects_invalid_json(tmp_path):
    artifact_dir = tmp_path / "artifacts"
    artifact_dir.mkdir()
    (artifact_dir / "bad.json").write_text("{bad", encoding="utf-8")

    with pytest.raises(ArtifactValidationError, match="invalid json"):
        ArtifactScanner(artifact_dir).scan()


def test_scanner_rejects_unsupported_type(tmp_path):
    artifact_dir = tmp_path / "artifacts"
    artifact_dir.mkdir()
    (artifact_dir / "bad.md").write_text(
        "---\ntype: UnknownType\n---\n\n# Bad\n",
        encoding="utf-8",
    )

    with pytest.raises(ArtifactValidationError, match="unsupported artifact type"):
        ArtifactScanner(artifact_dir).scan()


def test_scanner_ignores_manifest_and_rejects_hidden_or_nested_files(tmp_path):
    artifact_dir = tmp_path / "artifacts"
    artifact_dir.mkdir()
    (artifact_dir / "manifest.json").write_text('{"version":1}', encoding="utf-8")
    (artifact_dir / ".secret.md").write_text("# Secret", encoding="utf-8")

    with pytest.raises(ArtifactValidationError, match="hidden artifact file"):
        ArtifactScanner(artifact_dir).scan()


def test_scanner_rejects_code_sandbox_card_missing_language(tmp_path):
    artifact_dir = tmp_path / "artifacts"
    artifact_dir.mkdir()
    (artifact_dir / "bad-code-card.json").write_text(
        json.dumps(
            {
                "type": "CodeSandboxCard",
                "props": {
                    "question_text": "修复这段 C 代码",
                    "code": "#include<stdio.h>\\nint main(){return 0;}",
                    "default_stdin": "",
                },
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    with pytest.raises(ArtifactValidationError, match="language"):
        ArtifactScanner(artifact_dir).scan()


def test_scanner_rejects_code_sandbox_card_unsupported_language(tmp_path):
    artifact_dir = tmp_path / "artifacts"
    artifact_dir.mkdir()
    (artifact_dir / "bad-code-card.json").write_text(
        json.dumps(
            {
                "type": "CodeSandboxCard",
                "props": {
                    "question_text": "运行 Python 代码",
                    "code": "print('hello')",
                    "language": "python3",
                    "default_stdin": "",
                },
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    with pytest.raises(ArtifactValidationError, match="unsupported CodeSandboxCard language"):
        ArtifactScanner(artifact_dir).scan()


def test_scanner_accepts_valid_code_sandbox_card(tmp_path):
    artifact_dir = tmp_path / "artifacts"
    artifact_dir.mkdir()
    (artifact_dir / "code-card.json").write_text(
        json.dumps(
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
        ),
        encoding="utf-8",
    )

    artifacts = ArtifactScanner(artifact_dir).scan()

    assert len(artifacts) == 1
    assert artifacts[0].type == "CodeSandboxCard"
    assert artifacts[0].props == {
        "question_text": "修复这段 C 代码",
        "code": "#include<stdio.h>\\nint main(){return 0;}",
        "language": "c",
        "default_stdin": "",
    }


def test_scanner_normalizes_top_level_code_sandbox_card(tmp_path):
    artifact_dir = tmp_path / "artifacts"
    artifact_dir.mkdir()
    (artifact_dir / "code-card.json").write_text(
        json.dumps(
            {
                "type": "CodeSandboxCard",
                "title": "函数+循环综合练习：统计与筛选",
                "question_text": "补全函数和循环",
                "code": "#include<stdio.h>\\nint main(){return 0;}",
                "language": "c",
                "default_stdin": "1 10\\n-1 0",
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    artifacts = ArtifactScanner(artifact_dir).scan()

    assert artifacts[0].type == "CodeSandboxCard"
    assert artifacts[0].title == "函数+循环综合练习：统计与筛选"
    assert artifacts[0].props == {
        "question_text": "补全函数和循环",
        "code": "#include<stdio.h>\\nint main(){return 0;}",
        "language": "c",
        "default_stdin": "1 10\\n-1 0",
    }


def test_scanner_infers_code_sandbox_card_from_top_level_required_fields(tmp_path):
    artifact_dir = tmp_path / "artifacts"
    artifact_dir.mkdir()
    (artifact_dir / "code-card.json").write_text(
        json.dumps(
            {
                "question_text": "补全函数和循环",
                "code": "#include<stdio.h>\\nint main(){return 0;}",
                "language": "c",
                "default_stdin": "1 10\\n-1 0",
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    artifacts = ArtifactScanner(artifact_dir).scan()

    assert artifacts[0].type == "CodeSandboxCard"
    assert artifacts[0].props["language"] == "c"
    assert artifacts[0].props["question_text"] == "补全函数和循环"
