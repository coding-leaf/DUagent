from pathlib import Path

import pytest
from agentscope.agent import Agent

from agent_service_v2.agents.workbench_factory import (
    MissingModelConfigError,
    WorkbenchAgentFactory,
)
from agent_service_v2.workspaces.workbench_workspace_manager import (
    WorkbenchWorkspaceManager,
)


def test_factory_raises_clear_error_without_model(tmp_path: Path):
    workspace = WorkbenchWorkspaceManager(root_dir=tmp_path).get_workspace(
        user_id="u1",
        course_id="c1",
        conversation_id="conv1",
    )
    factory = WorkbenchAgentFactory(model_provider=lambda: None)

    with pytest.raises(MissingModelConfigError, match="model_not_configured"):
        factory.create_agent(user_id="u1", course_id="c1", workspace=workspace)


def test_factory_creates_agentscope_agent_with_model(tmp_path: Path):
    class FakeModel:
        pass

    workspace = WorkbenchWorkspaceManager(root_dir=tmp_path).get_workspace(
        user_id="u1",
        course_id="c1",
        conversation_id="conv1",
    )
    factory = WorkbenchAgentFactory(model_provider=lambda: FakeModel())

    agent = factory.create_agent(user_id="u1", course_id="c1", workspace=workspace)

    assert isinstance(agent, Agent)
