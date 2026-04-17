from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    bot_token: str = ""
    database_url: str = "sqlite+aiosqlite:///./opdbot.db"
    storage_root: Path = Path("./storage")
    templates_root: Path = Path("./templates")
    log_dir: Path = PROJECT_ROOT / "logs"
    redis_url: str = ""
    superadmin_tg_ids: list[int] = []
    log_level: str = "INFO"
    webhook_url: str = ""
    webhook_host: str = "0.0.0.0"
    webhook_port: int = 8080

    @field_validator("superadmin_tg_ids", mode="before")
    @classmethod
    def parse_tg_ids(cls, v: object) -> list[int]:
        if isinstance(v, str):
            return [int(x.strip()) for x in v.split(",") if x.strip()]
        return v  # type: ignore[return-value]


settings = Settings()
