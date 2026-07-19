from time import time

import pytest
from fastapi import HTTPException
from starlette.requests import Request

from backend.app import auth as auth_module


def _request(authorization: str | None = None) -> Request:
    headers = [] if authorization is None else [(b"authorization", authorization.encode("ascii"))]
    return Request({"type": "http", "method": "GET", "path": "/", "headers": headers})


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
async def test_trading_admin_rejects_regular_firebase_user(monkeypatch):
    async def fake_require_user(_request: Request):
        return {"uid": "regular-user", "auth_time": int(time())}

    monkeypatch.setattr(auth_module, "require_user", fake_require_user)
    with pytest.raises(HTTPException) as caught:
        await auth_module.require_trading_admin_recent(_request("Bearer token"))
    assert caught.value.status_code == 403
    assert caught.value.detail["code"] == "trading_admin_required"
