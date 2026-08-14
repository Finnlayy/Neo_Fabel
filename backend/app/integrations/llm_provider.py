"""Minimal example: official Google GenAI SDK (`google-genai`) usage.

Status: standalone example / opt-in — not wired into the app's request path.
The app's actual Gemini integration is `gemini_client.py` (raw httpx REST,
routed through `llm_router.py` with multi-provider failover + budget tracking).
Use this module as a reference if you want to migrate to the official SDK,
or call `example_generate_text()` directly for a quick manual check.

Auth: reads GEMINI_API_KEY from the environment (same variable the rest of
the app already uses — see Settings.gemini_api_key in ../settings.py).
"""

from __future__ import annotations

import os


class LlmProviderNotConfigured(RuntimeError):
    """Raised when GEMINI_API_KEY is missing or empty."""


def _require_api_key() -> str:
    api_key = (os.environ.get("GEMINI_API_KEY") or "").strip()
    if not api_key:
        raise LlmProviderNotConfigured(
            "GEMINI_API_KEY is not set. Export it in your shell or set it in .env.local "
            "(see README section below for platform-specific commands)."
        )
    return api_key


def example_generate_text(prompt: str = "Say hello in one short sentence.") -> str:
    """One-shot text generation via the official SDK. Returns the reply text.

    Raises:
        LlmProviderNotConfigured: GEMINI_API_KEY missing (checked before the SDK call).
        ValueError: the SDK itself also validates the key shape / rejects an
            invalid key at request time — surfaced as-is, not swallowed.
        ModuleNotFoundError: `google-genai` isn't installed in the interpreter
            that's actually running this file — see troubleshooting below.
    """
    api_key = _require_api_key()

    try:
        from google import genai
    except ModuleNotFoundError as exc:
        raise ModuleNotFoundError(
            "No module named 'google' / 'google.genai'. This almost always means "
            "the package is installed in a different Python interpreter than the one "
            "running this process. Fix: activate the project's venv first, then "
            "`pip install google-genai` (or `pip install -e backend` after adding it "
            "to pyproject.toml), and confirm with `python -c \"import sys; print(sys.executable)\"` "
            "that it matches the interpreter you installed into."
        ) from exc

    client = genai.Client(api_key=api_key)
    try:
        response = client.models.generate_content(
            model="gemini-3.5-flash",
            contents=prompt,
        )
    except ValueError as exc:
        # The SDK raises ValueError for malformed/rejected credentials and
        # some invalid-argument cases — re-raise with the original context intact.
        raise ValueError(f"google-genai rejected the request (check GEMINI_API_KEY): {exc}") from exc

    return response.text or ""


if __name__ == "__main__":
    # Manual smoke test: `python -m backend.app.integrations.llm_provider`
    try:
        print(example_generate_text())
    except LlmProviderNotConfigured as exc:
        print(f"[config error] {exc}")
    except ModuleNotFoundError as exc:
        print(f"[import error] {exc}")
    except ValueError as exc:
        print(f"[api error] {exc}")
