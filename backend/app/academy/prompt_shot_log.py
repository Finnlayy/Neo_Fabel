"""Append-only JSONL log for orchestrator prompt-shot usage."""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from backend.app.academy.paths import ACADEMY_DATA_DIR, ensure_academy_data_dir

PROMPT_SHOT_LOG_FILE = ACADEMY_DATA_DIR / "prompt_shot_log.jsonl"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def append_prompt_shot_event(event: dict[str, Any]) -> Path:
    ensure_academy_data_dir()
    row = {"ts": _utc_now(), **event}
    with open(PROMPT_SHOT_LOG_FILE, "a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    return PROMPT_SHOT_LOG_FILE


async def append_prompt_shot_event_async(event: dict[str, Any]) -> Path:
    return await asyncio.to_thread(append_prompt_shot_event, event)


def read_recent_events(limit: int = 50) -> list[dict[str, Any]]:
    if not PROMPT_SHOT_LOG_FILE.exists():
        return []
    lines = PROMPT_SHOT_LOG_FILE.read_text(encoding="utf-8").splitlines()
    rows: list[dict[str, Any]] = []
    for line in lines[-max(1, limit) :]:
        try:
            data = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(data, dict):
            rows.append(data)
    return rows
