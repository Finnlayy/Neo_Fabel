import asyncio
import json
import re
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Literal


PAIR_RE = re.compile(r"^[A-Z0-9]+(?:[/-][A-Z0-9]+)?$")
ORDER_TYPES = {"market", "limit"}

# Public / paper commands — always available.
PUBLIC_COMMANDS = frozenset(
    {"ticker", "paper", "status", "server-time", "pairs", "orderbook", "ohlc", "trades"}
)
# Level 1 read-only account commands.
READ_COMMANDS = frozenset({"balance", "open-orders", "auth"})
# Level 3/4 trading commands (gated by caller).
TRADE_COMMANDS = frozenset({"order"})


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

    async def _run(self, args: list[str]) -> dict[str, Any]:
        if not args:
            raise KrakenCliError("validation", "command is not allowlisted")
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
            )
            stdout, _stderr = await asyncio.wait_for(process.communicate(), timeout=self.timeout_seconds)
        except FileNotFoundError as exc:
            raise KrakenCliError("config", "kraken executable is not installed") from exc
        except NotImplementedError as exc:
            # Windows SelectorEventLoop (common under uvicorn) cannot spawn subprocesses.
            raise KrakenCliError(
                "config",
                "kraken CLI subprocess is unavailable on this event loop; use public REST fallback",
            ) from exc
        except PermissionError as exc:
            # Process creation can also fail with WinError 5 in restricted Windows hosts.
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
            raise KrakenCliError(category, "kraken command failed", retryable=category in {"network", "rate_limit"})
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

    async def validate_order(
        self,
        side: Literal["buy", "sell"],
        pair: str,
        volume: Decimal,
        order_type: Literal["market", "limit"],
        price: Decimal | None,
    ) -> dict[str, Any]:
        return await self._order(side, pair, volume, order_type, price, validate=True, yes=False)

    async def place_order(
        self,
        side: Literal["buy", "sell"],
        pair: str,
        volume: Decimal,
        order_type: Literal["market", "limit"],
        price: Decimal | None,
        *,
        yes: bool = False,
    ) -> dict[str, Any]:
        return await self._order(side, pair, volume, order_type, price, validate=False, yes=yes)

    async def _order(
        self,
        side: Literal["buy", "sell"],
        pair: str,
        volume: Decimal,
        order_type: Literal["market", "limit"],
        price: Decimal | None,
        *,
        validate: bool,
        yes: bool,
    ) -> dict[str, Any]:
        if not self.allow_trade_commands:
            raise KrakenCliError("validation", "live trading commands are disabled")
        if side not in {"buy", "sell"} or order_type not in ORDER_TYPES:
            raise KrakenCliError("validation", "unsupported order")
        if volume <= 0 or (order_type == "limit" and (price is None or price <= 0)):
            raise KrakenCliError("validation", "invalid order values")
        args = ["order", side, self._pair(pair), format(volume, "f"), "--type", order_type]
        if price is not None:
            args.extend(["--price", format(price, "f")])
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
        order_type: Literal["market", "limit"],
        price: Decimal | None,
    ) -> dict[str, Any]:
        if side not in {"buy", "sell"} or order_type not in ORDER_TYPES:
            raise KrakenCliError("validation", "unsupported paper order")
        if volume <= 0 or (order_type == "limit" and (price is None or price <= 0)):
            raise KrakenCliError("validation", "invalid paper order values")
        args = ["paper", side, self._pair(pair), format(volume, "f"), "--type", order_type]
        if price is not None:
            args.extend(["--price", format(price, "f")])
        return await self._run(args)

    async def paper_status(self) -> dict[str, Any]:
        return await self._run(["paper", "status"])
