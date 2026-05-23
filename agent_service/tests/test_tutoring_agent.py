from agent_service.agents.tutoring import generate_tutoring_events
from agent_service.memory.tutoring_retrieval import TutoringRetrievalContext
from agent_service.schemas.tutoring import TutoringChatRequest, TutoringUserProfile


def test_generate_tutoring_events_builds_rule_based_sse_sequence() -> None:
    request = TutoringChatRequest(
        user_id="user-1",
        course_id="course-1",
        message="我不理解导数和切线斜率的关系",
        user_profile=TutoringUserProfile(
            guidance_level="L1",
            knowledge_mastered=["函数"],
            knowledge_weak=["导数"],
        ),
        conversation_summary="用户最近在学习导数定义。",
    )

    events = generate_tutoring_events(request)

    assert [event.type for event in events] == ["chunk", "knowledge_points", "suggestion", "done"]
    assert "导数" in events[0].content
    assert events[1].knowledge_points[0].name == "导数"
    assert events[2].suggested_exercises[0].title == "导数 巩固练习"
    assert events[3].message_id.startswith("msg_")
    assert events[3].knowledge_points_used == events[1].knowledge_points
    assert events[3].suggested_exercises == events[2].suggested_exercises


def test_generate_tutoring_events_uses_retrieval_context_knowledge_points() -> None:
    request = TutoringChatRequest(
        user_id="user-1",
        course_id="course-1",
        message="帮我讲一下链式法则",
        user_profile=TutoringUserProfile(guidance_level="L2", knowledge_weak=["导数"]),
    )
    context = TutoringRetrievalContext(
        user_id="user-1",
        course_id="course-1",
        query_text="帮我讲一下链式法则",
        include_course_knowledge=True,
        knowledge_points=["链式法则"],
        user_memory_facts=["用户容易混淆复合函数求导顺序"],
        course_knowledge_chunks=["链式法则用于复合函数求导"],
    )

    events = generate_tutoring_events(request, retrieval_context=context)

    assert events[0].content.startswith("结合长期记忆和课程知识，")
    assert events[1].knowledge_points[0].name == "链式法则"
    assert events[1].knowledge_points[0].mastery is None
