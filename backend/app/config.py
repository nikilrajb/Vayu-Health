from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field

ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    openaq_api_key: str = ""
    airnow_api_key: str = ""
    provider_connect_timeout_seconds: float = Field(default=8, ge=1, le=60)
    provider_read_timeout_seconds: float = Field(default=25, ge=1, le=120)
    provider_retries: int = Field(default=1, ge=0, le=2)
    vayu_host: str = "0.0.0.0"
    vayu_port: int = 8000
    default_city: str = "Delhi"
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    auto_train: bool = True

    data_dir: Path = ROOT / "data"
    sample_dir: Path = ROOT / "data" / "sample"
    processed_dir: Path = ROOT / "data" / "processed"
    model_dir: Path = ROOT / "backend" / "app" / "ml" / "artifacts"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.processed_dir.mkdir(parents=True, exist_ok=True)
    settings.model_dir.mkdir(parents=True, exist_ok=True)
    settings.sample_dir.mkdir(parents=True, exist_ok=True)
    return settings
