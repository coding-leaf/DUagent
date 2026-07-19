from agentscope.permission import PermissionBehavior, PermissionContext, PermissionRule, PermissionMode


ROLE_TOOL_NAMES: dict[str, tuple[str, ...]] = {
    "resource_team_leader": (
        "TeamCreate",
        "AgentCreate",
        "TeamSay",
        "TeamDelete",
        "publish_personalized_resource",
        "retrieve_course_context_tool",
    ),
    "resource_generator": (
        "retrieve_course_context_tool",
        "create_personalized_resource_draft",
        "record_personalized_validation",
        "publish_personal_code_problem",
        "TeamSay",
    ),
    "resource_reviewer": (
        "review_personalized_resource",
        "TeamSay",
    ),
}


def _permission_context(tool_names: tuple[str, ...]) -> PermissionContext:
    context = PermissionContext(mode=PermissionMode.DONT_ASK)
    for tool_name in tool_names:
        context.allow_rules[tool_name] = [
            PermissionRule(
                tool_name=tool_name,
                rule_content=None,
                behavior=PermissionBehavior.ALLOW,
                source="eduagent:resource_team_role",
            )
        ]
    return context


def build_generator_permission_context() -> PermissionContext:
    return _permission_context(ROLE_TOOL_NAMES["resource_generator"])


def build_leader_permission_context() -> PermissionContext:
    return _permission_context(ROLE_TOOL_NAMES["resource_team_leader"])


def build_reviewer_permission_context() -> PermissionContext:
    return _permission_context(ROLE_TOOL_NAMES["resource_reviewer"])


def build_role_permissions() -> dict[str, PermissionContext]:
    return {
        "resource_team_leader": build_leader_permission_context(),
        "resource_generator": build_generator_permission_context(),
        "resource_reviewer": build_reviewer_permission_context(),
    }
