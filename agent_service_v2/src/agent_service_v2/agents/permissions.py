from __future__ import annotations

from agentscope.permission import PermissionBehavior, PermissionContext, PermissionRule

SAFE_WORKBENCH_TOOLS = [
    "reset_tools",
    "TaskCreate",
    "TaskGet",
    "TaskList",
    "TaskUpdate",
    "read_learning_progress",
    "read_recent_answers",
    "write_artifact_file",
    "create_code_sandbox_card",
    "run_code_in_oj",
    "validate_personal_code_problem_draft",
    "search_memory",
    "add_memory",
    "retrieve_course_context_tool",
]

DANGEROUS_WORKBENCH_TOOLS = [
    "Bash",
    "bash",
    "Shell",
    "shell",
    "exec",
    "command",
    "terminal",
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
    for tool_name in DANGEROUS_WORKBENCH_TOOLS:
        context.deny_rules[tool_name] = [
            PermissionRule(
                tool_name=tool_name,
                rule_content=None,
                behavior=PermissionBehavior.DENY,
                source="eduagent:workbench_dangerous_tools",
            )
        ]
    return context
