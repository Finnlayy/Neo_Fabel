import pytest

from backend.app.integrations import kraken_cli as kraken_module
from backend.app.integrations.kraken_cli import KrakenCli, KrakenCliError


@pytest.mark.asyncio
async def test_permission_error_is_wrapped_for_public_rest_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    async def deny_process_creation(*_args: object, **_kwargs: object) -> None:
        raise PermissionError(5, "process creation denied")

    monkeypatch.setattr(kraken_module.asyncio, "create_subprocess_exec", deny_process_creation)

    with pytest.raises(KrakenCliError) as caught:
        await KrakenCli().ticker("BTCUSD")

    assert caught.value.category == "config"
    assert "fallback" in str(caught.value)
