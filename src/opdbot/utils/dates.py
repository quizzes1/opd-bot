from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from opdbot.config import settings


def _tz() -> ZoneInfo:
    return ZoneInfo(settings.timezone)


def to_local(dt: datetime) -> datetime:
    """Treat naive datetimes as UTC, convert to configured local tz."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(_tz())


def fmt_date(dt: datetime) -> str:
    return to_local(dt).strftime("%d.%m.%Y")


def fmt_datetime(dt: datetime) -> str:
    return to_local(dt).strftime("%d.%m.%Y %H:%M")
