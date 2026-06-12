from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    APP_NAME: str = "DUagent API"
    APP_VERSION: str = "5.0"
    DEBUG: bool = True

    # MySQL Database
    DB_HOST: str = "localhost"
    DB_PORT: int = 3306
    DB_USER: str = "root"
    DB_PASSWORD: str = "123456"
    DB_NAME: str = "duagent"

    DATABASE_URL: str = ""

    @property
    def resolved_database_url(self) -> str:
        if self.DATABASE_URL:
            return self.DATABASE_URL
        return f"mysql+aiomysql://{self.DB_USER}:{self.DB_PASSWORD}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}?charset=utf8mb4"

    # JWT — v1 single token, 7-day expiry
    JWT_SECRET_KEY: str = "duagent-jwt-secret-change-in-production"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 10080  # 7 days

    # Server
    HOST: str = "0.0.0.0"
    PORT: int = 8001

    # Agent service (internal)
    AGENT_SERVICE_URL: str = "http://localhost:8002"

    # LLM provider used by backend-side KG generation
    LLM_API_KEY: str = ""
    LLM_BASE_URL: str = "https://api.deepseek.com"
    LLM_MODEL: str = "deepseek-chat"

    # CourseCatalog local material storage
    COURSE_CATALOG_STORAGE_ROOT: str = "storage/course_catalogs"
    COURSE_CATALOG_MAX_UPLOAD_BYTES: int = 20 * 1024 * 1024

    # Captcha
    CAPTCHA_EXPIRE_SECONDS: int = 300

    # Webhook auth — shared secret between Backend and Agent Service
    WEBHOOK_SECRET: str = ""

    # CORS
    CORS_ORIGINS: list[str] = ["http://localhost:5173", "http://localhost:3000"]

    model_config = {"env_file": ".env", "case_sensitive": True, "extra": "ignore"}


settings = Settings()
