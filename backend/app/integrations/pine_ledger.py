"""Pine script content ledger — hash snapshots for change detection (MCP phase 9)."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

LEDGER_PATH = Path(__file__).resolve().parents[2] / "data" / "pine" / "script_ledger.json"


def _now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def content_hash(source: str) -> str:
    return hashlib.sha256(source.encode("utf-8")).hexdigest()


def load_ledger() -> dict[str, Any]:
    if not LEDGER_PATH.exists():
        return {"version": 1, "scripts": {}}
    try:
        data = json.loads(LEDGER_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"version": 1, "scripts": {}}
    if not isinstance(data, dict):
        return {"version": 1, "scripts": {}}
    scripts = data.get("scripts") if isinstance(data.get("scripts"), dict) else {}
    return {"version": int(data.get("version") or 1), "scripts": scripts}


def save_ledger(data: dict[str, Any]) -> None:
    LEDGER_PATH.parent.mkdir(parents=True, exist_ok=True)
    LEDGER_PATH.write_text(json.dumps(data, indent=2), encoding="utf-8")


def upsert_script_snapshot(
    *,
    script_id: str,
    name: str,
    source: str,
) -> dict[str, Any]:
    digest = content_hash(source)
    ledger = load_ledger()
    scripts: dict[str, Any] = dict(ledger.get("scripts") or {})
    prev = scripts.get(script_id) if isinstance(scripts.get(script_id), dict) else None
    changed = bool(prev and prev.get("sha256") and prev.get("sha256") != digest)
    entry = {
        "id": script_id,
        "name": name,
        "sha256": digest,
        "bytes": len(source.encode("utf-8")),
        "lines": source.count("\n") + (1 if source else 0),
        "updated_at": _now(),
        "previous_sha256": (prev or {}).get("sha256"),
        "changed_since_last": changed,
    }
    scripts[script_id] = entry
    ledger["scripts"] = scripts
    ledger["updated_at"] = _now()
    save_ledger(ledger)
    return entry


def diff_against_ledger(script_id: str, source: str) -> dict[str, Any]:
    digest = content_hash(source)
    ledger = load_ledger()
    prev = (ledger.get("scripts") or {}).get(script_id)
    if not isinstance(prev, dict) or not prev.get("sha256"):
        return {
            "id": script_id,
            "status": "new",
            "sha256": digest,
            "previous_sha256": None,
            "changed": True,
        }
    changed = prev.get("sha256") != digest
    return {
        "id": script_id,
        "status": "changed" if changed else "unchanged",
        "sha256": digest,
        "previous_sha256": prev.get("sha256"),
        "changed": changed,
        "ledger_updated_at": prev.get("updated_at"),
        "name": prev.get("name"),
    }
