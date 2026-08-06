import pytest

from backend.app.settings import Settings
from backend.app.signals.auth import (
    GeneratedCredential,
    digest_credential,
    make_credential,
)


def test_make_credential_tradingview_secret():
    settings = Settings(signal_credential_pepper="test-pepper")
    credential = make_credential("tradingview_secret", settings)

    assert isinstance(credential, GeneratedCredential)
    assert credential.plaintext.startswith("tvsec_")
    assert credential.display_prefix == credential.plaintext[:12]
    assert credential.pepper_version == "v1"
    assert credential.digest == digest_credential(credential.plaintext, settings)


def test_make_credential_mcp_bearer():
    settings = Settings(signal_credential_pepper="test-pepper")
    credential = make_credential("mcp_bearer", settings)

    assert isinstance(credential, GeneratedCredential)
    assert credential.plaintext.startswith("mcptok_")
    assert credential.display_prefix == credential.plaintext[:12]
    assert credential.pepper_version == "v1"
    assert credential.digest == digest_credential(credential.plaintext, settings)


def test_make_credential_unsupported_kind():
    settings = Settings(signal_credential_pepper="test-pepper")
    with pytest.raises(ValueError, match="unsupported credential kind"):
        make_credential("invalid_kind", settings)
