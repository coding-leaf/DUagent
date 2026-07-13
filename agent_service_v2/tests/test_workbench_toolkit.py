from agentscope.tool import ToolGroup
from agentscope.workspace import LocalWorkspace

from agent_service_v2.tools import workbench_toolkit as toolkit_module
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
        "artifact",
    ]
    artifact_group = next(group for group in groups if group.name == "artifact")
    assert [getattr(tool, "name", type(tool).__name__) for tool in artifact_group.tools] == [
        "write_artifact_file",
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
        "artifact",
    ]


def test_workbench_tool_groups_include_personal_code_problem_group_when_tools_exist():
    class FakeTool:
        name = "publish_personal_code_problem"

    groups = build_workbench_tool_groups(
        memory_tools=[],
        rag_tools=[],
        learning_progress_tools=[],
        personal_code_problem_tools=[FakeTool()],
        workspace=LocalWorkspace(workdir="/tmp/eduagent-test-workspace", workspace_id="ws"),
        run_id="run-1",
    )

    group = next(group for group in groups if group.name == "personal_code_problem")

    assert "explicitly requests" in group.description
    assert "publish_personal_code_problem" in group.description


def test_workbench_tool_groups_include_personal_choice_quiz_group_when_tools_exist():
    class FakeTool:
        name = "publish_personal_choice_quiz"

    groups = build_workbench_tool_groups(
        memory_tools=[],
        rag_tools=[],
        learning_progress_tools=[],
        personal_choice_quiz_tools=[FakeTool()],
        workspace=LocalWorkspace(workdir="/tmp/eduagent-test-workspace", workspace_id="ws"),
        run_id="run-1",
    )

    group = next(group for group in groups if group.name == "personal_choice_quiz")

    assert "explicitly requests" in group.description
    assert "publish_personal_choice_quiz" in group.description


def test_workbench_tool_groups_split_foundation_tools_from_optional_practice():
    class FakeTool:
        def __init__(self, name):
            self.name = name

    groups = build_workbench_tool_groups(
        memory_tools=[],
        rag_tools=[FakeTool("retrieve_course_context_tool")],
        learning_progress_tools=[FakeTool("read_learning_progress")],
        personal_code_problem_tools=[FakeTool("publish_personal_code_problem")],
        personal_choice_quiz_tools=[FakeTool("publish_personal_choice_quiz")],
        workspace=LocalWorkspace(workdir="/tmp/eduagent-test-workspace", workspace_id="ws"),
        run_id="run-1",
    )

    assert hasattr(toolkit_module, "split_workbench_tool_groups")
    basic_tools, dynamic_groups = toolkit_module.split_workbench_tool_groups(groups)

    basic_names = {getattr(tool, "name", type(tool).__name__) for tool in basic_tools}
    assert {"TaskCreate", "retrieve_course_context_tool", "read_learning_progress"} <= basic_names
    assert {group.name for group in dynamic_groups} == {
        "personal_code_problem",
        "personal_choice_quiz",
    }


def test_dynamic_practice_groups_contain_complete_state_instructions():
    class FakeTool:
        def __init__(self, name):
            self.name = name

    groups = build_workbench_tool_groups(
        memory_tools=[],
        rag_tools=[],
        learning_progress_tools=[],
        personal_code_problem_tools=[FakeTool("publish_personal_code_problem")],
        personal_choice_quiz_tools=[FakeTool("publish_personal_choice_quiz")],
        workspace=LocalWorkspace(workdir="/tmp/eduagent-test-workspace", workspace_id="ws"),
        run_id="run-1",
    )
    by_name = {group.name: group for group in groups}

    choice_instructions = by_name["personal_choice_quiz"].instructions
    assert 'outcome="success"' in choice_instructions
    assert 'status="published"' in choice_instructions
    assert "QuizCard artifact" in choice_instructions
    assert "single_choice" in choice_instructions

    code_instructions = by_name["personal_code_problem"].instructions
    assert "reference_solution" in code_instructions
    assert "hidden_inputs" in code_instructions
    assert "problem_id" in code_instructions
    assert "CodeSandboxCard artifact" in code_instructions
    assert "delivery_incomplete" in code_instructions
