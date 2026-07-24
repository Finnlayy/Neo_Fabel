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

def test_command_env_injects_kraken_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("KRAKEN_API_KEY", raising=False)
    monkeypatch.delenv("KRAKEN_API_SECRET", raising=False)
    cli = KrakenCli(api_key="key123", api_secret="sec456")
    env = cli._command_env()
    assert env["KRAKEN_API_KEY"] == "key123"
    assert env["KRAKEN_API_SECRET"] == "sec456"


def test_command_env_does_not_override_existing_environ(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("KRAKEN_API_KEY", "from-os")
    monkeypatch.delenv("KRAKEN_API_SECRET", raising=False)
    cli = KrakenCli(api_key="from-settings", api_secret="sec")
    env = cli._command_env()
    assert env["KRAKEN_API_KEY"] == "from-os"
    assert env["KRAKEN_API_SECRET"] == "sec"


def test_command_env_sets_wslenv_on_windows(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("KRAKEN_API_KEY", raising=False)
    monkeypatch.delenv("KRAKEN_API_SECRET", raising=False)
    monkeypatch.setattr(kraken_module.os, "name", "nt")
    cli = KrakenCli(api_key="key123", api_secret="sec456")
    env = cli._command_env()
    assert "KRAKEN_API_KEY/u" in env.get("WSLENV", "")
    assert "KRAKEN_API_SECRET/u" in env.get("WSLENV", "")


def test_failure_message_prefers_kraken_json_message() -> None:
    payload = {
        "error": "auth",
        "message": "Authentication failed: No Spot API credentials found.",
    }
    assert "Authentication failed" in KrakenCli._failure_message(payload, b"")


@pytest.mark.asyncio
async def test_binary_must_be_kraken() -> None:
    cli = KrakenCli(binary="malicious_binary")

    with pytest.raises(KrakenCliError) as caught:
        await cli.ticker("BTCUSD")

    assert caught.value.category == "validation"
    assert "binary must be 'kraken'" in str(caught.value)
