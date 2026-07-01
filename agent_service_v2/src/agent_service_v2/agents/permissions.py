from __future__ import annotations

from agentscope.permission import PermissionBehavior, PermissionContext, PermissionRule

SAFE_WORKBENCH_TOOLS = [
    "reset_tools",
    "TaskCreate",
    "TaskGet",
    "TaskList",
    "TaskUpdate",
    "read_learning_state",
    "draft_study_artifact",
    "review_grounding",
]


def build_workbench_permission_context() -> PermissionContext:
    context = PermissionContext()
    for tool_name in SAFE_WORKBENCH_TOOLS:
        context.allow_rules[tool_name] = [
            PermissionRule(
                tool_name=tool_name,
                rule_content=None,
                behavior=PermissionBehavior.ALLOW,
                source="eduagent:workbench_safe_tools",
            )
        ]
    return context
