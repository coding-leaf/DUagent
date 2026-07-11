from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class AgentModelSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(
            ".env",
            "agent_service/.env",
            "../agent_service/.env",
        ),
        extra="ignore",
    )

    LLM_PROVIDER: str | None = None
    LLM_BASE_URL: str | None = None
    LLM_API_KEY: str | None = None
    LLM_MODEL: str | None = None
    LLM_TIMEOUT: float = 60.0
    LLM_FORMATTER: str = "deepseek"
    BACKEND_INTERNAL_BASE_URL: str | None = None
    BACKEND_INTERNAL_AGENT_TOKEN: str | None = None
    BACKEND_INTERNAL_TIMEOUT: float = 10.0
    WEBHOOK_SECRET: str = ""

    EMBEDDING_PROVIDER: str | None = None
    EMBEDDING_MODEL: str | None = None
    EMBEDDING_BASE_URL: str | None = None
    EMBEDDING_API_KEY: str | None = None
    EMBEDDING_DIMENSION: int = 1024

    RERANKER_PROVIDER: str | None = None
    RERANKER_MODEL: str | None = None
    RERANKER_BASE_URL: str | None = None
    RERANKER_API_KEY: str | None = None

    QDRANT_URL: str | None = None
    QDRANT_PATH: str | None = None
    QDRANT_COURSE_KNOWLEDGE_COLLECTION: str = "course_knowledge_v1_1024"

    COURSE_CATALOG_STORAGE_ROOT: str = "/home/yezisama/workspace/workflow/EDUagent/backend/storage/course_catalogs"


def build_chat_model_from_settings(
    settings: AgentModelSettings | None = None,
    *,
    stream: bool = True,
):
    settings = settings or AgentModelSettings()
    if (
        settings.LLM_PROVIDER != "agentscope_openai"
        or not settings.LLM_BASE_URL
        or not settings.LLM_API_KEY
        or not settings.LLM_MODEL
    ):
        return None

    from agentscope.credential import OpenAICredential
    from agentscope.formatter import DeepSeekChatFormatter, OpenAIChatFormatter
    from agentscope.model import OpenAIChatModel

    formatter = (
        OpenAIChatFormatter()
        if settings.LLM_FORMATTER == "openai"
        else DeepSeekChatFormatter()
    )
    return OpenAIChatModel(
        credential=OpenAICredential(
            api_key=settings.LLM_API_KEY,
            base_url=settings.LLM_BASE_URL,
        ),
        model=settings.LLM_MODEL,
        stream=stream,
        formatter=formatter,
        client_kwargs={"timeout": settings.LLM_TIMEOUT},
    )


def build_embedding_model_from_settings(settings: AgentModelSettings | None = None):
    settings = settings or AgentModelSettings()
    if (
        settings.EMBEDDING_PROVIDER != "agentscope_openai"
        or not settings.EMBEDDING_BASE_URL
        or not settings.EMBEDDING_API_KEY
        or not settings.EMBEDDING_MODEL
    ):
        return None

    from agentscope.credential import OpenAICredential
    from agentscope.embedding import OpenAIEmbeddingModel

    return OpenAIEmbeddingModel(
        credential=OpenAICredential(
            api_key=settings.EMBEDDING_API_KEY,
            base_url=settings.EMBEDDING_BASE_URL,
        ),
        model=settings.EMBEDDING_MODEL,
        dimensions=settings.EMBEDDING_DIMENSION,
        pass_dimensions=False,
    )



class OpenAICompatibleRerankerProvider:
    def __init__(self, base_url: str, api_key: str, model: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model

    async def score(self, query: str, documents: list[str]) -> list[float]:
        if not documents:
            return []
        import json
        import urllib.request
        import asyncio

        payload = {
            "model": self.model,
            "query": query,
            "documents": list(documents),
        }
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        def _post():
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            req = urllib.request.Request(f"{self.base_url}/rerank", data=body, headers=headers, method="POST")
            with urllib.request.urlopen(req, timeout=30) as resp:
                return json.loads(resp.read().decode("utf-8"))

        response = await asyncio.to_thread(_post)
        results = response.get("data") or response.get("results") or []

        # Sort scores to keep original document order
        indexed_scores = []
        for item in results:
            index = item.get("index")
            score = item.get("score") or item.get("relevance_score") or 0.0
            indexed_scores.append((index, float(score)))

        indexed_scores.sort(key=lambda x: x[0])
        return [score for _, score in indexed_scores]


def build_reranker_model_from_settings(settings: AgentModelSettings | None = None):
    settings = settings or AgentModelSettings()
    if (
        settings.RERANKER_PROVIDER != "openai_compatible"
        or not settings.RERANKER_BASE_URL
        or not settings.RERANKER_API_KEY
        or not settings.RERANKER_MODEL
    ):
        return None

    return OpenAICompatibleRerankerProvider(
        base_url=settings.RERANKER_BASE_URL,
        api_key=settings.RERANKER_API_KEY,
        model=settings.RERANKER_MODEL,
    )
