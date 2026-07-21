"""MCP paper bridge → LocalPaperLedger (paper-only).

Datei: test_mcp_paper_bridge.py
Zweck: TestClient-Nachweis fuer POST /api/v1/mcp/paper/fill.
Erstellt: 2026-07-21 | Version: 1.0
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from backend.app.integrations.local_paper import LocalPaperLedger, reset_local_paper_ledger_for_tests
from backend.app.integrations.paper_router import PaperExecutionRouter
from backend.app.main import app
from backend.app.settings import get_settings

client = TestClient(app)

_AUTH = {"Authorization": "Bearer test-bridge-token"}


@pytest.fixture
def isolated_bridge_ledger(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> LocalPaperLedger:
    reset_local_paper_ledger_for_tests()
    get_settings.cache_clear()
    monkeypatch.setenv("FABLE_MCP_BRIDGE_ENABLED", "true")
    monkeypatch.setenv("FABLE_MCP_BRIDGE_TOKEN", "test-bridge-token")
    monkeypatch.setenv("PAPER_LOCAL_LEDGER", "true")
    get_settings.cache_clear()

    ledger = LocalPaperLedger(_path=tmp_path / "ledger.json")

    async def _price(_market_type: str, pair: str) -> Decimal:
        return Decimal("0.50") if "ADA" in pair.upper() else Decimal("100")

    ledger.set_price_resolver(_price)

    def _build(_settings):  # type: ignore[no-untyped-def]
        cli = AsyncMock()
        return PaperExecutionRouter(cli=cli, ledger=ledger, prefer_local=True)

    monkeypatch.setattr("backend.app.routers.mcp_paper.build_paper_router", _build)
    yield ledger
    get_settings.cache_clear()
    reset_local_paper_ledger_for_tests()


def test_mcp_paper_fill_updates_ledger(isolated_bridge_ledger: LocalPaperLedger) -> None:
    res = client.post(
        "/api/v1/mcp/paper/fill",
        headers=_AUTH,
        json={
            "event": "entry",
            "side": "buy",
            "pair": "ADAUSD",
            "price": "0.50",
            "volume": "100",
            "rationale": "MCP bridge smoke - grid zone 2",
            "market_type": "spot",
            "source": "fable-mcp",
        },
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["ok"] is True
    assert body["mode"] == "paper"
    assert "grid zone" in body["rationale"]
    assert body["result"]["source"] == "local-paper-ledger"
    assert body["result"]["order"]["rationale"].startswith("MCP bridge")


def test_mcp_paper_fill_requires_token_when_configured(isolated_bridge_ledger: LocalPaperLedger) -> None:
    denied = client.post(
        "/api/v1/mcp/paper/fill",
        json={
            "event": "entry",
            "side": "buy",
            "pair": "ADAUSD",
            "price": "0.50",
            "volume": "10",
            "rationale": "no auth",
        },
    )
    assert denied.status_code == 401
    ok = client.post(
        "/api/v1/mcp/paper/fill",
        headers=_AUTH,
        json={
            "event": "entry",
            "side": "buy",
            "pair": "ADAUSD",
            "price": "0.50",
            "volume": "10",
            "rationale": "with auth",
        },
    )
    assert ok.status_code == 200, ok.text


def test_mcp_paper_fill_exit_maps_trade_side(isolated_bridge_ledger: LocalPaperLedger) -> None:
    client.post(
        "/api/v1/mcp/paper/fill",
        headers=_AUTH,
        json={
            "event": "entry",
            "side": "buy",
            "pair": "ADAUSD",
            "price": "0.50",
            "volume": "50",
            "rationale": "open long",
        },
    )
    res = client.post(
        "/api/v1/mcp/paper/fill",
        headers=_AUTH,
        json={
            "event": "stop_loss",
            "side": "buy",
            "pair": "ADAUSD",
            "price": "0.40",
            "volume": "50",
            "pnl": "-5",
            "rationale": "SL hit",
        },
    )
    assert res.status_code == 200, res.text
    assert res.json()["result"]["order"]["side"] == "sell"


def test_mcp_paper_bridge_default_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    get_settings.cache_clear()
    monkeypatch.delenv("FABLE_MCP_BRIDGE_ENABLED", raising=False)
    monkeypatch.delenv("FABLE_MCP_BRIDGE_TOKEN", raising=False)
    get_settings.cache_clear()
    settings = get_settings()
    assert settings.fable_mcp_bridge_enabled is False
