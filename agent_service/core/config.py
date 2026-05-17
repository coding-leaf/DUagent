from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    PROJECT_NAME: str = "EduAgent Agent Service API"
    VERSION: str = "5.0"
    API_V1_STR: str = "/agent/v1"

    # Qdrant Settings
    QDRANT_PATH: str = "./qdrant_data"

    # Add other settings here (e.g., API keys for LLM)

    class Config:
        env_file = ".env"

settings = Settings()
