"""Operator secrets vault (App Settings integrations)."""

from __future__ import annotations

import os

import pytest

from backend.app.integrations import secrets_store as vault


@pytest.fixture()
def isolated_vault(tmp_path, monkeypatch):
    monkeypatch.setattr(vault, "DATA_DIR", tmp_path)
    monkeypatch.setattr(vault, "STORE_PATH", tmp_path / "integrations.json")
    yield tmp_path


def test_set_and_list_masks_secret(isolated_vault):
    vault.set_integration_value("KRAKEN_API_KEY", "supersecretkey1234")
    listing = vault.list_integrations()
    item = next(i for i in listing["items"] if i["key"] == "KRAKEN_API_KEY")
    assert item["configured"] is True
    assert item["masked"] == "••••1234"
    assert "supersecret" not in str(listing)


def test_apply_to_environ_and_reload(isolated_vault, monkeypatch):
    vault.set_integration_value("GEMINI_API_KEY", "gem-test-key-zzzz")
    os.environ.pop("GEMINI_API_KEY", None)
    n = vault.apply_secrets_to_environ()
    assert n >= 1
    assert os.environ.get("GEMINI_API_KEY") == "gem-test-key-zzzz"


def test_password_vault_crud(isolated_vault):
    row = vault.upsert_password(password_id=None, label="Kraken Login", secret="hunter2", username="finn")
    assert row["id"]
    assert row["masked"] == "••••ter2" or row["masked"].endswith("ter2")
    listed = vault.list_passwords(reveal=False)
    assert listed[0]["label"] == "Kraken Login"
    assert "hunter2" not in str(listed)
    revealed = vault.reveal_password(row["id"])
    assert revealed["secret"] == "hunter2"
    vault.delete_password(row["id"])
    assert vault.list_passwords() == []


def test_rejects_unknown_key(isolated_vault):
    with pytest.raises(ValueError):
        vault.set_integration_value("NOT_A_REAL_KEY", "x")


def test_public_api_base_not_secret_shows_value(isolated_vault):
    vault.set_integration_value("PUBLIC_API_BASE_URL", "https://lesa-ionospheric-affably.ngrok-free.dev")
    item = next(i for i in vault.list_integrations()["items"] if i["key"] == "PUBLIC_API_BASE_URL")
    assert item["secret"] is False
    assert item["masked"] == "https://lesa-ionospheric-affably.ngrok-free.dev"
