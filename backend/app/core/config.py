from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "AgentOps"
    debug: bool = False

    # LLM
    openai_api_key: str = ""

    # DB — 로컬 개발은 SQLite, 운영은 Postgres URL로 교체
    # (앱 코드에서 SQLite 전용 문법을 금지해 이 교체가 한 줄 변경으로 끝나도록 함)
    database_url: str = "sqlite+aiosqlite:///./agentops.db"

    # 벡터 스토어
    chroma_persist_dir: str = "./data/chroma"

    # 관측성(Observability)
    langfuse_public_key: str = ""
    langfuse_secret_key: str = ""
    langfuse_host: str = "https://cloud.langfuse.com"

    # CORS
    cors_origins: list[str] = ["http://localhost:3000"]


@lru_cache
def get_settings() -> Settings:
    return Settings()
