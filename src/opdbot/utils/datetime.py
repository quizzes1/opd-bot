from datetime import datetime


def format_dt(dt: datetime | None, fmt: str = "%d.%m.%Y %H:%M") -> str:
    if dt is None:
        return "—"
    return dt.strftime(fmt)


def parse_dt(text: str, fmt: str = "%d.%m.%Y %H:%M") -> datetime | None:
    try:
        return datetime.strptime(text.strip(), fmt)
    except ValueError:
        return None
