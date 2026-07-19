from agent_service_v2.safety.internal_disclosure_filter import (
    INTERNAL_DISCLOSURE_REPLACEMENT,
    InternalDisclosureFilter,
)


PROTECTED_TOOLS = ("read_learning_progress", "reset_tools")


def test_internal_disclosure_filter_hides_internal_implementation_details():
    checker = InternalDisclosureFilter(protected_identifiers=PROTECTED_TOOLS)

    filtered, count = checker.filter(
        "调用 read_learning_progress，并请求 "
        "/internal/ai-chat/learning-progress，使用 X-Internal-Agent-Token；"
        "不要输出 reference_solution 或 hidden_inputs。"
    )

    assert count == 5
    assert filtered.count(INTERNAL_DISCLOSURE_REPLACEMENT) == 5
    assert "read_learning_progress" not in filtered
    assert "/internal/" not in filtered
    assert "X-Internal-Agent-Token" not in filtered
    assert "reference_solution" not in filtered
    assert "hidden_inputs" not in filtered


def test_internal_disclosure_filter_preserves_normal_teaching_content():
    checker = InternalDisclosureFilter(protected_identifiers=PROTECTED_TOOLS)
    text = "可以用 read_progress() 封装学习进度读取，再解释二叉树的遍历过程。"

    assert checker.filter(text) == (text, 0)

    wrapped, count = checker.filter("trace_read_learning_progress_result")
    assert wrapped == f"trace_{INTERNAL_DISCLOSURE_REPLACEMENT}_result"
    assert count == 1


def test_internal_disclosure_stream_hides_matches_split_across_chunks():
    stream = InternalDisclosureFilter(protected_identifiers=PROTECTED_TOOLS).stream()

    parts = [
        stream.feed("内部调用 read_learning_"),
        stream.feed("progress，请求 /inter"),
        stream.feed("nal/ai-chat/recent-answers 后返回。"),
        stream.finish(),
    ]
    output = "".join(parts)

    assert output.count(INTERNAL_DISCLOSURE_REPLACEMENT) == 2
    assert "read_learning_progress" not in output
    assert "/internal/" not in output
    assert stream.match_count == 2
