from backend.app.signals.auth import display_prefix


def test_display_prefix_longer_than_12():
    assert display_prefix("123456789012345") == "123456789012"

def test_display_prefix_exactly_12():
    assert display_prefix("123456789012") == "123456789012"

def test_display_prefix_shorter_than_12():
    assert display_prefix("12345") == "12345"

def test_display_prefix_empty_string():
    assert display_prefix("") == ""
