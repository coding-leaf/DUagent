from agentscope.tool import ToolGroup

from agent_service_v2.tools.workbench_placeholders import (
    draft_study_artifact,
    read_learning_state,
    review_grounding,
)
from agent_service_v2.tools.planning import build_planning_group
from agent_service_v2.tools.workbench_toolkit import build_workbench_tool_groups


def test_planning_group_contains_agentscope_plan_tools():
    group = build_planning_group()

    assert isinstance(group, ToolGroup)
    assert group.name == "planning"
    assert {type(tool).__name__ for tool in group.tools} == {
        "TaskCreate",
        "TaskGet",
        "TaskList",
        "TaskUpdate",
    }


def test_planning_group_is_optional_for_simple_replies():
    group = build_planning_group()

    assert "complex" in group.instructions.lower()
    assert "simple" in group.instructions.lower()
    assert "before giving final learning advice" not in group.instructions


def test_workbench_tool_groups_include_expected_boundaries():
    groups = build_workbench_tool_groups(memory_tools=[], rag_tools=[])

    assert [group.name for group in groups] == [
        "planning",
        "learning_state",
        "artifact",
        "review",
    ]


def test_placeholder_tools_return_structured_observations():
    assert read_learning_state(user_id="u1", course_id="c1") == {
        "status": "placeholder",
        "tool": "read_learning_state",
        "user_id": "u1",
        "course_id": "c1",
    }
    assert draft_study_artifact(kind="study_plan") == {
        "status": "placeholder",
        "tool": "draft_study_artifact",
        "kind": "study_plan",
    }
    assert review_grounding(summary="answer") == {
        "status": "placeholder",
        "tool": "review_grounding",
        "summary": "answer",
    }
