from __future__ import annotations

from agentscope.tool import FunctionTool, ToolBase, ToolGroup
from agentscope.workspace import LocalWorkspace

from agent_service_v2.tools.artifact_files import build_write_artifact_file
from agent_service_v2.tools.planning import build_planning_group
from agent_service_v2.tools.input_models import ArtifactFileInput


def build_workbench_tool_groups(
    *,
    memory_tools: list[ToolBase] | None,
    rag_tools: list[ToolBase] | None,
    learning_progress_tools: list[ToolBase] | None,
    oj_execution_tools: list[ToolBase] | None = None,
    personal_code_problem_tools: list[ToolBase] | None = None,
    personal_choice_quiz_tools: list[ToolBase] | None = None,
    workspace: LocalWorkspace,
    run_id: str,
) -> list[ToolGroup]:
    groups = [build_planning_group()]
    if memory_tools:
        groups.append(
            ToolGroup(
                name="memory",
                description="Search and update long-term learner memory.",
                tools=memory_tools,
            )
        )
    if rag_tools:
        groups.append(
            ToolGroup(
                name="rag",
                description="Retrieve course-grounded learning context.",
                tools=rag_tools,
            )
        )
    if learning_progress_tools:
        groups.append(
            ToolGroup(
                name="learning_progress",
                description="Read real learner progress and recent answer evidence from Backend.",
                instructions=(
                    "Use read_learning_progress before giving overall next-step learning advice. "
                    "Use read_recent_answers before explaining specific mistakes. "
                    "If the tools return empty or unavailable data, say evidence is insufficient."
                ),
                tools=learning_progress_tools,
            )
        )
    if oj_execution_tools:
        groups.append(
            ToolGroup(
                name="oj_execution",
                description="Compile and run source code in an isolated online sandbox.",
                tools=oj_execution_tools,
            )
        )
    if personal_code_problem_tools:
        groups.append(
            ToolGroup(
                name="personal_code_problem",
                description="Create validated private fixed-test-case programming problems.",
                tools=personal_code_problem_tools,
            )
        )
    if personal_choice_quiz_tools:
        groups.append(
            ToolGroup(
                name="personal_choice_quiz",
                description="Create validated private single-choice and multi-choice practice sets.",
                tools=personal_choice_quiz_tools,
            )
        )
    artifact_tool = FunctionTool(build_write_artifact_file(workspace=workspace, run_id=run_id))
    artifact_tool.input_schema = ArtifactFileInput.tool_schema()
    groups.extend(
        [
            ToolGroup(
                name="artifact",
                description="Create validated learning artifacts in the AgentScope run workspace.",
                instructions=(
                    "Use write_artifact_file only for Markdown or Mermaid. "
                    "Interactive practice cards are created atomically by their publishing tools."
                ),
                tools=[artifact_tool],
            ),
        ]
    )
    return groups
