import pytest
from datetime import datetime, UTC

from backend.app.signals.policy import parse_occurred_at

def test_parse_occurred_at_with_z_suffix():
    result = parse_occurred_at("2023-10-27T10:00:00Z")
    assert result == datetime(2023, 10, 27, 10, 0, 0, tzinfo=UTC)

def test_parse_occurred_at_with_explicit_timezone():
    result = parse_occurred_at("2023-10-27T10:00:00+00:00")
    assert result == datetime(2023, 10, 27, 10, 0, 0, tzinfo=UTC)

def test_parse_occurred_at_with_different_timezone():
    result = parse_occurred_at("2023-10-27T10:00:00-05:00")
    # Should convert to UTC
    expected = datetime(2023, 10, 27, 15, 0, 0, tzinfo=UTC)
    assert result == expected

def test_parse_occurred_at_missing_timezone_raises_value_error():
    with pytest.raises(ValueError, match="timestamp must be timezone-aware UTC"):
        parse_occurred_at("2023-10-27T10:00:00")

def test_parse_occurred_at_strips_whitespace():
    result = parse_occurred_at("  2023-10-27T10:00:00Z  ")
    assert result == datetime(2023, 10, 27, 10, 0, 0, tzinfo=UTC)
