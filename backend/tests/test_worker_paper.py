"""Signal worker paper execution adapter."""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.app.signals.executor import PaperOrderExecutionAdapter


@pytest.mark.asyncio
async def test_execution_adapter_forwards_market_type_and_leverage() -> None:
    service = MagicMock()
    service.place_signal = AsyncMock(return_value={"status": "ACCEPTED", "result": {"ok": True}})
    adapter = PaperOrderExecutionAdapter(service=service, default_market="spot")
    session = MagicMock()

    await adapter.submit_paper(
        session=session,
        user_uid="local-dev",
        event_id="evt-1",
        pair="BTCUSD",
        side="buy",
        volume=Decimal("0.001"),
        order_type="market",
        price=None,
        request_id="req-1",
        market_type="futures",
        leverage=5,
    )

    service.place_signal.assert_awaited_once()
    kwargs = service.place_signal.await_args.kwargs
    assert kwargs["market_type"] == "futures"
    assert kwargs["leverage"] == 5
