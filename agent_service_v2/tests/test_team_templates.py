def test_resource_team_templates_disable_leader_permission_and_workspace_inheritance():
    from agent_service_v2.agents.team_templates import build_resource_team_templates

    templates = build_resource_team_templates()

    assert {template.type for template in templates} == {
        "resource_generator",
        "resource_reviewer",
    }
    assert all(not template.extend_leader_permission_rules for template in templates)
    assert all(not template.extend_leader_working_directories for template in templates)
    assert all(template.override_leader_mode for template in templates)
