import pytest
from opdbot.utils.validators import validate_file


def test_valid_pdf():
    assert validate_file("application/pdf", 1024 * 1024, "pdf,jpg", 5) is None


def test_invalid_mime():
    assert validate_file("image/gif", 1024, "pdf,jpg,jpeg", 5) == "mime"


def test_file_too_large():
    assert validate_file("application/pdf", 20 * 1024 * 1024, "pdf", 5) == "size"


def test_jpeg_alias():
    assert validate_file("image/jpeg", 1024, "jpg", 10) is None
    assert validate_file("image/jpg", 1024, "jpeg", 10) is None
