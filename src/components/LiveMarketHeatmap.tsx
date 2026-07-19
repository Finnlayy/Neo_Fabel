import React from "react";
import { TickerData } from "../types";
import { TrendingUp, TrendingDown, RefreshCw } from "lucide-react";

interface LiveMarketHeatmapProps {
  tickers: TickerData[];
  onSelectTicker: (symbol: string) => void;
  activeSymbol: string;
  marketLive?: boolean;
}

export default function LiveMarketHeatmap({ tickers, onSelectTicker, activeSymbol, marketLive = false }: LiveMarketHeatmapProps) {
  return (
    <div id="live-heatmap-card" className="bg-slate-900/40 border border-white/5 hover:border-white/10 rounded-xl p-5 font-mono text-xs space-y-4 transition-all duration-300">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-white/10 pb-3">
        <div className="flex items-center gap-2">
          <span className={`w-2 h-2 rounded-full ${marketLive ? "bg-emerald-400 animate-pulse" : "bg-amber-400"}`}></span>
          <h3 className="text-white font-bold uppercase tracking-wider text-[11px]">
            MARKET TELEMETRY TICKER
          </h3>
        </div>
        <span className={`text-[10px] uppercase flex items-center gap-1 font-mono ${marketLive ? "text-emerald-400" : "text-amber-400"}`}>
          <RefreshCw className={`w-3 h-3 ${marketLive ? "animate-spin" : ""}`} />
          {marketLive ? "LIVE STREAM" : "STALE / EMPTY"}
        </span>
      </div>

      {/* Grid */}
      {tickers.length === 0 ? (
        <div className="border border-dashed border-white/10 rounded-lg p-6 text-slate-500 text-[11px]">
          No ticker rows. Waiting for WS /api/v1/market/stream or GET /api/v1/market/batch.
        </div>
      ) : null}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
        {tickers.map((t) => {
          const isUp = t.change >= 0;
          const isActive = t.symbol === activeSymbol;

          return (
            <button
              key={t.symbol}
              type="button"
              onClick={() => onSelectTicker(t.symbol)}
              className={`p-3.5 rounded-xl border text-left transition-all duration-300 relative cursor-pointer overflow-hidden ${
                isActive
                  ? "bg-slate-900 border-cyan-500/80 glow-cyan ring-1 ring-cyan-500/10"
                  : isUp
                  ? "bg-slate-900/25 hover:bg-slate-900/50 border-emerald-500/10"
                  : "bg-slate-900/25 hover:bg-slate-900/50 border-rose-500/10"
              }`}
            >
              {/* Backing pulse indicator */}
              {isActive && (
                <div className="absolute right-2.5 top-2.5 w-1.5 h-1.5 rounded-full bg-cyan-400 animate-ping" />
              )}

              <div className="flex items-center justify-between mb-1.5">
                <span className="font-bold text-slate-200 tracking-tight text-[11px]">{t.symbol}</span>
                <span
                  className={`text-[9px] font-bold flex items-center gap-0.5 ${
                    isUp ? "text-emerald-400" : "text-rose-400"
                  }`}
                >
                  {isUp ? (
                    <TrendingUp className="w-2.5 h-2.5" />
                  ) : (
                    <TrendingDown className="w-2.5 h-2.5" />
                  )}
                  {isUp ? "+" : ""}
                  {t.change.toFixed(1)}%
                </span>
              </div>

              <div className="space-y-0.5">
                <p className="text-white font-bold text-[12px]">
                  ${t.price.toLocaleString(undefined, { minimumFractionDigits: t.price > 1 ? 2 : 4 })}
                </p>
                <p className="text-[9px] text-slate-500 uppercase">{t.name}</p>
              </div>

              {/* Ticker Mini Sparkline */}
              <div className="h-6 mt-3.5 flex items-end gap-0.5">
                {t.history.map((val, idx) => {
                  const maxVal = Math.max(...t.history);
                  const minVal = Math.min(...t.history);
                  const range = maxVal - minVal || 1;
                  const percent = Math.min(100, Math.max(10, ((val - minVal) / range) * 100));

                  return (
                    <div
                      key={idx}
                      className={`flex-1 rounded-t-sm transition-all duration-500 ${
                        isUp ? "bg-emerald-500/30" : "bg-rose-500/30"
                      }`}
                      style={{ height: `${percent}%` }}
                    />
                  );
                })}
              </div>
            </button>
          );
        })}
      </div>
    </div>
  );
}
