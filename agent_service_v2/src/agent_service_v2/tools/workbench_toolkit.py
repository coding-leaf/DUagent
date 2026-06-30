from __future__ import annotations

from agentscope.tool import FunctionTool, ToolBase, ToolGroup

from agent_service_v2.tools.planning import build_planning_group
from agent_service_v2.tools.workbench_placeholders import (
    draft_study_artifact,
    read_learning_state,
    review_grounding,
)


def build_workbench_tool_groups(
    *,
    memory_tools: list[ToolBase] | None,
    rag_tools: list[ToolBase] | None,
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
    groups.extend(
        [
            ToolGroup(
                name="learning_state",
                description="Read Backend-provided learner state summaries.",
                tools=[FunctionTool(read_learning_state, is_read_only=True)],
            ),
            ToolGroup(
                name="artifact",
                description="Draft workbench artifacts for the middle panel.",
                tools=[FunctionTool(draft_study_artifact)],
            ),
            ToolGroup(
                name="review",
                description="Review generated advice for grounding and safety.",
                tools=[FunctionTool(review_grounding, is_read_only=True)],
            ),
        ]
    )
    return groups
