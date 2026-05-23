from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env")

    PROJECT_NAME: str = "EduAgent Agent Service API"
    VERSION: str = "5.0"
    API_V1_STR: str = "/agent/v1"

    # Qdrant 相关配置
    QDRANT_PATH: str = "./qdrant_data"
    QDRANT_USER_MEMORY_COLLECTION: str = "user_memory_v1_1024"
    QDRANT_COURSE_KNOWLEDGE_COLLECTION: str = "course_knowledge_v1_1024"

    # AI 供应商相关配置。密钥类字段应通过 .env 注入，不应写入提交到仓库的配置文件。
    AI_PROVIDER: str = "none"
    EMBEDDING_PROVIDER: str = "none"
    EMBEDDING_MODEL: str | None = None
    EMBEDDING_BASE_URL: str | None = None
    EMBEDDING_API_KEY: str | None = None
    EMBEDDING_DIMENSION: int = 1024
    RERANKER_PROVIDER: str = "none"
    RERANKER_MODEL: str | None = None
    RERANKER_BASE_URL: str | None = None
    RERANKER_API_KEY: str | None = None
    LLM_PROVIDER: str = "none"
    LLM_MODEL: str | None = None
    LLM_BASE_URL: str | None = None
    LLM_API_KEY: str | None = None


settings = Settings()
