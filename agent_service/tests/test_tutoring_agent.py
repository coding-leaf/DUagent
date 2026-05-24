from agent_service.agents.tutoring import (
    build_tutoring_generation_result,
    generate_tutoring_events,
    parse_tutoring_model_response,
)
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


def test_generate_tutoring_events_prefers_model_structured_overrides() -> None:
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
        knowledge_points=["导数"],
        user_memory_facts=["用户容易混淆复合函数求导顺序"],
        course_knowledge_chunks=["链式法则用于复合函数求导"],
    )

    events = generate_tutoring_events(
        request,
        retrieval_context=context,
        knowledge_point_names=["链式法则", "复合函数"],
        suggestion_text="先确认外层函数，再检查内层自变量怎么变化。",
    )

    assert [item.name for item in events[1].knowledge_points] == ["链式法则", "复合函数"]
    assert events[2].suggestion == "先确认外层函数，再检查内层自变量怎么变化。"
    assert events[3].knowledge_points_used == events[1].knowledge_points


def test_parse_tutoring_model_response_extracts_structured_payload() -> None:
    model_output = (
        "链式法则用于复合函数求导，要先看外层函数。"
        "\n<agent_result>{\"knowledge_points\":[\"链式法则\",\"复合函数\"],"
        "\"suggestion\":\"先确认外层，再检查内层导数。\"}</agent_result>"
    )

    parsed = parse_tutoring_model_response(model_output)

    assert parsed.model_text == "链式法则用于复合函数求导，要先看外层函数。"
    assert parsed.knowledge_point_names == ["链式法则", "复合函数"]
    assert parsed.suggestion_text == "先确认外层，再检查内层导数。"


def test_parse_tutoring_model_response_falls_back_on_invalid_json() -> None:
    model_output = (
        "链式法则用于复合函数求导。"
        "\n<agent_result>{\"knowledge_points\": [}</agent_result>"
    )

    parsed = parse_tutoring_model_response(model_output)

    assert parsed.model_text == "链式法则用于复合函数求导。"
    assert parsed.knowledge_point_names == []
    assert parsed.suggestion_text is None


def test_build_tutoring_generation_result_collects_single_runtime_object() -> None:
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
        knowledge_points=["导数"],
        user_memory_facts=["用户容易混淆复合函数求导顺序"],
        course_knowledge_chunks=["链式法则用于复合函数求导"],
    )
    model_response = parse_tutoring_model_response(
        "链式法则先看外层函数，再乘以内层导数。"
        "\n<agent_result>{\"knowledge_points\":[\"链式法则\"],"
        "\"suggestion\":\"先确认外层函数，再检查内层导数。\"}</agent_result>"
    )

    result = build_tutoring_generation_result(request, context, model_response=model_response)

    assert result.chunk_text == "链式法则先看外层函数，再乘以内层导数。"
    assert [item.name for item in result.knowledge_points] == ["链式法则"]
    assert result.suggestion_text == "先确认外层函数，再检查内层导数。"
    assert result.used_rule_fallback is False
