from agent_service.memory.tutoring_retrieval import TutoringRetrievalContext
from agent_service.prompts.tutoring import build_strategy_selection_messages, build_tutoring_messages
from agent_service.schemas.tutoring import RecentMessage, TutoringChatRequest, TutoringUserProfile


def test_build_tutoring_messages_includes_profile_retrieval_and_current_question() -> None:
    request = TutoringChatRequest(
        user_id="user-1",
        course_id="course-1",
        message="链式法则为什么要从外到内？",
        conversation_summary="用户正在学习复合函数求导。",
        recent_messages=[RecentMessage(role="assistant", content="我们先看复合函数。")],
        user_profile=TutoringUserProfile(guidance_level="L2", knowledge_weak=["链式法则"]),
    )
    context = TutoringRetrievalContext(
        user_id="user-1",
        course_id="course-1",
        query_text=request.message,
        include_course_knowledge=True,
        knowledge_points=["链式法则"],
        user_memory_facts=["用户容易把内外层顺序写反"],
        course_knowledge_chunks=["链式法则用于复合函数求导"],
    )

    messages = build_tutoring_messages(request, context)
    content = "\n".join(message.content for message in messages)

    assert [message.role for message in messages] == ["system", "assistant", "user"]
    assert "L2" in content
    assert "用户容易把内外层顺序写反" in content
    assert "链式法则用于复合函数求导" in content
    assert "链式法则为什么要从外到内？" in content
    assert "knowledge_points" in content
    assert "suggestion" in content


def test_build_strategy_selection_messages_requires_json_object() -> None:
    request = TutoringChatRequest(
        user_id="user-1",
        course_id="course-1",
        message="链式法则怎么用？",
        user_profile=TutoringUserProfile(guidance_level="L2", knowledge_weak=["链式法则"]),
    )
    context = TutoringRetrievalContext(
        user_id="user-1",
        course_id="course-1",
        query_text=request.message,
        include_course_knowledge=True,
        knowledge_points=["链式法则"],
        user_memory_facts=["用户容易把内外层顺序写反"],
        course_knowledge_chunks=["链式法则用于复合函数求导"],
    )

    messages = build_strategy_selection_messages(request, context)
    content = "\n".join(message.content for message in messages)

    assert [message.role for message in messages] == ["system", "user"]
    assert '{"strategy": "...", "focus_points": ["..."], "reason": "..."}' in content
    assert "guided_hint" in content
    assert "worked_example" in content
    assert "链式法则怎么用？" in content
