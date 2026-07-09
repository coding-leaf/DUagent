from __future__ import annotations

from agentscope.tool import FunctionTool, ToolBase, ToolGroup
from agentscope.workspace import LocalWorkspace

from agent_service_v2.tools.artifact_files import build_write_artifact_file
from agent_service_v2.tools.planning import build_planning_group
from agent_service_v2.tools.workbench_placeholders import (
    read_learning_state,
    review_grounding,
)


def build_workbench_tool_groups(
    *,
    memory_tools: list[ToolBase] | None,
    rag_tools: list[ToolBase] | None,
    learning_progress_tools: list[ToolBase] | None,
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
    groups.extend(
        [
            ToolGroup(
                name="learning_state",
                description="Read Backend-provided learner state summaries.",
                tools=[FunctionTool(read_learning_state, is_read_only=True)],
            ),
            ToolGroup(
                name="artifact",
                description="Write saveable learning artifacts into the run workspace.",
                tools=[FunctionTool(build_write_artifact_file(workspace=workspace, run_id=run_id))],
            ),
            ToolGroup(
                name="review",
                description="Review generated advice for grounding and safety.",
                tools=[FunctionTool(review_grounding, is_read_only=True)],
            ),
        ]
    )
    return groups
