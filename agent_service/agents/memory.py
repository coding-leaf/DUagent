from agent_service.core.ai import EmbeddingProvider, get_ai_providers
from agent_service.core.logging import get_logger
from agent_service.memory.user_memory_store import QdrantUserMemoryStore
from agent_service.schemas.memory import ExtractedFact, MemoryCompressRequest, MemoryCompressResult, MemoryMessage

logger = get_logger(__name__)


def compress_memory_data(request: MemoryCompressRequest) -> MemoryCompressResult:
    """根据待压缩消息生成规则版摘要和事实列表，输入压缩请求，输出记忆压缩结果。"""
    new_summary = _build_summary(request.old_summary, request.messages_to_compress)
    extracted_facts = _extract_facts(request.messages_to_compress, set(request.existing_facts))
    return MemoryCompressResult(new_summary=new_summary, extracted_facts=extracted_facts)


async def compress_and_persist_memory(
    request: MemoryCompressRequest,
    embedding_provider: EmbeddingProvider | None = None,
    memory_store: QdrantUserMemoryStore | None = None,
) -> MemoryCompressResult:
    """压缩对话并尝试写入长期记忆，输入请求，输出不变的记忆压缩结果。"""
    result = compress_memory_data(request)
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
