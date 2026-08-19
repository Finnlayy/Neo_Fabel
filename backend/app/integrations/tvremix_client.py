"""tvremix hosted MCP client (Streamable HTTP) for Pine list/read + OHLCV.

Auth: Bearer API key from https://tvremix.xyz/account#api-keys
Endpoint: https://tvremix.xyz/api/mcp/v1

Pine tools (when exposed for the account / TV link):
  pine_list_saved_scripts, pine_list_session_scripts, pine_list_scripts,
  pine_read_script, pine_get_session_script, pine_get_source, …

Market tools always (catalog): get_ohlcv, search_symbols, …
"""

from __future__ import annotations

import json
import logging
import math
import re
import time
from typing import Any

import httpx

from backend.app.settings import Settings, get_settings

DEFAULT_MCP_URL = "https://tvremix.xyz/api/mcp/v1"
logger = logging.getLogger(__name__)

# Prefer session/active first, then saved library.
_LIST_TOOLS = (
    "pine_list_session_scripts",
    "pine_list_saved_scripts",
    "pine_list_scripts",
    "list_scripts",
)
_READ_TOOLS = (
    "pine_read_script",
    "pine_get_session_script",
    "pine_get_source",
    "get_script",
)


class TvremixError(RuntimeError):
    pass


class TvremixClient:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self.base_url = (self.settings.tvremix_mcp_url or DEFAULT_MCP_URL).rstrip("/")
        self.api_key = (self.settings.tvremix_api_key or "").strip()
        self._session_id: str | None = None
        self._rpc_id = 0
        self._tool_names: set[str] | None = None
        self._rate_limited_until = 0.0

    @property
    def configured(self) -> bool:
        return bool(self.api_key)

    def _headers(self) -> dict[str, str]:
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
            "Authorization": f"Bearer {self.api_key}",
        }
        if self._session_id:
            headers["Mcp-Session-Id"] = self._session_id
        return headers

    def _next_id(self) -> int:
        self._rpc_id += 1
        return self._rpc_id

    async def _post_rpc(self, method: str, params: dict[str, Any] | None = None) -> Any:
        if not self.configured:
            raise TvremixError("TVREMIX_API_KEY is not configured")
        remaining = self._rate_limited_until - time.monotonic()
        if remaining > 0:
            raise TvremixError(
                f"tvremix rate limited — retry in {math.ceil(remaining)}s"
            )
        payload = {"jsonrpc": "2.0", "id": self._next_id(), "method": method, "params": params or {}}
        async with httpx.AsyncClient(timeout=self.settings.tvremix_timeout_seconds) as client:
            response = await client.post(self.base_url, headers=self._headers(), json=payload)
            sid = response.headers.get("mcp-session-id") or response.headers.get("Mcp-Session-Id")
            if sid:
                self._session_id = sid
            if response.status_code == 401:
                raise TvremixError("tvremix unauthorized — check TVREMIX_API_KEY")
            if response.status_code == 429:
                try:
                    retry_after = float(response.headers.get("Retry-After") or 60)
                except ValueError:
                    retry_after = 60.0
                retry_after = min(max(retry_after, 1.0), 3600.0)
                self._rate_limited_until = time.monotonic() + retry_after
                raise TvremixError(
                    f"tvremix rate limited — retry in {math.ceil(retry_after)}s"
                )
            body = response.text
            data = _parse_mcp_body(body)
            if response.status_code >= 400:
                raise TvremixError(f"tvremix HTTP {response.status_code}: {body[:300]}")
            if isinstance(data, dict) and data.get("error"):
                err = data["error"]
                raise TvremixError(str(err.get("message") or err))
            return data.get("result") if isinstance(data, dict) else data

    async def initialize(self) -> None:
        await self._post_rpc(
            "initialize",
            {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "neo-fabel", "version": "1.0"},
            },
        )
        # notifications have no response id — best-effort
        try:
            async with httpx.AsyncClient(timeout=self.settings.tvremix_timeout_seconds) as client:
                await client.post(
                    self.base_url,
                    headers=self._headers(),
                    json={"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}},
                )
        except httpx.HTTPError as exc:
            logger.debug("tvremix initialized notification failed: %s", exc)

    async def list_tools(self) -> list[str]:
        await self.initialize()
        result = await self._post_rpc("tools/list", {})
        tools: list[dict[str, Any]] = []
        if isinstance(result, dict):
            tools = result.get("tools") or []
        names = [str(t.get("name")) for t in tools if isinstance(t, dict) and t.get("name")]
        self._tool_names = set(names)
        return names

    async def call_tool(self, name: str, arguments: dict[str, Any] | None = None) -> Any:
        if self._tool_names is None:
            await self.list_tools()
        result = await self._post_rpc(
            "tools/call",
            {"name": name, "arguments": arguments or {}},
        )
        return _unwrap_tool_result(result)

    async def _first_working_tool(self, candidates: tuple[str, ...], arguments: dict[str, Any]) -> tuple[str, Any] | None:
        if self._tool_names is None:
            await self.list_tools()
        assert self._tool_names is not None
        for name in candidates:
            if name not in self._tool_names:
                continue
            try:
                return name, await self.call_tool(name, arguments)
            except TvremixError:
                continue
        # Try anyway if tools/list was incomplete
        for name in candidates:
            try:
                return name, await self.call_tool(name, arguments)
            except TvremixError:
                continue
        return None

    async def list_pine_scripts(self) -> list[dict[str, Any]]:
        """Return normalized strategy cards from session + saved Pine lists."""
        collected: list[dict[str, Any]] = []
        seen: set[str] = set()

        for tool_name in _LIST_TOOLS:
            hit = await self._first_working_tool((tool_name,), {})
            if not hit:
                continue
            _, raw = hit
            for item in _coerce_script_list(raw):
                sid = str(item.get("id") or item.get("scriptId") or item.get("script_id") or item.get("name") or "")
                if not sid or sid in seen:
                    continue
                seen.add(sid)
                collected.append(item)
            # Prefer gathering from all list tools that exist
        return collected

    async def read_pine_script(self, script_id: str, *, name: str | None = None) -> dict[str, Any]:
        args_variants = [
            {"id": script_id},
            {"scriptId": script_id},
            {"script_id": script_id},
            {"name": name or script_id},
        ]
        last_err: Exception | None = None
        for args in args_variants:
            hit = await self._first_working_tool(_READ_TOOLS, args)
            if not hit:
                continue
            tool, raw = hit
            source = _extract_source(raw)
            if source:
                return {
                    "id": script_id,
                    "name": name or _extract_name(raw) or script_id,
                    "source": source,
                    "tool": tool,
                    "raw": raw if isinstance(raw, dict) else {"value": raw},
                }
        if last_err:
            raise TvremixError(str(last_err))
        raise TvremixError(f"Could not read Pine script id={script_id}")

    async def fetch_ohlcv_raw(
        self,
        symbol: str,
        interval: str = "5m",
        count: int = 300,
    ) -> Any:
        """Raw get_ohlcv payload for Academy / candle mappers."""
        tv_symbol = _to_tv_symbol(symbol)
        return await self.call_tool(
            "get_ohlcv",
            {"symbol": tv_symbol, "interval": interval, "count": min(count, 5000), "summary": False},
        )

    async def fetch_ohlcv_bars(
        self,
        symbol: str,
        interval: str = "5m",
        count: int = 300,
    ) -> list[dict[str, float]]:
        """TradingView bars via tvremix get_ohlcv when available."""
        raw = await self.fetch_ohlcv_raw(symbol, interval=interval, count=count)
        return _bars_from_ohlcv(raw)

    async def fetch_quote(self, symbol: str) -> dict[str, Any] | None:
        """Best-effort last/change snapshot from get_quote."""
        tv_symbol = _to_tv_symbol(symbol)
        raw = await self.call_tool("get_quote", {"symbol": tv_symbol})
        if not isinstance(raw, dict):
            return None
        last = raw.get("last") or raw.get("price") or raw.get("close") or raw.get("lp")
        if last is None and isinstance(raw.get("quote"), dict):
            q = raw["quote"]
            last = q.get("last") or q.get("price") or q.get("close")
        if last is None:
            return None
        change = raw.get("change_pct") or raw.get("changePercent") or raw.get("chp")
        if change is None and isinstance(raw.get("quote"), dict):
            change = raw["quote"].get("change_pct") or raw["quote"].get("chp")
        try:
            return {"last": float(last), "change_pct": float(change or 0.0), "raw": raw}
        except (TypeError, ValueError):
            return None

    async def fetch_technicals(self, symbol: str, *, interval: str = "5m") -> dict[str, Any] | None:
        tv_symbol = _to_tv_symbol(symbol)
        for tool, args in (
            ("get_technicals_rating", {"symbol": tv_symbol, "interval": interval}),
            ("get_technicals", {"symbol": tv_symbol, "interval": interval}),
            ("get_full_technicals", {"symbol": tv_symbol, "interval": interval}),
        ):
            try:
                raw = await self.call_tool(tool, args)
            except TvremixError:
                continue
            if isinstance(raw, dict) and raw:
                out = dict(raw)
                out["_tool"] = tool
                return out
            if isinstance(raw, str) and raw.strip():
                return {"rating": raw.strip(), "_tool": tool}
        return None

    async def fetch_structure_levels(
        self, symbol: str, *, interval: str = "5m"
    ) -> dict[str, Any] | None:
        """SMC / swing levels as order-book substitute (tvremix has no L2)."""
        tv_symbol = _to_tv_symbol(symbol)
        merged: dict[str, Any] = {}
        for tool, args in (
            ("analyze_smc_tool", {"symbol": tv_symbol, "interval": interval}),
            ("analyze_swing_tool", {"symbol": tv_symbol, "interval": interval}),
            ("compute_levels_batch", {"symbols": [tv_symbol], "interval": interval}),
        ):
            try:
                raw = await self.call_tool(tool, args)
            except TvremixError:
                continue
            if isinstance(raw, dict) and raw:
                merged[tool] = raw
        return merged or None

    async def search_pine_scripts(self, query: str, *, limit: int = 50) -> list[dict[str, Any]]:
        """Search Pine sources for a string (e.g. alertcondition, strategy.entry)."""
        q = (query or "").strip()
        if not q:
            return []
        # Prefer native MCP search when the account exposes it.
        for tool, args in (
            ("pine_search_script", {"query": q, "limit": limit}),
            ("pine_search_scripts", {"query": q, "limit": limit}),
            ("search_scripts", {"query": q, "limit": limit}),
        ):
            try:
                raw = await self.call_tool(tool, args)
            except TvremixError:
                continue
            items = _coerce_script_list(raw)
            if items:
                return items[:limit]
            if isinstance(raw, list):
                return [x for x in raw if isinstance(x, dict)][:limit]

        # Fallback: list + read + substring scan (slower; capped).
        scripts = await self.list_pine_scripts()
        hits: list[dict[str, Any]] = []
        needle = q.lower()
        for item in scripts[:40]:
            sid = str(item.get("id") or item.get("scriptId") or item.get("script_id") or "")
            name = str(item.get("name") or item.get("title") or sid)
            try:
                read = await self.read_pine_script(sid, name=name)
            except TvremixError:
                continue
            source = read.get("source") or ""
            if needle not in source.lower() and needle not in name.lower():
                continue
            lines = []
            for i, line in enumerate(source.splitlines(), start=1):
                if needle in line.lower():
                    lines.append({"line": i, "text": line.strip()[:240]})
                    if len(lines) >= 8:
                        break
            hits.append(
                {
                    "id": sid,
                    "name": name,
                    "match_count": len(lines),
                    "matches": lines,
                    "tool": "local_scan",
                }
            )
            if len(hits) >= limit:
                break
        return hits

    async def read_pine_lines(
        self,
        script_id: str,
        *,
        start_line: int,
        end_line: int,
        name: str | None = None,
    ) -> dict[str, Any]:
        """Read a line slice of a Pine script (1-indexed, inclusive)."""
        start = max(1, int(start_line))
        end = max(start, int(end_line))
        for tool, args in (
            (
                "pine_read_lines",
                {"id": script_id, "start": start, "end": end},
            ),
            (
                "pine_read_lines",
                {"scriptId": script_id, "startLine": start, "endLine": end},
            ),
        ):
            try:
                raw = await self.call_tool(tool, args)
            except TvremixError:
                continue
            source = _extract_source(raw)
            if source:
                return {
                    "id": script_id,
                    "name": name or script_id,
                    "start_line": start,
                    "end_line": end,
                    "source": source,
                    "tool": tool,
                }
        full = await self.read_pine_script(script_id, name=name)
        lines = (full.get("source") or "").splitlines()
        sliced = "\n".join(lines[start - 1 : end])
        return {
            "id": script_id,
            "name": full.get("name") or name or script_id,
            "start_line": start,
            "end_line": min(end, len(lines)),
            "source": sliced,
            "tool": "pine_read_script+slice",
            "total_lines": len(lines),
        }

    async def get_pine_errors(self, script_id: str | None = None, *, source: str | None = None) -> dict[str, Any]:
        """Compile-check Pine via MCP when available."""
        args_list: list[dict[str, Any]] = []
        if script_id:
            args_list.extend(
                [
                    {"id": script_id},
                    {"scriptId": script_id},
                    {"script_id": script_id},
                ]
            )
        if source:
            args_list.append({"source": source})
            args_list.append({"code": source})
        last_err: str | None = None
        for tool in ("pine_get_errors", "pine_check", "pine_compile", "get_pine_errors"):
            for args in args_list or [{}]:
                try:
                    raw = await self.call_tool(tool, args)
                except TvremixError as exc:
                    last_err = str(exc)
                    continue
                if raw is None:
                    continue
                if isinstance(raw, dict):
                    return {"ok": not bool(raw.get("errors") or raw.get("diagnostics")), "tool": tool, "result": raw}
                if isinstance(raw, list):
                    return {"ok": len(raw) == 0, "tool": tool, "errors": raw}
                return {"ok": True, "tool": tool, "result": raw}
        return {
            "ok": False,
            "tool": None,
            "error": last_err or "pine_get_errors not available on this tvremix account",
        }

    async def get_strategy_report(self, **kwargs: Any) -> dict[str, Any]:
        try:
            raw = await self.call_tool("get_strategy_report", kwargs)
        except TvremixError as exc:
            raise TvremixError(f"get_strategy_report unavailable: {exc}") from exc
        if isinstance(raw, dict):
            return raw
        return {"raw": raw}

    async def strategy_sweep(self, **kwargs: Any) -> dict[str, Any]:
        for tool in ("strategy_sweep", "run_strategy_sweep", "pine_strategy_sweep"):
            try:
                raw = await self.call_tool(tool, kwargs)
            except TvremixError:
                continue
            if isinstance(raw, dict):
                return {"tool": tool, **raw}
            return {"tool": tool, "raw": raw}
        raise TvremixError("strategy_sweep not available on this tvremix account")

    async def analyze_multi_timeframe(self, symbol: str, *, intervals: list[str] | None = None) -> dict[str, Any]:
        tv_symbol = _to_tv_symbol(symbol)
        ivals = intervals or ["5m", "15m", "1h", "4h"]
        for tool, args in (
            ("analyze_multi_timeframe", {"symbol": tv_symbol, "intervals": ivals}),
            ("analyze_multi_timeframe", {"symbol": tv_symbol, "timeframes": ivals}),
            ("get_multi_timeframe", {"symbol": tv_symbol, "intervals": ivals}),
        ):
            try:
                raw = await self.call_tool(tool, args)
            except TvremixError:
                continue
            if isinstance(raw, dict):
                return {"tool": tool, "symbol": tv_symbol, **raw}
            if raw is not None:
                return {"tool": tool, "symbol": tv_symbol, "raw": raw}
        # Soft fallback: technicals per interval
        per: dict[str, Any] = {}
        for iv in ivals:
            tech = await self.fetch_technicals(symbol, interval=iv)
            if tech:
                per[iv] = tech
        if not per:
            raise TvremixError("analyze_multi_timeframe unavailable")
        return {"tool": "get_technicals_rating*fallback", "symbol": tv_symbol, "by_interval": per}


def parse_pine_inputs(source: str) -> dict[str, Any]:
    """Best-effort extract of input.* defaults from Pine v5 source."""
    inputs: dict[str, Any] = {}
    if not source:
        return inputs
    # len = input.int(14, "RSI Length")  OR  input.float(2.5, title="BB Mult")
    pattern = re.compile(
        r"(?:(?P<var>\w+)\s*=\s*)?input\.(?P<kind>int|float|bool|string)\s*\(\s*"
        r"(?P<default>[^,\)]+)\s*"
        r"(?:,\s*(?:title\s*=\s*)?[\"'](?P<title>[^\"']+)[\"'])?",
        re.IGNORECASE,
    )
    for match in pattern.finditer(source):
        var = match.group("var")
        kind = (match.group("kind") or "string").lower()
        raw_default = (match.group("default") or "").strip().strip("\"'")
        title = match.group("title")
        key = title or var or f"input_{len(inputs)}"
        if kind == "int":
            try:
                inputs[key] = int(float(raw_default))
            except ValueError:
                inputs[key] = raw_default
        elif kind == "float":
            try:
                inputs[key] = float(raw_default)
            except ValueError:
                inputs[key] = raw_default
        elif kind == "bool":
            inputs[key] = raw_default.lower() in {"true", "1"}
        else:
            inputs[key] = raw_default
    return inputs


def scripts_to_strategies(scripts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for item in scripts:
        sid = str(item.get("id") or item.get("scriptId") or item.get("script_id") or "")
        name = str(item.get("name") or item.get("title") or item.get("description") or sid)
        if not sid:
            sid = name
        kind = "pine_tvremix"
        lower = name.lower()
        if "ema" in lower and "cross" in lower:
            kind = "ema_cross"
        elif "smc" in lower:
            kind = "smc"
        source = item.get("source") or item.get("pine") or item.get("code")
        inputs = parse_pine_inputs(str(source)) if source else {}
        out.append(
            {
                "id": sid,
                "name": name,
                "kind": kind,
                "pane": "overlay",
                "inputs": inputs,
                "hasSource": bool(source),
                "origin": item.get("origin") or "tvremix",
            }
        )
    return out


_shared_client: TvremixClient | None = None
_shared_client_signature: tuple[str, str, float] | None = None


def get_tvremix_client(settings: Settings | None = None) -> TvremixClient:
    """Reuse MCP discovery/session state until connection settings change."""
    global _shared_client, _shared_client_signature

    cfg = settings or get_settings()
    signature = (
        (cfg.tvremix_mcp_url or DEFAULT_MCP_URL).rstrip("/"),
        (cfg.tvremix_api_key or "").strip(),
        float(cfg.tvremix_timeout_seconds),
    )
    if _shared_client is None or _shared_client_signature != signature:
        _shared_client = TvremixClient(cfg)
        _shared_client_signature = signature
    return _shared_client


def _parse_mcp_body(body: str) -> Any:
    text = (body or "").strip()
    if not text:
        return {}
    if text.startswith("{"):
        return json.loads(text)
    # SSE: data: {...}
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("data:"):
            chunk = line[5:].strip()
            if chunk and chunk != "[DONE]":
                try:
                    return json.loads(chunk)
                except json.JSONDecodeError:
                    continue
    return {"raw": text[:500]}


def _unwrap_tool_result(result: Any) -> Any:
    if not isinstance(result, dict):
        return result
    content = result.get("content")
    if isinstance(content, list):
        texts = []
        for part in content:
            if isinstance(part, dict) and part.get("type") == "text":
                texts.append(str(part.get("text") or ""))
        joined = "\n".join(texts).strip()
        if joined:
            try:
                return json.loads(joined)
            except json.JSONDecodeError:
                return joined
    if "structuredContent" in result:
        return result["structuredContent"]
    return result


def _coerce_script_list(raw: Any) -> list[dict[str, Any]]:
    if raw is None:
        return []
    if isinstance(raw, list):
        return [x for x in raw if isinstance(x, dict)]
    if isinstance(raw, dict):
        for key in ("scripts", "items", "data", "results", "saved", "session"):
            val = raw.get(key)
            if isinstance(val, list):
                return [x for x in val if isinstance(x, dict)]
        # single script object
        if raw.get("id") or raw.get("name") or raw.get("source"):
            return [raw]
    return []


def _extract_source(raw: Any) -> str:
    if isinstance(raw, str):
        return raw
    if not isinstance(raw, dict):
        return ""
    for key in ("source", "pine", "code", "script", "content", "text"):
        val = raw.get(key)
        if isinstance(val, str) and val.strip():
            return val
    nested = raw.get("data")
    if isinstance(nested, dict):
        return _extract_source(nested)
    return ""


def _extract_name(raw: Any) -> str | None:
    if isinstance(raw, dict):
        for key in ("name", "title", "description"):
            if raw.get(key):
                return str(raw[key])
    return None


def _to_tv_symbol(symbol: str) -> str:
    s = (symbol or "BTCUSD").upper().replace("/", "")
    if ":" in s:
        return s
    mapping = {
        "BTCUSD": "BINANCE:BTCUSDT",
        "ETHUSD": "BINANCE:ETHUSDT",
        "SOLUSD": "BINANCE:SOLUSDT",
        "XRPUSD": "BINANCE:XRPUSDT",
        "ADAUSD": "BINANCE:ADAUSDT",
    }
    return mapping.get(s, f"BINANCE:{s}" if s.endswith("USD") else s)


def _bars_from_ohlcv(raw: Any) -> list[dict[str, float]]:
    bars: list[Any] = []
    if isinstance(raw, list):
        bars = raw
    elif isinstance(raw, dict):
        for key in ("bars", "data", "ohlcv", "candles"):
            if isinstance(raw.get(key), list):
                bars = raw[key]
                break
    out: list[dict[str, float]] = []
    for bar in bars:
        if isinstance(bar, dict):
            close = bar.get("close") or bar.get("c")
            if close is None:
                continue
            out.append(
                {
                    "open": float(bar.get("open") or bar.get("o") or close),
                    "high": float(bar.get("high") or bar.get("h") or close),
                    "low": float(bar.get("low") or bar.get("l") or close),
                    "close": float(close),
                }
            )
        elif isinstance(bar, (list, tuple)) and len(bar) >= 5:
            out.append(
                {
                    "open": float(bar[1]),
                    "high": float(bar[2]),
                    "low": float(bar[3]),
                    "close": float(bar[4]),
                }
            )
    return out
