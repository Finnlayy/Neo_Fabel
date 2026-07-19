from datetime import UTC, datetime
from functools import lru_cache
from typing import Any

from fastapi import HTTPException, Request
from starlette.concurrency import run_in_threadpool

from .settings import get_settings

_LOCAL_DEV_USER: dict[str, Any] = {
    "uid": "local-dev",
    "email": "local-dev@localhost",
    "email_verified": True,
    "name": "Local Dev",
    "firebase": {"sign_in_provider": "google.com"},
    "auth_time": int(datetime.now(UTC).timestamp()),
    "signal_admin": True,
}


def _is_loopback(request: Request) -> bool:
    host = (request.client.host if request.client else "") or ""
    if host in {"127.0.0.1", "::1", "localhost", "testclient"}:
        return True
    # Starlette TestClient / some proxies
    return host.startswith("127.") or host == "localhost"


def _dev_bypass_allowed(request: Request) -> bool:
    settings = get_settings()
    if settings.app_env.lower() not in {"development", "dev", "local", "test"}:
        return False
    if not settings.auth_dev_bypass:
        return False
    return _is_loopback(request)


@lru_cache(maxsize=1)
def _firebase_auth():
    settings = get_settings()
    if not settings.firebase_project_id:
        return None
    try:
        import firebase_admin
        from firebase_admin import auth, credentials
    except ImportError as exc:
        raise RuntimeError("firebase-admin is not installed") from exc

    app_name = "neo-fabel-api"
    try:
        firebase_app = firebase_admin.get_app(app_name)
    except ValueError:
        if settings.firebase_credentials_path:
            credential = credentials.Certificate(settings.firebase_credentials_path)
            firebase_app = firebase_admin.initialize_app(
                credential,
                {"projectId": settings.firebase_project_id},
                name=app_name,
            )
        else:
            firebase_app = firebase_admin.initialize_app(
                options={"projectId": settings.firebase_project_id},
                name=app_name,
            )
    return auth, firebase_app


async def require_user(request: Request) -> dict[str, Any]:
    authorization = request.headers.get("authorization", "")
    scheme, _, token = authorization.partition(" ")
    has_bearer = scheme.lower() == "bearer" and bool(token.strip())

    # Prefer a real Firebase token when the browser sent one.
    if has_bearer:
        return await _verify_firebase_token(token)

    # Local development without service-account chaos: unlock Telegram/paper/AI on loopback.
    if _dev_bypass_allowed(request):
        return dict(_LOCAL_DEV_USER)

    raise HTTPException(
        status_code=401,
        detail={"code": "auth_required", "message": "Bearer token required"},
        headers={"WWW-Authenticate": "Bearer"},
    )


async def _verify_firebase_token(token: str) -> dict[str, Any]:
    firebase_auth = None
    try:
        firebase_context = _firebase_auth()
        if firebase_context is None:
            raise HTTPException(
                status_code=503,
                detail={"code": "auth_unconfigured", "message": "Firebase Auth is not configured"},
            )
        firebase_auth, firebase_app = firebase_context
        settings = get_settings()
        check_revoked = bool(settings.firebase_credentials_path)
        user = await run_in_threadpool(
            firebase_auth.verify_id_token,
            token,
            check_revoked=check_revoked,
            app=firebase_app,
        )
        uid = str(user.get("uid", "")).strip()
        if not uid:
            raise ValueError("verified Firebase token is missing uid")
        firebase_claims = user.get("firebase") if isinstance(user.get("firebase"), dict) else {}
        if firebase_claims.get("sign_in_provider") != "google.com" or user.get("email_verified") is not True:
            raise HTTPException(
                status_code=403,
                detail={
                    "code": "google_sign_in_required",
                    "message": "A verified Google Firebase account is required",
                },
            )
        return user
    except HTTPException:
        raise
    except Exception as exc:
        invalid_names = (
            "InvalidIdTokenError",
            "ExpiredIdTokenError",
            "RevokedIdTokenError",
            "UserDisabledError",
            "UserNotFoundError",
            "CertificateFetchError",
        )
        invalid_types = tuple(
            error_type
            for name in invalid_names
            if isinstance((error_type := getattr(firebase_auth, name, None)), type)
        )
        if isinstance(exc, (ValueError, *invalid_types)):
            raise HTTPException(
                status_code=401,
                detail={"code": "auth_invalid", "message": "Invalid Firebase ID token"},
                headers={"WWW-Authenticate": "Bearer"},
            ) from exc
        raise HTTPException(
            status_code=503,
            detail={"code": "auth_unavailable", "message": f"Firebase token verification is unavailable: {exc}"},
        ) from exc


def _has_signal_admin_claim(user: dict[str, Any]) -> bool:
    return _has_custom_claim(user, "signal_admin")


def _has_custom_claim(user: dict[str, Any], claim: str) -> bool:
    if user.get(claim) is True:
        return True
    raw_claims = user.get("claims")
    claims: dict[str, Any] = raw_claims if isinstance(raw_claims, dict) else {}
    if claims.get(claim) is True:
        return True
    return False


def _auth_time_recent(user: dict[str, Any], max_age_seconds: int) -> bool:
    if user.get("uid") == "local-dev":
        return True
    auth_time = user.get("auth_time")
    if auth_time is None:
        return False
    try:
        stamped = datetime.fromtimestamp(int(auth_time), tz=UTC)
    except (TypeError, ValueError, OSError):
        return False
    age = (datetime.now(UTC) - stamped).total_seconds()
    return 0 <= age <= max_age_seconds


async def require_signal_admin(request: Request) -> dict[str, Any]:
    """Firebase bearer + signal_admin custom claim. Does not weaken require_user."""
    user = await require_user(request)
    if not _has_signal_admin_claim(user):
        raise HTTPException(
            status_code=403,
            detail={"code": "signal_admin_required", "message": "signal_admin claim required"},
        )
    return user


async def require_signal_admin_recent(request: Request) -> dict[str, Any]:
    """Recent re-auth required for credential rotation or Bypass switches."""
    user = await require_signal_admin(request)
    settings = get_settings()
    if not _auth_time_recent(user, settings.signal_recent_auth_seconds):
        raise HTTPException(
            status_code=401,
            detail={
                "code": "recent_auth_required",
                "message": "re-authenticate to perform this action",
            },
        )
    return user


async def require_trading_admin_recent(request: Request) -> dict[str, Any]:
    """Recent Firebase sign-in plus a dedicated live-safety operator claim."""
    user = await require_trading_admin(request)
    settings = get_settings()
    if not _auth_time_recent(user, settings.signal_recent_auth_seconds):
        raise HTTPException(
            status_code=401,
            detail={"code": "recent_auth_required", "message": "re-authenticate to perform this action"},
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


async def require_trading_admin(request: Request) -> dict[str, Any]:
    """Verified Google Firebase user with the private Kraken operator claim."""
    user = await require_user(request)
    if not _has_custom_claim(user, "trading_admin"):
        raise HTTPException(
            status_code=403,
            detail={"code": "trading_admin_required", "message": "trading_admin claim required"},
        )
    return user


def ownership_or_404(user: dict[str, Any], owner_uid: str) -> None:
    """Non-enumerating ownership check — same response for missing/cross-owner."""
    if str(user.get("uid", "")) != owner_uid:
        raise HTTPException(status_code=404, detail={"code": "not_found", "message": "resource not found"})
