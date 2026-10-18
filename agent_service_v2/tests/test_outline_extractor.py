from __future__ import annotations

import sys
import types
from pathlib import Path
from unittest.mock import patch

import pytest
from agentscope.tool import FunctionTool

from agent_service_v2.tools.outline_extractor import (
    build_outline_extractor_tools,
    extract_docx_outline,
    extract_markdown_outline,
    extract_outline,
    summarize_outline_for_planning,
)


MARKDOWN_OUTLINE = """# 数据结构与算法

## 第一章 绪论

### 基本概念

### 算法复杂度

- 时间复杂度
- 空间复杂度

## 第二章 线性表

### 顺序表

- 插入
- 删除

### 链表

- 单链表
- 双向链表
"""


def test_extract_markdown_outline_builds_chapter_section_knowledge_tree() -> None:
    outline = extract_markdown_outline(MARKDOWN_OUTLINE)

    # 唯一的 "#" 标题被识别为文档标题，不占用章节点。
    assert outline["title"] == "数据结构与算法"
    assert [chapter["chapter"] for chapter in outline["chapters"]] == [
        "第一章 绪论",
        "第二章 线性表",
    ]
    chapters = {chapter["chapter"]: chapter for chapter in outline["chapters"]}

    first = chapters["第一章 绪论"]
    assert [section["section"] for section in first["sections"]] == [
        "基本概念",
        "算法复杂度",
    ]
    assert first["sections"][0]["knowledge_points"] == ["基本概念"]
    assert first["sections"][1]["knowledge_points"] == ["时间复杂度", "空间复杂度"]

    second = chapters["第二章 线性表"]
    assert [section["section"] for section in second["sections"]] == ["顺序表", "链表"]
    assert second["sections"][0]["knowledge_points"] == ["插入", "删除"]
    assert second["sections"][1]["knowledge_points"] == ["单链表", "双向链表"]
    assert outline["knowledge_point_count"] == 7
    assert outline["heading_count"] == 7


def test_extract_markdown_outline_flat_nodes_are_planner_ready() -> None:
    outline = extract_markdown_outline(MARKDOWN_OUTLINE)

    flat_nodes = outline["flat_nodes"]
    assert flat_nodes
    assert all(node["id"] for node in flat_nodes)
    assert all(node["name"] for node in flat_nodes)
    assert all(node["chapter"] for node in flat_nodes)
    assert {node["level"] for node in flat_nodes} <= {1, 2, 3}
    assert len({node["id"] for node in flat_nodes}) == len(flat_nodes)


def test_extract_markdown_outline_ignores_fenced_code_headings() -> None:
    content = """# 计算机网络

## 第一章 体系结构

```
# 这行在代码块里，不是标题
## 也不是标题
```

## 第二章 传输层
"""
    outline = extract_markdown_outline(content)

    assert outline["title"] == "计算机网络"
    assert [chapter["chapter"] for chapter in outline["chapters"]] == [
        "第一章 体系结构",
        "第二章 传输层",
    ]
    names = {node["name"] for node in outline["flat_nodes"]}
    assert "这行在代码块里，不是标题" not in names
    assert "也不是标题" not in names


def test_extract_markdown_outline_supports_setext_headings() -> None:
    content = """高等数学
========

极限
----

- 数列极限
- 函数极限

导数
----

- 导数定义
"""
    outline = extract_markdown_outline(content)

    assert outline["title"] == "高等数学"
    chapters = {chapter["chapter"]: chapter for chapter in outline["chapters"]}
    assert set(chapters) == {"极限", "导数"}
    assert chapters["极限"]["sections"][0]["knowledge_points"] == [
        "数列极限",
        "函数极限",
    ]
    assert chapters["导数"]["sections"][0]["knowledge_points"] == ["导数定义"]


def test_extract_markdown_outline_handles_nested_level_start() -> None:
    content = """## 第一章 导论
### 课程目标
## 第二章 基础
### 变量
"""
    outline = extract_markdown_outline(content)

    # 最浅标题被当成“章”，不会因为缺少 "#" 全部塌成一层
    assert [chapter["chapter"] for chapter in outline["chapters"]] == [
        "第一章 导论",
        "第二章 基础",
    ]
    assert outline["chapters"][0]["sections"][0]["section"] == "课程目标"


def test_extract_markdown_outline_numbered_plain_text_toc() -> None:
    content = """第 1 章 绪论
1.1 课程介绍
1.2 学习方法
第 2 章 基本概念
2.1 定义
2.1.1 概念的边界
"""
    outline = extract_markdown_outline(content)

    # 从 Word/PDF 拷出的纯文本目录：编号标题同样能被结构化。
    assert outline["heading_count"] == 6
    assert [chapter["chapter"] for chapter in outline["chapters"]] == [
        "第 1 章 绪论",
        "第 2 章 基本概念",
    ]
    first, second = outline["chapters"]
    assert [section["section"] for section in first["sections"]] == [
        "1.1 课程介绍",
        "1.2 学习方法",
    ]
    assert [section["section"] for section in second["sections"]] == ["2.1 定义"]
    assert second["sections"][0]["knowledge_points"] == ["2.1.1 概念的边界"]


def test_extract_markdown_outline_accepts_numbered_and_markdown_headings_together() -> None:
    content = """# 计算机网络

第一章 体系结构

1.1 OSI 模型

第二章 传输层
"""
    outline = extract_markdown_outline(content)

    # 两种标题写法都能被识别，不会丢掉编号章节。
    assert "计算机网络" in [chapter["chapter"] for chapter in outline["chapters"]]
    assert "第一章 体系结构" in [chapter["chapter"] for chapter in outline["chapters"]]
    assert "第二章 传输层" in [chapter["chapter"] for chapter in outline["chapters"]]
    structure = {chapter["chapter"]: chapter for chapter in outline["chapters"]}
    assert [s["section"] for s in structure["第一章 体系结构"]["sections"]] == ["1.1 OSI 模型"]


def test_extract_markdown_outline_does_not_treat_sentences_as_headings() -> None:
    content = """1. 第一步先阅读教材。

2. 然后完成练习。

第 1 章 绪论
"""
    outline = extract_markdown_outline(content)

    names = {node["name"] for node in outline["flat_nodes"]}
    assert "第一步先阅读教材。" not in names
    assert "然后完成练习。" not in names
    assert [chapter["chapter"] for chapter in outline["chapters"]] == ["第 1 章 绪论"]


def test_flat_nodes_are_unique_across_sections() -> None:
    outline = extract_markdown_outline(MARKDOWN_OUTLINE)

    names = [node["name"] for node in outline["flat_nodes"]]
    assert len(names) == len(set(names))


@pytest.mark.parametrize(
    "content",
    ["", "   ", "\n\n\n"],
)
def test_extract_markdown_outline_rejects_empty_content(content: str) -> None:
    outline = extract_markdown_outline(content)

    assert outline["error"] == "markdown content is empty"
    assert outline["chapters"] == []


@pytest.mark.parametrize("content", [123, ["# 标题"], {"content": "x"}, b"# bytes"])
def test_extract_markdown_outline_degrades_on_non_string_input(content: object) -> None:
    # 工具会被大模型以任意 JSON 类型调用，必须返回结构化错误而不是抛异常。
    outline = extract_markdown_outline(content)  # type: ignore[arg-type]

    assert "must be a string" in (outline["error"] or "")
    assert outline["chapters"] == []
    assert outline["flat_nodes"] == []


# ---------------------------------------------------------------------------
# Docx extraction
# ---------------------------------------------------------------------------


class _FakeParagraph:
    def __init__(self, text: str, style_name: str) -> None:
        self.text = text
        self.style = types.SimpleNamespace(name=style_name)


class _FakeDocument:
    def __init__(self, paragraphs: list[_FakeParagraph]) -> None:
        self.paragraphs = paragraphs


def _write_docx(tmp_path: Path, paragraphs: list[_FakeParagraph]) -> Path:
    path = tmp_path / "outline.docx"
    path.write_bytes(b"fake-docx")
    return path


def test_extract_docx_outline_uses_english_heading_styles(tmp_path: Path) -> None:
    path = _write_docx(
        tmp_path,
        [
            _FakeParagraph("Operating Systems", "Title"),
            _FakeParagraph("Chapter 1 Introduction", "Heading 1"),
            _FakeParagraph("Processes", "Heading 2"),
            _FakeParagraph("Scheduling", "List Bullet"),
            _FakeParagraph("Threads", "Heading 2"),
            _FakeParagraph("Chapter 2 Memory", "Heading 1"),
        ],
    )

    with patch.dict(sys.modules, {"docx": types.SimpleNamespace(Document=lambda _: _FakeDocument([
        _FakeParagraph("Operating Systems", "Title"),
        _FakeParagraph("Chapter 1 Introduction", "Heading 1"),
        _FakeParagraph("Processes", "Heading 2"),
        _FakeParagraph("Scheduling", "List Bullet"),
        _FakeParagraph("Threads", "Heading 2"),
        _FakeParagraph("Chapter 2 Memory", "Heading 1"),
    ]))}):
        outline = extract_docx_outline(path)

    assert outline["source"] == "docx"
    assert outline["title"] == "Operating Systems"
    assert [chapter["chapter"] for chapter in outline["chapters"]] == [
        "Chapter 1 Introduction",
        "Chapter 2 Memory",
    ]
    intro = outline["chapters"][0]
    assert [section["section"] for section in intro["sections"]] == ["Processes", "Threads"]
    assert intro["sections"][0]["knowledge_points"] == ["Scheduling"]


def test_extract_docx_outline_supports_chinese_heading_styles(tmp_path: Path) -> None:
    path = _write_docx(tmp_path, [])
    document = _FakeDocument(
        [
            _FakeParagraph("数据结构", "标题 1"),
            _FakeParagraph("第一章 绪论", "标题 2"),
            _FakeParagraph("基本概念", "列表段落"),
        ]
    )

    with patch.dict(sys.modules, {"docx": types.SimpleNamespace(Document=lambda _: document)}):
        outline = extract_docx_outline(path)

    assert outline["title"] == "数据结构"
    assert outline["chapters"][0]["sections"][0]["section"] == "第一章 绪论"
    assert outline["chapters"][0]["sections"][0]["knowledge_points"] == ["基本概念"]


def test_extract_docx_outline_reports_missing_python_docx(tmp_path: Path) -> None:
    path = _write_docx(tmp_path, [])

    with patch.dict(sys.modules, {"docx": None}):
        outline = extract_docx_outline(path)

    assert outline["error"] == "python-docx is not installed"
    assert outline["chapters"] == []


def test_extract_docx_outline_reports_missing_file_and_bad_suffix(tmp_path: Path) -> None:
    missing = extract_docx_outline(tmp_path / "missing.docx")
    assert "not found" in (missing["error"] or "")

    wrong = tmp_path / "outline.pdf"
    wrong.write_bytes(b"%PDF")
    bad_suffix = extract_docx_outline(wrong)
    assert "unsupported docx suffix" in (bad_suffix["error"] or "")


def test_extract_docx_outline_reports_document_without_headings(tmp_path: Path) -> None:
    path = _write_docx(tmp_path, [])
    document = _FakeDocument([_FakeParagraph("普通正文", "Normal")])

    with patch.dict(sys.modules, {"docx": types.SimpleNamespace(Document=lambda _: document)}):
        outline = extract_docx_outline(path)

    assert outline["error"] == "no docx heading style found"


def test_extract_docx_outline_handles_corrupt_document(tmp_path: Path) -> None:
    path = _write_docx(tmp_path, [])

    def _raise(_: str):
        raise ValueError("not a zip file")

    with patch.dict(sys.modules, {"docx": types.SimpleNamespace(Document=_raise)}):
        outline = extract_docx_outline(path)

    assert "failed to open docx" in (outline["error"] or "")


# ---------------------------------------------------------------------------
# Dispatch helpers and AgentScope tool wiring
# ---------------------------------------------------------------------------


def test_extract_outline_dispatches_by_suffix(tmp_path: Path) -> None:
    md_path = tmp_path / "course.md"
    md_path.write_text(MARKDOWN_OUTLINE, encoding="utf-8")

    outline = extract_outline(md_path)
    assert outline["source"] == "markdown"
    assert outline["title"] == "数据结构与算法"

    unknown = tmp_path / "course.xlsx"
    unknown.write_bytes(b"x")
    assert "unsupported outline suffix" in (extract_outline(unknown)["error"] or "")


def test_extract_outline_degrades_on_non_utf8_file(tmp_path: Path) -> None:
    # GBK 导出的教材文本很常见，工具必须返回结构化错误而不是抛 UnicodeDecodeError。
    path = tmp_path / "gbk.md"
    path.write_bytes("# 中文标题\n".encode("gbk"))

    outline = extract_outline(path)

    assert "not valid UTF-8" in (outline["error"] or "")
    assert outline["chapters"] == []


def test_summarize_outline_for_planning_produces_compact_hint() -> None:
    outline = extract_markdown_outline(MARKDOWN_OUTLINE)

    digest = summarize_outline_for_planning(outline)

    assert "第二章 线性表" in digest
    assert "单向/双向链表" not in digest
    assert "双向链表" in digest
    assert len(digest) < 4000


def test_summarize_outline_for_planning_truncates_and_handles_empty() -> None:
    assert summarize_outline_for_planning({}) == ""
    assert summarize_outline_for_planning({"chapters": []}) == ""

    outline = extract_markdown_outline(MARKDOWN_OUTLINE)
    digest = summarize_outline_for_planning(outline, max_chars=40)
    assert digest.endswith("...(outline truncated)")
    assert len(digest) < 120


def test_build_outline_extractor_tools_exposes_function_tools() -> None:
    tools = build_outline_extractor_tools()

    assert [tool.name for tool in tools] == [
        "extract_markdown_outline",
        "extract_docx_outline",
    ]
    assert all(isinstance(tool, FunctionTool) for tool in tools)
    assert all(tool.is_read_only for tool in tools)
