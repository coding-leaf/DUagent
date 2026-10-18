"""原生文档大纲提取工具 (Document Outline Extractor).

为知识图谱规划提供**确定性**的大纲结构，替代“让大模型临时编写脚本解析教材”的
不可控做法：

- :func:`extract_markdown_outline` —— 解析 Markdown ATX / Setext 标题树，
  输出 ``章节 -> 小节 -> 知识点`` 的层级大纲。
- :func:`extract_docx_outline` —— 基于 Word 段落样式（``Heading 1`` / ``标题 1``）
  提取标题层级，``python-docx`` 缺失时返回带 ``error`` 的结构化结果而不是崩溃。
- :func:`extract_outline` —— 按文件后缀自动分派。
- :func:`build_outline_extractor_tools` —— 以 AgentScope ``FunctionTool`` 规范暴露
  上述能力，供智能体在推理过程中直接调用。

所有函数均返回纯 JSON 可序列化结构，并对异常输入做降级处理（工具不得向智能体
抛出未捕获异常）。
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from agentscope.tool import FunctionTool

MARKDOWN_SUFFIXES = frozenset({".md", ".markdown", ".mdx", ".txt"})
DOCX_SUFFIXES = frozenset({".docx"})

# 最多保留 3 级知识树（章 -> 节 -> 知识点），过深的碎标题只会污染知识图谱。
MAX_OUTLINE_LEVEL = 3
MAX_ITEMS_PER_SECTION = 200
MAX_ITEM_CHARS = 120

_ATX_HEADING_RE = re.compile(r"^(#{1,6})\s+(.*?)\s*#*\s*$")
_SETEXT_UNDERLINE_RE = re.compile(r"^\s*(=+|-{2,})\s*$")
_FENCE_RE = re.compile(r"^\s*(```+|~~~+)")
_LIST_ITEM_RE = re.compile(r"^\s*(?:[-*+]|\d+[.)])\s+(.*\S)\s*$")
_DECORATION_RE = re.compile(r"^[\s\-=_*#·.]+$")

# 纯文本教材目录（Word 导出、PDF 拷贝）里最常见的两种编号标题。
_NUMBERED_UNIT_RE = re.compile(
    r"^(?:第\s*[0-9一二三四五六七八九十百零两]+\s*[章节讲单元篇]"
    r"|chapter\s*\d+|part\s*\d+|section\s*\d+)",
    re.IGNORECASE,
)
_DOTTED_NUMBER_RE = re.compile(r"^(\d+(?:\.\d+)+)\.?\s+\S")
_EMPHASIS_WRAP_RE = re.compile(r"^(\*\*|__)(.+)\1$")
MAX_NUMBERED_HEADING_CHARS = 80
_SENTENCE_END_RE = re.compile(r"[。！？；.!?;]$")

# 事件流：标题事件携带原始层级，列表项事件继承当前章节位置。
Event = tuple[str, int, str]


def _clean(value: Any) -> str:
    return " ".join(str(value or "").split())


def _is_usable_heading(text: str) -> bool:
    return bool(text) and not _DECORATION_RE.match(text)


def _strip_emphasis(text: str) -> str:
    wrapped = _EMPHASIS_WRAP_RE.match(text)
    return _clean(wrapped.group(2)) if wrapped else text


def _numbered_heading_level(line: str) -> tuple[int, str] | None:
    """Detect a plain-text numbered heading and return ``(level, text)``.

    Recognises ``第 1 章 / 第一节 / Chapter 1 / Part 2 / Section 3`` as level 1 and
    dotted numbering like ``1.1`` / ``1.1.1`` as deeper levels. Sentences and
    overlong lines are rejected to avoid swallowing body paragraphs.
    """
    text = _strip_emphasis(line.strip())
    if not text or len(text) > MAX_NUMBERED_HEADING_CHARS:
        return None
    if _SENTENCE_END_RE.search(text):
        return None

    if _NUMBERED_UNIT_RE.match(text):
        return 1, text

    dotted = _DOTTED_NUMBER_RE.match(text)
    if dotted:
        depth = dotted.group(1).count(".") + 1
        return min(max(depth, 2), MAX_OUTLINE_LEVEL), text
    return None


def _empty_outline(source: str, *, error: str | None = None) -> dict[str, Any]:
    result: dict[str, Any] = {
        "source": source,
        "title": None,
        "chapters": [],
        "flat_nodes": [],
        "heading_count": 0,
        "knowledge_point_count": 0,
    }
    if error:
        result["error"] = error
    return result


def _markdown_events(content: str) -> list[Event]:
    """Convert Markdown into an ordered ``heading`` / ``item`` event stream."""
    events: list[Event] = []
    lines = (content or "").splitlines()
    fence_token: str | None = None

    for index, line in enumerate(lines):
        fence_match = _FENCE_RE.match(line)
        if fence_match:
            token = fence_match.group(1)[0] * 3
            if fence_token is None:
                fence_token = token
            elif line.strip().startswith(fence_token):
                fence_token = None
            continue
        if fence_token is not None:
            continue

        atx_match = _ATX_HEADING_RE.match(line)
        if atx_match:
            text = _clean(atx_match.group(2)).strip("#").strip()
            if _is_usable_heading(text):
                events.append(("heading", len(atx_match.group(1)), text))
            continue

        if index > 0 and _SETEXT_UNDERLINE_RE.match(line):
            previous = lines[index - 1].strip()
            if (
                previous
                and not _ATX_HEADING_RE.match(previous)
                and not _LIST_ITEM_RE.match(previous)
                and not _SETEXT_UNDERLINE_RE.match(previous)
                and _is_usable_heading(_clean(previous))
            ):
                level = 1 if line.strip().startswith("=") else 2
                events.append(("heading", level, _clean(previous)))
            continue

        item_match = _LIST_ITEM_RE.match(line)
        if item_match:
            item = _clean(item_match.group(1))
            if item and len(item) <= MAX_ITEM_CHARS:
                events.append(("item", 0, item))
            continue

        numbered = _numbered_heading_level(line)
        if numbered is not None:
            events.append(("heading", numbered[0], numbered[1]))

    return events


def _build_outline(source: str, events: list[Event]) -> dict[str, Any]:
    """Assemble ``chapters -> sections -> knowledge_points`` from an event stream.

    Heading depth is interpreted relatively: the shallowest level is the document
    title when it appears exactly once (``# 课程名`` / Word "Title"), then the next
    level becomes chapters, the next sections, and anything deeper becomes a
    knowledge point. This keeps 2-level and 3-level material both well shaped.
    """
    headings = [event for event in events if event[0] == "heading"]
    if not headings:
        return _empty_outline(source, error=f"no {source} heading found")

    levels = sorted({level for _, level, _ in headings})
    shallowest = levels[0]
    title_level: int | None = None
    if len(levels) > 1 and sum(1 for _, level, _ in headings if level == shallowest) == 1:
        title_level = shallowest
    body_levels = [level for level in levels if level != title_level]

    chapters: list[dict[str, Any]] = []
    flat_nodes: list[dict[str, Any]] = []
    title: str | None = None

    current_chapter: dict[str, Any] | None = None
    current_section: dict[str, Any] | None = None
    # 同一名称只产生一个扁平节点，避免“小节既是标题又当知识点”时重复。
    emitted_names: set[str] = set()

    def ensure_chapter(name: str) -> dict[str, Any]:
        nonlocal current_section
        for chapter in chapters:
            if chapter["chapter"] == name:
                current_section = None
                return chapter
        chapter = {"chapter": name, "sections": []}
        chapters.append(chapter)
        current_section = None
        return chapter

    def ensure_section(chapter: dict[str, Any], name: str) -> dict[str, Any]:
        for section in chapter["sections"]:
            if section["section"] == name:
                return section
        section = {"section": name, "knowledge_points": []}
        chapter["sections"].append(section)
        return section

    def add_knowledge_point(name: str) -> None:
        nonlocal current_section
        if current_chapter is None:
            return
        if current_section is None:
            current_section = ensure_section(current_chapter, current_chapter["chapter"])
        bucket = current_section["knowledge_points"]
        if name in bucket or len(bucket) >= MAX_ITEMS_PER_SECTION:
            return
        bucket.append(name)
        if name in emitted_names:
            return
        emitted_names.add(name)
        flat_nodes.append(
            {
                "id": f"outline_{len(flat_nodes) + 1}",
                "name": name,
                "chapter": current_chapter["chapter"],
                "level": 3,
            }
        )

    for kind, level, text in events:
        if kind == "item":
            add_knowledge_point(text)
            continue

        if title_level is not None and level == title_level:
            if title is None:
                title = text
            continue

        rank = 1
        if level in body_levels:
            rank = body_levels.index(level) + 1
        relative = max(1, min(rank, MAX_OUTLINE_LEVEL))

        if relative == 1 or current_chapter is None:
            current_chapter = ensure_chapter(text)
            if title is None:
                title = text
            if text not in emitted_names:
                emitted_names.add(text)
                flat_nodes.append(
                    {
                        "id": f"outline_{len(flat_nodes) + 1}",
                        "name": text,
                        "chapter": text,
                        "level": 1,
                    }
                )
        elif relative == 2:
            current_section = ensure_section(current_chapter, text)
            if text not in emitted_names:
                emitted_names.add(text)
                flat_nodes.append(
                    {
                        "id": f"outline_{len(flat_nodes) + 1}",
                        "name": text,
                        "chapter": current_chapter["chapter"],
                        "level": 2,
                    }
                )
        else:
            add_knowledge_point(text)

    # 叶子小节没有任何列表项时，小节标题本身就是知识图谱节点。
    for chapter in chapters:
        for section in chapter["sections"]:
            section_name = section["section"]
            if section_name == chapter["chapter"] or section["knowledge_points"]:
                continue
            section["knowledge_points"].append(section_name)
            if section_name in emitted_names:
                continue
            emitted_names.add(section_name)
            flat_nodes.append(
                {
                    "id": f"outline_{len(flat_nodes) + 1}",
                    "name": section_name,
                    "chapter": chapter["chapter"],
                    "level": 3,
                }
            )

    knowledge_point_count = sum(
        len(section["knowledge_points"])
        for chapter in chapters
        for section in chapter["sections"]
    )

    return {
        "source": source,
        "title": title,
        "chapters": chapters,
        "flat_nodes": flat_nodes,
        "heading_count": len(headings),
        "knowledge_point_count": knowledge_point_count,
    }


def extract_markdown_outline(content: str) -> dict[str, Any]:
    """Extract a ``chapters -> sections -> knowledge_points`` outline from Markdown.

    Supports ATX (``#``) and Setext (``===`` / ``---``) headings, ignores fenced
    code blocks, and folds following list items into the nearest section as
    knowledge points (useful for tables of contents that only use 1-2 levels).

    Args:
        content: Markdown (or plain-text) course material / table of contents.

    Returns:
        JSON-serializable outline tree. ``flat_nodes`` can be fed straight into
        the curriculum planner as candidate knowledge points.
    """
    if not isinstance(content, str):
        # 工具契约：模型可能传入任意 JSON 类型，这里降级为结构化错误而不是抛异常。
        return _empty_outline(
            "markdown",
            error=f"markdown content must be a string, got {type(content).__name__}",
        )
    if not content.strip():
        return _empty_outline("markdown", error="markdown content is empty")
    return _build_outline("markdown", _markdown_events(content))


def _docx_heading_level(paragraph: Any) -> int | None:
    style_name = _clean(getattr(getattr(paragraph, "style", None), "name", ""))
    if not style_name:
        return None

    normalized = style_name.lower()
    if normalized in {"title", "标题"}:
        return 0
    for prefix in ("heading ", "标题 ", "标题"):
        if normalized.startswith(prefix):
            remainder = normalized[len(prefix) :].strip()
            if remainder.isdigit():
                return max(1, int(remainder))
    return None


def _is_docx_list_paragraph(paragraph: Any) -> bool:
    style_name = _clean(getattr(getattr(paragraph, "style", None), "name", "")).lower()
    return style_name.startswith(("list", "列表"))


def extract_docx_outline(file_path: str | Path) -> dict[str, Any]:
    """Extract heading hierarchy from a ``.docx`` file using paragraph styles.

    Args:
        file_path: Path to the Word document.

    Returns:
        Same outline shape as :func:`extract_markdown_outline`. When
        ``python-docx`` is unavailable or the file cannot be read, the returned
        dict carries an ``error`` field instead of raising.
    """
    path = Path(str(file_path))
    if path.suffix.lower() not in DOCX_SUFFIXES:
        return _empty_outline("docx", error=f"unsupported docx suffix: {path.suffix}")
    if not path.exists():
        return _empty_outline("docx", error=f"docx file not found: {path.name}")

    try:
        from docx import Document  # type: ignore[import-untyped]
    except ImportError:
        return _empty_outline("docx", error="python-docx is not installed")

    try:
        document = Document(str(path))
    except Exception as exc:  # pragma: no cover - depends on corrupt binaries
        return _empty_outline("docx", error=f"failed to open docx: {exc}")

    events: list[Event] = []
    for paragraph in document.paragraphs:
        text = _clean(paragraph.text)
        if not text:
            continue

        level = _docx_heading_level(paragraph)
        if level is not None:
            if _is_usable_heading(text):
                events.append(("heading", level, text))
            continue

        if _is_docx_list_paragraph(paragraph) and len(text) <= MAX_ITEM_CHARS:
            events.append(("item", 0, text))

    if not any(event[0] == "heading" for event in events):
        return _empty_outline("docx", error="no docx heading style found")
    return _build_outline("docx", events)


def extract_outline(file_path: str | Path) -> dict[str, Any]:
    """Dispatch to the Markdown or Docx extractor based on the file suffix."""
    path = Path(str(file_path))
    suffix = path.suffix.lower()
    if suffix in DOCX_SUFFIXES:
        return extract_docx_outline(path)
    if suffix in MARKDOWN_SUFFIXES:
        try:
            content = path.read_text(encoding="utf-8")
        except OSError as exc:
            return _empty_outline("markdown", error=f"failed to read file: {exc}")
        except UnicodeDecodeError as exc:
            # GBK/Latin-1 教材导出很常见，工具必须降级返回错误而不是抛出。
            return _empty_outline(
                "markdown",
                error=f"file is not valid UTF-8: {exc.reason}",
            )
        return extract_markdown_outline(content)
    return _empty_outline("unknown", error=f"unsupported outline suffix: {suffix}")


def summarize_outline_for_planning(outline: dict[str, Any], *, max_chars: int = 4000) -> str:
    """Render an extracted outline into a compact planning hint for the LLM prompt."""
    chapters = outline.get("chapters") if isinstance(outline, dict) else None
    if not isinstance(chapters, list) or not chapters:
        return ""

    lines: list[str] = []
    for chapter in chapters:
        if not isinstance(chapter, dict):
            continue
        chapter_name = _clean(chapter.get("chapter"))
        if not chapter_name:
            continue
        lines.append(f"- {chapter_name}")
        sections = chapter.get("sections")
        if not isinstance(sections, list):
            continue
        for section in sections:
            if not isinstance(section, dict):
                continue
            points = [
                _clean(point)
                for point in section.get("knowledge_points") or []
                if _clean(point)
            ]
            section_name = _clean(section.get("section"))
            if section_name and section_name != chapter_name:
                lines.append(f"  * {section_name}")
                if points:
                    lines.append(f"    - {'；'.join(points[:20])}")
            elif points:
                lines.append(f"  * {'；'.join(points[:20])}")

    digest = "\n".join(lines).strip()
    if len(digest) > max_chars:
        digest = digest[:max_chars].rstrip() + "\n...(outline truncated)"
    return digest


def build_outline_extractor_tools() -> list[FunctionTool]:
    """Expose the outline extractors as AgentScope native tools."""
    return [
        FunctionTool(
            extract_markdown_outline,
            name="extract_markdown_outline",
            description=(
                "Extract the chapter/section/knowledge-point outline tree from Markdown "
                "course material. Returns JSON with a `chapters` tree and `flat_nodes`."
            ),
            is_read_only=True,
        ),
        FunctionTool(
            extract_docx_outline,
            name="extract_docx_outline",
            description=(
                "Extract the heading hierarchy (chapters, sections, knowledge points) from a "
                ".docx course material file. Returns the same JSON outline shape."
            ),
            is_read_only=True,
        ),
    ]
