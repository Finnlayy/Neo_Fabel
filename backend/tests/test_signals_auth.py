import pytest

from backend.app.signals.auth import (
    generate_credential,
    TV_PREFIX,
    MCP_PREFIX
)

def test_generate_credential_tradingview_secret():
    token = generate_credential("tradingview_secret")
    assert token.startswith(TV_PREFIX)
    assert len(token) > len(TV_PREFIX)

def test_generate_credential_mcp_bearer():
    token = generate_credential("mcp_bearer")
    assert token.startswith(MCP_PREFIX)
    assert len(token) > len(MCP_PREFIX)

def test_generate_credential_unsupported_kind():
    with pytest.raises(ValueError, match="unsupported credential kind"):
        generate_credential("unsupported_kind")

def test_generate_credential_randomness():
    token1 = generate_credential("tradingview_secret")
    token2 = generate_credential("tradingview_secret")
    assert token1 != token2
