"""Kraken status catalog memory + trade gates."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from backend.app.integrations.kraken_status import (
    assert_safe_to_trade_pair,
    load_index,
    save_summary,
)
from backend.app.trading.guardrails import GuardrailViolation

DATA = Path(__file__).resolve().parents[1] / "data" / "kraken"


def test_catalog_files_exist_and_populated():
    components = DATA / "status_components.json"
    index = DATA / "status_index.json"
    assert components.exists(), "status_components.json must be committed as agent/server memory"
    assert index.exists()
    catalog = json.loads(components.read_text(encoding="utf-8"))
    assert catalog.get("component_count", 0) >= 800
    assert isinstance(catalog.get("components"), list)
    assert len(catalog["components"]) >= 800
    names = {c["name"] for c in catalog["components"] if isinstance(c, dict)}
    assert "Cardano (ADA)" in names
    assert "XRP (XRP)" in names
    assert "REST API" in names


def test_load_index_has_by_name():
    idx = load_index()
    assert idx.get("by_name")
    assert idx["by_name"].get("Cardano (ADA)") == "operational" or idx["by_name"].get("Cardano (ADA)")


def test_ada_xrp_allowed_when_operational(tmp_path, monkeypatch):
    summary = {
        "status": {"indicator": "minor", "description": "Partially Degraded Service"},
        "components": [
            {"id": "1", "name": "REST API", "status": "operational", "group": False},
            {"id": "2", "name": "Websocket API", "status": "operational", "group": False},
            {"id": "3", "name": "Kraken API", "status": "operational", "group": False},
            {"id": "4", "name": "Cardano (ADA)", "status": "operational", "group": False},
            {"id": "5", "name": "XRP (XRP)", "status": "operational", "group": False},
            {"id": "6", "name": "Digital Currency Funding", "status": "degraded_performance", "group": False},
        ],
        "incidents": [],
    }
    monkeypatch.setattr(
        "backend.app.integrations.kraken_status.DATA_DIR",
        tmp_path,
    )
    monkeypatch.setattr(
        "backend.app.integrations.kraken_status.COMPONENTS_PATH",
        tmp_path / "status_components.json",
    )
    monkeypatch.setattr(
        "backend.app.integrations.kraken_status.INDEX_PATH",
        tmp_path / "status_index.json",
    )
    save_summary(summary)
    assert_safe_to_trade_pair("ADAUSD")
    assert_safe_to_trade_pair("XRPUSD")


def test_blocks_when_asset_degraded(tmp_path, monkeypatch):
    summary = {
        "status": {"indicator": "minor", "description": "degraded"},
        "components": [
            {"id": "1", "name": "REST API", "status": "operational", "group": False},
            {"id": "2", "name": "Websocket API", "status": "operational", "group": False},
            {"id": "3", "name": "Kraken API", "status": "operational", "group": False},
            {"id": "4", "name": "Cardano (ADA)", "status": "degraded_performance", "group": False},
            {"id": "5", "name": "XRP (XRP)", "status": "operational", "group": False},
        ],
        "incidents": [],
    }
    monkeypatch.setattr("backend.app.integrations.kraken_status.DATA_DIR", tmp_path)
    monkeypatch.setattr(
        "backend.app.integrations.kraken_status.COMPONENTS_PATH",
        tmp_path / "status_components.json",
    )
    monkeypatch.setattr(
        "backend.app.integrations.kraken_status.INDEX_PATH",
        tmp_path / "status_index.json",
    )
    save_summary(summary)
    with pytest.raises(GuardrailViolation) as exc:
        assert_safe_to_trade_pair("ADAUSD")
    assert exc.value.code == "kraken_status_asset"


def test_blocks_when_rest_api_down(tmp_path, monkeypatch):
    summary = {
        "status": {"indicator": "major", "description": "outage"},
        "components": [
            {"id": "1", "name": "REST API", "status": "major_outage", "group": False},
            {"id": "2", "name": "Websocket API", "status": "operational", "group": False},
            {"id": "3", "name": "Kraken API", "status": "operational", "group": False},
            {"id": "4", "name": "Cardano (ADA)", "status": "operational", "group": False},
        ],
        "incidents": [],
    }
    monkeypatch.setattr("backend.app.integrations.kraken_status.DATA_DIR", tmp_path)
    monkeypatch.setattr(
        "backend.app.integrations.kraken_status.COMPONENTS_PATH",
        tmp_path / "status_components.json",
    )
    monkeypatch.setattr(
        "backend.app.integrations.kraken_status.INDEX_PATH",
        tmp_path / "status_index.json",
    )
    save_summary(summary)
    with pytest.raises(GuardrailViolation) as exc:
        assert_safe_to_trade_pair("ADAUSD")
    assert exc.value.code == "kraken_status_api"
