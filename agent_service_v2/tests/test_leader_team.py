from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, patch

from agentscope.message import Msg
from agentscope.message import TextBlock
from agentscope.model import ChatResponse

from agent_service_v2.agents.leader_team import CoursePlannerAgent, ResourceWorkerAgent
from agent_service_v2.agents.model_provider import AgentModelSettings


async def _streamed_response(text: str):
    yield ChatResponse(content=[TextBlock(text=text[:10])], is_last=False)
    yield ChatResponse(content=[TextBlock(text=text)], is_last=True)


def test_course_planner_awaits_agentscope_chat_model() -> None:
    mock_model = AsyncMock(
        return_value=_streamed_response(
            '{"nodes":[{"id":"pointer","name":"指针","chapter":"第 5 章"}],"edges":[]}'
        ),
    )

    with patch(
        "agent_service_v2.agents.leader_team.build_chat_model_from_settings",
        return_value=mock_model,
    ) as mock_build_model:
        result = asyncio.run(
            CoursePlannerAgent(AgentModelSettings()).plan_curriculum("指针保存变量地址。")
        )

    assert mock_build_model.call_args.kwargs["stream"] is False
    assert result["nodes"][0]["id"] == "pointer"
    mock_model.assert_awaited_once()
    messages = mock_model.await_args.args[0]
    assert isinstance(messages, list)
    assert isinstance(messages[0], Msg)
    assert messages[0].role == "user"
    assert "指针保存变量地址。" in messages[0].content[0].text


def test_resource_worker_awaits_agentscope_chat_model() -> None:
    mock_model = AsyncMock(
        return_value=_streamed_response(
            '{"questions":[{"title":"指针是什么？","type":"single_choice","options":["地址","数值"],"answer":"A","explanation":"指针保存地址。"}]}'
        ),
    )

    with patch(
        "agent_service_v2.agents.leader_team.build_chat_model_from_settings",
        return_value=mock_model,
    ) as mock_build_model:
        result = asyncio.run(
            ResourceWorkerAgent(AgentModelSettings()).generate_asset(
                "quiz",
                "第 5 章",
                "指针",
                count=1,
                question_types=["single_choice"],
            )
        )

    assert mock_build_model.call_args.kwargs["stream"] is False
    assert result["questions"][0]["content"] == "指针是什么？"
    assert result["questions"][0]["options"][0] == {"key": "A", "text": "地址"}
    mock_model.assert_awaited_once()
    messages = mock_model.await_args.args[0]
    assert isinstance(messages, list)
    assert isinstance(messages[0], Msg)
    assert messages[0].role == "user"
    assert "指针" in messages[0].content[0].text
