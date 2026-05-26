import json
import re

from agent_service.core.ai import ChatMessage, EmbeddingProvider, get_ai_providers
from agent_service.core.logging import get_logger
from agent_service.memory.user_memory_store import QdrantUserMemoryStore
from agent_service.prompts.memory import (
    build_memory_compress_system_prompt,
    build_memory_compress_user_message,
)
from agent_service.schemas.memory import ExtractedFact, MemoryCompressRequest, MemoryCompressResult, MemoryMessage

logger = get_logger(__name__)

_MEMORY_MARKDOWN_FENCE_PATTERN = re.compile(r"```(?:json)?\s*\n?(.*?)```", re.DOTALL)
_VALID_FACT_TYPES = {"blind_spot", "mastered_point", "cognitive_preference"}


def compress_memory_data(request: MemoryCompressRequest) -> MemoryCompressResult:
    """根据待压缩消息生成规则版摘要和事实列表，输入压缩请求，输出记忆压缩结果。"""
    new_summary = _build_summary(request.old_summary, request.messages_to_compress)
    extracted_facts = _extract_facts(request.messages_to_compress, set(request.existing_facts))
    return MemoryCompressResult(new_summary=new_summary, extracted_facts=extracted_facts)


async def compress_memory_with_llm(
    request: MemoryCompressRequest,
    chat_provider,
) -> MemoryCompressResult | None:
    """尝试用 LLM 压缩记忆并提取事实，输入请求和 chat provider，输出 MemoryCompressResult 或 None（降级）。"""
    if chat_provider is None:
        return None
    try:
        messages = [
            ChatMessage(role="system", content=build_memory_compress_system_prompt()),
            ChatMessage(role="user", content=build_memory_compress_user_message(request)),
        ]
        raw = await chat_provider.complete(messages)
        parsed = _parse_memory_compress_json(raw)
        return _coerce_memory_compress_result(parsed)
    except Exception:
        logger.warning("LLM memory compression failed, falling back to rule-based", exc_info=True)
        return None


async def compress_and_persist_memory(
    request: MemoryCompressRequest,
    embedding_provider: EmbeddingProvider | None = None,
    memory_store: QdrantUserMemoryStore | None = None,
    compress_result: MemoryCompressResult | None = None,
) -> MemoryCompressResult:
    """压缩对话并尝试写入长期记忆，输入请求和可选的预压缩结果，输出不变的记忆压缩结果。

    compress_result 非 None 时跳过规则压缩直接持久化；为 None 时走规则版 compress_memory_data。
    """
    result = compress_result or compress_memory_data(request)
    if not result.extracted_facts:
        return result

    try:
        provider = embedding_provider or get_ai_providers().embedding
        store = memory_store or QdrantUserMemoryStore()
        vectors = await provider.embed_texts([fact.content or "" for fact in result.extracted_facts])
        await store.upsert_facts(
            user_id=request.user_id,
            conversation_id=request.conversation_id,
            facts=result.extracted_facts,
            vectors=vectors,
        )
    except Exception as exc:
        logger.warning(
            "Memory persistence failed: user_id=%s conversation_id=%s error=%s",
            request.user_id,
            request.conversation_id,
            exc,
        )
    return result


def _parse_memory_compress_json(raw: str) -> dict:
    text = raw.strip()
    match = _MEMORY_MARKDOWN_FENCE_PATTERN.search(text)
    if match:
        text = match.group(1).strip()
    data = json.loads(text)
    if not isinstance(data, dict):
        raise ValueError("LLM output is not a JSON object")
    return data


def _coerce_memory_compress_result(data: dict) -> MemoryCompressResult:
    new_summary = data.get("new_summary")
    if not isinstance(new_summary, str) or not new_summary.strip():
        new_summary = None
    facts_list = data.get("extracted_facts")
    if not isinstance(facts_list, list):
        facts_list = []
    facts = _coerce_extracted_facts(facts_list)
    return MemoryCompressResult(new_summary=new_summary, extracted_facts=facts)


def _coerce_extracted_facts(items: list[dict]) -> list[ExtractedFact]:
    facts: list[ExtractedFact] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        content = item.get("content")
        if not isinstance(content, str) or not content.strip():
            continue
        fact_type = item.get("fact_type")
        if fact_type not in _VALID_FACT_TYPES:
            fact_type = "blind_spot"
        knowledge_point = item.get("knowledge_point")
        if not isinstance(knowledge_point, str):
            knowledge_point = None
        confidence = item.get("confidence")
        if isinstance(confidence, int | float):
            confidence = max(0.0, min(1.0, float(confidence)))
        else:
            confidence = 0.5
        facts.append(ExtractedFact(
            content=content.strip(),
            fact_type=fact_type,
            knowledge_point=knowledge_point,
            confidence=confidence,
        ))
    return facts


def _build_summary(old_summary: str | None, messages: list[MemoryMessage]) -> str:
    message_summary = "；".join(_summarize_message(message) for message in messages)
    if old_summary and message_summary:
        return f"{old_summary.strip()} 本轮对话：{message_summary}"
    if old_summary:
        return old_summary.strip()
    if message_summary:
        return f"本轮对话：{message_summary}"
    return ""


def _summarize_message(message: MemoryMessage) -> str:
    role_name = "用户" if message.role == "user" else "助手"
    action = "提到" if message.role == "user" else "回应"
    return f"{role_name}{action}：{message.content.strip()}"


def _extract_facts(messages: list[MemoryMessage], existing_facts: set[str]) -> list[ExtractedFact]:
    facts = []
    for message in messages:
        fact = _extract_blind_spot_fact(message)
        if fact is None or fact.content in existing_facts:
            continue
        facts.append(fact)
    return facts


def _extract_blind_spot_fact(message: MemoryMessage) -> ExtractedFact | None:
    if message.role != "user":
        return None

    content = message.content.strip()
    for marker in ("总是在", "一直在", "经常在"):
        if marker not in content:
            continue
        after_marker = content.split(marker, 1)[1]
        knowledge_point = _trim_blind_spot_suffix(after_marker)
        if not knowledge_point:
            return None
        fact_content = f"用户在{knowledge_point}上卡住"
        return ExtractedFact(
            content=fact_content,
            fact_type="blind_spot",
            knowledge_point=knowledge_point,
            confidence=0.8,
        )
    return None


def _trim_blind_spot_suffix(value: str) -> str:
    cleaned = value.strip()
    for suffix in ("上卡住", "卡住", "上不理解", "不理解"):
        if cleaned.endswith(suffix):
            return cleaned[: -len(suffix)].strip()
    return cleaned
