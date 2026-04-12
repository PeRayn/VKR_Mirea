from functools import lru_cache
from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "Smart Disk API"
    debug: bool = False
    secret_key: str = "change-me"
    access_token_expire_minutes: int = 120
    database_url: str
    cors_origins: str = "http://localhost:5173"
    files_root: Path = Path("./data/files")
    models_root: Path = Path("../models")
    max_upload_mb: int = 20

    embedding_model: str = "../models/bge-m3"
    embedding_dim: int = 1024
    top_k: int = 5
    retrieval_top_k: int = 10
    reranker_enabled: bool = True
    reranker_model: str = "../models/bge-reranker-base"

    llm_provider: str = "llama_cpp"
    llm_model_path: Path = Path("../models/Qwen3-4B-Q4_K_M.gguf")
    llm_model_name: str = "Qwen3-4B-Q4_K_M"
    llm_n_ctx: int = 4096
    llm_max_tokens: int = 400
    llm_temperature: float = 0.1
    llm_fallback_to_stub: bool = True

    @field_validator("files_root", mode="before")
    @classmethod
    def _path_from_string(cls, value: str | Path) -> Path:
        return Path(value)

    @field_validator("models_root", "llm_model_path", mode="before")
    @classmethod
    def _optional_path_from_string(cls, value: str | Path) -> Path:
        return Path(value)

    @property
    def cors_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_mb * 1024 * 1024


@lru_cache
def get_settings() -> Settings:
    return Settings()
