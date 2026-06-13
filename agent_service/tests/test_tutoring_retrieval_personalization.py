"""检索个性化加权：weak chunk 上浮 + user_memory 在 course_knowledge 之前。"""

from agent_service.agents.tutoring_react_flow import _build_react_user_message
from agent_service.agents.tutoring_strategy import TutoringStrategy
from agent_service.memory.tutoring_retrieval import TutoringRetrievalContext
from agent_service.schemas.tutoring import TutoringChatRequest, TutoringUserProfile


def _make_request(weak: list[str]) -> TutoringChatRequest:
    return TutoringChatRequest(
        user_id="u1",
        course_id="c1",
        message="指针怎么用？",
        user_profile=TutoringUserProfile(guidance_level="L2", knowledge_weak=weak),
    )


def _make_context(user_facts: list[str], chunks: list[str]) -> TutoringRetrievalContext:
    return TutoringRetrievalContext(
        user_id="u1",
        course_id="c1",
        query_text="指针怎么用？",
        include_course_knowledge=True,
        knowledge_points=[],
        user_memory_facts=user_facts,
        course_knowledge_chunks=chunks,
        matched_kg_nodes=[],
    )


def _make_strategy() -> TutoringStrategy:
    return TutoringStrategy(
        strategy="worked_example",
        instruction="用相似例题解释",
        focus_points=["指针"],
        source="rule",
    )


def test_user_memory_section_before_course_knowledge() -> None:
    """user_memory 段在 course_knowledge 段之前。"""
    context = _make_context(
        user_facts=["学生之前用 malloc 忘记 free"],
        chunks=["指针是存储内存地址的变量"],
    )
    msg = _build_react_user_message(_make_request(["指针"]), context, strategy=_make_strategy())
    mem_idx = msg.index("长期记忆")
    course_idx = msg.index("课程知识")
    assert mem_idx < course_idx, "user_memory 段应在 course_knowledge 段之前"


def test_weak_related_chunk_floats_to_front() -> None:
    """含 weak 词条的 chunk 应排在不含 weak 词条的 chunk 之前。"""
    context = _make_context(
        user_facts=[],
        chunks=["数组是连续内存的集合", "指针存储内存地址，可以动态分配", "循环语句是控制流"],
    )
    msg = _build_react_user_message(_make_request(["指针"]), context, strategy=_make_strategy())
    idx_pointer = msg.index("指针存储内存地址")
    idx_array = msg.index("数组是连续内存")
    assert idx_pointer < idx_array, "含 weak 词条的 chunk 应上浮到前面"


def test_no_chunk_dropped_after_reorder() -> None:
    """重排不丢 chunk。"""
    chunks = ["数组是连续内存的集合", "指针存储内存地址，可以动态分配", "循环语句是控制流"]
    context = _make_context(user_facts=[], chunks=chunks)
    msg = _build_react_user_message(_make_request(["指针"]), context, strategy=_make_strategy())
    for chunk in chunks:
        assert chunk in msg, f"chunk 不应被丢弃: {chunk}"
