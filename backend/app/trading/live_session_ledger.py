"""Live trading session ledger — named by wall-clock window, with uptime metrics.

Sessions require max margin + max concurrent trades; optional symbol allowlist
further restricts the env pair list for that run only.
"""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from pathlib import Path
from threading import Lock
from typing import Any

_LOCK = Lock()
_SESSIONS_DIR = Path(__file__).resolve().parents[2] / "data" / "trading" / "sessions"


def sessions_dir() -> Path:
    _SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
    return _SESSIONS_DIR


def normalize_pair(symbol: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", (symbol or "").upper())


def _fmt_stamp(dt: datetime) -> str:
    return dt.astimezone(UTC).strftime("%Y%m%dT%H%MZ")


def session_name_for(started_at: datetime, ended_at: datetime | None = None) -> str:
    """Name sessions after the period they ran, e.g. 20260721T0115Z_to_20260721T0330Z."""
    start = _fmt_stamp(started_at)
    if ended_at is None:
        return f"{start}_running"
    return f"{start}_to_{_fmt_stamp(ended_at)}"


def parse_symbol_list(raw: str | list[str] | None) -> list[str]:
    if raw is None:
        return []
    if isinstance(raw, list):
        parts = raw
    else:
        parts = re.split(r"[\s,;]+", str(raw))
    out: list[str] = []
    seen: set[str] = set()
    for part in parts:
        norm = normalize_pair(str(part))
        if not norm or norm in seen:
            continue
        seen.add(norm)
        out.append(norm)
    return out


class LiveSessionLedger:
    """In-memory active session + JSON persistence per completed window."""

    def __init__(self) -> None:
        self._active: dict[str, Any] | None = None
        self._last_sample_at: datetime | None = None
        self._in_trade_at_last_sample = False

    @property
    def active(self) -> dict[str, Any] | None:
        return dict(self._active) if self._active else None

    def start(
        self,
        *,
        max_margin_eur: float,
        max_concurrent_trades: int,
        symbols: list[str] | None = None,
        starting_capital_eur: float | None = None,
        position_sizing: dict[str, Any] | None = None,
        risk_policy: dict[str, Any] | None = None,
        autonomy: int,
        deadman_seconds: int,
    ) -> dict[str, Any]:
        if max_margin_eur <= 0:
            raise ValueError("max_margin_eur must be > 0")
        if max_concurrent_trades < 1:
            raise ValueError("max_concurrent_trades must be >= 1")
        if self._active is not None:
            raise RuntimeError("session already active")

        now = datetime.now(UTC)
        name = session_name_for(now)
        allowlist = parse_symbol_list(symbols)
        capital = float(starting_capital_eur) if starting_capital_eur is not None else float(max_margin_eur)
        sizing = position_sizing or {"mode": "half_kelly"}
        self._active = {
            "session_name": name,
            "started_at": now.isoformat().replace("+00:00", "Z"),
            "ended_at": None,
            "max_margin_eur": float(max_margin_eur),
            "starting_capital_eur": capital,
            "max_concurrent_trades": int(max_concurrent_trades),
            "symbol_allowlist": allowlist,
            "position_sizing": sizing,
            "risk_policy": risk_policy,
            "realized_loss_eur_today": 0.0,
            "initial_equity_usd": None,
            "current_equity_usd": None,
            "peak_equity_usd": None,
            "session_drawdown_usd": 0.0,
            "max_drawdown_usd": float((risk_policy or {}).get("max_drawdown_usd") or 0.0),
            "max_drawdown_hit": False,
            "autonomy": int(autonomy),
            "deadman_seconds": int(deadman_seconds),
            "uptime_seconds": 0.0,
            "time_in_trades_seconds": 0.0,
            "peak_open_trades": 0,
            "samples": 0,
            "status": "running",
        }
        self._last_sample_at = now
        self._in_trade_at_last_sample = False
        self._persist_active()
        return dict(self._active)

    def record_equity(self, *, equity_usd: float) -> dict[str, Any] | None:
        """Record marked account equity and latch the configured drawdown stop."""
        if self._active is None:
            return None
        equity = float(equity_usd)
        if equity < 0:
            raise ValueError("equity_usd must be >= 0")
        initial = self._active.get("initial_equity_usd")
        if initial is None:
            self._active["initial_equity_usd"] = equity
        peak = self._active.get("peak_equity_usd")
        peak_value = equity if peak is None else max(float(peak), equity)
        drawdown = max(0.0, peak_value - equity)
        limit = float(self._active.get("max_drawdown_usd") or 0.0)
        hit = limit > 0 and drawdown >= limit
        self._active["current_equity_usd"] = equity
        self._active["peak_equity_usd"] = peak_value
        self._active["session_drawdown_usd"] = drawdown
        if hit:
            self._active["max_drawdown_hit"] = True
            self._active["status"] = "max_drawdown"
        self._persist_active()
        return dict(self._active)

    def note_heartbeat(self, *, kind: str = "heartbeat") -> None:
        if self._active is None:
            return
        from datetime import UTC, datetime

        self._active["last_heartbeat_kind"] = kind
        self._active["last_heartbeat_at"] = datetime.now(UTC).isoformat().replace("+00:00", "Z")
        self._persist_active()

    def sample(self, *, open_trades: int) -> dict[str, Any] | None:
        """Advance uptime / time_in_trades using open trade count."""
        if self._active is None:
            return None
        now = datetime.now(UTC)
        prev = self._last_sample_at or now
        dt = max(0.0, (now - prev).total_seconds())
        self._active["uptime_seconds"] = float(self._active.get("uptime_seconds") or 0) + dt
        if self._in_trade_at_last_sample and dt > 0:
            self._active["time_in_trades_seconds"] = (
                float(self._active.get("time_in_trades_seconds") or 0) + dt
            )
        self._in_trade_at_last_sample = open_trades > 0
        peak = int(self._active.get("peak_open_trades") or 0)
        self._active["peak_open_trades"] = max(peak, int(open_trades))
        self._active["samples"] = int(self._active.get("samples") or 0) + 1
        self._active["last_open_trades"] = int(open_trades)
        self._last_sample_at = now
        started = datetime.fromisoformat(str(self._active["started_at"]).replace("Z", "+00:00"))
        self._active["session_name"] = session_name_for(started)
        self._persist_active()
        return dict(self._active)

    def stop(self, *, open_trades: int = 0, status: str = "stopped") -> dict[str, Any] | None:
        if self._active is None:
            return None
        self.sample(open_trades=open_trades)
        now = datetime.now(UTC)
        started = datetime.fromisoformat(str(self._active["started_at"]).replace("Z", "+00:00"))
        name = session_name_for(started, now)
        self._active["ended_at"] = now.isoformat().replace("+00:00", "Z")
        self._active["session_name"] = name
        self._active["status"] = status
        final = dict(self._active)
        path = sessions_dir() / f"{name}.json"
        with _LOCK:
            path.write_text(json.dumps(final, indent=2), encoding="utf-8")
            active_path = sessions_dir() / "_active.json"
            if active_path.exists():
                active_path.unlink()
        self._active = None
        self._last_sample_at = None
        self._in_trade_at_last_sample = False
        return final

    def _persist_active(self) -> None:
        if self._active is None:
            return
        with _LOCK:
            (sessions_dir() / "_active.json").write_text(
                json.dumps(self._active, indent=2), encoding="utf-8"
            )

    def list_sessions(self, limit: int = 50) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        if self._active:
            rows.append(dict(self._active))
        files = sorted(sessions_dir().glob("*.json"), reverse=True)
        for path in files:
            if path.name.startswith("_"):
                continue
            try:
                rows.append(json.loads(path.read_text(encoding="utf-8")))
            except (OSError, json.JSONDecodeError):
                continue
            if len(rows) >= limit:
                break
        return rows[:limit]


live_session_ledger = LiveSessionLedger()
