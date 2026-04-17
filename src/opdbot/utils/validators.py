def validate_file(
    mime: str,
    size_bytes: int,
    allowed_mime: str,
    max_size_mb: int,
) -> str | None:
    allowed = [ext.strip().lower() for ext in allowed_mime.split(",")]
    mime_lower = mime.lower()

    mime_to_ext = {
        "application/pdf": "pdf",
        "image/jpeg": "jpg",
        "image/jpg": "jpg",
        "image/png": "png",
        "application/msword": "doc",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "docx",
        "image/gif": "gif",
        "image/webp": "webp",
    }

    file_ext = mime_to_ext.get(mime_lower)
    # Also check jpeg == jpg alias
    jpeg_aliases = {"jpg", "jpeg"}

    def ext_matches(ext: str) -> bool:
        if ext == file_ext:
            return True
        if file_ext in ("jpg", "jpeg") and ext in jpeg_aliases:
            return True
        return False

    if not any(ext_matches(a) for a in allowed):
        return "mime"

    max_bytes = max_size_mb * 1024 * 1024
    if size_bytes > max_bytes:
        return "size"

    return None
