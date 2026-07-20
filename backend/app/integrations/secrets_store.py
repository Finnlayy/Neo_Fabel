"""Operator secrets vault — API keys + passwords for App Settings.

Stored under backend/data/secrets/integrations.json (gitignored).
Values are applied into os.environ so pydantic Settings picks them up after reload.
Plaintext never returned by list endpoints — only configured + masked hints.
"""

from __future__ import annotations

import json
import os
import re
import threading
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

DATA_DIR = Path(__file__).resolve().parents[2] / "data" / "secrets"
STORE_PATH = DATA_DIR / "integrations.json"
_lock = threading.RLock()

# Editable integration env keys (label, group, secret?).
INTEGRATION_CATALOG: tuple[dict[str, str | bool], ...] = (
    {"key": "PUBLIC_API_BASE_URL", "label": "Public API base (ngrok)", "group": "webhook", "secret": False},
    {"key": "KRAKEN_API_KEY", "label": "Kraken API key", "group": "kraken", "secret": True},
    {"key": "KRAKEN_API_SECRET", "label": "Kraken API secret", "group": "kraken", "secret": True},
    {"key": "PIONEX_API_KEY", "label": "Pionex API key", "group": "pionex", "secret": True},
    {"key": "PIONEX_API_SECRET", "label": "Pionex API secret", "group": "pionex", "secret": True},
    {"key": "PIONEX_SIGNAL_WEBHOOK_TOKEN", "label": "Pionex webhook token", "group": "pionex", "secret": True},
    {"key": "BYBIT_API_KEY", "label": "Bybit API key", "group": "bybit", "secret": True},
    {"key": "BYBIT_API_SECRET", "label": "Bybit API secret", "group": "bybit", "secret": True},
    {"key": "ALPHAVANTAGE_API_KEY", "label": "Alpha Vantage API key", "group": "market", "secret": True},
    {"key": "FINNHUB_API_KEY", "label": "Finnhub API key", "group": "market", "secret": True},
    {"key": "GEMINI_API_KEY", "label": "Gemini API key", "group": "ai", "secret": True},
    {"key": "OPENROUTER_API_KEY", "label": "OpenRouter API key", "group": "ai", "secret": True},
    {"key": "GROQ_API_KEY", "label": "Groq API key", "group": "ai", "secret": True},
    {"key": "CEREBRAS_API_KEY", "label": "Cerebras API key", "group": "ai", "secret": True},
    {"key": "AIPRIMETECH_API_KEY", "label": "AIPrimeTech / OpenAI key", "group": "ai", "secret": True},
    {"key": "XAI_API_KEY", "label": "xAI API key", "group": "ai", "secret": True},
    {"key": "TELEGRAM_BOT_TOKEN", "label": "Telegram bot token", "group": "telegram", "secret": True},
    {"key": "TVREMIX_API_KEY", "label": "tvremix API key", "group": "tradingview", "secret": True},
    {"key": "TRADINGVIEW_RAPIDAPI_KEY", "label": "TradingView RapidAPI key", "group": "tradingview", "secret": True},
    {"key": "QDRANT_API_KEY", "label": "Qdrant API key", "group": "infra", "secret": True},
    {"key": "SIGNAL_CREDENTIAL_PEPPER", "label": "Signal credential pepper", "group": "signals", "secret": True},
)

_ALLOWED_KEYS = frozenset(str(item["key"]) for item in INTEGRATION_CATALOG)
_KEY_RE = re.compile(r"^[A-Z][A-Z0-9_]{1,64}$")
_LABEL_RE = re.compile(r"^[\w .@#/\-]{1,80}$", re.UNICODE)


def _now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _empty_store() -> dict[str, Any]:
    return {"version": 1, "updated_at": None, "env": {}, "passwords": []}


def _read_unlocked() -> dict[str, Any]:
    if not STORE_PATH.exists():
        return _empty_store()
    try:
        data = json.loads(STORE_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return _empty_store()
    if not isinstance(data, dict):
        return _empty_store()
    env = data.get("env") if isinstance(data.get("env"), dict) else {}
    passwords = data.get("passwords") if isinstance(data.get("passwords"), list) else []
    return {
        "version": int(data.get("version") or 1),
        "updated_at": data.get("updated_at"),
        "env": {str(k): str(v) for k, v in env.items() if v is not None and str(v) != ""},
        "passwords": [p for p in passwords if isinstance(p, dict)],
    }


def _write_unlocked(data: dict[str, Any]) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    data = {**data, "updated_at": _now()}
    tmp = STORE_PATH.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
    tmp.replace(STORE_PATH)
    try:
        os.chmod(STORE_PATH, 0o600)
    except OSError:
        pass


def load_store() -> dict[str, Any]:
    with _lock:
        return _read_unlocked()


def apply_secrets_to_environ(*, overwrite_existing: bool = True) -> int:
    """Push vault env entries into os.environ. Returns count applied."""
    store = load_store()
    applied = 0
    with _lock:
        for key, value in (store.get("env") or {}).items():
            if key not in _ALLOWED_KEYS:
                continue
            text = str(value).strip()
            if not text:
                continue
            if not overwrite_existing and os.environ.get(key):
                continue
            os.environ[key] = text
            applied += 1
    return applied


def mask_secret(value: str | None) -> str | None:
    if not value:
        return None
    if len(value) <= 4:
        return "••••"
    return f"••••{value[-4:]}"


def effective_value(key: str) -> str | None:
    """Vault wins over process env for catalog keys when set."""
    store = load_store()
    env = store.get("env") or {}
    if key in env and str(env[key]).strip():
        return str(env[key]).strip()
    raw = os.environ.get(key)
    return raw.strip() if raw and raw.strip() else None


def list_integrations() -> dict[str, Any]:
    items = []
    for meta in INTEGRATION_CATALOG:
        key = str(meta["key"])
        value = effective_value(key)
        source = "vault" if key in (load_store().get("env") or {}) else ("env" if value else None)
        items.append(
            {
                "key": key,
                "label": meta["label"],
                "group": meta["group"],
                "secret": bool(meta["secret"]),
                "configured": bool(value),
                "masked": mask_secret(value) if value and meta["secret"] else (value if value and not meta["secret"] else None),
                "source": source,
            }
        )
    store = load_store()
    return {
        "updated_at": store.get("updated_at"),
        "store_path": str(STORE_PATH.as_posix()),
        "items": items,
        "password_count": len(store.get("passwords") or []),
    }


def set_integration_value(key: str, value: str | None) -> dict[str, Any]:
    key = key.strip().upper()
    if key not in _ALLOWED_KEYS or not _KEY_RE.match(key):
        raise ValueError(f"key not allowed: {key}")
    with _lock:
        store = _read_unlocked()
        env = dict(store.get("env") or {})
        if value is None or str(value).strip() == "":
            env.pop(key, None)
            os.environ.pop(key, None)
        else:
            text = str(value).strip()
            if len(text) > 4096:
                raise ValueError("value too long")
            env[key] = text
            os.environ[key] = text
        store["env"] = env
        _write_unlocked(store)
    return {"key": key, "configured": bool(value and str(value).strip()), "masked": mask_secret(value)}


def reveal_integration(key: str) -> str:
    key = key.strip().upper()
    if key not in _ALLOWED_KEYS:
        raise ValueError("key not allowed")
    value = effective_value(key)
    if not value:
        raise KeyError(key)
    return value


def list_passwords(*, reveal: bool = False) -> list[dict[str, Any]]:
    store = load_store()
    out = []
    for row in store.get("passwords") or []:
        secret = str(row.get("secret") or "")
        item = {
            "id": row.get("id"),
            "label": row.get("label"),
            "username": row.get("username") or None,
            "notes": row.get("notes") or None,
            "updated_at": row.get("updated_at"),
            "configured": bool(secret),
            "masked": mask_secret(secret),
        }
        if reveal:
            item["secret"] = secret
        out.append(item)
    return out


def upsert_password(
    *,
    password_id: str | None,
    label: str,
    secret: str | None,
    username: str | None = None,
    notes: str | None = None,
) -> dict[str, Any]:
    label = (label or "").strip()
    if not label or not _LABEL_RE.match(label):
        raise ValueError("invalid label")
    with _lock:
        store = _read_unlocked()
        rows: list[dict[str, Any]] = list(store.get("passwords") or [])
        if password_id:
            found = None
            for row in rows:
                if row.get("id") == password_id:
                    found = row
                    break
            if found is None:
                raise KeyError(password_id)
            found["label"] = label
            found["username"] = (username or "").strip() or None
            found["notes"] = (notes or "").strip() or None
            if secret is not None and str(secret).strip() != "":
                found["secret"] = str(secret).strip()
            found["updated_at"] = _now()
            row_out = found
        else:
            if secret is None or str(secret).strip() == "":
                raise ValueError("secret required for new password")
            row_out = {
                "id": str(uuid4()),
                "label": label,
                "username": (username or "").strip() or None,
                "notes": (notes or "").strip() or None,
                "secret": str(secret).strip(),
                "updated_at": _now(),
            }
            rows.append(row_out)
        if len(rows) > 200:
            raise ValueError("password vault full (max 200)")
        store["passwords"] = rows
        _write_unlocked(store)
    return {
        "id": row_out["id"],
        "label": row_out["label"],
        "username": row_out.get("username"),
        "notes": row_out.get("notes"),
        "updated_at": row_out.get("updated_at"),
        "configured": True,
        "masked": mask_secret(str(row_out.get("secret") or "")),
    }


def delete_password(password_id: str) -> None:
    with _lock:
        store = _read_unlocked()
        rows = [r for r in (store.get("passwords") or []) if r.get("id") != password_id]
        if len(rows) == len(store.get("passwords") or []):
            raise KeyError(password_id)
        store["passwords"] = rows
        _write_unlocked(store)


def reveal_password(password_id: str) -> dict[str, Any]:
    for row in load_store().get("passwords") or []:
        if row.get("id") == password_id:
            return {
                "id": row.get("id"),
                "label": row.get("label"),
                "username": row.get("username"),
                "notes": row.get("notes"),
                "secret": row.get("secret"),
                "updated_at": row.get("updated_at"),
            }
    raise KeyError(password_id)


def reload_app_settings() -> None:
    """Re-apply vault → environ and clear Settings cache."""
    apply_secrets_to_environ(overwrite_existing=True)
    from backend.app.settings import get_settings, get_trade_rate_limiter

    get_settings.cache_clear()
    get_trade_rate_limiter.cache_clear()
    get_settings()
