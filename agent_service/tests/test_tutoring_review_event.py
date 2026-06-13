from agent_service.schemas.tutoring import ReviewEvent, TutoringSSEEvent


def test_review_event_schema_fields() -> None:
    ev = ReviewEvent(status="flagged", reason="off_topic")
    assert ev.type == "review"
    assert ev.status == "flagged"
    assert ev.reason == "off_topic"


def test_review_event_in_sse_union() -> None:
    # 能被 parse 为 TutoringSSEEvent（union 包含 ReviewEvent）
    from pydantic import TypeAdapter
    ta = TypeAdapter(TutoringSSEEvent)
    ev = ta.validate_python({"type": "review", "status": "flagged", "reason": "off_topic"})
    assert isinstance(ev, ReviewEvent)
