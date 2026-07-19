"""Daily LLM spend ledger (EUR) — hard cap for paid gateways like AIPrimeTech."""

from __future__ import annotations

import json
import threading
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

from backend.app.integrations.aiprimetech_catalog import DEFAULT_AIPRIMETECH_MODEL, model_meta

BACKEND_ROOT = Path(__file__).resolve().parents[2]
SPEND_DIR = BACKEND_ROOT / "data" / "llm_spend"
_LOCK = threading.Lock()


class DailyBudgetExceeded(Exception):
    """Raised when a provider would exceed its configured daily EUR budget."""

    def __init__(self, provider: str, spent_eur: float, limit_eur: float):
        self.provider = provider
        self.spent_eur = spent_eur
        self.limit_eur = limit_eur
        super().__init__(
            f"{provider} daily budget exhausted: €{spent_eur:.4f} / €{limit_eur:.2f}"
        )


@dataclass(frozen=True)
class SpendSnapshot:
    day: str
    provider: str
    spent_eur: float
    limit_eur: float
    calls: int
    remaining_eur: float

    @property
    def exhausted(self) -> bool:
        return self.remaining_eur <= 0.0


def ensure_spend_dir() -> Path:
    SPEND_DIR.mkdir(parents=True, exist_ok=True)
    return SPEND_DIR


def _day_key(day: date | None = None) -> str:
    return (day or datetime.now(UTC).date()).isoformat()


def _path(provider: str, day: date | None = None) -> Path:
    safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in provider.lower())
    return ensure_spend_dir() / f"{safe}_{_day_key(day)}.json"


def _read(provider: str, day: date | None = None) -> dict[str, Any]:
    path = _path(provider, day)
    if not path.exists():
        return {"day": _day_key(day), "provider": provider, "spent_eur": 0.0, "calls": 0, "events": []}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"day": _day_key(day), "provider": provider, "spent_eur": 0.0, "calls": 0, "events": []}


def _write(provider: str, data: dict[str, Any], day: date | None = None) -> None:
    path = _path(provider, day)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def snapshot(provider: str, limit_eur: float, day: date | None = None) -> SpendSnapshot:
    with _LOCK:
        data = _read(provider, day)
        spent = float(data.get("spent_eur") or 0.0)
        calls = int(data.get("calls") or 0)
        rem = max(0.0, float(limit_eur) - spent)
        return SpendSnapshot(
            day=_day_key(day),
            provider=provider,
            spent_eur=round(spent, 6),
            limit_eur=float(limit_eur),
            calls=calls,
            remaining_eur=round(rem, 6),
        )


def assert_budget_available(provider: str, limit_eur: float, *, reserve_eur: float = 0.005) -> SpendSnapshot:
    snap = snapshot(provider, limit_eur)
    if snap.remaining_eur < reserve_eur:
        raise DailyBudgetExceeded(provider, snap.spent_eur, limit_eur)
    return snap


def estimate_cost_eur(
    *,
    model: str,
    prompt_tokens: int,
    completion_tokens: int,
    input_eur_per_1m: float | None = None,
    output_eur_per_1m: float | None = None,
    min_eur: float = 0.0001,
) -> float:
    meta = model_meta(model or DEFAULT_AIPRIMETECH_MODEL)
    in_rate = float(input_eur_per_1m if input_eur_per_1m is not None else meta["eur_per_1m_input"])
    out_rate = float(output_eur_per_1m if output_eur_per_1m is not None else meta["eur_per_1m_output"])
    cost = (max(0, prompt_tokens) / 1_000_000.0) * in_rate + (
        max(0, completion_tokens) / 1_000_000.0
    ) * out_rate
    return max(min_eur, round(cost, 8))


def tokens_from_messages(messages: list[dict[str, str]], reply: str = "") -> tuple[int, int]:
    """Rough fallback when provider omits usage (≈4 chars / token)."""
    prompt_chars = sum(len(m.get("content") or "") for m in messages)
    return max(1, prompt_chars // 4), max(1, len(reply) // 4)


def record_spend(
    provider: str,
    *,
    cost_eur: float,
    model: str,
    prompt_tokens: int,
    completion_tokens: int,
    limit_eur: float,
) -> SpendSnapshot:
    with _LOCK:
        data = _read(provider)
        spent = float(data.get("spent_eur") or 0.0) + float(cost_eur)
        data["spent_eur"] = round(spent, 8)
        data["calls"] = int(data.get("calls") or 0) + 1
        events = list(data.get("events") or [])
        events.append(
            {
                "ts": datetime.now(UTC).isoformat(),
                "model": model,
                "cost_eur": round(float(cost_eur), 8),
                "prompt_tokens": int(prompt_tokens),
                "completion_tokens": int(completion_tokens),
            }
        )
        # Keep ledger small.
        data["events"] = events[-200:]
        _write(provider, data)
        rem = max(0.0, float(limit_eur) - spent)
        return SpendSnapshot(
            day=str(data.get("day") or _day_key()),
            provider=provider,
            spent_eur=round(spent, 6),
            limit_eur=float(limit_eur),
            calls=int(data["calls"]),
            remaining_eur=round(rem, 6),
        )


def reset_spend_for_tests(provider: str = "aiprimetech") -> None:
    """Test helper — wipe today's ledger file."""
    path = _path(provider)
    if path.exists():
        path.unlink()
