"""Kraken status catalog — durable memory for safe exchange interaction.

Source of truth snapshot: backend/data/kraken/status_components.json
Refresh: GET https://status.kraken.com/api/v2/summary.json
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx

from backend.app.trading.guardrails import GuardrailViolation

logger = logging.getLogger("neo_fabel.kraken_status")

DATA_DIR = Path(__file__).resolve().parents[2] / "data" / "kraken"
COMPONENTS_PATH = DATA_DIR / "status_components.json"
INDEX_PATH = DATA_DIR / "status_index.json"
SUMMARY_URL = "https://status.kraken.com/api/v2/summary.json"

# Map Neo Fabel pairs → status component names (exact or "Name - …" variants).
# Fiat deposit rails (SEPA/Wire) are intentionally excluded — they do not block spot.
PAIR_STATUS_HINTS: dict[str, tuple[str, ...]] = {
    "ADAUSD": ("Cardano (ADA)",),
    "ADAEUR": ("Cardano (ADA)",),
    "XRPUSD": ("XRP (XRP)",),
    "XRPEUR": ("XRP (XRP)",),
}

API_COMPONENT_NAMES = (
    "REST API",
    "Websocket API",
    "Kraken API",
    "REST",
    "Websocket",
)


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning("kraken status load failed %s: %s", path, exc)
        return {}


def load_catalog() -> dict[str, Any]:
    return _load_json(COMPONENTS_PATH)


def load_index() -> dict[str, Any]:
    idx = _load_json(INDEX_PATH)
    if idx:
        return idx
    catalog = load_catalog()
    if not catalog:
        return {}
    return {
        "fetched_at": catalog.get("fetched_at"),
        "indicator": (catalog.get("page_status") or {}).get("indicator"),
        "description": (catalog.get("page_status") or {}).get("description"),
        "by_name": {
            c["name"]: c["status"]
            for c in catalog.get("components") or []
            if isinstance(c, dict) and c.get("name")
        },
        "non_operational": catalog.get("non_operational") or [],
        "incidents": catalog.get("incidents") or [],
    }


def save_summary(summary: dict[str, Any]) -> dict[str, Any]:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    comps = []
    for c in summary.get("components") or []:
        if not isinstance(c, dict):
            continue
        comps.append(
            {
                "id": c.get("id"),
                "name": c.get("name"),
                "status": c.get("status"),
                "group": c.get("group"),
                "description": c.get("description"),
            }
        )
    comps = sorted(comps, key=lambda x: (x.get("name") or "").lower())
    status_page = summary.get("status") or {}
    incidents = []
    for inc in summary.get("incidents") or []:
        if not isinstance(inc, dict):
            continue
        incidents.append(
            {
                "id": inc.get("id"),
                "name": inc.get("name"),
                "status": inc.get("status"),
                "impact": inc.get("impact"),
                "updated_at": inc.get("updated_at"),
                "shortlink": inc.get("shortlink"),
            }
        )
    non_op = [c for c in comps if (c.get("status") or "") != "operational"]
    fetched_at = datetime.now(UTC).isoformat().replace("+00:00", "Z")
    catalog = {
        "source": SUMMARY_URL,
        "status_page": "https://status.kraken.com",
        "fetched_at": fetched_at,
        "page_status": status_page,
        "component_count": len(comps),
        "non_operational": non_op,
        "incidents": incidents,
        "components": comps,
        "safe_trading_policy": {
            "block_if_api_not_operational": True,
            "block_asset_if_component_degraded": True,
            "never_deposit_withdraw_via_bot": True,
            "prefer_pairs": ["ADAUSD", "ADAEUR", "XRPUSD", "XRPEUR"],
        },
    }
    COMPONENTS_PATH.write_text(json.dumps(catalog, indent=2), encoding="utf-8")
    index = {
        "fetched_at": fetched_at,
        "indicator": status_page.get("indicator"),
        "description": status_page.get("description"),
        "by_name": {c["name"]: c["status"] for c in comps if c.get("name")},
        "non_operational": non_op,
        "incidents": incidents,
    }
    INDEX_PATH.write_text(json.dumps(index, indent=2), encoding="utf-8")
    return catalog


async def refresh_from_statuspage(*, timeout: float = 20.0) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=timeout) as client:
        response = await client.get(SUMMARY_URL)
        response.raise_for_status()
        return save_summary(response.json())


def _is_bad_status(status: str | None) -> bool:
    s = (status or "").lower().replace(" ", "_")
    return s in {
        "degraded_performance",
        "partial_outage",
        "major_outage",
        "under_maintenance",
    }


def assert_safe_to_trade_pair(pair: str, *, index: dict[str, Any] | None = None) -> None:
    """Raise GuardrailViolation if status memory says API or asset rails are unhealthy."""
    idx = index if index is not None else load_index()
    by_name: dict[str, str] = idx.get("by_name") or {}
    if not by_name:
        # No catalog yet — do not hard-fail; caller may refresh.
        return

    for api_name in API_COMPONENT_NAMES:
        st = by_name.get(api_name)
        if st and _is_bad_status(st):
            raise GuardrailViolation(
                "kraken_status_api",
                f"Kraken status component {api_name!r} is {st} — refuse live trade",
            )

    normalized = pair.strip().upper().replace("/", "").replace("-", "")
    hints = PAIR_STATUS_HINTS.get(normalized, ())
    for name, st in by_name.items():
        if not _is_bad_status(st):
            continue
        # Funding / deposit rails never block spot API trades
        if name == "Digital Currency Funding":
            continue
        if hints and any(_component_matches_hint(name, h) for h in hints):
            raise GuardrailViolation(
                "kraken_status_asset",
                f"Kraken status {name!r} is {st} — refuse {normalized}",
            )


def _component_matches_hint(name: str, hint: str) -> bool:
    n = name.strip().lower()
    h = hint.strip().lower()
    return n == h or n.startswith(f"{h} -")
