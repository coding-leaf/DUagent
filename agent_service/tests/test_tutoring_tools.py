import asyncio

from agent_service.memory.vector_store import VectorSearchResult


class FakeEmbeddingProvider:
    """可配置成功/失败的 fake embedding provider。"""

    def __init__(self, should_fail: bool = False) -> None:
        self.calls: list[list[str]] = []
        self._should_fail = should_fail

    async def embed_texts(self, texts):
        self.calls.append(list(texts))
        if self._should_fail:
            raise RuntimeError("embedding unavailable")
        return [[0.1, 0.2, 0.3] for _ in texts]


class FakeVectorStore:
    """可配置返回结果的 fake QdrantVectorStore。"""

    def __init__(self, results: list[VectorSearchResult] | None = None) -> None:
        self.calls: list[dict] = []
        self._results = results or []

    async def search_course_knowledge(self, course_id, vector, limit=3):
        self.calls.append({"course_id": course_id, "limit": limit})
        return self._results


def _result(text: str) -> VectorSearchResult:
    return VectorSearchResult(text=text, score=0.9, payload={"content": text})


# ── Tests ──────────────────────────────────────────────────────────


def test_global_scope_returns_no_knowledge_message() -> None:
    """course_id=None 时直接返回提示，不调 embedding。"""
    from agent_service.agents.tutoring_tools import build_tutoring_toolkit

    provider = FakeEmbeddingProvider()
    store = FakeVectorStore()
    toolkit = build_tutoring_toolkit(
        course_id=None, embedding_provider=provider, vector_store=store
    )
    tool_func = _get_registered_tool(toolkit, "retrieve_course_knowledge")
    result = asyncio.run(tool_func("线性表是什么？"))

    assert result.content == [{"text": "当前对话无指定课程知识库。"}]
    assert provider.calls == []


def test_search_returns_chunks_joined_with_separator() -> None:
    from agent_service.agents.tutoring_tools import build_tutoring_toolkit

    store = FakeVectorStore(
        results=[
            _result("线性表是相同类型数据元素的有限序列。"),
            _result("链表用指针表示元素之间的逻辑关系。"),
        ]
    )
    provider = FakeEmbeddingProvider()
    toolkit = build_tutoring_toolkit(
        course_id="data-structures",
        embedding_provider=provider,
        vector_store=store,
    )
    tool_func = _get_registered_tool(toolkit, "retrieve_course_knowledge")

    result = asyncio.run(tool_func("线性表"))

    text = result.content[0]["text"]
    assert "线性表是相同类型数据元素的有限序列" in text
    assert "---" in text
    assert "链表用指针" in text
    assert store.calls[0]["course_id"] == "data-structures"
    assert store.calls[0]["limit"] == 3


def test_empty_search_returns_empty_message() -> None:
    from agent_service.agents.tutoring_tools import build_tutoring_toolkit

    store = FakeVectorStore(results=[])
    provider = FakeEmbeddingProvider()
    toolkit = build_tutoring_toolkit(
        course_id="data-structures",
        embedding_provider=provider,
        vector_store=store,
    )
    tool_func = _get_registered_tool(toolkit, "retrieve_course_knowledge")

    result = asyncio.run(tool_func("不存在的内容"))

    assert result.content == [{"text": "未找到相关课程知识。"}]


def test_embedding_failure_returns_error_message() -> None:
    from agent_service.agents.tutoring_tools import build_tutoring_toolkit

    provider = FakeEmbeddingProvider(should_fail=True)
    toolkit = build_tutoring_toolkit(
        course_id="data-structures",
        embedding_provider=provider,
        vector_store=FakeVectorStore(),
    )
    tool_func = _get_registered_tool(toolkit, "retrieve_course_knowledge")

    result = asyncio.run(tool_func("线性表"))

    assert result.content == [{"text": "课程知识检索暂时不可用。"}]


def test_tool_schema_only_exposes_query() -> None:
    """确认模型的 JSON schema 只暴露 query，不暴露 course_id / provider / limit。"""
    from agent_service.agents.tutoring_tools import build_tutoring_toolkit

    toolkit = build_tutoring_toolkit(
        course_id="data-structures",
        embedding_provider=FakeEmbeddingProvider(),
        vector_store=FakeVectorStore(),
        limit=3,
    )
    func = toolkit.get_json_schemas()[0]["function"]

    assert func["name"] == "retrieve_course_knowledge"
    props = func["parameters"]["properties"]
    assert set(props.keys()) == {"query"}
    assert props["query"]["type"] == "string"
    assert "course_id" not in props
    assert "limit" not in props
    assert "embedding_provider" not in props


def _get_registered_tool(toolkit, name: str):
    if name in toolkit.tools:
        return toolkit.tools[name].original_func
    raise KeyError(f"tool {name} not found in toolkit")
