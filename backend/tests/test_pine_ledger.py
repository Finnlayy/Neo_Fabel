"""Pine ledger + tvremix client gap wrappers (unit, no live MCP)."""

from __future__ import annotations

import pytest

from backend.app.integrations import pine_ledger


@pytest.fixture()
def isolated_ledger(tmp_path, monkeypatch):
    monkeypatch.setattr(pine_ledger, "LEDGER_PATH", tmp_path / "script_ledger.json")
    yield tmp_path


def test_ledger_detects_change(isolated_ledger):
    a = pine_ledger.upsert_script_snapshot(script_id="s1", name="Fable", source="//@version=5\na=1")
    assert a["sha256"]
    d1 = pine_ledger.diff_against_ledger("s1", "//@version=5\na=1")
    assert d1["changed"] is False
    d2 = pine_ledger.diff_against_ledger("s1", "//@version=5\na=2")
    assert d2["changed"] is True
    assert d2["status"] == "changed"


def test_read_pine_lines_slice_fallback(monkeypatch):
    import asyncio

    from backend.app.integrations.tvremix_client import TvremixClient, TvremixError

    client = TvremixClient.__new__(TvremixClient)
    client.settings = None  # type: ignore[assignment]
    client.api_key = "x"
    client._tool_names = set()
    client._session_id = None
    client._rpc_id = 0

    async def boom(*_a, **_k):
        raise TvremixError("no native")

    async def fake_read(script_id, *, name=None):
        return {
            "id": script_id,
            "name": name or script_id,
            "source": "\n".join(f"line{i}" for i in range(1, 11)),
            "tool": "pine_read_script",
        }

    monkeypatch.setattr(client, "call_tool", boom)
    monkeypatch.setattr(client, "read_pine_script", fake_read)

    out = asyncio.run(client.read_pine_lines("abc", start_line=3, end_line=5, name="t"))
    assert "line3" in out["source"]
    assert "line5" in out["source"]
    assert "line2" not in out["source"]
