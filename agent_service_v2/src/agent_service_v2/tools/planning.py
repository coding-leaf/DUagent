from __future__ import annotations

from agentscope.tool import TaskCreate, TaskGet, TaskList, TaskUpdate, ToolGroup


def build_planning_group() -> ToolGroup:
    return ToolGroup(
        name="planning",
        description="Plan and track AIChat learning workbench tasks.",
        instructions=(
            "Use these tools for complex multi-step learning tasks. "
            "For simple questions or direct explanations, answer directly without creating a plan."
        ),
        tools=[TaskCreate(), TaskGet(), TaskList(), TaskUpdate()],
    )
