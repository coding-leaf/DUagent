from pathlib import Path

import pytest
from agentscope.agent import Agent

from agent_service_v2.agents import workbench_factory as factory_module
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

    agent = factory.create_agent(user_id="u1", course_id="c1", workspace=workspace, run_id="run-1")

    assert isinstance(agent, Agent)


def test_factory_configures_safe_tool_permission_allow_rules(tmp_path: Path):
    class FakeModel:
        pass

    workspace = WorkbenchWorkspaceManager(root_dir=tmp_path).get_workspace(
        user_id="u1",
        course_id="c1",
        conversation_id="conv1",
    )
    factory = WorkbenchAgentFactory(model_provider=lambda: FakeModel())

    agent = factory.create_agent(
        user_id="u1",
        course_id="c1",
        workspace=workspace,
        run_id="run-1",
    )

    allow_rules = agent.state.permission_context.allow_rules

    assert "reset_tools" in allow_rules
    assert "read_learning_state" in allow_rules
    assert "read_learning_progress" in allow_rules
    assert "read_recent_answers" in allow_rules
    assert "write_artifact_file" in allow_rules
    assert "draft_study_artifact" not in allow_rules
    assert "TaskCreate" in allow_rules
    assert "run_code_in_oj" in allow_rules
    assert "create_validated_personal_code_problem" in allow_rules

    deny_rules = agent.state.permission_context.deny_rules

    assert "Bash" in deny_rules
    assert "bash" in deny_rules
    assert "shell" in deny_rules
    assert "exec" in deny_rules


def test_factory_allows_long_enough_workbench_tool_runs(tmp_path: Path):
    class FakeModel:
        pass

    workspace = WorkbenchWorkspaceManager(root_dir=tmp_path).get_workspace(
        user_id="u1",
        course_id="c1",
        conversation_id="conv1",
    )
    factory = WorkbenchAgentFactory(model_provider=lambda: FakeModel())

    agent = factory.create_agent(
        user_id="u1",
        course_id="c1",
        workspace=workspace,
        run_id="run-1",
    )

    assert agent.react_config.max_iters >= 12


def test_factory_prompt_mentions_learning_progress_tools(tmp_path: Path):
    class FakeModel:
        pass

    workspace = WorkbenchWorkspaceManager(root_dir=tmp_path).get_workspace(
        user_id="u1",
        course_id="c1",
        conversation_id="conv1",
    )
    factory = WorkbenchAgentFactory(model_provider=lambda: FakeModel())

    agent = factory.create_agent(
        user_id="u1",
        course_id="c1",
        workspace=workspace,
        run_id="run-1",
    )

    prompt = agent._system_prompt
    assert "read_learning_progress" in prompt
    assert "read_recent_answers" in prompt
    assert "do not fabricate" in prompt.lower()


def test_mem0_config_uses_project_embedding_dimension():
    assert hasattr(factory_module, "_build_mem0_config")
    config = factory_module._build_mem0_config(
        qdrant_url="http://qdrant:6333",
        collection_name="student_memories",
        embedding_dimension=1024,
    )

    assert config.vector_store.config.embedding_model_dims == 1024


def test_empty_memory_collection_with_wrong_dimension_is_recreated():
    class FakeCollection:
        points_count = 0

        class config:
            class params:
                class vectors:
                    size = 1536

    class FakeQdrantClient:
        deleted = []
        created = []

        def collection_exists(self, collection_name):
            return True

        def get_collection(self, collection_name):
            return FakeCollection()

        def delete_collection(self, collection_name):
            self.deleted.append(collection_name)

        def create_collection(self, collection_name, vectors_config):
            self.created.append((collection_name, vectors_config.size))

    client = FakeQdrantClient()

    factory_module._ensure_memory_collection(
        client=client,
        collection_name="student_memories",
        embedding_dimension=1024,
    )

    assert client.deleted == ["student_memories"]
    assert client.created == [("student_memories", 1024)]


def test_nonempty_memory_collection_with_wrong_dimension_is_preserved():
    class FakeCollection:
        points_count = 3

        class config:
            class params:
                class vectors:
                    size = 1536

    class FakeQdrantClient:
        deleted = []

        def collection_exists(self, collection_name):
            return True

        def get_collection(self, collection_name):
            return FakeCollection()

        def delete_collection(self, collection_name):
            self.deleted.append(collection_name)

    client = FakeQdrantClient()

    assert hasattr(factory_module, "MemoryCollectionDimensionError")
    with pytest.raises(factory_module.MemoryCollectionDimensionError, match="expected=1024 actual=1536"):
        factory_module._ensure_memory_collection(
            client=client,
            collection_name="student_memories",
            embedding_dimension=1024,
        )

    assert client.deleted == []
