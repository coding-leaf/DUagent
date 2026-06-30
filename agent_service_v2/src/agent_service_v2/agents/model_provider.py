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


def build_chat_model_from_settings(settings: AgentModelSettings | None = None):
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
        stream=True,
        formatter=formatter,
        client_kwargs={"timeout": settings.LLM_TIMEOUT},
    )
