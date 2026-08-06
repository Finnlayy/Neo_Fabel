import re

from backend.app.signals.repository import secrets_public_key


def test_secrets_public_key():
    key1 = secrets_public_key()
    key2 = secrets_public_key()

    assert isinstance(key1, str)
    assert len(key1) == 24
    assert key1 != key2

    # Verify url-safe base64 characters
    # token_urlsafe returns characters from A-Z, a-z, 0-9, -, _
    assert re.match(r'^[-_a-zA-Z0-9]+$', key1) is not None
