"""Append-only audit log for live trading decisions (place / reject / kill)."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from threading import Lock
from typing import Any

_LOCK = Lock()
_DEFAULT_PATH = Path(__file__).resolve().parents[2] / "data" / "trading" / "live_audit.jsonl"


def audit_path() -> Path:
    path = _DEFAULT_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def log_live_event(event: str, **fields: Any) -> None:
    record = {
        "ts": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "event": event,
        **{k: v for k, v in fields.items() if v is not None},
    }
    line = json.dumps(record, default=str)
    with _LOCK:
        with audit_path().open("a", encoding="utf-8") as fh:
            fh.write(line + "\n")
