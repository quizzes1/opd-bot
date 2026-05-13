from datetime import datetime
from zoneinfo import ZoneInfo

from opdbot.config import settings


def _tz() -> ZoneInfo:
    return ZoneInfo(settings.timezone)


def to_local(dt: datetime) -> datetime:
    """Naive datetimes are assumed already in local tz (that's how the codebase
    writes them — via datetime.now() and strptime). Only aware datetimes get
    converted."""
    if dt.tzinfo is None:
        return dt
    return dt.astimezone(_tz())


def fmt_date(dt: datetime) -> str:
    return to_local(dt).strftime("%d.%m.%Y")


def fmt_datetime(dt: datetime) -> str:
    return to_local(dt).strftime("%d.%m.%Y %H:%M")
