"""Build OpenCode (https://opencode.ai) provider config from server settings."""

from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path
from typing import Any

from ..settings import Settings, get_settings
from .aiprimetech_catalog import AIPRIMETECH_BASE_URL, AIPRIMETECH_MODELS

logger = logging.getLogger(__name__)

OPENCODE_SCHEMA = "https://opencode.ai/config.json"


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _model_to_opencode(meta: dict[str, Any]) -> dict[str, Any]:
    variants = meta.get("variants") or ()
    return {
        "name": meta["name"],
        "limit": {"context": meta["context"], "output": meta["output"]},
        "options": {"store": False},
        "variants": {variant: {} for variant in variants},
    }


def build_opencode_config(
    settings: Settings,
    *,
    include_api_key: bool = True,
) -> dict[str, Any]:
    """Return OpenCode-shaped JSON; apiKey omitted unless include_api_key and key is set."""
    base_url = (settings.aiprimetech_base_url or AIPRIMETECH_BASE_URL).rstrip("/")
    provider_options: dict[str, Any] = {"baseURL": base_url}
    if include_api_key and settings.aiprimetech_api_key:
        provider_options["apiKey"] = settings.aiprimetech_api_key

    models = {mid: _model_to_opencode(meta) for mid, meta in AIPRIMETECH_MODELS.items()}
    return {
        "$schema": OPENCODE_SCHEMA,
        "provider": {
            "openai": {
                "options": provider_options,
                "models": models,
            }
        },
        "agent": {
            "build": {"options": {"store": False}},
            "plan": {"options": {"store": False}},
        },
    }


def resolve_opencode_path(settings: Settings) -> Path:
    raw = (settings.opencode_config_path or "opencode.json").strip()
    path = Path(raw)
    if path.is_absolute():
        return path
    return _repo_root() / path


def write_opencode_config(settings: Settings | None = None) -> Path | None:
    """Write opencode.json when AIPrimeTech is configured. Returns path or None if skipped."""
    cfg = settings or get_settings()
    if not cfg.aiprimetech_api_key:
        logger.info("opencode config write skipped: AIPRIMETECH_API_KEY not set")
        return None
    path = resolve_opencode_path(cfg)
    payload = build_opencode_config(cfg, include_api_key=True)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    logger.info("wrote opencode config to %s", path)
    return path


def _main() -> None:
    parser = argparse.ArgumentParser(description="Write OpenCode config from server env")
    parser.add_argument(
        "--write",
        action="store_true",
        help="Write opencode.json (default path from OPENCODE_CONFIG_PATH or repo root)",
    )
    parser.add_argument(
        "--stdout",
        action="store_true",
        help="Print config JSON to stdout (apiKey redacted unless --include-key)",
    )
    parser.add_argument(
        "--include-key",
        action="store_true",
        help="Include apiKey in stdout output",
    )
    args = parser.parse_args()
    settings = get_settings()
    if args.write:
        path = write_opencode_config(settings)
        if path is None:
            raise SystemExit("No AIPRIMETECH_API_KEY — set it in .env.local first")
        print(path)
        return
    if args.stdout:
        payload = build_opencode_config(settings, include_api_key=args.include_key)
        print(json.dumps(payload, indent=2))
        return
    parser.print_help()


if __name__ == "__main__":
    _main()
