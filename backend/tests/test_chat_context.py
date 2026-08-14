"""Chat wire-protocol trim budget."""

from __future__ import annotations

from backend.app.integrations.chat_context import trim_chat_messages


def test_trim_drops_system_and_keeps_recent_user() -> None:
    messages = [
        {"role": "system", "content": "ignore me"},
        {"role": "assistant", "content": "welcome"},
        {"role": "user", "content": "first"},
        {"role": "assistant", "content": "a" * 9000},
        {"role": "user", "content": "second question"},
    ]
    window, meta = trim_chat_messages(
        messages, max_messages=4, max_chars=5000, max_content_chars=500
    )
    assert all(m["role"] != "system" for m in window)
    assert window[-1]["content"] == "second question"
    assert meta["trimmed"] is True
    assert all(len(m["content"]) <= 500 + 40 for m in window)


def test_trim_respects_max_messages() -> None:
    messages = [{"role": "user", "content": f"u{i}"} for i in range(30)]
    window, meta = trim_chat_messages(messages, max_messages=8, max_chars=50_000)
    assert len(window) == 8
    assert window[0]["content"] == "u22"
    assert meta["sent_messages"] == 8
    assert meta["input_messages"] == 30


def test_trim_respects_max_chars_sliding_window() -> None:
    messages = [
        {"role": "user", "content": "x" * 400},
        {"role": "assistant", "content": "y" * 400},
        {"role": "user", "content": "latest"},
    ]
    window, meta = trim_chat_messages(
        messages, max_messages=12, max_chars=500, max_content_chars=10_000
    )
    assert window[-1]["content"] == "latest"
    assert meta["sent_chars"] <= 500
    assert meta["trimmed"] is True
