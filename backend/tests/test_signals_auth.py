from datetime import UTC, datetime, timedelta
import pytest

from backend.app.settings import Settings
from backend.app.signals.auth import (
    generate_credential,
    make_credential,
    verify_credential,
    GeneratedCredential,
    TV_PREFIX,
    MCP_PREFIX,
)

def test_generate_credential_tradingview():
    cred = generate_credential("tradingview_secret")
    assert cred.startswith(TV_PREFIX)
    assert len(cred) > len(TV_PREFIX)

def test_generate_credential_mcp():
    cred = generate_credential("mcp_bearer")
    assert cred.startswith(MCP_PREFIX)
    assert len(cred) > len(MCP_PREFIX)

def test_generate_credential_invalid_kind():
    with pytest.raises(ValueError, match="unsupported credential kind"):
        generate_credential("invalid_kind")

def test_make_credential_tradingview():
    settings = Settings(signal_credential_pepper="test-pepper")
    result = make_credential("tradingview_secret", settings)

    assert isinstance(result, GeneratedCredential)
    assert result.plaintext.startswith(TV_PREFIX)
    assert result.display_prefix == result.plaintext[:12]
    assert result.pepper_version == "v1"
    assert result.digest

    # Verify the digest actually matches what we expect
    assert verify_credential(
        result.plaintext,
        result.digest,
        settings,
        revoked_at=None,
        expires_at=None
    )

def test_make_credential_mcp():
    settings = Settings(signal_credential_pepper="test-pepper")
    result = make_credential("mcp_bearer", settings)

    assert isinstance(result, GeneratedCredential)
    assert result.plaintext.startswith(MCP_PREFIX)
    assert result.display_prefix == result.plaintext[:12]
    assert result.pepper_version == "v1"
    assert result.digest

def test_verify_credential_revoked():
    settings = Settings(signal_credential_pepper="test-pepper")
    cred = make_credential("tradingview_secret", settings)

    assert not verify_credential(
        cred.plaintext,
        cred.digest,
        settings,
        revoked_at=datetime.now(UTC),
        expires_at=None
    )

def test_verify_credential_expired():
    settings = Settings(signal_credential_pepper="test-pepper")
    cred = make_credential("tradingview_secret", settings)

    assert not verify_credential(
        cred.plaintext,
        cred.digest,
        settings,
        revoked_at=None,
        expires_at=datetime.now(UTC) - timedelta(days=1)
    )

def test_verify_credential_not_expired():
    settings = Settings(signal_credential_pepper="test-pepper")
    cred = make_credential("tradingview_secret", settings)

    assert verify_credential(
        cred.plaintext,
        cred.digest,
        settings,
        revoked_at=None,
        expires_at=datetime.now(UTC) + timedelta(days=1)
    )

def test_verify_credential_invalid_digest():
    settings = Settings(signal_credential_pepper="test-pepper")
    cred = make_credential("tradingview_secret", settings)

    assert not verify_credential(
        cred.plaintext,
        "invalid_digest",
        settings,
        revoked_at=None,
        expires_at=None
    )
