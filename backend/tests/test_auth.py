import sys
from time import time
from types import ModuleType, SimpleNamespace

import pytest
from fastapi import HTTPException
from starlette.requests import Request

from backend.app import auth as auth_module


def _request(authorization: str | None = None) -> Request:
    headers = [] if authorization is None else [(b"authorization", authorization.encode("ascii"))]
    return Request({"type": "http", "method": "GET", "path": "/", "headers": headers})


def test_firebase_auth_uses_adc_for_google_application_credentials(monkeypatch):
    app = object()
    calls: list[tuple[object, dict[str, str], str]] = []
    application_default = object()
    fake_firebase_admin = ModuleType("firebase_admin")
    fake_firebase_admin.auth = SimpleNamespace()
    fake_firebase_admin.credentials = SimpleNamespace(ApplicationDefault=lambda: application_default)
    fake_firebase_admin.get_app = lambda _name: (_ for _ in ()).throw(ValueError("missing app"))

    def initialize_app(credential, options, name):
        calls.append((credential, options, name))
        return app

    fake_firebase_admin.initialize_app = initialize_app
    monkeypatch.setitem(sys.modules, "firebase_admin", fake_firebase_admin)
    monkeypatch.setenv("GOOGLE_APPLICATION_CREDENTIALS", "/run/secrets/application_default_credentials.json")
    monkeypatch.setattr(
        auth_module,
        "get_settings",
        lambda: SimpleNamespace(firebase_project_id="tv-trading-f3be0", firebase_credentials_path=None),
    )
    auth_module._firebase_auth.cache_clear()

    try:
        returned_auth, returned_app = auth_module._firebase_auth()
    finally:
        auth_module._firebase_auth.cache_clear()

    assert returned_auth is fake_firebase_admin.auth
    assert returned_app is app
    assert calls == [(application_default, {"projectId": "tv-trading-f3be0"}, "neo-fabel-api")]


@pytest.mark.asyncio
async def test_require_user_verifies_firebase_bearer(monkeypatch):
    class FakeFirebaseAuth:
        @staticmethod
        def verify_id_token(token: str, *, check_revoked: bool, app: object):
            assert token == "google-firebase-id-token"
            # Without GOOGLE_APPLICATION_CREDENTIALS, revocation checks stay off.
            assert check_revoked is False
            assert app is not None
            return {
                "uid": "google-user",
                "email": "user@example.com",
                "email_verified": True,
                "firebase": {"sign_in_provider": "google.com"},
            }

    monkeypatch.setattr(auth_module, "_firebase_auth", lambda: (FakeFirebaseAuth, object()))
    user = await auth_module.require_user(_request("Bearer google-firebase-id-token"))
    assert user["uid"] == "google-user"


@pytest.mark.asyncio
async def test_require_user_rejects_non_google_firebase_provider(monkeypatch):
    class FakeFirebaseAuth:
        @staticmethod
        def verify_id_token(_token: str, **_kwargs):
            return {
                "uid": "password-user",
                "email_verified": True,
                "firebase": {"sign_in_provider": "password"},
            }

    monkeypatch.setattr(auth_module, "_firebase_auth", lambda: (FakeFirebaseAuth, object()))
    with pytest.raises(HTTPException) as caught:
        await auth_module.require_user(_request("Bearer firebase-id-token"))
    assert caught.value.status_code == 403
    assert caught.value.detail["code"] == "google_sign_in_required"


@pytest.mark.asyncio
async def test_require_user_rejects_missing_bearer():
    with pytest.raises(HTTPException) as caught:
        await auth_module.require_user(_request())
    assert caught.value.status_code == 401
    assert caught.value.detail["code"] == "auth_required"


@pytest.mark.asyncio
async def test_trading_admin_requires_claim_and_recent_google_login(monkeypatch):
    recent_user = {"uid": "operator", "trading_admin": True, "auth_time": int(time())}

    async def fake_require_user(_request: Request):
        return recent_user

    monkeypatch.setattr(auth_module, "require_user", fake_require_user)
    user = await auth_module.require_trading_admin_recent(_request("Bearer token"))
    assert user["uid"] == "operator"


@pytest.mark.asyncio
async def test_trading_admin_requires_claim_when_live_enabled(monkeypatch):
    async def fake_require_user(_request: Request):
        return {"uid": "regular-user", "auth_time": int(time())}

    monkeypatch.setattr(auth_module, "require_user", fake_require_user)
    settings = auth_module.get_settings()
    monkeypatch.setattr(settings, "kraken_live_trading_enabled", True)

    with pytest.raises(HTTPException) as caught:
        await auth_module.require_trading_admin(_request("Bearer token"))
    assert caught.value.status_code == 403
    assert caught.value.detail["code"] == "trading_admin_required"

@pytest.mark.asyncio
async def test_trading_admin_allows_paper_without_claim(monkeypatch):
    async def fake_require_user(_request: Request):
        return {"uid": "regular-user", "auth_time": int(time())}

    monkeypatch.setattr(auth_module, "require_user", fake_require_user)
    settings = auth_module.get_settings()
    monkeypatch.setattr(settings, "kraken_live_trading_enabled", False)

    user = await auth_module.require_trading_admin(_request("Bearer token"))
    assert user["uid"] == "regular-user"


@pytest.mark.asyncio
async def test_trading_admin_rejects_regular_firebase_user(monkeypatch):
    async def fake_require_user(_request: Request):
        return {"uid": "regular-user", "auth_time": int(time())}

    monkeypatch.setattr(auth_module, "require_user", fake_require_user)
    settings = auth_module.get_settings()
    monkeypatch.setattr(settings, "kraken_live_trading_enabled", True)

    with pytest.raises(HTTPException) as caught:
        await auth_module.require_trading_admin_recent(_request("Bearer token"))
    assert caught.value.status_code == 403
    assert caught.value.detail["code"] == "trading_admin_required"