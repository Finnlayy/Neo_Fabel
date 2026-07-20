"""TVAPI optimize: candle backtest + tvremix Pine list/read."""

from __future__ import annotations

from typing import Any

from backend.app.integrations.backtest.ema_grid import run_candle_optimize, synthetic_candles
from backend.app.integrations.tvremix_client import (
    TvremixClient,
    TvremixError,
    parse_pine_inputs,
    scripts_to_strategies,
)
from backend.app.settings import get_settings


def _probe_strategies(symbol: str) -> list[dict[str, Any]]:
    return [
        {
            "id": "ltm_willy_v130",
            "name": "Liquidity Trail Matrix [WillyAlgoTrader] v1.3",
            "kind": "ltm",
            "pane": "overlay",
            "inputs": {
                "bandPreset": "Balanced",
                "flipBand": "Balanced (Band 3)",
                "minScore": 80,
                "retestWindow": 8,
                "cooldown": 5,
                "atrLen": 13,
                "riskPreset": "Balanced",
                "slMode": "Wick-Anchored",
            },
            "origin": "probe",
            "hasSource": True,
            "note": "Precision analyzer: ATR trail + scored retests (Neo LTM port)",
        },
        {
            "id": "ema_cross_grid",
            "name": "EMA Cross Grid (candle backtest)",
            "kind": "ema_cross",
            "pane": "overlay",
            "inputs": {
                "emaFast": 8,
                "emaSlow": 21,
                "takeProfitPct": 1.5,
                "stopLossPct": 1.0,
            },
            "origin": "probe",
        },
        {
            "id": "neo_quantum_smc",
            "name": "Neo-Quantum SMC [Cluster Optimized]",
            "kind": "smc",
            "pane": "overlay",
            "inputs": {
                "Structure Length": 5,
                "Base Risk (%)": 1.0,
                "Risk:Reward Ratio": 2.0,
                "swingLength": 5,
                "displacement": 1.0,
            },
            "origin": "probe",
        },
        {
            "id": "bb_rsi_hard_sl",
            "name": "BB / RSI Hard SL Sweep",
            "kind": "bb_rsi_sl",
            "pane": "overlay",
            "inputs": {
                "in_0": 14,
                "in_1": 2.5,
                "in_2": 1.0,
                "in_6": 14,
            },
            "origin": "probe",
        },
        {
            "id": "trailing_exit_sweep",
            "name": "Trailing Exit Sweep",
            "kind": "trailing",
            "pane": "overlay",
            "inputs": {
                "in_3": 0.20,
                "in_4": 0.10,
                "trailPct": 0.8,
            },
            "origin": "probe",
        },
        {
            "id": "btc_luxalgo_confluence_15m_v1",
            "name": "BTCUSDT.P 15m LuxAlgo Confluence Strategy",
            "kind": "pine_bundled",
            "pane": "overlay",
            "inputs": {},
            "origin": "probe",
            "hasSource": True,
            "note": "Bundled under assets/strategies/BTCUSDT_P_15m_LuxAlgo_Confluence_Strategy_v1.pine",
        },
        {
            "id": "btc_pf2_duration_15m_v1",
            "name": "BTCUSDT.P 15m PF2 Duration Strategy",
            "kind": "pine_bundled",
            "pane": "overlay",
            "inputs": {},
            "origin": "probe",
            "hasSource": True,
            "note": "Bundled under assets/strategies/BTCUSDT_P_15m_PF2_Duration_Strategy_v1.pine",
        },
        {
            "id": "clean_trade_quantum_v8",
            "name": "CleanTradeQuantum Refactored v8",
            "kind": "smc",
            "pane": "overlay",
            "inputs": {},
            "origin": "probe",
            "hasSource": True,
            "note": "Bundled under assets/strategies/CleanTradeQuantum_Refactored_v8_fixed.pine",
        },
        {
            "id": "competition_hype_1m_pionex",
            "name": "CompetitionBot HYPEUSDT 1m (Pionex)",
            "kind": "pine_bundled",
            "pane": "overlay",
            "inputs": {},
            "origin": "probe",
            "hasSource": True,
            "note": "Bundled under assets/strategies/CompetitionBot_HYPEUSDT_1m_output1_pionex.pine",
        },
        {
            "id": "eth_glintnews_pionex_v6",
            "name": "ETH/USDT GlintNews PionexBot v6",
            "kind": "pine_bundled",
            "pane": "overlay",
            "inputs": {},
            "origin": "probe",
            "hasSource": True,
            "note": "Bundled under assets/strategies/ETH_USDT_GlintNews_PionexBot_v6_strategy.pine",
        },
        {
            "id": "luxalgo_connector_bridge_v1",
            "name": "LuxAlgo Connector Strategy Bridge v1",
            "kind": "pine_bundled",
            "pane": "overlay",
            "inputs": {},
            "origin": "probe",
            "hasSource": True,
            "note": "Bundled under assets/strategies/LuxAlgo_Connector_Strategy_Bridge_v1.pine",
        },
        {
            "id": "mem_mtf_cisd_montecarlo_v6",
            "name": "Mem MTF CISD MonteCarlo Pionex v6",
            "kind": "smc",
            "pane": "overlay",
            "inputs": {},
            "origin": "probe",
            "hasSource": True,
            "note": "Bundled under assets/strategies/Mem_MTF_CISD_MonteCarlo_Pionex_v6.pine",
        },
        {
            "id": "mtf_cisd_ob_fvg_wti5m_live",
            "name": "MTF CISD OB/FVG WTI 5m Live",
            "kind": "smc",
            "pane": "overlay",
            "inputs": {},
            "origin": "probe",
            "hasSource": True,
            "note": "Bundled under assets/strategies/MTF_CISD_OB_FVG_v2_WTI5M_STRATEGY_LIVE.pine",
        },
        {
            "id": "onnx_qm_hub_v2_strategy",
            "name": "ONNX Quant Management Hub v2 (Strategy)",
            "kind": "pine_bundled",
            "pane": "overlay",
            "inputs": {},
            "origin": "probe",
            "hasSource": True,
            "note": "Bundled under assets/strategies/ONNX_QM_Hub_v2_strategy.pine",
        },
        {
            "id": "onnx_qm_hub_v2",
            "name": "ONNX Quant Management Hub v2",
            "kind": "pine_bundled",
            "pane": "overlay",
            "inputs": {},
            "origin": "probe",
            "hasSource": True,
            "note": "Bundled under assets/strategies/ONNX_Quant_Management_Hub_v2.pine",
        },
        {
            "id": "pin_bar_magic_v1",
            "name": "Pin Bar Magic v1",
            "kind": "pine_bundled",
            "pane": "overlay",
            "inputs": {},
            "origin": "probe",
            "hasSource": True,
            "note": "Bundled under assets/strategies/Pin_Bar_Magic_v1_fixed.pine",
        },
        {
            "id": "quantum_forex_pionex_direct_v2",
            "name": "QuantumForexTrader v2 (Pionex Direct)",
            "kind": "pine_bundled",
            "pane": "overlay",
            "inputs": {},
            "origin": "probe",
            "hasSource": True,
            "note": "Bundled under assets/strategies/QuantumForexTrader_v2_reconstructed_pionex_direct.pine",
        },
        {
            "id": "recovery_center_alpha_mos_v6",
            "name": "Recovery Center Alpha + MOS BTC 5m v6",
            "kind": "pine_bundled",
            "pane": "overlay",
            "inputs": {},
            "origin": "probe",
            "hasSource": True,
            "note": "Bundled under assets/strategies/Recovery_Center_Alpha_MOS_BTCUSDT_P_5m_optimized_v6.pine",
        },
        {
            "id": "recovery_center_alpha_v1",
            "name": "Recovery Center Alpha Working v1",
            "kind": "pine_bundled",
            "pane": "overlay",
            "inputs": {},
            "origin": "probe",
            "hasSource": True,
            "note": "Bundled under assets/strategies/Recovery_Center_Alpha_working_v1.pine",
        },
        {
            "id": "wti_quantdesk_pro_v4_1",
            "name": "WTI/USDT QuantDesk Pro v4.1",
            "kind": "pine_bundled",
            "pane": "overlay",
            "inputs": {},
            "origin": "probe",
            "hasSource": True,
            "note": "Bundled under assets/strategies/WTI_USDT_QuantDesk_Pro_v4_1_fixed.pine",
        },
        {
            "id": "bprc_pro_institutional_v3",
            "name": "BPRC PRO Institutional Strategy v3",
            "kind": "pine_bundled",
            "pane": "overlay",
            "inputs": {},
            "origin": "probe",
            "hasSource": True,
            "note": "Bundled under assets/strategies/BPRC_PRO_Institutional_Strategy_clean_v3_alertcalls.pine",
        },
        {
            "id": "cleanroom_inst_imbalance_pionex",
            "name": "Cleanroom Institutional Imbalance Framework - Pionex",
            "kind": "pine_bundled",
            "pane": "overlay",
            "inputs": {
                "Tracked FVGs": 80,
                "Minimum FVG Width ATR": 0.05,
                "Institutional Quality Threshold": 1.45,
                "CVMI Normalization Length": 120,
                "Order Block Timeframe": "60",
            },
            "origin": "probe",
            "hasSource": True,
            "note": "Bundled under assets/strategies/Cleanroom_Institutional_Imbalance_Pionex.pine",
        },
    ]


async def list_chart_strategies(symbol: str) -> dict[str, Any]:
    """List strategies: tvremix Pine (session/saved) + local probe catalog.

    Both when tvremix is configured; probe-only fallback otherwise.
    """
    sym = (symbol or "BTCUSD").upper()
    settings = get_settings()
    probe = _probe_strategies(sym)
    note_parts: list[str] = []
    tvremix_rows: list[dict[str, Any]] = []
    source = "chart-layout-probe"
    error: str | None = None

    if settings.tvremix_enabled and settings.tvremix_api_key:
        client = TvremixClient(settings)
        try:
            scripts = await client.list_pine_scripts()
            tvremix_rows = scripts_to_strategies(scripts)
            if tvremix_rows:
                source = "tvremix+probe"
                note_parts.append(
                    f"Loaded {len(tvremix_rows)} Pine script(s) via tvremix MCP "
                    f"({settings.tvremix_mcp_url})."
                )
            else:
                source = "probe+tvremix-empty"
                note_parts.append(
                    "tvremix connected but no Pine scripts returned "
                    "(link TradingView in the tvremix extension for session/saved scripts, "
                    "or ensure pine_list_* tools are enabled for your key)."
                )
        except TvremixError as exc:
            error = str(exc)
            source = "probe+tvremix-error"
            note_parts.append(f"tvremix unavailable ({exc}); using probe catalog.")
    else:
        note_parts.append(
            "Set TVREMIX_API_KEY (https://tvremix.xyz/account#api-keys) to list your "
            "TradingView Pine strategies via MCP. Probe catalog remains available."
        )

    # tvremix first (user strategies), then probe fallbacks
    merged = [*tvremix_rows, *probe]
    return {
        "success": True,
        "symbol": sym,
        "strategies": merged,
        "source": source,
        "tvremixConfigured": bool(settings.tvremix_api_key),
        "tvremixCount": len(tvremix_rows),
        "note": " ".join(note_parts),
        "error": error,
    }


def list_chart_strategies_sync(symbol: str) -> dict[str, Any]:
    """Sync probe-only helper for unit tests that avoid asyncio."""
    sym = (symbol or "BTCUSD").upper()
    return {
        "success": True,
        "symbol": sym,
        "strategies": _probe_strategies(sym),
        "source": "chart-layout-probe",
        "note": "Sync probe catalog (no tvremix).",
    }


def _bars_from_ccxt(rows: list[list[Any]]) -> list[dict[str, float]]:
    candles: list[dict[str, float]] = []
    for row in rows:
        if not isinstance(row, (list, tuple)) or len(row) < 5:
            continue
        candles.append(
            {
                "open": float(row[1]),
                "high": float(row[2]),
                "low": float(row[3]),
                "close": float(row[4]),
            }
        )
    return candles


async def fetch_optimize_candles(symbol: str, timeframe: str, *, limit: int = 300) -> tuple[list[dict[str, float]], str]:
    """Prefer tvremix OHLCV, then CCXT, then synthetic."""
    settings = get_settings()
    tf = (timeframe or "5m").lower().replace("min", "m")
    if tf in {"1", "5", "15", "30", "60"}:
        tf = f"{tf}m"
    elif tf == "1h":
        tf = "60m"

    if settings.tvremix_enabled and settings.tvremix_api_key:
        try:
            client = TvremixClient(settings)
            await client.initialize()
            bars = await client.fetch_ohlcv_bars(symbol, interval=tf if tf != "60m" else "1h", count=limit)
            if len(bars) >= 30:
                return bars, "tvremix-ohlcv"
        except Exception:  # noqa: BLE001
            pass

    client = None
    try:
        from backend.app.integrations.ccxt_market import CcxtMarketClient

        client = CcxtMarketClient()
        raw = await client.fetch_ohlcv(symbol, timeframe=tf, limit=limit)
        candles = _bars_from_ccxt(raw)
        if len(candles) >= 30:
            return candles, "ccxt-ohlcv"
    except Exception:  # noqa: BLE001
        pass
    finally:
        if client is not None:
            try:
                await client._exchange.close()  # noqa: SLF001
            except Exception:  # noqa: BLE001
                pass

    return synthetic_candles(symbol, n=limit), "synthetic-ohlcv"


def _load_bundled_ltm_pine() -> str:
    from pathlib import Path

    path = Path(__file__).resolve().parents[3] / "assets" / "strategies" / "liquidity_trail_matrix_v1_3_0.pine"
    if path.is_file():
        return path.read_text(encoding="utf-8")
    return ""


async def run_optimize(payload: dict[str, Any]) -> dict[str, Any]:
    """Candle backtest; optionally bind Pine from tvremix by scriptId / pineSource."""
    settings = get_settings()
    symbol = str(payload.get("symbol") or "BTCUSD")
    timeframe = str(payload.get("timeframe") or "5m")
    script_id = str(payload.get("scriptId") or "").strip()
    pine_name = str(payload.get("pineName") or "").strip()
    pine_source = str(payload.get("pineSource") or "").strip()
    parameters = dict(payload.get("parameters") or {})

    # Bundled LTM gold strategy (always available offline)
    wants_ltm = script_id in {"ltm_willy_v130", "ltm"} or str(payload.get("strategy") or "").lower() == "ltm"
    if not pine_source and wants_ltm:
        bundled = _load_bundled_ltm_pine()
        if bundled:
            pine_source = bundled
            pine_name = pine_name or "Liquidity Trail Matrix [WillyAlgoTrader] v1.3"
            script_id = script_id or "ltm_willy_v130"
            payload = {**payload, "strategy": "ltm", "pineName": pine_name, "scriptId": script_id}

    pine_meta: dict[str, Any] = {}
    if pine_source:
        pine_meta = {"id": script_id or "inline", "name": pine_name or "inline", "source": pine_source}
    elif script_id and settings.tvremix_enabled and settings.tvremix_api_key:
        try:
            client = TvremixClient(settings)
            pine_meta = await client.read_pine_script(script_id, name=pine_name or None)
            pine_source = str(pine_meta.get("source") or "")
        except TvremixError as exc:
            pine_meta = {"error": str(exc), "id": script_id, "name": pine_name}

    if pine_source:
        parsed = parse_pine_inputs(pine_source)
        # Parsed defaults first; explicit request parameters win.
        parameters = {**parsed, **parameters}
        payload = {**payload, "parameters": parameters}

    injected = payload.get("candles")
    if isinstance(injected, list) and len(injected) >= 30:
        candles = [
            {"close": float(c["close"]), "open": float(c.get("open", c["close"]))}
            for c in injected
            if isinstance(c, dict) and "close" in c
        ]
        source = "injected-ohlcv"
    else:
        candles, source = await fetch_optimize_candles(symbol, timeframe)

    result = run_candle_optimize(payload, candles, candle_source=source)
    if pine_meta.get("name") or pine_meta.get("id"):
        label = pine_meta.get("name") or pine_meta.get("id")
        if result.get("success"):
            result["bericht"] = (
                str(result.get("bericht") or "")
                + f"\n- Pine strategy: **{label}** (tvremix read / inline)\n"
                + f"- Parsed inputs: `{list((payload.get('parameters') or {}).keys())[:12]}`\n"
            )
            result["source"] = f"{result.get('source')}+tvremix-pine"
            result["pine"] = {
                "id": pine_meta.get("id"),
                "name": pine_meta.get("name"),
                "chars": len(pine_source),
                "error": pine_meta.get("error"),
            }
        elif pine_meta.get("error"):
            result["pine"] = pine_meta
    return result


def run_deterministic_optimize(payload: dict[str, Any]) -> dict[str, Any]:
    """Sync wrapper: synthetic candles only (no network). Prefer `run_optimize`."""
    symbol = str(payload.get("symbol") or "BTCUSD")
    candles = synthetic_candles(symbol, n=240)
    return run_candle_optimize(payload, candles, candle_source="synthetic-ohlcv")
