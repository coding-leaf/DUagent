from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from agentscope.message import TextBlock
from agentscope.rag import Chunk, Section, VectorSearchResult

from agent_service_v2.agents.model_provider import AgentModelSettings
from agent_service_v2.tools.rag import (
    TokenAwareRecursiveChunker,
    _get_historical_fallback_collection,
    _matches_vector_dim,
    _text_from_agentscope_payload,
    build_catalog_kg_context,
    clean_text_preserving_syntax,
    detect_heading,
    estimate_token_count,
    get_course_knowledge_collection_name,
    get_safe_token_threshold,
    ingest_course_material,
    retrieve_course_context,
    split_paragraphs_preserving_blocks,
)


def test_clean_text_preserving_syntax_protects_code_and_formulas() -> None:
    raw = """
# 目录
1.1 快速入门 .................................................... 1
1.2 变量与算术表达式 . . . . . . . . . . . . . . . . . . . . . . . . . . . 7
1.3 流程控制 ······················································· 15
1.4 特殊符号 ••••••••••••••••••••••••••••••••••••••••••••••••••••••• 22

```c
#include <stdio.h>
/* 严格保留 C 语言代码缩进与注释 */
int main(void) {
    int count = 0;
    while (count < 10) {
        printf("count = %d\\n", count++);
    }
    return 0;
}
```

数学公式测试：
块级公式：
$$E = mc^2 + \\int_0^\\infty e^{-x} dx$$
行内公式：$a^2 + b^2 = c^2$ 以及行内代码 `int x = 42;` 必须原封不动。

换页符测试：\x0c页面底端\x00噪音

连续换行测试：



正文结束。
"""
    cleaned = clean_text_preserving_syntax(raw)

    # 验证目录长连点折叠
    assert "................" not in cleaned
    assert "···············" not in cleaned
    assert "•••••••••••••••" not in cleaned
    assert "1.1 快速入门 ... 1" in cleaned or "1.1 快速入门 ... 1" in " ".join(cleaned.split())

    # 验证代码缩进、换行与注释完整保留
    expected_code = """```c
#include <stdio.h>
/* 严格保留 C 语言代码缩进与注释 */
int main(void) {
    int count = 0;
    while (count < 10) {
        printf("count = %d\\n", count++);
    }
    return 0;
}
```"""
    assert expected_code in cleaned

    # 验证公式与行内代码完整保留
    assert "$$E = mc^2 + \\int_0^\\infty e^{-x} dx$$" in cleaned
    assert "$a^2 + b^2 = c^2$" in cleaned
    assert "`int x = 42;`" in cleaned

    # 验证控制字符被清除
    assert "\x0c" not in cleaned
    assert "\x00" not in cleaned

    # 验证冗余空行被压缩（最多两个连续换行）
    assert "\n\n\n" not in cleaned


def test_detect_heading_and_breadcrumbs() -> None:
    assert detect_heading("第 1 章 导言") == (1, "第 1 章 导言")
    assert detect_heading("第1章 导言") == (1, "第1章 导言")
    assert detect_heading("Chapter 2 Types, Operators and Expressions") == (
        1,
        "Chapter 2 Types, Operators and Expressions",
    )
    assert detect_heading("1.2 变量与算术表达式") == (2, "1.2 变量与算术表达式")
    assert detect_heading("1.2.1 基础整型") == (3, "1.2.1 基础整型")
    assert detect_heading("前言") == (1, "前言")
    assert detect_heading("附录 A 参考手册") == (1, "附录 A 参考手册")
    assert detect_heading("## Markdown 二级标题") == (2, "Markdown 二级标题")

    # 句子不是标题
    assert detect_heading("这是一个以句号结尾的普通正文句子。") is None
    assert detect_heading("while (i < 10) { i++; }") is None


def test_estimate_token_count_conservative() -> None:
    # 中文字符 conservative 估计 > 字符数
    zh_text = "C语言是一种通用的计算机程序设计语言"  # 18 字
    assert estimate_token_count(zh_text) >= 18 * 1.2

    # 英文单词与标点
    en_text = "The C Programming Language by Kernighan and Ritchie."
    assert estimate_token_count(en_text) >= 9

    # 确保空文本返回 0
    assert estimate_token_count("") == 0


def test_safe_token_threshold_configuration() -> None:
    # 512 窗口模型设为 400
    assert get_safe_token_threshold("BAAI/bge-large-zh-v1.5", 512) == 400
    assert get_safe_token_threshold("bge-base-zh", 512) == 400

    # bge-m3 (8192) 设为 1200
    assert get_safe_token_threshold("BAAI/bge-m3", 512) == 512
    assert get_safe_token_threshold("BAAI/bge-m3", 2048) == 1200

    # 默认兜底
    assert get_safe_token_threshold(None, 512) == 400


def test_token_aware_recursive_chunker_splits_oversized_text() -> None:
    chunker = TokenAwareRecursiveChunker(chunk_size=400, overlap=30, safe_threshold=150)

    # 构造包含标题和超长文本的 section
    long_content = (
        "第 1 章 导言\n\n"
        "1.1 快速入门\n\n"
        + "这是入门章节的第一段内容，介绍基本的环境搭建和运行方式。" * 15
        + "\n\n"
        + "这是入门章节的第二段内容，包含非常密集的语法结构说明。" * 15
    )

    section = Section(
        content=TextBlock(text=long_content),
        source="c_book.pdf",
        metadata={"page": 1},
    )

    chunks = asyncio.run(chunker.chunk([section]))

    assert len(chunks) > 1
    # 验证每个 chunk 的估算 token 都被严格限制在 safe_threshold 之内
    for idx, c in enumerate(chunks):
        assert c.chunk_index == idx
        assert c.total_chunks == len(chunks)
        text = c.content.text
        # 每个切片必须携带章节前缀
        assert "[第 1 章 导言 > 1.1 快速入门]" in text
        assert c.metadata.get("chapter_path") == "第 1 章 导言 > 1.1 快速入门"
        assert c.metadata.get("headings") == ["第 1 章 导言", "1.1 快速入门"]
        # token 严格受限
        assert estimate_token_count(text) <= 150


def test_collection_isolation_by_model() -> None:
    settings = AgentModelSettings(
        QDRANT_COURSE_KNOWLEDGE_COLLECTION="course_knowledge_v1_1024",
        EMBEDDING_MODEL="BAAI/bge-large-zh-v1.5",
        EMBEDDING_DIMENSION=1024,
    )
    col1 = get_course_knowledge_collection_name(settings)
    assert col1 == "course_knowledge_baai_bge_large_zh_v1_5_1024"

    settings2 = AgentModelSettings(
        QDRANT_COURSE_KNOWLEDGE_COLLECTION="course_knowledge_v1_1024",
        EMBEDDING_MODEL="BAAI/bge-m3",
        EMBEDDING_DIMENSION=1024,
    )
    col2 = get_course_knowledge_collection_name(settings2)
    assert col2 == "course_knowledge_baai_bge_m3_1024"
    assert col1 != col2  # 物理隔离，集合名互不相同

    # 若未指定模型，保持默认配置集合
    settings3 = AgentModelSettings(
        QDRANT_COURSE_KNOWLEDGE_COLLECTION="course_knowledge_custom",
        EMBEDDING_MODEL=None,
    )
    assert get_course_knowledge_collection_name(settings3) == "course_knowledge_custom"


def test_ingest_course_material_blue_green_lifecycle() -> None:
    settings = AgentModelSettings()

    mock_parser = MagicMock()
    mock_parser.parse = AsyncMock(
        return_value=[
            Section(
                content=TextBlock(text="第 1 章 导言\n\n正文第一句。"),
                source="test.pdf",
                metadata={"page": 1},
            )
        ]
    )

    # 模拟 Qdrant 客户端与 KnowledgeBase
    mock_client = MagicMock()
    mock_client.get_collections = AsyncMock(return_value=MagicMock(collections=[]))
    mock_client.create_collection = AsyncMock()
    mock_client.count = AsyncMock(return_value=MagicMock(count=1))
    mock_client.set_payload = AsyncMock()
    mock_client.delete = AsyncMock()

    mock_store = MagicMock()
    mock_store.get_client.return_value = mock_client

    mock_kb = MagicMock()
    mock_kb.vector_store = mock_store
    mock_kb.insert_document = AsyncMock(return_value="doc_123")

    with (
        patch("agent_service_v2.tools.rag.PDFParser", return_value=mock_parser),
        patch("agent_service_v2.tools.rag.get_course_knowledge_base", return_value=mock_kb),
        patch("pathlib.Path.exists", return_value=True),
        patch("pathlib.Path.is_file", return_value=True),
    ):
        cnt = asyncio.run(
            ingest_course_material(
                file_path="/fake/c_book.pdf",
                course_id="catalog_100",
                settings=settings,
            )
        )

        assert cnt == 1
        # 1. 验证先写入新切片 (带 is_active=False 元数据)
        mock_kb.insert_document.assert_called_once()
        inserted_chunks = mock_kb.insert_document.call_args.args[0]
        assert len(inserted_chunks) == 1
        meta = inserted_chunks[0].metadata
        assert meta["course_id"] == "catalog_100"
        assert meta["catalog_id"] == "catalog_100"
        assert "ingestion_version" in meta
        version = meta["ingestion_version"]
        assert meta["is_active"] is False

        # 2. 验证写入后与激活后共执行 2 次 count 校验 (写入强校验 + 激活完整性验证)
        assert mock_client.count.call_count == 2
        first_count_filter = mock_client.count.call_args_list[0].kwargs["count_filter"]
        assert any(c.key == "chunk.metadata.course_id" and c.match.value == "catalog_100" for c in first_count_filter.must)
        assert any(c.key == "chunk.metadata.material_id" and c.match.value == "c_book.pdf" for c in first_count_filter.must)

        # 3. 验证校验通过后原子切换生效 (set_payload is_active=True)
        assert mock_client.set_payload.called
        set_payload_calls = mock_client.set_payload.call_args_list
        # 至少一次嵌套更新与一次顶层更新
        assert len(set_payload_calls) >= 2

        # 4. 验证切换生效后异步删除旧版本淘汰数据点 (必须指定当前 course_id 与 material_id 且排除当前 version)
        mock_client.delete.assert_called_once()
        delete_filter = mock_client.delete.call_args.kwargs["points_selector"]
        must_keys = {c.key: c.match.value for c in delete_filter.must}
        assert must_keys["chunk.metadata.course_id"] == "catalog_100"
        assert must_keys["chunk.metadata.material_id"] == "c_book.pdf"
        must_not_cond = delete_filter.must_not[0]
        assert must_not_cond.key == "chunk.metadata.ingestion_version"
        assert must_not_cond.match.value == version


def test_ingest_course_material_with_custom_material_id() -> None:
    settings = AgentModelSettings()

    mock_parser = MagicMock()
    mock_parser.parse = AsyncMock(
        return_value=[
            Section(
                content=TextBlock(text="自定义教材测试正文。"),
                source="custom.pdf",
                metadata={"page": 1},
            )
        ]
    )

    mock_client = MagicMock()
    mock_client.get_collections = AsyncMock(return_value=MagicMock(collections=[]))
    mock_client.create_collection = AsyncMock()
    mock_client.count = AsyncMock(return_value=MagicMock(count=1))
    mock_client.set_payload = AsyncMock()
    mock_client.delete = AsyncMock()

    mock_store = MagicMock()
    mock_store.get_client.return_value = mock_client

    mock_kb = MagicMock()
    mock_kb.vector_store = mock_store
    mock_kb.insert_document = AsyncMock(return_value="doc_custom")

    with (
        patch("agent_service_v2.tools.rag.PDFParser", return_value=mock_parser),
        patch("agent_service_v2.tools.rag.get_course_knowledge_base", return_value=mock_kb),
        patch("pathlib.Path.exists", return_value=True),
        patch("pathlib.Path.is_file", return_value=True),
    ):
        cnt = asyncio.run(
            ingest_course_material(
                file_path="/fake/custom.pdf",
                course_id="catalog_200",
                settings=settings,
                material_id="cmat_unique_999",
            )
        )

        assert cnt == 1
        mock_kb.insert_document.assert_called_once()
        inserted_chunks = mock_kb.insert_document.call_args.args[0]
        meta = inserted_chunks[0].metadata
        assert meta["material_id"] == "cmat_unique_999"
        assert meta["filename"] == "custom.pdf"

        # 校验 count filter 绑定的是 material_id
        first_count_filter = mock_client.count.call_args_list[0].kwargs["count_filter"]
        assert any(c.key == "chunk.metadata.material_id" and c.match.value == "cmat_unique_999" for c in first_count_filter.must)

        # 校验 delete 淘汰旧版绑定的是 material_id
        mock_client.delete.assert_called_once()
        delete_filter = mock_client.delete.call_args.kwargs["points_selector"]
        must_keys = {c.key: c.match.value for c in delete_filter.must}
        assert must_keys["chunk.metadata.material_id"] == "cmat_unique_999"


def test_ingest_course_material_rollback_on_failure() -> None:
    settings = AgentModelSettings()

    mock_parser = MagicMock()
    mock_parser.parse = AsyncMock(
        return_value=[
            Section(
                content=TextBlock(text="章节内容。"),
                source="test.pdf",
                metadata={"page": 1},
            )
        ]
    )

    mock_client = MagicMock()
    mock_client.get_collections = AsyncMock(return_value=MagicMock(collections=[]))
    mock_client.delete = AsyncMock()

    mock_store = MagicMock()
    mock_store.get_client.return_value = mock_client

    mock_kb = MagicMock()
    mock_kb.vector_store = mock_store
    # 模拟写入发生不可恢复异常
    mock_kb.insert_document = AsyncMock(side_effect=RuntimeError("SiliconFlow 500 error"))

    with (
        patch("agent_service_v2.tools.rag.PDFParser", return_value=mock_parser),
        patch("agent_service_v2.tools.rag.get_course_knowledge_base", return_value=mock_kb),
        patch("pathlib.Path.exists", return_value=True),
        patch("pathlib.Path.is_file", return_value=True),
    ):
        with pytest.raises(RuntimeError, match="SiliconFlow 500 error"):
            asyncio.run(
                ingest_course_material(
                    file_path="/fake/c_book.pdf",
                    course_id="catalog_100",
                    settings=settings,
                )
            )

        # 验证失败时触发安全回滚，删除该批次未完成的点位
        mock_client.delete.assert_called_once()
        rollback_filter = mock_client.delete.call_args.kwargs["points_selector"]
        assert rollback_filter.must[0].key == "chunk.metadata.ingestion_version"


def test_ingest_course_material_parser_fallback_on_exception() -> None:
    settings = AgentModelSettings()

    # 模拟 PDFParser 解析崩溃（如格式畸形损坏）
    mock_parser = MagicMock()
    mock_parser.parse = AsyncMock(side_effect=ValueError("Corrupt PDF stream"))

    mock_client = MagicMock()
    mock_client.get_collections = AsyncMock(return_value=MagicMock(collections=[]))
    mock_client.count = AsyncMock(return_value=MagicMock(count=1))
    mock_client.set_payload = AsyncMock()
    mock_client.delete = AsyncMock()

    mock_store = MagicMock()
    mock_store.get_client.return_value = mock_client

    mock_kb = MagicMock()
    mock_kb.vector_store = mock_store
    mock_kb.insert_document = AsyncMock(return_value="doc_123")

    with (
        patch("agent_service_v2.tools.rag.PDFParser", return_value=mock_parser),
        patch("agent_service_v2.tools.rag.get_course_knowledge_base", return_value=mock_kb),
        patch("pathlib.Path.exists", return_value=True),
        patch("pathlib.Path.is_file", return_value=True),
        patch("pathlib.Path.read_text", return_value="降级兜底：提取出的纯文本正文内容。"),
    ):
        cnt = asyncio.run(
            ingest_course_material(
                file_path="/fake/corrupt.pdf",
                course_id="catalog_fallback",
                settings=settings,
            )
        )

        # 降级生效，不抛异常阻断，成功切片入库
        assert cnt >= 1
        mock_kb.insert_document.assert_called_once()


def test_ingest_course_material_rollback_on_count_mismatch() -> None:
    settings = AgentModelSettings()

    mock_parser = MagicMock()
    mock_parser.parse = AsyncMock(
        return_value=[
            Section(
                content=TextBlock(text="章节内容。"),
                source="test.pdf",
                metadata={"page": 1},
            )
        ]
    )

    mock_client = MagicMock()
    mock_client.get_collections = AsyncMock(return_value=MagicMock(collections=[]))
    # 模拟实际写入计数不一致 (预期 1，返回 0)
    mock_client.count = AsyncMock(return_value=MagicMock(count=0))
    mock_client.delete = AsyncMock()

    mock_store = MagicMock()
    mock_store.get_client.return_value = mock_client

    mock_kb = MagicMock()
    mock_kb.vector_store = mock_store
    mock_kb.insert_document = AsyncMock(return_value="doc_123")

    with (
        patch("agent_service_v2.tools.rag.PDFParser", return_value=mock_parser),
        patch("agent_service_v2.tools.rag.get_course_knowledge_base", return_value=mock_kb),
        patch("pathlib.Path.exists", return_value=True),
        patch("pathlib.Path.is_file", return_value=True),
    ):
        with pytest.raises(RuntimeError, match="Ingestion count verification failed"):
            asyncio.run(
                ingest_course_material(
                    file_path="/fake/test.pdf",
                    course_id="c_err",
                    settings=settings,
                )
            )

        # 验证触发回滚且删除当前版本未完成切片
        mock_client.delete.assert_called_once()
        rollback_filter = mock_client.delete.call_args.kwargs["points_selector"]
        assert rollback_filter.must[0].key == "chunk.metadata.ingestion_version"


def test_ingest_course_material_rollback_on_activation_exception() -> None:
    settings = AgentModelSettings()

    mock_parser = MagicMock()
    mock_parser.parse = AsyncMock(
        return_value=[
            Section(
                content=TextBlock(text="章节内容。"),
                source="test.pdf",
                metadata={"page": 1},
            )
        ]
    )

    mock_client = MagicMock()
    mock_client.get_collections = AsyncMock(return_value=MagicMock(collections=[]))
    mock_client.count = AsyncMock(return_value=MagicMock(count=1))
    mock_client.set_payload = AsyncMock(side_effect=RuntimeError("Qdrant set_payload timeout"))
    mock_client.delete = AsyncMock()

    mock_store = MagicMock()
    mock_store.get_client.return_value = mock_client

    mock_kb = MagicMock()
    mock_kb.vector_store = mock_store
    mock_kb.insert_document = AsyncMock(return_value="doc_123")

    with (
        patch("agent_service_v2.tools.rag.PDFParser", return_value=mock_parser),
        patch("agent_service_v2.tools.rag.get_course_knowledge_base", return_value=mock_kb),
        patch("pathlib.Path.exists", return_value=True),
        patch("pathlib.Path.is_file", return_value=True),
    ):
        with pytest.raises(RuntimeError, match="Failed to activate ingestion version"):
            asyncio.run(
                ingest_course_material(
                    file_path="/fake/test.pdf",
                    course_id="c_err",
                    settings=settings,
                )
            )

        # 验证回滚且绝不调用淘汰清理旧版本
        mock_client.delete.assert_called_once()
        rollback_filter = mock_client.delete.call_args.kwargs["points_selector"]
        assert rollback_filter.must[0].key == "chunk.metadata.ingestion_version"



def test_build_catalog_kg_context_respects_active_filter_and_fallback() -> None:
    settings = AgentModelSettings()

    point_active = MagicMock()
    point_active.payload = {
        "document_id": "doc-a",
        "chunk": {
            "content": {"type": "text", "text": "指针是存储内存地址的变量。"},
            "metadata": {"course_id": "catalog-1", "is_active": True},
        },
    }

    mock_client = MagicMock()
    mock_client.scroll = AsyncMock(return_value=([point_active], None))
    mock_store = MagicMock()
    mock_store.get_client.return_value = mock_client

    with patch("agent_service_v2.tools.rag.build_qdrant_store", return_value=mock_store):
        context = asyncio.run(
            build_catalog_kg_context("catalog-1", settings=settings)
        )

    assert "指针是存储内存地址的变量。" in context
    scroll_filter = mock_client.scroll.await_args.kwargs["scroll_filter"]
    # 验证主检索 must 显式限定 course_id 与 is_active=True
    must_keys = {c.key: c.match.value for c in scroll_filter.must}
    assert must_keys["chunk.metadata.course_id"] == "catalog-1"
    assert must_keys["chunk.metadata.is_active"] is True


def test_retrieve_course_context_excludes_unactivated_chunks() -> None:
    settings = AgentModelSettings()

    # 构造两个结果：一个是已激活切片，另一个是未激活（is_active=False）的切片
    active_chunk = Chunk(
        content=TextBlock(text="已生效的教材切片内容"),
        source="book.pdf",
        chunk_index=0,
        total_chunks=2,
        metadata={"course_id": "c1", "is_active": True, "filename": "book.pdf"},
    )
    res_active = MagicMock(spec=VectorSearchResult)
    res_active.chunk = active_chunk
    res_active.score = 0.95

    pending_chunk = Chunk(
        content=TextBlock(text="未生效的切片内容"),
        source="book.pdf",
        chunk_index=1,
        total_chunks=2,
        metadata={"course_id": "c1", "is_active": False, "filename": "book.pdf"},
    )
    res_pending = MagicMock(spec=VectorSearchResult)
    res_pending.chunk = pending_chunk
    res_pending.score = 0.99  # 即使分数更高

    mock_kb = MagicMock()
    mock_kb.search = AsyncMock(return_value=[res_pending, res_active])

    with patch("agent_service_v2.tools.rag.get_course_knowledge_base", return_value=mock_kb):
        result = asyncio.run(
            retrieve_course_context(
                query="教材内容",
                course_id="c1",
                limit=2,
                settings=settings,
            )
        )

        assert result["outcome"] == "success"
        sources = result["sources"]
        assert len(sources) == 1
        assert sources[0]["snippet"] == "已生效的教材切片内容"


def test_split_paragraphs_preserving_code_and_math_blocks() -> None:
    text = (
        "# 导言\n\n"
        "正文说明段落。\n\n"
        "```c\n"
        "#include <stdio.h>\n\n"
        "int main(void) {\n"
        "    int a = 1;\n\n"
        "    int b = 2;\n"
        "    return a + b;\n"
        "}\n"
        "```\n\n"
        "$$\n"
        "\\int_0^1 f(x) dx = F(1) - F(0)\n\n"
        "\\sum_{i=1}^n i = \\frac{n(n+1)}{2}\n"
        "$$\n\n"
        "正文总结段落。"
    )
    paras = split_paragraphs_preserving_blocks(text)
    assert len(paras) == 5
    assert paras[0] == "# 导言"
    assert paras[1] == "正文说明段落。"
    # 代码块内部空行完整保留，且未被切碎
    assert paras[2].startswith("```c\n#include <stdio.h>")
    assert paras[2].endswith("}\n```")
    # 数学块内部空行完整保留
    assert paras[3].startswith("$$\n\\int_0^1")
    assert paras[3].endswith("$$")
    assert paras[4] == "正文总结段落。"


def test_detect_heading_ignores_preprocessor_directives() -> None:
    # 确保 C 预处理指令不被误判为 ATX 一级标题
    assert detect_heading("#include <stdio.h>") is None
    assert detect_heading("# include <stdlib.h>") is None
    assert detect_heading("#define BUFFER_SIZE 1024") is None
    assert detect_heading("# define MAX_LEN 256") is None
    assert detect_heading("#ifdef DEBUG") is None
    assert detect_heading("#endif") is None
    assert detect_heading("#pragma once") is None


def test_text_from_agentscope_payload_robustness() -> None:
    # 1. 标准结构
    p1 = {"chunk": {"content": {"type": "text", "text": "标准文本"}}}
    assert _text_from_agentscope_payload(p1) == "标准文本"

    # 2. content 直接为字符串
    p2 = {"chunk": {"content": "直接字符串内容"}}
    assert _text_from_agentscope_payload(p2) == "直接字符串内容"

    # 3. chunk.text
    p3 = {"chunk": {"text": "块文本"}}
    assert _text_from_agentscope_payload(p3) == "块文本"

    # 4. 顶层 text
    p4 = {"text": "顶层文本"}
    assert _text_from_agentscope_payload(p4) == "顶层文本"

    # 5. 空或无效
    assert _text_from_agentscope_payload({}) == ""
    assert _text_from_agentscope_payload(None) == ""


def test_retrieve_course_context_handles_string_content() -> None:
    settings = AgentModelSettings()

    # 模拟 chunk.content 直接为 str 而不是 TextBlock
    mock_chunk = MagicMock()
    mock_chunk.content = "纯字符串内容切片"
    mock_chunk.metadata = {"course_id": "c1", "filename": "pure.txt"}
    mock_chunk.source = "pure.txt"

    mock_res = MagicMock(spec=VectorSearchResult)
    mock_res.chunk = mock_chunk
    mock_res.score = 0.88

    mock_kb = MagicMock()
    mock_kb.search = AsyncMock(return_value=[mock_res])

    with patch("agent_service_v2.tools.rag.get_course_knowledge_base", return_value=mock_kb):
        result = asyncio.run(
            retrieve_course_context(
                query="测试",
                course_id="c1",
                limit=1,
                settings=settings,
            )
        )

        assert result["outcome"] == "success"
        assert result["sources"][0]["snippet"] == "纯字符串内容切片"
        assert "Content: 纯字符串内容切片" in result["context_text"]


def test_matches_vector_dim() -> None:
    # 1. 单向量且维度匹配
    info_match = MagicMock()
    info_match.config.params.vectors.size = 1024
    assert _matches_vector_dim(info_match, 1024) is True
    assert _matches_vector_dim(info_match, 512) is False

    # 2. 命名多向量且其中一个匹配
    v1 = MagicMock(size=512)
    v2 = MagicMock(size=1024)
    info_multi = MagicMock()
    info_multi.config.params.vectors = {"text": v1, "dense": v2}
    assert _matches_vector_dim(info_multi, 1024) is True
    assert _matches_vector_dim(info_multi, 768) is False

    # 3. 畸形或缺失字段
    assert _matches_vector_dim(None, 1024) is False
    assert _matches_vector_dim(MagicMock(config=None), 1024) is False


def test_get_historical_fallback_collection_dimension_check() -> None:
    settings = AgentModelSettings(
        QDRANT_COURSE_KNOWLEDGE_COLLECTION="course_knowledge_v1_1024",
        EMBEDDING_DIMENSION=1024,
    )
    mock_client = MagicMock()
    mock_client.collection_exists = AsyncMock(return_value=True)

    # 维度匹配场景：返回候选集合名称
    mock_info_match = MagicMock()
    mock_info_match.config.params.vectors.size = 1024
    mock_client.get_collection = AsyncMock(return_value=mock_info_match)

    res = asyncio.run(
        _get_historical_fallback_collection(
            mock_client,
            settings,
            target_collection="course_knowledge_v1_1024_baai_1024",
        )
    )
    assert res == "course_knowledge_v1_1024"

    # 维度不匹配场景（例如历史集合为 512 维，当前配置为 1024 维）：严禁回退，返回 None
    mock_info_mismatch = MagicMock()
    mock_info_mismatch.config.params.vectors.size = 512
    mock_client.get_collection = AsyncMock(return_value=mock_info_mismatch)

    res_mismatch = asyncio.run(
        _get_historical_fallback_collection(
            mock_client,
            settings,
            target_collection="course_knowledge_v1_1024_baai_1024",
        )
    )
    assert res_mismatch is None

    # 集合不存在场景：返回 None
    mock_client.collection_exists = AsyncMock(return_value=False)
    res_not_exists = asyncio.run(
        _get_historical_fallback_collection(
            mock_client,
            settings,
            target_collection="course_knowledge_v1_1024_baai_1024",
        )
    )
    assert res_not_exists is None

    # 维度相同但模型不兼容：严格拒绝回退返回 None
    mock_client.collection_exists = AsyncMock(return_value=True)
    mock_client.get_collection = AsyncMock(return_value=mock_info_match)
    incompat_settings = AgentModelSettings(
        QDRANT_COURSE_KNOWLEDGE_COLLECTION="course_knowledge_v1_1024",
        EMBEDDING_DIMENSION=1024,
        EMBEDDING_MODEL="incompatible-model-foo",
    )
    res_incompat = asyncio.run(
        _get_historical_fallback_collection(
            mock_client,
            incompat_settings,
            target_collection="course_knowledge_v1_1024_other",
        )
    )
    assert res_incompat is None

    # 显式白名单机制生效
    whitelist_settings = AgentModelSettings(
        QDRANT_COURSE_KNOWLEDGE_COLLECTION="course_knowledge_v1_1024",
        EMBEDDING_DIMENSION=1024,
        EMBEDDING_MODEL="incompatible-model-foo",
        HISTORICAL_FALLBACK_COMPATIBLE_MODELS=["incompatible-model-foo"],
    )
    res_wl = asyncio.run(
        _get_historical_fallback_collection(
            mock_client,
            whitelist_settings,
            target_collection="course_knowledge_v1_1024_other",
        )
    )
    assert res_wl == "course_knowledge_v1_1024"

    # Client 为 None：返回 None
    assert asyncio.run(_get_historical_fallback_collection(None, settings, "target")) is None

