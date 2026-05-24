import asyncio
import json
from dataclasses import dataclass
from typing import Protocol, Sequence
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
    embedding: EmbeddingProvider
    reranker: RerankerProvider
    chat: ChatProvider


class UnconfiguredEmbeddingProvider:
    async def embed_texts(self, texts: Sequence[str]) -> list[list[float]]:
        raise NotImplementedError("Embedding provider is not configured")


class UnconfiguredRerankerProvider:
    async def score(self, query: str, documents: Sequence[str]) -> list[float]:
        raise NotImplementedError("Reranker provider is not configured")


class UnconfiguredChatProvider:
    async def complete(self, messages: Sequence[ChatMessage]) -> str:
        raise NotImplementedError("Chat provider is not configured")


class OpenAICompatibleEmbeddingProvider:
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

    async def embed_texts(self, texts: Sequence[str]) -> list[list[float]]:
        payload = {"model": self.model, "input": list(texts)}
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        if self.run_request_in_thread:
            response = await asyncio.to_thread(
                self.request_sender,
                f"{self.base_url}/embeddings",
                headers,
                payload,
            )
        else:
            response = self.request_sender(
                f"{self.base_url}/embeddings",
                headers,
                payload,
            )
        return _parse_embedding_vectors(response)


class OpenAICompatibleChatProvider:
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

    async def complete(self, messages: Sequence[ChatMessage]) -> str:
        payload = {
            "model": self.model,
            "messages": [{"role": message.role, "content": message.content} for message in messages],
        }
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        if self.run_request_in_thread:
            response = await asyncio.to_thread(
                self.request_sender,
                f"{self.base_url}/chat/completions",
                headers,
                payload,
            )
        else:
            response = self.request_sender(
                f"{self.base_url}/chat/completions",
                headers,
                payload,
            )
        return _parse_chat_completion_text(response)


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


def _build_embedding_provider_from_settings() -> EmbeddingProvider:
    if (
        getattr(settings, "EMBEDDING_PROVIDER", None) == "openai_compatible"
        and getattr(settings, "EMBEDDING_BASE_URL", None)
        and getattr(settings, "EMBEDDING_API_KEY", None)
        and getattr(settings, "EMBEDDING_MODEL", None)
    ):
        return OpenAICompatibleEmbeddingProvider(
            base_url=settings.EMBEDDING_BASE_URL,
            api_key=settings.EMBEDDING_API_KEY,
            model=settings.EMBEDDING_MODEL,
        )
    return UnconfiguredEmbeddingProvider()


def _build_chat_provider_from_settings() -> ChatProvider:
    if (
        getattr(settings, "LLM_PROVIDER", None) == "openai_compatible"
        and getattr(settings, "LLM_BASE_URL", None)
        and getattr(settings, "LLM_API_KEY", None)
        and getattr(settings, "LLM_MODEL", None)
    ):
        return OpenAICompatibleChatProvider(
            base_url=settings.LLM_BASE_URL,
            api_key=settings.LLM_API_KEY,
            model=settings.LLM_MODEL,
        )
    return UnconfiguredChatProvider()


def _build_reranker_provider_from_settings() -> RerankerProvider:
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
    return UnconfiguredRerankerProvider()


def _post_openai_compatible_json(url: str, headers: dict[str, str], payload: dict) -> dict:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = urllib_request.Request(url, data=body, headers=headers, method="POST")
    with urllib_request.urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def _parse_embedding_vectors(response: dict) -> list[list[float]]:
    data = response.get("data")
    if not isinstance(data, list):
        raise ValueError("Embedding response missing data list")

    indexed_embeddings: list[tuple[int, list[float]]] = []
    for item in data:
        if not isinstance(item, dict):
            raise ValueError("Embedding response item must be an object")
        index = item.get("index")
        embedding = item.get("embedding")
        if not isinstance(index, int) or not isinstance(embedding, list):
            raise ValueError("Embedding response item missing index or embedding")
        indexed_embeddings.append((index, [float(value) for value in embedding]))

    indexed_embeddings.sort(key=lambda item: item[0])
    return [embedding for _, embedding in indexed_embeddings]


def _parse_chat_completion_text(response: dict) -> str:
    choices = response.get("choices")
    if not isinstance(choices, list) or not choices:
        raise ValueError("Chat completion response missing choices list")
    message = choices[0].get("message") if isinstance(choices[0], dict) else None
    if not isinstance(message, dict):
        raise ValueError("Chat completion response missing message object")
    content = message.get("content")
    if not isinstance(content, str):
        raise ValueError("Chat completion response missing text content")
    return content


def _parse_reranker_scores(response: dict, expected_documents: int) -> list[float]:
    data = response.get("data")
    if not isinstance(data, list):
        raise ValueError("Reranker response missing data list")

    indexed_scores: list[tuple[int, float]] = []
    for item in data:
        if not isinstance(item, dict):
            raise ValueError("Reranker response item must be an object")
        index = item.get("index")
        score = item.get("score")
        if not isinstance(index, int) or not isinstance(score, int | float):
            raise ValueError("Reranker response item missing index or score")
        indexed_scores.append((index, float(score)))

    indexed_scores.sort(key=lambda item: item[0])
    if len(indexed_scores) != expected_documents:
        raise ValueError("Reranker response length does not match documents")
    return [score for _, score in indexed_scores]
