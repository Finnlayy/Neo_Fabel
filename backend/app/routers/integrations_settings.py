"""App Settings — integrations API keys + password vault."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from backend.app.auth import require_trading_admin_recent, require_user
from backend.app.integrations import secrets_store as vault

router = APIRouter(prefix="/api/v1/settings", tags=["settings"])


class IntegrationUpsert(BaseModel):
    model_config = ConfigDict(extra="forbid")

    value: str | None = Field(default=None, max_length=4096)


class PasswordUpsert(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str | None = Field(default=None, max_length=64)
    label: str = Field(min_length=1, max_length=80)
    username: str | None = Field(default=None, max_length=128)
    secret: str | None = Field(default=None, max_length=2048)
    notes: str | None = Field(default=None, max_length=500)


@router.get("/integrations")
async def get_integrations(_user: dict[str, Any] = Depends(require_user)) -> dict[str, Any]:
    return vault.list_integrations()


@router.put("/integrations/{key}")
async def put_integration(
    key: str,
    payload: IntegrationUpsert,
    _user: dict[str, Any] = Depends(require_trading_admin_recent),
) -> dict[str, Any]:
    try:
        result = vault.set_integration_value(key, payload.value)
        vault.reload_app_settings()
        return {"ok": True, **result}
    except ValueError as exc:
        raise HTTPException(status_code=422, detail={"code": "invalid_key", "message": str(exc)}) from exc


@router.delete("/integrations/{key}")
async def delete_integration(
    key: str,
    _user: dict[str, Any] = Depends(require_trading_admin_recent),
) -> dict[str, Any]:
    try:
        result = vault.set_integration_value(key, None)
        vault.reload_app_settings()
        return {"ok": True, **result}
    except ValueError as exc:
        raise HTTPException(status_code=422, detail={"code": "invalid_key", "message": str(exc)}) from exc


@router.get("/integrations/{key}/reveal")
async def reveal_integration(
    key: str,
    _user: dict[str, Any] = Depends(require_trading_admin_recent),
) -> dict[str, Any]:
    try:
        value = vault.reveal_integration(key)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail={"code": "invalid_key", "message": str(exc)}) from exc
    except KeyError:
        raise HTTPException(status_code=404, detail={"code": "not_configured", "message": "not set"}) from None
    return {"key": key.upper(), "value": value}


@router.get("/passwords")
async def get_passwords(_user: dict[str, Any] = Depends(require_user)) -> dict[str, Any]:
    return {"items": vault.list_passwords(reveal=False)}


@router.put("/passwords")
async def put_password(
    payload: PasswordUpsert,
    _user: dict[str, Any] = Depends(require_trading_admin_recent),
) -> dict[str, Any]:
    try:
        row = vault.upsert_password(
            password_id=payload.id,
            label=payload.label,
            secret=payload.secret,
            username=payload.username,
            notes=payload.notes,
        )
        return {"ok": True, "item": row}
    except KeyError:
        raise HTTPException(status_code=404, detail={"code": "not_found", "message": "password not found"}) from None
    except ValueError as exc:
        raise HTTPException(status_code=422, detail={"code": "invalid_password", "message": str(exc)}) from exc


@router.delete("/passwords/{password_id}")
async def delete_password(
    password_id: str,
    _user: dict[str, Any] = Depends(require_trading_admin_recent),
) -> dict[str, Any]:
    try:
        vault.delete_password(password_id)
    except KeyError:
        raise HTTPException(status_code=404, detail={"code": "not_found", "message": "password not found"}) from None
    return {"ok": True}


@router.get("/passwords/{password_id}/reveal")
async def reveal_password(
    password_id: str,
    _user: dict[str, Any] = Depends(require_trading_admin_recent),
) -> dict[str, Any]:
    try:
        return vault.reveal_password(password_id)
    except KeyError:
        raise HTTPException(status_code=404, detail={"code": "not_found", "message": "password not found"}) from None
