from functools import lru_cache
from pathlib import Path

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    easynet_host: str = "https://easynet.local"
    easynet_username: str = ""
    easynet_password: SecretStr = SecretStr("")
    database_path: Path = Path("./data/easynet.db")
    collect_interval_seconds: int = Field(default=60, ge=10, le=3600)
    history_interval_seconds: int = Field(default=300, ge=60, le=3600)
    api_host: str = "127.0.0.1"
    api_port: int = Field(default=8000, ge=1, le=65535)
    log_level: str = "INFO"
    easynet_verify_tls: bool = False
    easynet_timeout_seconds: float = Field(default=10.0, gt=0, le=60)
    timezone: str = "Europe/Madrid"

    @property
    def database_absolute_path(self) -> Path:
        return self.database_path.expanduser().resolve()


@lru_cache
def get_settings() -> Settings:
    return Settings()

