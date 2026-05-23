from dataclasses import dataclass
from typing import Protocol, Sequence


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


def get_ai_providers(
    embedding_provider: EmbeddingProvider | None = None,
    reranker_provider: RerankerProvider | None = None,
    chat_provider: ChatProvider | None = None,
) -> AIProviders:
    """构建可替换 AI 供应商边界，当前不绑定具体模型，后续由 Agent 编排层注入使用。"""
    return AIProviders(
        embedding=embedding_provider or UnconfiguredEmbeddingProvider(),
        reranker=reranker_provider or UnconfiguredRerankerProvider(),
        chat=chat_provider or UnconfiguredChatProvider(),
    )
