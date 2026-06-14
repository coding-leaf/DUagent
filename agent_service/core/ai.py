from __future__ import annotations

import asyncio
import inspect
import json
from dataclasses import dataclass
from typing import Any, Protocol, Sequence
from urllib import request as urllib_request

from agent_service.core.config import settings


@dataclass(frozen=True)
class ChatMessage:
    role: str
    content: str


class EmbeddingProvider(Protocol):
    async def embed_texts(self, texts: Sequence[str]) -> list[list[float]]:
        """向量化文本列表，输入文本序列，输出与输入等长的向量列表。"""


class RerankerProvider(Protocol):
    async def score(self, query: str, documents: Sequence[str]) -> list[float]:
        """计算 query 与文档列表的相关分，输入查询和文档，输出与文档等长的分数列表。"""


class ChatProvider(Protocol):
    async def complete(self, messages: Sequence[ChatMessage]) -> str:
        """生成对话回复，输入消息序列，输出模型文本回复。"""


@dataclass(frozen=True)
class AIProviders:
    embedding: EmbeddingProvider | None
    reranker: RerankerProvider | None
    chat: ChatProvider | None


class AgentScopeEmbeddingProvider:
    def __init__(self, model: Any) -> None:
        self.model = model

    async def embed_texts(self, texts: Sequence[str]) -> list[list[float]]:
        response = await self.model(list(texts))
        embeddings = getattr(response, "embeddings", None)
        if not isinstance(embeddings, list):
            raise ValueError("AgentScope embedding response missing embeddings list")
        return [[float(value) for value in embedding] for embedding in embeddings]


class AgentScopeChatProvider:
    def __init__(self, model, formatter, json_mode: bool = False, timeout: float = 120) -> None:
        self.model = model
        self.formatter = formatter
        self.json_mode = json_mode
        self.timeout = timeout

    async def complete(self, messages: Sequence[ChatMessage], structured_model=None) -> str:
        from agentscope.message import Msg

        kwargs: dict = {}
        if structured_model is not None:
            kwargs["structured_model"] = structured_model
        elif self.json_mode:
            kwargs["response_format"] = {"type": "json_object"}
        response = await asyncio.wait_for(
            self.model(await self._format_messages(messages, Msg), **kwargs),
            timeout=self.timeout,
        )
        return _parse_agentscope_chat_response_text(response)

    async def _format_messages(self, messages: Sequence[ChatMessage], msg_cls) -> list:
        formatted = self.formatter.format(_to_agentscope_msgs(messages, msg_cls))
        if inspect.isawaitable(formatted):
            formatted = await formatted
        return formatted


class OpenAICompatibleRerankerProvider:
    def __init__(
        self,
        base_url: str,
        api_key: str,
        model: str,
        request_sender=None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.request_sender = request_sender or _post_openai_compatible_json
        self.run_request_in_thread = request_sender is None

    async def score(self, query: str, documents: Sequence[str]) -> list[float]:
        payload = {
            "model": self.model,
            "query": query,
            "documents": list(documents),
        }
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        if self.run_request_in_thread:
            response = await asyncio.to_thread(
                self.request_sender,
                f"{self.base_url}/rerank",
                headers,
                payload,
            )
        else:
            response = self.request_sender(
                f"{self.base_url}/rerank",
                headers,
                payload,
            )
        return _parse_reranker_scores(response, expected_documents=len(documents))


def get_ai_providers(
    embedding_provider: EmbeddingProvider | None = None,
    reranker_provider: RerankerProvider | None = None,
    chat_provider: ChatProvider | None = None,
) -> AIProviders:
    """构建可替换 AI 供应商边界，当前不绑定具体模型，后续由 Agent 编排层注入使用。"""
    return AIProviders(
        embedding=embedding_provider or _build_embedding_provider_from_settings(),
        reranker=reranker_provider or _build_reranker_provider_from_settings(),
        chat=chat_provider or _build_chat_provider_from_settings(),
    )


def _build_embedding_provider_from_settings() -> EmbeddingProvider | None:
    if (
        getattr(settings, "EMBEDDING_PROVIDER", None) == "agentscope_openai"
        and getattr(settings, "EMBEDDING_BASE_URL", None)
        and getattr(settings, "EMBEDDING_API_KEY", None)
        and getattr(settings, "EMBEDDING_MODEL", None)
    ):
        from agentscope.embedding import OpenAITextEmbedding

        request_dimensions = (
            getattr(settings, "EMBEDDING_DIMENSION", 1024)
            if getattr(settings, "EMBEDDING_REQUEST_DIMENSIONS_ENABLED", False)
            else None
        )
        return AgentScopeEmbeddingProvider(
            OpenAITextEmbedding(
                api_key=settings.EMBEDDING_API_KEY,
                model_name=settings.EMBEDDING_MODEL,
                dimensions=request_dimensions,
                base_url=settings.EMBEDDING_BASE_URL,
            )
        )
    return None


def _build_chat_provider_from_settings() -> ChatProvider | None:
    if (
        getattr(settings, "LLM_PROVIDER", None) == "agentscope_openai"
        and getattr(settings, "LLM_BASE_URL", None)
        and getattr(settings, "LLM_API_KEY", None)
        and getattr(settings, "LLM_MODEL", None)
    ):
        from agentscope.formatter import DeepSeekChatFormatter
        from agentscope.model import OpenAIChatModel

        json_mode_enabled = getattr(settings, "LLM_JSON_MODE_ENABLED", None)
        if json_mode_enabled is None:
            json_mode_enabled = getattr(settings, "LLM_STRUCTURED_OUTPUT_ENABLED", False)
        return AgentScopeChatProvider(
            model=OpenAIChatModel(
                model_name=settings.LLM_MODEL,
                api_key=settings.LLM_API_KEY,
                stream=getattr(settings, "LLM_STREAM", True),
                client_kwargs={
                    "base_url": settings.LLM_BASE_URL,
                    "timeout": getattr(settings, "LLM_TIMEOUT", 60.0),
                },
            ),
            formatter=DeepSeekChatFormatter(),
            json_mode=json_mode_enabled,
        )
    return None


def _build_reranker_provider_from_settings() -> RerankerProvider | None:
    if (
        getattr(settings, "RERANKER_PROVIDER", None) == "openai_compatible"
        and getattr(settings, "RERANKER_BASE_URL", None)
        and getattr(settings, "RERANKER_API_KEY", None)
        and getattr(settings, "RERANKER_MODEL", None)
    ):
        return OpenAICompatibleRerankerProvider(
            base_url=settings.RERANKER_BASE_URL,
            api_key=settings.RERANKER_API_KEY,
            model=settings.RERANKER_MODEL,
        )
    return None


def _post_openai_compatible_json(url: str, headers: dict[str, str], payload: dict) -> dict:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = urllib_request.Request(url, data=body, headers=headers, method="POST")
    with urllib_request.urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def _parse_agentscope_chat_response_text(response) -> str:
    text = _parse_optional_agentscope_chat_response_text(response)
    if text is None:
        raise ValueError("AgentScope chat response missing text content")
    return text


def _parse_optional_agentscope_chat_response_text(response) -> str | None:
    content = getattr(response, "content", None)
    if isinstance(content, str):
        return content
    if not isinstance(content, list):
        return _extract_structured_result_from_metadata(response)
    parts = []
    for block in content:
        if isinstance(block, str):
            parts.append(block)
            continue
        if isinstance(block, dict):
            text = block.get("text")
            if isinstance(text, str):
                parts.append(text)
            continue
        text = getattr(block, "text", None)
        if isinstance(text, str):
            parts.append(text)
    if not parts:
        return _extract_structured_result_from_metadata(response)
    return "".join(parts)


def _extract_structured_result_from_metadata(response) -> str | None:
    import json

    metadata = getattr(response, "metadata", None)
    if not isinstance(metadata, dict):
        return None
    for key in ("model_text", "content", "text", "result"):
        value = metadata.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    try:
        return json.dumps(metadata, ensure_ascii=False)
    except (TypeError, ValueError):
        pass
    return None


def _to_agentscope_msgs(messages: Sequence[ChatMessage], msg_cls) -> list:
    return [
        msg_cls(name=message.role, role=message.role, content=message.content)
        for message in messages
    ]


def _parse_reranker_scores(response: dict, expected_documents: int) -> list[float]:
    data = response.get("data")
    if isinstance(data, list):
        indexed_scores = _parse_indexed_scores(data, score_key="score")
    else:
        results = response.get("results")
        if not isinstance(results, list):
            raise ValueError("Reranker response missing data or results list")
        indexed_scores = _parse_indexed_scores(results, score_key="relevance_score")

    indexed_scores.sort(key=lambda item: item[0])
    if len(indexed_scores) != expected_documents:
        raise ValueError("Reranker response length does not match documents")
    return [score for _, score in indexed_scores]


def _parse_indexed_scores(items: list, score_key: str) -> list[tuple[int, float]]:
    indexed_scores: list[tuple[int, float]] = []
    for item in items:
        if not isinstance(item, dict):
            raise ValueError("Reranker response item must be an object")
        index = item.get("index")
        score = item.get(score_key)
        if not isinstance(index, int) or not isinstance(score, int | float):
            raise ValueError("Reranker response item missing index or score")
        indexed_scores.append((index, float(score)))
    return indexed_scores
