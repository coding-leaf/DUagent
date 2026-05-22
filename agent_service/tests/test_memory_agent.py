import importlib

from agent_service.schemas.memory import MemoryCompressRequest, MemoryMessage


def test_compress_memory_merges_old_summary_and_messages() -> None:
    memory = importlib.import_module("agent_service.agents.memory")

    result = memory.compress_memory_data(
        _build_request(
            old_summary="此前用户在学习函数基础。",
            messages=[
                MemoryMessage(role="user", content="我总是在导数定义上卡住", timestamp="2026-05-22T10:00:00Z"),
                MemoryMessage(role="assistant", content="可以从极限定义开始拆解。", timestamp="2026-05-22T10:01:00Z"),
            ],
        )
    )

    assert result.new_summary == "此前用户在学习函数基础。 本轮对话：用户提到：我总是在导数定义上卡住；助手回应：可以从极限定义开始拆解。"


def test_compress_memory_extracts_blind_spot_fact() -> None:
    memory = importlib.import_module("agent_service.agents.memory")

    result = memory.compress_memory_data(
        _build_request(
            old_summary=None,
            messages=[
                MemoryMessage(role="user", content="我总是在递归概念上卡住", timestamp="2026-05-22T10:00:00Z"),
            ],
        )
    )

    assert len(result.extracted_facts) == 1
    assert result.extracted_facts[0].content == "用户在递归概念上卡住"
    assert result.extracted_facts[0].fact_type == "blind_spot"
    assert result.extracted_facts[0].knowledge_point == "递归概念"
    assert result.extracted_facts[0].confidence == 0.8


def test_compress_memory_skips_existing_fact_content() -> None:
    memory = importlib.import_module("agent_service.agents.memory")

    result = memory.compress_memory_data(
        _build_request(
            old_summary=None,
            messages=[
                MemoryMessage(role="user", content="我总是在递归概念上卡住", timestamp="2026-05-22T10:00:00Z"),
            ],
            existing_facts=["用户在递归概念上卡住"],
        )
    )

    assert result.extracted_facts == []


def _build_request(
    old_summary: str | None,
    messages: list[MemoryMessage],
    existing_facts: list[str] | None = None,
) -> MemoryCompressRequest:
    return MemoryCompressRequest(
        user_id="user-1",
        conversation_id="conversation-1",
        old_summary=old_summary,
        messages_to_compress=messages,
        existing_facts=existing_facts or [],
    )
