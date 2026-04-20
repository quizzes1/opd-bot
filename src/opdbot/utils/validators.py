import re
from pathlib import Path

# Strict: +7 then exactly 10 digits.
PHONE_RE = re.compile(r"^\+7\d{10}$")

# Student FIO: 2-3 cyrillic words, hyphens allowed inside a word.
FULL_NAME_RE = re.compile(
    r"^[А-ЯЁа-яё]+(?:-[А-ЯЁа-яё]+)?(?:\s[А-ЯЁа-яё]+(?:-[А-ЯЁа-яё]+)?){1,2}$"
)

# Supervisor FIO: exactly 3 cyrillic words, hyphens allowed.
SUPERVISOR_FIO_RE = re.compile(
    r"^[А-ЯЁа-яё]+(?:-[А-ЯЁа-яё]+)?"
    r"(?:\s[А-ЯЁа-яё]+(?:-[А-ЯЁа-яё]+)?){2}$"
)

# Catalog doc code
CATALOG_CODE_RE = re.compile(r"^[a-z][a-z0-9_]*$")


def normalize_phone(text: str) -> str:
    """Strip only whitespace/hyphens/parens; other chars survive and will fail regex."""
    s = re.sub(r"[\s\-()]", "", text or "")
    if re.fullmatch(r"8\d{10}", s):
        s = "+7" + s[1:]
    return s


def validate_phone(text: str) -> str | None:
    normalized = normalize_phone(text or "")
    if not PHONE_RE.fullmatch(normalized):
        return None
    return normalized


def validate_full_name(text: str) -> str | None:
    s = (text or "").strip()
    s = re.sub(r"\s+", " ", s)
    if not FULL_NAME_RE.match(s):
        return None
    return " ".join(w.capitalize() for w in s.split(" "))


def validate_supervisor_fio(text: str) -> str | None:
    s = (text or "").strip()
    s = re.sub(r"\s+", " ", s)
    if not SUPERVISOR_FIO_RE.match(s):
        return None
    return " ".join(w.capitalize() for w in s.split(" "))


def validate_catalog_code(text: str) -> str | None:
    s = (text or "").strip().lower()
    if not CATALOG_CODE_RE.match(s):
        return None
    return s


# Registry of file formats the system understands.
ALLOWED_FORMATS_REGISTRY: set[str] = {
    "pdf",
    "jpg",
    "jpeg",
    "png",
    "doc",
    "docx",
}


def parse_allowed_formats(text: str) -> tuple[list[str], list[str]]:
    """Split a user-entered list of extensions into (accepted, unknown)."""
    raw = [t.strip().lower().lstrip(".") for t in (text or "").split(",")]
    raw = [t for t in raw if t]
    accepted: list[str] = []
    unknown: list[str] = []
    seen: set[str] = set()
    for ext in raw:
        norm = "jpg" if ext == "jpeg" else ext
        if norm in ALLOWED_FORMATS_REGISTRY:
            if norm not in seen:
                accepted.append(norm)
                seen.add(norm)
        else:
            unknown.append(ext)
    return accepted, unknown


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
