import re
import uuid
from datetime import datetime
from pathlib import Path

from aiogram import Bot

from opdbot.config import settings


def _sanitize(name: str) -> str:
    return re.sub(r"[^\w.\-]", "_", name)


def storage_root() -> Path:
    return Path(settings.storage_root).resolve()


async def save_tg_file(
    bot: Bot,
    file_id: str,
    user_id: int,
    application_id: int,
    req_code: str,
    filename: str,
) -> Path:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    suffix = uuid.uuid4().hex[:6]
    ext = Path(filename).suffix or ".bin"
    safe_name = f"{_sanitize(req_code)}_{ts}_{suffix}{ext}"

    root = storage_root()
    dest_dir = root / str(user_id) / str(application_id)
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / safe_name

    tg_file = await bot.get_file(file_id)
    await bot.download_file(tg_file.file_path, destination=dest)  # type: ignore[arg-type]

    return dest.relative_to(root)


def get_absolute_path(relative: str | Path) -> Path:
    rel = Path(relative)
    if rel.is_absolute():
        return rel
    return storage_root() / rel
