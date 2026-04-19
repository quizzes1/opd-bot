import json
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
    dev_mode: bool = False

    @field_validator("superadmin_tg_ids", mode="before")
    @classmethod
    def parse_tg_ids(cls, v: object) -> list[int]:
        if v is None or v == "":
            return []
        if isinstance(v, int):
            return [v]
        if isinstance(v, str):
            s = v.strip()
            if not s:
                return []
            if s.startswith("["):
                try:
                    parsed = json.loads(s)
                    return [int(x) for x in parsed]
                except (ValueError, TypeError):
                    pass
            return [int(x.strip()) for x in s.split(",") if x.strip()]
        if isinstance(v, (list, tuple)):
            return [int(x) for x in v]
        return v  # type: ignore[return-value]


settings = Settings()
