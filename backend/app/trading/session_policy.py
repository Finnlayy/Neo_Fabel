"""Live/paper session risk policy — size caps, daily loss, confidence, hours, human gate."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from typing import Any, Literal

AmountUnit = Literal["eur", "usd", "pct"]
AMOUNT_UNITS: tuple[AmountUnit, ...] = ("eur", "usd", "pct")

_CRYPTO_BASES = frozenset(
    {
        "BTC",
        "ETH",
        "XRP",
        "ADA",
        "SOL",
        "DOT",
        "AVAX",
        "POL",
        "MATIC",
        "LINK",
        "DOGE",
        "LTC",
        "ATOM",
        "NEAR",
        "UNI",
        "AAVE",
    }
)


@dataclass(frozen=True)
class CapAmount:
    value: float
    unit: AmountUnit = "eur"

    def to_dict(self) -> dict[str, Any]:
        return {"value": float(self.value), "unit": self.unit}

    def resolve_eur(self, *, capital_eur: float, usd_eur_rate: float = 1.0) -> float:
        if self.value < 0:
            raise ValueError("cap value must be >= 0")
        if self.unit == "eur":
            return float(self.value)
        if self.unit == "usd":
            rate = float(usd_eur_rate) if usd_eur_rate > 0 else 1.0
            return float(self.value) * rate
        # pct of capital
        if self.value > 100:
            raise ValueError("pct cap must be <= 100")
        return float(capital_eur) * (float(self.value) / 100.0)


def parse_cap_amount(raw: Any, *, field: str = "cap") -> CapAmount:
    if raw is None:
        raise ValueError(f"{field} is required")
    if isinstance(raw, (int, float)):
        return CapAmount(value=float(raw), unit="eur")
    if isinstance(raw, str):
        text = raw.strip().lower().replace(",", ".")
        if text.endswith("%"):
            return CapAmount(value=float(text[:-1].strip()), unit="pct")
        if text.endswith("usd") or text.startswith("$"):
            num = text.replace("usd", "").replace("$", "").strip()
            return CapAmount(value=float(num), unit="usd")
        if text.endswith("eur") or text.startswith("€"):
            num = text.replace("eur", "").replace("€", "").strip()
            return CapAmount(value=float(num), unit="eur")
        return CapAmount(value=float(text), unit="eur")
    if isinstance(raw, dict):
        unit_raw = str(raw.get("unit") or "eur").strip().lower()
        if unit_raw in {"%", "percent", "pct"}:
            unit: AmountUnit = "pct"
        elif unit_raw in {"$", "usd"}:
            unit = "usd"
        elif unit_raw in {"€", "eur", "euro"}:
            unit = "eur"
        else:
            raise ValueError(f"{field}.unit must be eur|usd|pct")
        return CapAmount(value=float(raw.get("value")), unit=unit)
    raise ValueError(f"invalid {field}")


@dataclass(frozen=True)
class SessionRiskPolicy:
    max_session_size: CapAmount
    max_concurrent_trades: int
    daily_loss_limit: CapAmount
    min_confidence_pct: float
    allow_pre_post_market: bool
    human_verification: bool
    starting_capital_eur: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "max_session_size": self.max_session_size.to_dict(),
            "max_concurrent_trades": self.max_concurrent_trades,
            "daily_loss_limit": self.daily_loss_limit.to_dict(),
            "min_confidence_pct": self.min_confidence_pct,
            "allow_pre_post_market": self.allow_pre_post_market,
            "human_verification": self.human_verification,
            "starting_capital_eur": self.starting_capital_eur,
            "max_session_size_eur": self.max_session_size_eur(),
            "daily_loss_limit_eur": self.daily_loss_limit_eur(),
        }

    def max_session_size_eur(self) -> float:
        return self.max_session_size.resolve_eur(capital_eur=self.starting_capital_eur)

    def daily_loss_limit_eur(self) -> float:
        return self.daily_loss_limit.resolve_eur(capital_eur=self.starting_capital_eur)


def validate_session_risk_policy(
    *,
    max_session_size: Any,
    max_concurrent_trades: int,
    daily_loss_limit: Any,
    min_confidence_pct: float = 0.0,
    allow_pre_post_market: bool = True,
    human_verification: bool = False,
    starting_capital_eur: float,
) -> SessionRiskPolicy:
    capital = float(starting_capital_eur)
    if capital <= 0:
        raise ValueError("starting_capital_eur must be > 0")
    concurrent = int(max_concurrent_trades)
    if concurrent < 1 or concurrent > 10:
        raise ValueError("max_concurrent_trades must be 1..10")
    conf = float(min_confidence_pct)
    if conf < 0 or conf > 100:
        raise ValueError("min_confidence_pct must be 0..100")
    size = parse_cap_amount(max_session_size, field="max_session_size")
    loss = parse_cap_amount(daily_loss_limit, field="daily_loss_limit")
    if size.resolve_eur(capital_eur=capital) <= 0:
        raise ValueError("max_session_size must resolve to > 0")
    if loss.resolve_eur(capital_eur=capital) < 0:
        raise ValueError("daily_loss_limit must resolve to >= 0")
    return SessionRiskPolicy(
        max_session_size=size,
        max_concurrent_trades=concurrent,
        daily_loss_limit=loss,
        min_confidence_pct=conf,
        allow_pre_post_market=bool(allow_pre_post_market),
        human_verification=bool(human_verification),
        starting_capital_eur=capital,
    )


def is_crypto_pair(pair: str) -> bool:
    raw = "".join(ch for ch in (pair or "").upper() if ch.isalnum())
    for quote in ("USD", "EUR", "USDT", "USDC"):
        if raw.endswith(quote) and len(raw) > len(quote):
            base = raw[: -len(quote)]
            return base in _CRYPTO_BASES
    return False


def assert_market_hours_allowed(
    pair: str,
    *,
    allow_pre_post_market: bool,
    now: datetime | None = None,
) -> None:
    """When pre/post is disabled, block non-crypto outside US cash hours (UTC)."""
    if allow_pre_post_market or is_crypto_pair(pair):
        return
    stamp = now or datetime.now(UTC)
    if stamp.tzinfo is None:
        stamp = stamp.replace(tzinfo=UTC)
    else:
        stamp = stamp.astimezone(UTC)
    # Rough US equity cash session: 14:30–21:00 UTC, weekdays
    if stamp.weekday() >= 5:
        raise ValueError("pre/post market disabled — weekend trading blocked for this pair")
    minutes = stamp.hour * 60 + stamp.minute
    if minutes < (14 * 60 + 30) or minutes >= (21 * 60):
        raise ValueError("pre/post market disabled — outside regular cash session for this pair")


def assert_confidence_ok(confidence_pct: float | None, *, min_confidence_pct: float) -> None:
    if min_confidence_pct <= 0:
        return
    if confidence_pct is None:
        raise ValueError(f"min confidence {min_confidence_pct}% required but signal has no confidence")
    if float(confidence_pct) < float(min_confidence_pct):
        raise ValueError(
            f"confidence {confidence_pct}% below session min {min_confidence_pct}%"
        )


def assert_daily_loss_ok(*, realized_loss_eur: float, daily_loss_limit_eur: float) -> None:
    """realized_loss_eur is positive when money was lost today."""
    limit = float(daily_loss_limit_eur)
    if limit <= 0:
        return
    if float(realized_loss_eur) >= limit:
        raise ValueError(
            f"daily loss limit hit ({realized_loss_eur:.2f} € >= {limit:.2f} €)"
        )
