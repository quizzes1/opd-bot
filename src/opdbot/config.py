from pathlib import Path
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    bot_token: str
    database_url: str = "sqlite+aiosqlite:///./opdbot.db"
    storage_root: Path = Path("./storage")
    templates_root: Path = Path("./templates")
    superadmin_tg_ids: list[int] = []
    log_level: str = "INFO"
    webhook_url: str = ""

    @field_validator("superadmin_tg_ids", mode="before")
    @classmethod
    def parse_tg_ids(cls, v: object) -> list[int]:
        if isinstance(v, str):
            return [int(x.strip()) for x in v.split(",") if x.strip()]
        return v  # type: ignore[return-value]


settings = Settings()  # type: ignore[call-arg]
