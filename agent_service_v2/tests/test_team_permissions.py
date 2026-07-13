def test_generator_and_reviewer_permissions_are_role_isolated():
    from agent_service_v2.agents.team_permissions import (
        build_generator_permission_context,
        build_reviewer_permission_context,
    )

    generator = build_generator_permission_context().allow_rules
    reviewer = build_reviewer_permission_context().allow_rules

    assert "create_personalized_resource_draft" in generator
    assert "record_personalized_validation" in generator
    assert "review_personalized_resource" not in generator
    assert "publish_personalized_resource" not in generator

    assert "review_personalized_resource" in reviewer
    assert "run_code_in_oj" not in reviewer
    assert "publish_personalized_resource" not in reviewer

    from agent_service_v2.agents.team_permissions import build_leader_permission_context

    leader = build_leader_permission_context().allow_rules
    assert "AgentCreate" in leader
    assert "TeamDelete" in leader
    assert "publish_personalized_resource" in leader
    assert "Bash" not in leader


def test_every_role_tool_is_explicitly_whitelisted():
    from agent_service_v2.agents.team_permissions import ROLE_TOOL_NAMES, build_role_permissions

    permissions = build_role_permissions()
    for role, tool_names in ROLE_TOOL_NAMES.items():
        assert set(tool_names) <= set(permissions[role].allow_rules)
