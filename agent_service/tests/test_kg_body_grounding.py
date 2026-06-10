import asyncio

from agent_service.memory.kg_body_grounding import score_kg_body_grounding
from agent_service.memory.vector_store import VectorSearchResult


class FakeEmbeddingProvider:
    def __init__(self) -> None:
        self.calls: list[list[str]] = []

    async def embed_texts(self, texts):
        self.calls.append(list(texts))
        return [[float(len(text))] for text in texts]


class FakeVectorStore:
    def __init__(self, results_by_vector: dict[float, list[VectorSearchResult]]) -> None:
        self.results_by_vector = results_by_vector
        self.calls: list[dict] = []

    async def search_course_knowledge(self, course_id, vector, limit=5):
        self.calls.append({"course_id": course_id, "vector": list(vector), "limit": limit})
        return self.results_by_vector.get(float(vector[0]), [])


def test_scores_each_node_with_embedding_and_course_search() -> None:
    embedding = FakeEmbeddingProvider()
    nodes = [
        {"id": "n1", "name": "顺序表"},
        {"id": "n2", "name": "链表"},
    ]
    store = FakeVectorStore(
        {
            float(len("顺序表")): [
                VectorSearchResult(
                    text="顺序表是一种使用连续存储空间保存线性表元素的数据结构，支持按下标随机访问。",
                    score=0.82,
                    payload={"chunk_id": "c1", "source_file": "chapter1.md"},
                )
            ],
            float(len("链表")): [
                VectorSearchResult(
                    text="链表通过指针把节点连接起来，插入和删除时通常不需要移动大量元素。",
                    score=0.78,
                    payload={"chunk_id": "c2", "source_file": "chapter2.md"},
                )
            ],
        }
    )

    results = asyncio.run(score_kg_body_grounding("course-1", nodes, embedding, vector_store=store, limit=4))

    assert embedding.calls == [["顺序表"], ["链表"]]
    assert store.calls == [
        {"course_id": "course-1", "vector": [3.0], "limit": 4},
        {"course_id": "course-1", "vector": [2.0], "limit": 4},
    ]
    assert [result.node_id for result in results] == ["n1", "n2"]
    assert [result.node_name for result in results] == ["顺序表", "链表"]
    assert [result.supported for result in results] == [True, True]
    assert results[0].body_top1_score == 0.82
    assert results[0].chunk_id == "c1"
    assert results[0].source_file == "chapter1.md"
    assert len(results[0].preview) <= 120


def test_query_expansion_includes_chapter_and_neighbor_node_names() -> None:
    embedding = FakeEmbeddingProvider()
    nodes = [
        {"id": "n1", "name": "变量与算术表达式", "chapter": "第1章 导言"},
        {"id": "n2", "name": "for语句", "chapter": "第1章 导言"},
        {"id": "n3", "name": "符号常量", "chapter": "第1章 导言"},
    ]
    query = "第1章 导言 变量与算术表达式 for语句 符号常量"
    store = FakeVectorStore(
        {
            float(len(query)): [
                VectorSearchResult(
                    text="变量与算术表达式用于说明 C 程序中变量声明、赋值和表达式求值的基本规则。",
                    score=0.73,
                    payload={"chunk_id": "expanded", "source_file": "chapter1.md"},
                )
            ]
        }
    )

    results = asyncio.run(
        score_kg_body_grounding(
            "course-1",
            nodes,
            embedding,
            vector_store=store,
            query_expansion=True,
            edges=[{"from": "n1", "to": "n2"}, {"from": "n3", "to": "n1"}],
        )
    )

    assert embedding.calls[0] == ["变量与算术表达式", query]
    assert results[0].node_name == "变量与算术表达式"
    assert results[0].supported is True
    assert results[0].chunk_id == "expanded"


def test_query_expansion_keeps_better_node_name_candidate() -> None:
    embedding = FakeEmbeddingProvider()
    nodes = [
        {"id": "n1", "name": "赋值运算符与表达式", "chapter": "第2章 类型、运算符与表达式"},
        {"id": "n2", "name": "条件表达式", "chapter": "第2章 类型、运算符与表达式"},
    ]
    expanded_query = "第2章 类型、运算符与表达式 赋值运算符与表达式 条件表达式"
    store = FakeVectorStore(
        {
            float(len("赋值运算符与表达式")): [
                VectorSearchResult(
                    text="赋值运算符要求左操作数是可修改的左值，赋值表达式的值为赋值后的左操作数。",
                    score=0.74,
                    payload={"chunk_id": "node-name-hit", "source_file": "chapter2.md"},
                )
            ],
            float(len(expanded_query)): [],
        }
    )

    result = asyncio.run(
        score_kg_body_grounding(
            "course-1",
            nodes,
            embedding,
            vector_store=store,
            query_expansion=True,
            edges=[{"from": "n1", "to": "n2"}],
        )
    )[0]

    assert embedding.calls[0] == ["赋值运算符与表达式", expanded_query]
    assert result.supported is True
    assert result.body_top1_score == 0.74
    assert result.chunk_id == "node-name-hit"


def test_filters_toc_like_top_hit_and_uses_next_body_hit() -> None:
    embedding = FakeEmbeddingProvider()
    store = FakeVectorStore(
        {
            float(len("二叉树")): [
                VectorSearchResult(
                    text="目录\n1. 树的概念\n2. 二叉树\n3. 遍历",
                    score=0.94,
                    payload={"chunk_id": "toc", "source_file": "chapter3.md"},
                ),
                VectorSearchResult(
                    text="二叉树是每个节点至多有两个子节点的树形结构，常见遍历方式包括前序、中序和后序。",
                    score=0.76,
                    payload={"chunk_id": "body", "source_file": "chapter3.md"},
                ),
            ]
        }
    )

    result = asyncio.run(score_kg_body_grounding("course-1", [{"id": "n1", "name": "二叉树"}], embedding, vector_store=store))[0]

    assert result.supported is True
    assert result.body_top1_score == 0.76
    assert result.chunk_id == "body"
    assert "目录" not in result.preview


def test_filters_dotted_page_number_listing_and_uses_next_body_hit() -> None:
    embedding = FakeEmbeddingProvider()
    store = FakeVectorStore(
        {
            float(len("指针与数组")): [
                VectorSearchResult(
                    text=(
                        "5.7 指针和多维数组 ........ 123\n"
                        "5.8 指针数组的初始化 ........ 128\n"
                        "5.9 命令行参数 ........ 134"
                    ),
                    score=0.95,
                    payload={"chunk_id": "dotted-toc", "source_file": "chapter5.pdf"},
                ),
                VectorSearchResult(
                    text="指针与数组关系密切，数组名在表达式中通常会转换为指向首元素的指针。",
                    score=0.74,
                    payload={"chunk_id": "body", "source_file": "chapter5.pdf"},
                ),
            ]
        }
    )

    result = asyncio.run(
        score_kg_body_grounding(
            "course-1",
            [{"id": "n1", "name": "指针与数组"}],
            embedding,
            vector_store=store,
        )
    )[0]

    assert result.supported is True
    assert result.body_top1_score == 0.74
    assert result.chunk_id == "body"


def test_filters_appendix_listing_and_bare_index_terms() -> None:
    embedding = FakeEmbeddingProvider()
    store = FakeVectorStore(
        {
            float(len("数学函数")): [
                VectorSearchResult(
                    text=(
                        "附录B 标准库\n"
                        "B.1 输入与输出 ........ 241\n"
                        "B.2 字符串函数 ........ 246\n"
                        "B.3 数学函数 ........ 252"
                    ),
                    score=0.91,
                    payload={"chunk_id": "appendix-toc", "source_file": "appendix.pdf"},
                )
            ],
            float(len("break语句")): [
                VectorSearchResult(
                    text="auto 201\nbreak 202\ncase 203\nchar 204\ncontinue 205\ndefault 206",
                    score=0.89,
                    payload={"chunk_id": "bare-index", "source_file": "chapter-index.pdf"},
                )
            ],
        }
    )

    results = asyncio.run(
        score_kg_body_grounding(
            "course-1",
            [{"id": "n1", "name": "数学函数"}, {"id": "n2", "name": "break语句"}],
            embedding,
            vector_store=store,
        )
    )

    assert [(result.node_id, result.supported, result.body_top1_score) for result in results] == [
        ("n1", False, None),
        ("n2", False, None),
    ]
    assert [result.chunk_id for result in results] == [None, None]


def test_filters_mixed_index_page_sequences_and_sparse_dotted_pages() -> None:
    embedding = FakeEmbeddingProvider()
    store = FakeVectorStore(
        {
            float(len("变量与算术表达式")): [
                VectorSearchResult(
                    text=(
                        "expression order of evaluation（表达式的求值次序），52，200 "
                        "expression parenthesized（用括号括起来的表达式），201 "
                        "external variable（外部变量），40，83"
                    ),
                    score=0.92,
                    payload={"chunk_id": "english-index", "source_file": "chapter1.pdf"},
                ),
                VectorSearchResult(
                    text="变量与算术表达式用于说明 C 语言中变量声明、赋值、算术运算和表达式求值的基本规则。",
                    score=0.72,
                    payload={"chunk_id": "body", "source_file": "chapter1.pdf"},
                ),
            ],
            float(len("文件复制")): [
                VectorSearchResult(
                    text=".....................................30 1.5.1. 文件复制 ................................................ 31",
                    score=0.9,
                    payload={"chunk_id": "sparse-dotted", "source_file": "chapter1.pdf"},
                ),
                VectorSearchResult(
                    text="文件复制示例通过反复调用 getchar 和 putchar，把输入中的每个字符复制到输出。",
                    score=0.71,
                    payload={"chunk_id": "copy-body", "source_file": "chapter1.pdf"},
                ),
            ],
            float(len("入门")): [
                VectorSearchResult(
                    text="...................................................................252 索引 ..............................................",
                    score=0.88,
                    payload={"chunk_id": "trailing-index", "source_file": "chapter1.pdf"},
                ),
                VectorSearchResult(
                    text="本章介绍 C 语言程序设计入门所需的基本元素，包括变量、表达式、循环和函数。",
                    score=0.69,
                    payload={"chunk_id": "intro-body", "source_file": "chapter1.pdf"},
                ),
            ],
        }
    )

    results = asyncio.run(
        score_kg_body_grounding(
            "course-1",
            [
                {"id": "n1", "name": "变量与算术表达式"},
                {"id": "n2", "name": "文件复制"},
                {"id": "n3", "name": "入门"},
            ],
            embedding,
            vector_store=store,
        )
    )

    assert [(result.node_id, result.chunk_id, result.body_top1_score) for result in results] == [
        ("n1", "body", 0.72),
        ("n2", "copy-body", 0.71),
        ("n3", "intro-body", 0.69),
    ]


def test_unsupported_when_no_body_candidate_or_score_below_threshold() -> None:
    embedding = FakeEmbeddingProvider()
    store = FakeVectorStore(
        {
            float(len("图")): [
                VectorSearchResult(
                    text="索引\n图\n树\n排序",
                    score=0.91,
                    payload={"chunk_id": "index", "source_file": "index.md"},
                )
            ],
            float(len("队列")): [
                VectorSearchResult(
                    text="队列是一种先进先出的线性结构，入队发生在队尾，出队发生在队首。",
                    score=0.61,
                    payload={"chunk_id": "queue", "source_file": "chapter4.md"},
                )
            ],
        }
    )

    results = asyncio.run(
        score_kg_body_grounding(
            "course-1",
            [{"id": "n1", "name": "图"}, {"id": "n2", "name": "队列"}],
            embedding,
            vector_store=store,
            threshold=0.70,
        )
    )

    assert [(result.node_id, result.supported, result.body_top1_score) for result in results] == [
        ("n1", False, None),
        ("n2", False, 0.61),
    ]
    assert results[0].chunk_id is None
    assert results[0].preview == ""
    assert results[1].chunk_id == "queue"


def test_extracts_node_name_with_title_label_and_id_fallbacks() -> None:
    embedding = FakeEmbeddingProvider()
    store = FakeVectorStore(
        {
            float(len("哈希表")): [],
            float(len("栈")): [],
            float(len("node-only")): [],
        }
    )

    results = asyncio.run(
        score_kg_body_grounding(
            "course-1",
            [
                {"id": "n1", "title": "哈希表"},
                {"id": "n2", "label": "栈"},
                {"id": "node-only"},
            ],
            embedding,
            vector_store=store,
        )
    )

    assert embedding.calls == [["哈希表"], ["栈"], ["node-only"]]
    assert [(result.node_id, result.node_name) for result in results] == [
        ("n1", "哈希表"),
        ("n2", "栈"),
        ("node-only", "node-only"),
    ]
