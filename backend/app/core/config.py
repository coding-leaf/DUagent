from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    APP_NAME: str = "DUagent API"
    APP_VERSION: str = "5.0"
    DEBUG: bool = True

    # Database
    DATABASE_URL: str = "sqlite+aiosqlite:///./duagent.db"

    # JWT
    JWT_SECRET_KEY: str = "duagent-jwt-secret-change-in-production"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # Server
    HOST: str = "0.0.0.0"
    PORT: int = 8001

    # Agent service (internal)
    AGENT_SERVICE_URL: str = "http://localhost:8002"
    AGENT_INTERNAL_KEY: str = "agent-internal-secret-key"

    # Captcha
    CAPTCHA_EXPIRE_SECONDS: int = 300

    # CORS
    CORS_ORIGINS: list[str] = ["http://localhost:5173", "http://localhost:3000"]

    model_config = {"env_file": ".env", "case_sensitive": True}


settings = Settings()
