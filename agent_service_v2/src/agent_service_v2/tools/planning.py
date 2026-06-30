from __future__ import annotations

from agentscope.tool import TaskCreate, TaskGet, TaskList, TaskUpdate, ToolGroup


def build_planning_group() -> ToolGroup:
    return ToolGroup(
        name="planning",
        description="Plan and track AIChat learning workbench tasks.",
        instructions="Create and update a task plan before giving final learning advice.",
        tools=[TaskCreate(), TaskGet(), TaskList(), TaskUpdate()],
    )
