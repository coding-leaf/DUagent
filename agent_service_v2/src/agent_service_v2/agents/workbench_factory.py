from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

from agentscope.agent import Agent, ContextConfig, ReActConfig
from agentscope.state import AgentState
from agentscope.tool import Toolkit
from agentscope.workspace import LocalWorkspace

from agent_service_v2.agents.permissions import build_workbench_permission_context
from agent_service_v2.agents.prompts import WORKBENCH_SYSTEM_PROMPT
from agent_service_v2.observability.agent_middleware import AgentRunLoggingMiddleware
from agent_service_v2.observability.logging import LogSink
from agent_service_v2.tools.backend_learning_client import build_backend_learning_client_from_settings
from agent_service_v2.tools.learning_progress import build_learning_progress_tools
from agent_service_v2.tools.memory_guard import guard_memory_tools
from agent_service_v2.tools.oj_execution import build_oj_execution_tools
from agent_service_v2.tools.personal_code_problem import build_personal_code_problem_tools
from agent_service_v2.tools.personal_choice_quiz import build_personal_choice_quiz_tools
from agent_service_v2.tools.workbench_toolkit import build_workbench_tool_groups


logger = logging.getLogger(__name__)
MEMORY_COLLECTION_NAME = "student_memories"


class MissingModelConfigError(RuntimeError):
    pass


class MemoryCollectionDimensionError(RuntimeError):
    pass


def _build_mem0_config(*, qdrant_url: str, collection_name: str, embedding_dimension: int):
    from mem0.configs.base import MemoryConfig

    return MemoryConfig(
        vector_store={
            "provider": "qdrant",
            "config": {
                "collection_name": collection_name,
                "url": qdrant_url,
                "embedding_model_dims": embedding_dimension,
            },
        },
    )


def _ensure_memory_collection(
    *,
    client: Any,
    collection_name: str,
    embedding_dimension: int,
) -> None:
    from qdrant_client.models import Distance, VectorParams

    if client.collection_exists(collection_name=collection_name):
        collection = client.get_collection(collection_name=collection_name)
        actual_dimension = collection.config.params.vectors.size
        if actual_dimension == embedding_dimension:
            return
        if collection.points_count:
            raise MemoryCollectionDimensionError(
                f"memory collection dimension mismatch: expected={embedding_dimension} "
                f"actual={actual_dimension} points={collection.points_count}",
            )
        logger.warning(
            "Recreating empty memory collection with correct dimension: "
            "collection=%s expected=%s actual=%s",
            collection_name,
            embedding_dimension,
            actual_dimension,
        )
        client.delete_collection(collection_name=collection_name)

    client.create_collection(
        collection_name=collection_name,
        vectors_config=VectorParams(
            size=embedding_dimension,
            distance=Distance.COSINE,
        ),
    )


class WorkbenchAgentFactory:
    def __init__(self, model_provider: Callable[[], Any]) -> None:
        self._model_provider = model_provider

    def create_agent(
        self,
        *,
        user_id: str,
        course_id: str | None,
        catalog_id: str | None = None,
        workspace: LocalWorkspace,
        run_id: str | None = None,
        conversation_id: str | None = None,
        log_sink: LogSink | None = None,
    ) -> Agent:
        model = self._model_provider()
        if model is None:
            raise MissingModelConfigError("model_not_configured")
        if run_id is None:
            raise ValueError("run_id is required for workbench artifact tools")

        learning_client = build_backend_learning_client_from_settings()
        learning_progress_tools = build_learning_progress_tools(
            client=learning_client,
            user_id=user_id,
            course_id=course_id,
        )
        oj_execution_tools = build_oj_execution_tools(
            client=learning_client,
        )
        personal_code_problem_tools = build_personal_code_problem_tools(
            client=learning_client,
            user_id=user_id,
            course_id=course_id,
            conversation_id=conversation_id,
            run_id=run_id,
            workspace=workspace,
        )
        personal_choice_quiz_tools = build_personal_choice_quiz_tools(
            client=learning_client,
            user_id=user_id,
            course_id=course_id,
            conversation_id=conversation_id,
            run_id=run_id,
            workspace=workspace,
        )

        from agentscope.tool import FunctionTool
        from agent_service_v2.tools.rag import retrieve_course_context

        if catalog_id:
            async def retrieve_course_context_tool(query: str, limit: int = 3) -> dict:
                """Retrieve related book paragraphs from the course textbook material to help answer questions.

                Args:
                    query (str): The search query keywords or question text.
                    limit (int, optional): Maximum number of segments to return. Defaults to 3.
                """
                return await retrieve_course_context(query=query, course_id=catalog_id, limit=limit)

            rag_tools = [FunctionTool(retrieve_course_context_tool)]
        else:
            rag_tools = []

        # Initialize Mem0 long-term memory middleware & extract memory tools
        from agent_service_v2.agents.model_provider import build_embedding_model_from_settings, AgentModelSettings
        settings = AgentModelSettings()
        embedding_model = build_embedding_model_from_settings(settings)

        memory_tools = []
        middlewares = []

        if embedding_model and settings.QDRANT_URL:
            try:
                from qdrant_client import QdrantClient
                from agentscope.middleware import Mem0Middleware
                from agentscope.middleware._longterm_memory._mem0._tools import _build_memory_tools

                q_client = QdrantClient(url=settings.QDRANT_URL)
                _ensure_memory_collection(
                    client=q_client,
                    collection_name=MEMORY_COLLECTION_NAME,
                    embedding_dimension=settings.EMBEDDING_DIMENSION,
                )
                mem0_qdrant_cfg = _build_mem0_config(
                    qdrant_url=settings.QDRANT_URL,
                    collection_name=MEMORY_COLLECTION_NAME,
                    embedding_dimension=settings.EMBEDDING_DIMENSION,
                )
                mem0_mw = Mem0Middleware(
                    user_id=user_id,
                    chat_model=model,
                    embedding_model=embedding_model,
                    mem0_config=mem0_qdrant_cfg,
                    mode="both",
                )
                memory_tools = guard_memory_tools(_build_memory_tools(mem0_mw))
                middlewares.append(mem0_mw)
            except Exception as exc:
                logger.exception("Memory middleware initialization disabled: %s", exc)

        tool_groups = build_workbench_tool_groups(
            memory_tools=memory_tools,
            rag_tools=rag_tools,
            learning_progress_tools=learning_progress_tools,
            oj_execution_tools=oj_execution_tools,
            personal_code_problem_tools=personal_code_problem_tools,
            personal_choice_quiz_tools=personal_choice_quiz_tools,
            workspace=workspace,
            run_id=run_id,
        )
        toolkit = Toolkit(tool_groups=tool_groups)
        default_active_groups = {
            "memory",
            "rag",
            "learning_progress",
            "oj_execution",
            "artifact",
        }
        activated_groups = [
            group.name for group in tool_groups if group.name in default_active_groups
        ]

        if run_id and log_sink:
            middlewares.append(
                AgentRunLoggingMiddleware(
                    run_id=run_id,
                    conversation_id=conversation_id,
                    user_id=user_id,
                    course_id=course_id,
                    sink=log_sink,
                )
            )

        return Agent(
            name=_agent_name(course_id),
            system_prompt=_system_prompt(user_id=user_id, course_id=course_id),
            model=model,
            toolkit=toolkit,
            middlewares=middlewares,
            state=AgentState(
                permission_context=build_workbench_permission_context(),
                tool_context={"activated_groups": activated_groups},
            ),
            offloader=workspace,
            context_config=ContextConfig(tool_result_limit=20000),
            react_config=ReActConfig(max_iters=20),
        )


def _agent_name(course_id: str | None) -> str:
    return f"edu_ai_chat_workbench:{course_id or 'global'}"


def _system_prompt(*, user_id: str, course_id: str | None) -> str:
    return (
        f"{WORKBENCH_SYSTEM_PROMPT}\n"
        f"Current user_id: {user_id}\n"
        f"Current course_id: {course_id or 'global'}\n"
    )
