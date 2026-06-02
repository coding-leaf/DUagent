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
        self.calls.append({"method": "search_course_knowledge", "course_id": course_id, "limit": limit})
        return self._results

    async def search_user_memory(self, user_id, vector, limit=3):
        self.calls.append({"method": "search_user_memory", "user_id": user_id, "limit": limit})
        return self._results


def _result(text: str) -> VectorSearchResult:
    return VectorSearchResult(text=text, score=0.9, payload={"content": text})


def _assert_text_block(result, expected_text: str | None = None) -> None:
    assert result.content
    block = result.content[0]
    assert block["type"] == "text"
    assert "text" in block
    if expected_text is not None:
        assert block["text"] == expected_text


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

    _assert_text_block(result, "当前对话无指定课程知识库。")
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

    _assert_text_block(result)
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

    _assert_text_block(result, "未找到相关课程知识。")


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

    _assert_text_block(result, "课程知识检索暂时不可用。")


def test_tool_schemas_expose_only_query() -> None:
    """确认两个工具的 JSON schema 各只暴露 query 参数。按 function name 查找，不依赖注册顺序。"""
    from agent_service.agents.tutoring_tools import build_tutoring_toolkit

    toolkit = build_tutoring_toolkit(
        course_id="data-structures",
        embedding_provider=FakeEmbeddingProvider(),
        vector_store=FakeVectorStore(),
        user_id="user-1",
        limit=3,
    )
    schemas = {s["function"]["name"]: s["function"] for s in toolkit.get_json_schemas()}

    for name in ("retrieve_course_knowledge", "retrieve_user_memory"):
        func = schemas[name]
        props = func["parameters"]["properties"]
        assert set(props.keys()) == {"query"}, f"{name} schema should only expose query"
        assert props["query"]["type"] == "string"
        assert "course_id" not in props
        assert "user_id" not in props
        assert "limit" not in props
        assert "embedding_provider" not in props


# ── retrieve_user_memory tests ─────────────────────────────────────


def test_retrieve_user_memory_returns_facts() -> None:
    from agent_service.agents.tutoring_tools import build_tutoring_toolkit

    store = FakeVectorStore(
        results=[
            _result("用户对二叉树遍历掌握较差。"),
            _result("用户上次练习快速排序正确率80%。"),
        ]
    )
    provider = FakeEmbeddingProvider()
    toolkit = build_tutoring_toolkit(
        course_id="data-structures",
        embedding_provider=provider,
        vector_store=store,
        user_id="user-1",
    )
    tool_func = _get_registered_tool(toolkit, "retrieve_user_memory")

    result = asyncio.run(tool_func("二叉树"))

    _assert_text_block(result)
    text = result.content[0]["text"]
    assert "二叉树遍历" in text
    assert "---" in text
    assert "快速排序" in text
    assert store.calls[0]["method"] == "search_user_memory"
    assert store.calls[0]["user_id"] == "user-1"
    assert store.calls[0]["limit"] == 3


def test_retrieve_user_memory_empty_user_id_skips_embedding() -> None:
    """user_id 为空时不调用 embedding 和 vector_store。"""
    from agent_service.agents.tutoring_tools import build_tutoring_toolkit

    provider = FakeEmbeddingProvider()
    store = FakeVectorStore()
    toolkit = build_tutoring_toolkit(
        course_id="data-structures",
        embedding_provider=provider,
        vector_store=store,
        user_id=None,
    )
    tool_func = _get_registered_tool(toolkit, "retrieve_user_memory")

    result = asyncio.run(tool_func("二叉树"))

    _assert_text_block(result, "当前对话无用户记忆数据。")
    assert provider.calls == []
    assert store.calls == []


def test_retrieve_user_memory_empty_results() -> None:
    from agent_service.agents.tutoring_tools import build_tutoring_toolkit

    store = FakeVectorStore(results=[])
    provider = FakeEmbeddingProvider()
    toolkit = build_tutoring_toolkit(
        course_id="data-structures",
        embedding_provider=provider,
        vector_store=store,
        user_id="user-1",
    )
    tool_func = _get_registered_tool(toolkit, "retrieve_user_memory")

    result = asyncio.run(tool_func("不存在的内容"))

    _assert_text_block(result, "未找到相关用户记忆。")


def test_retrieve_user_memory_embedding_failure() -> None:
    from agent_service.agents.tutoring_tools import build_tutoring_toolkit

    provider = FakeEmbeddingProvider(should_fail=True)
    toolkit = build_tutoring_toolkit(
        course_id="data-structures",
        embedding_provider=provider,
        vector_store=FakeVectorStore(),
        user_id="user-1",
    )
    tool_func = _get_registered_tool(toolkit, "retrieve_user_memory")

    result = asyncio.run(tool_func("二叉树"))

    _assert_text_block(result, "用户记忆检索暂时不可用。")


def test_retrieve_user_memory_truncates_long_chunks() -> None:
    from agent_service.agents.tutoring_tools import build_tutoring_toolkit

    long_text = "A" * 600
    store = FakeVectorStore(results=[_result(long_text)])
    provider = FakeEmbeddingProvider()
    toolkit = build_tutoring_toolkit(
        course_id="data-structures",
        embedding_provider=provider,
        vector_store=store,
        user_id="user-1",
    )
    tool_func = _get_registered_tool(toolkit, "retrieve_user_memory")

    result = asyncio.run(tool_func("test"))

    _assert_text_block(result)
    text = result.content[0]["text"]
    assert len(text) <= 503  # 500 chars + "..."
    assert text.endswith("...")


# ── user_id propagation test ────────────────────────────────────────


def test_build_tutoring_toolkit_receives_user_id() -> None:
    """generate_tutoring_react_response 传入 request.user_id 到 build_tutoring_toolkit。"""
    from unittest.mock import patch

    from agent_service.agents.tutoring_react_flow import generate_tutoring_react_response
    from agent_service.agents.tutoring_react import TutorReActAgent
    from agent_service.memory.tutoring_retrieval import TutoringRetrievalContext

    class _DummyModel:
        pass

    class _DummyFormatter:
        pass

    async def _dummy_generate(_self, _msg):
        return "{}"

    with (
        patch.object(TutorReActAgent, "generate", _dummy_generate),
        patch("agent_service.agents.tutoring_react_flow.build_tutoring_toolkit") as mock_build,
    ):
        mock_build.return_value = None

        request = _fake_chat_request(user_id="user-1", course_id="data-structures")
        retrieval_ctx = TutoringRetrievalContext(
            user_id="user-1",
            course_id="data-structures",
            query_text="测试问题",
            include_course_knowledge=True,
        )
        provider = _fake_chat_provider()
        embedding = FakeEmbeddingProvider()
        store = FakeVectorStore()

        asyncio.run(
            generate_tutoring_react_response(
                request, retrieval_ctx, provider,
                embedding_provider=embedding,
                vector_store=store,
            )
        )

        mock_build.assert_called_once()
        assert mock_build.call_args.kwargs["user_id"] == "user-1"


# ── Helpers ─────────────────────────────────────────────────────────


def _fake_chat_request(*, user_id: str, course_id: str):
    from agent_service.schemas.tutoring import TutoringChatRequest, TutoringUserProfile

    return TutoringChatRequest(
        user_id=user_id,
        course_id=course_id,
        message="测试问题",
        scope="course",
        user_profile=TutoringUserProfile(
            guidance_level="L2",
            knowledge_weak=["二叉树"],
            knowledge_mastered=["数组"],
        ),
    )


def _fake_chat_provider():
    from types import SimpleNamespace

    return SimpleNamespace(
        model=_DummyModel(),
        formatter=_DummyFormatter(),
    )


class _DummyModel:
    pass


class _DummyFormatter:
    pass


def _get_registered_tool(toolkit, name: str):
    if name in toolkit.tools:
        return toolkit.tools[name].original_func
    raise KeyError(f"tool {name} not found in toolkit")
