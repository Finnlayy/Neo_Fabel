import asyncio
import json
import os
import re
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Literal


PAIR_RE = re.compile(r"^[A-Z0-9]+(?:[/-][A-Z0-9]+)?$")

SPOT_ORDER_TYPES = frozenset(
    {
        "market",
        "limit",
        "stop-loss",
        "stop-loss-limit",
        "take-profit",
        "take-profit-limit",
        "trailing-stop",
        "trailing-stop-limit",
    }
)
ORDER_TYPES = SPOT_ORDER_TYPES  # backward-compatible alias
TIME_IN_FORCE = frozenset({"GTC", "IOC", "GTD", "FOK"})

# Public / paper commands — always available.
PUBLIC_COMMANDS = frozenset(
    {"ticker", "paper", "status", "server-time", "pairs", "orderbook", "ohlc", "trades"}
)
# Level 1 read-only account commands.
READ_COMMANDS = frozenset({"balance", "open-orders", "auth"})
# Level 3/4 trading commands (gated by caller).
TRADE_COMMANDS = frozenset({"order", "futures", "ws"})


class KrakenCliError(RuntimeError):
    def __init__(self, category: str, message: str, *, retryable: bool = False):
        super().__init__(message)
        self.category = category
        self.retryable = retryable


@dataclass(frozen=True)
class KrakenCli:
    binary: str = "kraken"
    timeout_seconds: float = 15.0
    allow_trade_commands: bool = False
    api_key: str | None = None
    api_secret: str | None = None

    def _command_env(self) -> dict[str, str]:
        """Subprocess env: inherit OS env and inject Kraken creds from Settings/vault."""
        env = os.environ.copy()
        if self.api_key and not env.get("KRAKEN_API_KEY"):
            env["KRAKEN_API_KEY"] = self.api_key
        if self.api_secret and not env.get("KRAKEN_API_SECRET"):
            env["KRAKEN_API_SECRET"] = self.api_secret
        # Windows kraken.exe shims invoke WSL — credentials must cross via WSLENV.
        if os.name == "nt" and (env.get("KRAKEN_API_KEY") or env.get("KRAKEN_API_SECRET")):
            parts: list[str] = []
            if env.get("KRAKEN_API_KEY"):
                parts.append("KRAKEN_API_KEY/u")
            if env.get("KRAKEN_API_SECRET"):
                parts.append("KRAKEN_API_SECRET/u")
            existing = env.get("WSLENV", "")
            for part in parts:
                if part not in existing.split(":"):
                    existing = f"{part}:{existing}" if existing else part
            env["WSLENV"] = existing
        return env

    @staticmethod
    def _failure_message(payload: dict[str, Any] | Any, stderr: bytes) -> str:
        if isinstance(payload, dict):
            for key in ("message", "detail", "error_description"):
                text = payload.get(key)
                if text and str(text).strip() and str(text).strip() != str(payload.get("error", "")).strip():
                    return str(text).strip()
            err = payload.get("error")
            if err and str(err).strip() not in {"", "api", "auth"}:
                return str(err).strip()
        stderr_text = stderr.decode("utf-8", errors="replace").strip()
        if stderr_text:
            try:
                parsed = json.loads(stderr_text)
                if isinstance(parsed, dict):
                    return KrakenCli._failure_message(parsed, b"")
            except json.JSONDecodeError:
                return stderr_text
        return "kraken command failed"

    async def _run(self, args: list[str]) -> dict[str, Any]:
        if not args:
            raise KrakenCliError("validation", "command is not allowlisted")
        from backend.app.trading.capital_policy import assert_args_forbid_external_capital
        from backend.app.trading.guardrails import GuardrailViolation

        try:
            assert_args_forbid_external_capital(args)
        except GuardrailViolation as exc:
            raise KrakenCliError("validation", f"{exc.code}: {exc}") from exc
        head = args[0]
        allowed = set(PUBLIC_COMMANDS) | set(READ_COMMANDS)
        if self.allow_trade_commands:
            allowed |= set(TRADE_COMMANDS)
        if head not in allowed:
            raise KrakenCliError("validation", "command is not allowlisted")
        command = [self.binary, *args, "-o", "json"]
        try:
            process = await asyncio.create_subprocess_exec(
                *command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=self._command_env(),
            )
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=self.timeout_seconds)
        except FileNotFoundError as exc:
            raise KrakenCliError("config", "kraken executable is not installed") from exc
        except NotImplementedError as exc:
            raise KrakenCliError(
                "config",
                "kraken CLI subprocess is unavailable on this event loop; use public REST fallback",
            ) from exc
        except PermissionError as exc:
            raise KrakenCliError(
                "config",
                "kraken CLI subprocess could not be started; use public REST fallback",
            ) from exc
        except asyncio.TimeoutError as exc:
            process.kill()
            await process.wait()
            raise KrakenCliError("network", "kraken command timed out", retryable=True) from exc

        try:
            payload = json.loads(stdout.decode("utf-8")) if stdout.strip() else {}
        except json.JSONDecodeError as exc:
            raise KrakenCliError("parse", "kraken returned invalid JSON") from exc
        if process.returncode != 0:
            category = str(payload.get("error", "api")) if isinstance(payload, dict) else "api"
            message = self._failure_message(payload, stderr)
            raise KrakenCliError(category, message, retryable=category in {"network", "rate_limit"})
        if not isinstance(payload, dict):
            raise KrakenCliError("parse", "kraken returned a non-object JSON value")
        return payload

    @staticmethod
    def _pair(pair: str) -> str:
        normalized = pair.strip().upper()
        if not PAIR_RE.fullmatch(normalized):
            raise KrakenCliError("validation", "invalid trading pair")
        return normalized

    async def ticker(self, pair: str) -> dict[str, Any]:
        return await self._run(["ticker", self._pair(pair)])

    async def orderbook(self, pair: str, *, count: int = 25) -> dict[str, Any]:
        depth = max(1, min(int(count), 100))
        return await self._run(["orderbook", self._pair(pair), "--count", str(depth)])

    async def pairs(self, pair: str) -> dict[str, Any]:
        return await self._run(["pairs", "--pair", self._pair(pair)])

    async def auth_test(self) -> dict[str, Any]:
        return await self._run(["auth", "test"])

    async def balance(self) -> dict[str, Any]:
        return await self._run(["balance"])

    async def open_orders(self) -> dict[str, Any]:
        return await self._run(["open-orders"])

    async def cancel_after(self, seconds: int) -> dict[str, Any]:
        if seconds < 1:
            raise KrakenCliError("validation", "cancel-after seconds must be positive")
        return await self._run(["order", "cancel-after", str(seconds)])

    async def cancel_order(self, txid: str) -> dict[str, Any]:
        if not self.allow_trade_commands:
            raise KrakenCliError("validation", "live trading commands are disabled")
        tid = txid.strip()
        if not tid:
            raise KrakenCliError("validation", "txid required")
        return await self._run(["order", "cancel", tid])

    async def cancel_batch(self, txids: list[str]) -> dict[str, Any]:
        if not self.allow_trade_commands:
            raise KrakenCliError("validation", "live trading commands are disabled")
        cleaned = [t.strip() for t in txids if t and t.strip()]
        if not cleaned:
            raise KrakenCliError("validation", "at least one txid required")
        return await self._run(["order", "cancel-batch", *cleaned])

    async def cancel_all(self) -> dict[str, Any]:
        if not self.allow_trade_commands:
            raise KrakenCliError("validation", "live trading commands are disabled")
        return await self._run(["order", "cancel-all"])

    async def place_order(
        self,
        side: Literal["buy", "sell"],
        pair: str,
        volume: Decimal,
        order_type: str,
        price: Decimal | str | None,
        *,
        price2: Decimal | str | None = None,
        time_in_force: str | None = None,
        yes: bool = False,
    ) -> dict[str, Any]:
        return await self._order(
            side, pair, volume, order_type, price, price2=price2, time_in_force=time_in_force, validate=False, yes=yes
        )

    async def validate_order(
        self,
        side: Literal["buy", "sell"],
        pair: str,
        volume: Decimal,
        order_type: str,
        price: Decimal | str | None,
        *,
        price2: Decimal | str | None = None,
        time_in_force: str | None = None,
    ) -> dict[str, Any]:
        return await self._order(
            side, pair, volume, order_type, price, price2=price2, time_in_force=time_in_force, validate=True, yes=False
        )

    async def amend_order(
        self,
        txid: str,
        *,
        price: Decimal | None = None,
        volume: Decimal | None = None,
    ) -> dict[str, Any]:
        """Prefer WebSocket amend; falls back to error if unsupported."""
        if not self.allow_trade_commands:
            raise KrakenCliError("validation", "live trading commands are disabled")
        tid = txid.strip()
        if not tid:
            raise KrakenCliError("validation", "txid required")
        args = ["ws", "amend-order", "--txid", tid]
        if price is not None:
            args.extend(["--price", format(price, "f")])
        if volume is not None:
            args.extend(["--volume", format(volume, "f")])
        try:
            return await self._run(args)
        except KrakenCliError:
            # Spot REST-style replace is cancel + caller re-places.
            raise KrakenCliError(
                "validation",
                "amend unavailable; cancel and replace the order",
                retryable=False,
            )

    async def futures_place_order(
        self,
        side: Literal["buy", "sell"],
        pair: str,
        volume: Decimal,
        order_type: str = "market",
        *,
        price: Decimal | None = None,
        stop_price: Decimal | None = None,
        reduce_only: bool = False,
        yes: bool = False,
    ) -> dict[str, Any]:
        if not self.allow_trade_commands:
            raise KrakenCliError("validation", "live trading commands are disabled")
        if side not in {"buy", "sell"} or volume <= 0:
            raise KrakenCliError("validation", "unsupported futures order")
        args = ["futures", "order", side, self._pair(pair), format(volume, "f"), "--type", order_type]
        if price is not None:
            args.extend(["--price", format(price, "f")])
        if stop_price is not None:
            args.extend(["--stop-price", format(stop_price, "f")])
        if reduce_only:
            args.append("--reduce-only")
        if yes:
            args.append("--yes")
        return await self._run(args)

    async def futures_edit_order(
        self,
        order_id: str,
        *,
        price: Decimal | None = None,
        volume: Decimal | None = None,
    ) -> dict[str, Any]:
        if not self.allow_trade_commands:
            raise KrakenCliError("validation", "live trading commands are disabled")
        oid = order_id.strip()
        if not oid:
            raise KrakenCliError("validation", "order_id required")
        args = ["futures", "edit-order", "--order-id", oid]
        if price is not None:
            args.extend(["--price", format(price, "f")])
        if volume is not None:
            args.extend(["--size", format(volume, "f")])
        return await self._run(args)

    async def futures_cancel(self, order_id: str) -> dict[str, Any]:
        if not self.allow_trade_commands:
            raise KrakenCliError("validation", "live trading commands are disabled")
        oid = order_id.strip()
        if not oid:
            raise KrakenCliError("validation", "order_id required")
        return await self._run(["futures", "cancel", "--order-id", oid])

    async def futures_cancel_all(self, *, symbol: str | None = None) -> dict[str, Any]:
        if not self.allow_trade_commands:
            raise KrakenCliError("validation", "live trading commands are disabled")
        args = ["futures", "cancel-all"]
        if symbol:
            args.extend(["--symbol", self._pair(symbol)])
        return await self._run(args)

    async def futures_cancel_after(self, seconds: int) -> dict[str, Any]:
        if not self.allow_trade_commands:
            raise KrakenCliError("validation", "live trading commands are disabled")
        if seconds < 1:
            raise KrakenCliError("validation", "cancel-after seconds must be positive")
        return await self._run(["futures", "cancel-after", str(seconds)])

    async def _order(
        self,
        side: Literal["buy", "sell"],
        pair: str,
        volume: Decimal,
        order_type: str,
        price: Decimal | str | None,
        *,
        price2: Decimal | str | None = None,
        time_in_force: str | None = None,
        validate: bool,
        yes: bool,
    ) -> dict[str, Any]:
        if not self.allow_trade_commands:
            raise KrakenCliError("validation", "live trading commands are disabled")
        ot = order_type.strip().lower()
        if side not in {"buy", "sell"} or ot not in SPOT_ORDER_TYPES:
            raise KrakenCliError("validation", "unsupported order")
        if volume <= 0:
            raise KrakenCliError("validation", "invalid order values")
        needs_price = ot in {
            "limit",
            "stop-loss",
            "stop-loss-limit",
            "take-profit",
            "take-profit-limit",
            "trailing-stop",
            "trailing-stop-limit",
        }
        if needs_price and price is None:
            raise KrakenCliError("validation", "invalid order values")
        if ot in {"limit", "stop-loss", "take-profit"} and isinstance(price, Decimal) and price <= 0:
            raise KrakenCliError("validation", "invalid order values")
        needs_price2 = ot in {"stop-loss-limit", "take-profit-limit", "trailing-stop-limit"}
        if needs_price2 and price2 is None:
            raise KrakenCliError("validation", f"{ot} requires price2")
        args = ["order", side, self._pair(pair), format(volume, "f"), "--type", ot]
        if price is not None:
            price_arg = format(price, "f") if isinstance(price, Decimal) else str(price)
            args.extend(["--price", price_arg])
        if price2 is not None:
            price2_arg = format(price2, "f") if isinstance(price2, Decimal) else str(price2)
            args.extend(["--price2", price2_arg])
        if time_in_force:
            tif = time_in_force.strip().upper()
            if tif not in TIME_IN_FORCE:
                raise KrakenCliError("validation", "unsupported time_in_force")
            args.extend(["--timeinforce", tif])
        if validate:
            args.append("--validate")
        if yes:
            args.append("--yes")
        return await self._run(args)

    async def paper_order(
        self,
        side: Literal["buy", "sell"],
        pair: str,
        volume: Decimal,
        order_type: str,
        price: Decimal | None,
    ) -> dict[str, Any]:
        ot = order_type.strip().lower()
        if side not in {"buy", "sell"} or ot not in {"market", "limit"}:
            raise KrakenCliError("validation", "unsupported paper order")
        if volume <= 0 or (ot == "limit" and (price is None or price <= 0)):
            raise KrakenCliError("validation", "invalid paper order values")
        args = ["paper", side, self._pair(pair), format(volume, "f"), "--type", ot]
        if price is not None:
            args.extend(["--price", format(price, "f")])
        return await self._run(args)

    async def paper_cancel(self, order_id: str) -> dict[str, Any]:
        oid = order_id.strip()
        if not oid:
            raise KrakenCliError("validation", "order_id required")
        return await self._run(["paper", "cancel", oid])

    async def paper_status(self) -> dict[str, Any]:
        return await self._run(["paper", "status"])
