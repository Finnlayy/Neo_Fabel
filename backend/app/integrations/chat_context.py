"""Chat history budget — trim agent pipeline messages before Gemini calls.

UI may keep a long display transcript; the wire protocol must not resend
multi-KB Pine/code dumps on every turn.
"""

from __future__ import annotations

from typing import Any


def _chars(messages: list[dict[str, Any]]) -> int:
    return sum(len(str(m.get("content") or "")) for m in messages)


def trim_chat_messages(
    messages: list[dict[str, Any]],
    *,
    max_messages: int = 12,
    max_chars: int = 12_000,
    max_content_chars: int = 4_000,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Return a wire-safe message window + trim metadata.

    Rules:
    - Drop role=system from the array (router supplies systemInstruction).
    - Cap each content blob (long assistant code dumps).
    - Keep the newest messages within max_messages / max_chars.
    - Always keep the latest user message if present.
    """
    cleaned: list[dict[str, Any]] = []
    for raw in messages:
        role = str(raw.get("role") or "user")
        if role == "system":
            continue
        content = str(raw.get("content") or "")
        if len(content) > max_content_chars:
            content = content[: max_content_chars - 32] + "\n…[truncated for token budget]"
        if role not in {"user", "assistant"}:
            role = "user"
        cleaned.append({"role": role, "content": content})

    original_count = len(messages)
    original_chars = _chars([{"content": str(m.get("content") or "")} for m in messages])

    window = cleaned[-max(1, max_messages) :]
    while len(window) > 1 and _chars(window) > max_chars:
        window = window[1:]

    # Prefer ending on a user turn so the model has a clear question.
    if window and window[-1].get("role") != "user":
        for i in range(len(window) - 1, -1, -1):
            if window[i].get("role") == "user":
                window = window[i:]
                break

    meta = {
        "input_messages": original_count,
        "input_chars": original_chars,
        "sent_messages": len(window),
        "sent_chars": _chars(window),
        "trimmed": original_count > len(window) or original_chars > _chars(window),
    }
    return window, meta
