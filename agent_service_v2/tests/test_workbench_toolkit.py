from agentscope.tool import ToolGroup
from agentscope.workspace import LocalWorkspace

from agent_service_v2.tools.workbench_placeholders import (
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
    groups = build_workbench_tool_groups(
        memory_tools=[],
        rag_tools=[],
        learning_progress_tools=[],
        workspace=LocalWorkspace(workdir="/tmp/eduagent-test-workspace", workspace_id="ws"),
        run_id="run-1",
    )

    assert [group.name for group in groups] == [
        "planning",
        "learning_state",
        "artifact",
        "review",
    ]
    artifact_group = next(group for group in groups if group.name == "artifact")
    assert [getattr(tool, "name", type(tool).__name__) for tool in artifact_group.tools] == [
        "write_artifact_file"
    ]


def test_workbench_tool_groups_include_learning_progress_group_when_tools_exist():
    class FakeTool:
        name = "read_learning_progress"

    groups = build_workbench_tool_groups(
        memory_tools=[],
        rag_tools=[],
        learning_progress_tools=[FakeTool()],
        workspace=LocalWorkspace(workdir="/tmp/eduagent-test-workspace", workspace_id="ws"),
        run_id="run-1",
    )

    assert [group.name for group in groups] == [
        "planning",
        "learning_progress",
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
    assert review_grounding(summary="answer") == {
        "status": "placeholder",
        "tool": "review_grounding",
        "summary": "answer",
    }
