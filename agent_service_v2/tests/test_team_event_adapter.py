from agent_service_v2.runtime.team_event_adapter import TeamEventAdapter


def test_team_event_adapter_maps_role_and_review_without_raw_event_payloads():
    adapter = TeamEventAdapter(run_id="task-1", conversation_id=None)

    started = adapter.adapt({
        "type": "REPLY_START",
        "reply_id": "reply-1",
        "session_id": "session-1",
        "name": "resource_reviewer",
    })
    tool = adapter.adapt({
        "type": "TOOL_CALL_START",
        "reply_id": "reply-1",
        "tool_call_id": "tool-1",
        "tool_call_name": "review_personalized_resource",
    })
    reviewed = adapter.adapt({
        "type": "TOOL_RESULT_END",
        "reply_id": "reply-1",
        "tool_call_id": "tool-1",
        "state": "success",
    })

    assert started.to_dict()["type"] == "agent_started"
    assert started.agent == "resource_reviewer"
    assert tool.to_dict()["type"] == "tool_started"
    assert reviewed.to_dict()["type"] == "critic_completed"
    assert "REPLY_START" not in str(started.to_dict())


def test_team_event_adapter_ignores_unknown_framework_structural_events():
    adapter = TeamEventAdapter(run_id="task-1", conversation_id=None)

    assert adapter.adapt({"type": "MODEL_CALL_START", "secret": "raw"}) is None
