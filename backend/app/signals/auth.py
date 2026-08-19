"""TradingView/MCP credential generation, digest, verification, rotation."""

from __future__ import annotations

import hashlib
import hmac
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime

from ..settings import Settings

TV_PREFIX = "tvsec_"
MCP_PREFIX = "mcptok_"


@dataclass(frozen=True)
class GeneratedCredential:
    plaintext: str
    digest: str
    display_prefix: str
    pepper_version: str


def generate_credential(kind: str) -> str:
    token = secrets.token_urlsafe(32)
    if kind == "tradingview_secret":
        return f"{TV_PREFIX}{token}"
    if kind == "mcp_bearer":
        return f"{MCP_PREFIX}{token}"
    raise ValueError("unsupported credential kind")


def digest_credential(plaintext: str, settings: Settings, *, pepper_version: str = "v1") -> str:
    pepper = settings.signal_credential_pepper or "dev-only-insecure-pepper"
    material = f"{pepper_version}:{pepper}".encode()
    return hmac.new(material, plaintext.encode("utf-8"), hashlib.sha256).hexdigest()


def display_prefix(plaintext: str) -> str:
    return plaintext[:12]


def make_credential(kind: str, settings: Settings) -> GeneratedCredential:
    plaintext = generate_credential(kind)
    return GeneratedCredential(
        plaintext=plaintext,
        digest=digest_credential(plaintext, settings),
        display_prefix=display_prefix(plaintext),
        pepper_version="v1",
    )


def verify_credential(
    plaintext: str,
    digest: str,
    settings: Settings,
    *,
    pepper_version: str = "v1",
    revoked_at: datetime | None,
    expires_at: datetime | None,
) -> bool:
    if not plaintext or not isinstance(plaintext, str):
        return False
    if revoked_at is not None:
        return False
    if expires_at is not None and expires_at <= datetime.now(UTC):
        return False
    expected = digest_credential(plaintext, settings, pepper_version=pepper_version)
    return hmac.compare_digest(expected, digest)
