import pytest

from backend.app.settings import Settings


def test_cors_origins_valid():
    settings = Settings(allowed_origins="http://localhost:5173, https://example.com, *, http://192.168.1.100:8080")
    origins = settings.cors_origins
    assert origins == [
        "http://localhost:5173",
        "https://example.com",
        "*",
        "http://192.168.1.100:8080"
    ]

def test_cors_origins_trailing_slash_normalized():
    settings = Settings(allowed_origins="https://example.com/")
    assert settings.cors_origins == ["https://example.com"]

def test_cors_origins_invalid_scheme():
    settings = Settings(allowed_origins="ftp://example.com")
    with pytest.raises(ValueError, match="Must have http/https scheme"):
        _ = settings.cors_origins

def test_cors_origins_invalid_no_scheme():
    settings = Settings(allowed_origins="example.com")
    with pytest.raises(ValueError, match="Must have http/https scheme"):
        _ = settings.cors_origins

def test_cors_origins_invalid_path():
    settings = Settings(allowed_origins="https://example.com/api/v1")
    with pytest.raises(ValueError, match="Must not contain path, query, or fragment"):
        _ = settings.cors_origins

def test_cors_origins_invalid_query():
    settings = Settings(allowed_origins="https://example.com?foo=bar")
    with pytest.raises(ValueError, match="Must not contain path, query, or fragment"):
        _ = settings.cors_origins

def test_cors_origins_invalid_fragment():
    settings = Settings(allowed_origins="https://example.com#section")
    with pytest.raises(ValueError, match="Must not contain path, query, or fragment"):
        _ = settings.cors_origins

def test_cors_origins_empty_string():
    settings = Settings(allowed_origins="")
    assert settings.cors_origins == []

    settings = Settings(allowed_origins="   ,  , ")
    assert settings.cors_origins == []
