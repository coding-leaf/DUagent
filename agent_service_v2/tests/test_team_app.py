from agentscope.app import SubAgentTemplate
from agentscope.app.message_bus import InMemoryMessageBus
from fastapi import FastAPI


def _template(template_type: str) -> SubAgentTemplate:
    return SubAgentTemplate(
        type=template_type,
        description=template_type,
        system_prompt_template="仅执行被分配的任务，并通过 TeamSay 返回结构化结果。",
        extend_leader_permission_rules=False,
        extend_leader_working_directories=False,
    )


def test_team_app_passes_custom_templates_to_official_create_app(monkeypatch, tmp_path):
    from agent_service_v2 import team_app as module

    captured = {}

    def fake_create_app(**kwargs):
        captured.update(kwargs)
        return FastAPI()

    monkeypatch.setattr(module, "create_app", fake_create_app)
    app = module.build_team_app(
        templates=[_template("resource_generator"), _template("resource_reviewer")],
        message_bus=InMemoryMessageBus(),
        workspace_root=tmp_path,
    )

    assert isinstance(app, FastAPI)
    assert {item.type for item in captured["custom_subagent_templates"]} == {
        "resource_generator",
        "resource_reviewer",
    }
    assert captured["enable_index_worker"] is False


def test_main_mounts_official_team_app():
    from agent_service_v2.main import app

    mounts = {
        route.path: route.app
        for route in app.routes
        if route.__class__.__name__ == "Mount"
    }
    team_app = mounts["/agent/v2/team-runtime"]
    assert set(team_app.state.custom_subagent_templates) == {
        "resource_generator",
        "resource_reviewer",
    }
    assert callable(team_app.state.extra_agent_tools)
