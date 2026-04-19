import re
from pathlib import Path

PHONE_RE = re.compile(r"^\+?[78]?\d{10}$")


def normalize_phone(text: str) -> str:
    return re.sub(r"[^\d+]", "", text)


def validate_phone(text: str) -> str | None:
    normalized = normalize_phone(text)
    if not PHONE_RE.match(normalized):
        return None
    if normalized.startswith("8"):
        normalized = "+7" + normalized[1:]
    elif normalized.startswith("7"):
        normalized = "+" + normalized
    elif not normalized.startswith("+"):
        normalized = "+7" + normalized
    return normalized


MIME_TO_EXT = {
    "application/pdf": "pdf",
    "image/jpeg": "jpg",
    "image/jpg": "jpg",
    "image/png": "png",
    "application/msword": "doc",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "docx",
    "image/gif": "gif",
    "image/webp": "webp",
}


EXT_ALIASES: dict[str, set[str]] = {
    "jpg": {"jpg", "jpeg"},
    "jpeg": {"jpg", "jpeg"},
    "doc": {"doc", "docx"},
    "docx": {"doc", "docx"},
}


def _norm_ext(ext: str) -> str:
    ext = ext.lower().lstrip(".")
    return "jpg" if ext == "jpeg" else ext


def validate_file(
    mime: str,
    size_bytes: int,
    allowed_mime: str,
    max_size_mb: int,
    filename: str | None = None,
) -> str | None:
    allowed_raw = {_norm_ext(x.strip()) for x in allowed_mime.split(",") if x.strip()}
    allowed = set(allowed_raw)
    for ext in allowed_raw:
        allowed |= EXT_ALIASES.get(ext, set())

    ext_from_name = _norm_ext(Path(filename).suffix) if filename else ""
    ext_from_mime = MIME_TO_EXT.get((mime or "").lower(), "")

    detected = ext_from_name or ext_from_mime
    if not detected or detected not in allowed:
        return "mime"

    max_bytes = max_size_mb * 1024 * 1024
    if size_bytes > max_bytes:
        return "size"
    return None


TELEGRAM_DOWNLOAD_LIMIT_BYTES = 20 * 1024 * 1024
