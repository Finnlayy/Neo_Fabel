import React, { useMemo } from "react";
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  Cell,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { ChronosBacktestResponse, ChronosIndicatorsResponse } from "../../api/chronos";

type ClosePoint = { i: number; close: number };

type Props = {
  bars: number[][] | null;
  indicators: ChronosIndicatorsResponse | null;
  backtest: ChronosBacktestResponse | null;
  s1Ids?: number[];
  s2Ids?: number[];
  language?: "en" | "de";
};

function fmtNum(n: number | null | undefined, digits = 2): string {
  if (n == null || !Number.isFinite(n)) return "—";
  return n.toFixed(digits);
}

function rsiColor(rsi: number): string {
  if (rsi >= 70) return "#f87171";
  if (rsi <= 30) return "#34d399";
  return "#22d3ee";
}

export default function ChronosVisualizations({
  bars,
  indicators,
  backtest,
  s1Ids,
  s2Ids,
  language = "en",
}: Props) {
  const de = language === "de";

  const closeSeries = useMemo<ClosePoint[]>(() => {
    if (!bars?.length) return [];
    return bars.map((row, i) => ({ i, close: row[3] }));
  }, [bars]);

  const tokenHist = useMemo(() => {
    if (!s1Ids?.length) return [];
    const counts = new Map<number, number>();
    for (const id of s1Ids) counts.set(id, (counts.get(id) ?? 0) + 1);
    return [...counts.entries()]
      .sort((a, b) => b[1] - a[1])
      .slice(0, 12)
      .map(([id, count]) => ({ id: String(id), count }));
  }, [s1Ids]);

  const rsi = indicators?.indicators.rsi;
  const emaDist = indicators?.indicators.ema_distance_pct;
  const atrPct = indicators?.indicators.atr_pct;

  if (!bars?.length && !indicators && !backtest && !tokenHist.length) {
    return (
      <p className="text-[11px] text-slate-500 font-mono">
        {de
          ? "Lade Lookback-Bars, um Charts und Indikatoren zu sehen."
          : "Load lookback bars to see charts and indicators."}
      </p>
    );
  }

  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
      {closeSeries.length >= 2 ? (
        <figure className="bg-slate-900/50 border border-white/5 rounded-xl p-3 space-y-2">
          <figcaption className="text-[9px] text-cyan-300/90 uppercase tracking-widest font-mono">
            {de ? "Close-Verlauf (Lookback)" : "Close series (lookback)"}
          </figcaption>
          <div className="h-44">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={closeSeries} margin={{ top: 4, right: 4, left: 0, bottom: 0 }}>
                <defs>
                  <linearGradient id="chronosCloseFill" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="#22d3ee" stopOpacity={0.35} />
                    <stop offset="100%" stopColor="#22d3ee" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <XAxis dataKey="i" hide />
                <YAxis
                  domain={["auto", "auto"]}
                  tick={{ fill: "#64748b", fontSize: 9 }}
                  width={48}
                  tickFormatter={(v) => Number(v).toFixed(0)}
                />
                <Tooltip
                  contentStyle={{
                    background: "#0f172a",
                    border: "1px solid rgba(255,255,255,0.08)",
                    fontSize: 10,
                    fontFamily: "monospace",
                  }}
                  formatter={(v: number) => [v.toFixed(4), "close"]}
                  labelFormatter={(l) => `bar ${l}`}
                />
                <Area
                  type="monotone"
                  dataKey="close"
                  stroke="#22d3ee"
                  strokeWidth={1.5}
                  fill="url(#chronosCloseFill)"
                  dot={false}
                />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </figure>
      ) : null}

      {indicators ? (
        <figure className="bg-slate-900/50 border border-white/5 rounded-xl p-3 space-y-3">
          <figcaption className="text-[9px] text-violet-300/90 uppercase tracking-widest font-mono">
            {de ? "Technische Indikatoren" : "Technical indicators"}
          </figcaption>
          <div className="grid grid-cols-3 gap-2">
            <div className="rounded-lg border border-white/5 bg-slate-950/60 p-2 text-center">
              <div className="text-[8px] text-slate-500 uppercase tracking-wider">RSI</div>
              <div
                className="text-lg font-bold tabular-nums mt-1"
                style={{ color: rsi != null ? rsiColor(rsi) : "#94a3b8" }}
              >
                {fmtNum(rsi, 1)}
              </div>
              {rsi != null ? (
                <div className="mt-2 h-1.5 rounded-full bg-slate-800 overflow-hidden">
                  <div
                    className="h-full rounded-full transition-all"
                    style={{ width: `${Math.min(100, rsi)}%`, background: rsiColor(rsi) }}
                  />
                </div>
              ) : null}
            </div>
            <div className="rounded-lg border border-white/5 bg-slate-950/60 p-2 text-center">
              <div className="text-[8px] text-slate-500 uppercase tracking-wider">EMA Δ%</div>
              <div
                className={`text-lg font-bold tabular-nums mt-1 ${
                  emaDist != null && emaDist > 0
                    ? "text-emerald-400"
                    : emaDist != null && emaDist < 0
                      ? "text-rose-400"
                      : "text-slate-300"
                }`}
              >
                {emaDist != null ? `${emaDist >= 0 ? "+" : ""}${fmtNum(emaDist)}%` : "—"}
              </div>
            </div>
            <div className="rounded-lg border border-white/5 bg-slate-950/60 p-2 text-center">
              <div className="text-[8px] text-slate-500 uppercase tracking-wider">ATR %</div>
              <div className="text-lg font-bold tabular-nums mt-1 text-amber-300">{fmtNum(atrPct)}%</div>
            </div>
          </div>
          <p className="text-[9px] text-slate-500 font-mono">{indicators.engine}</p>
        </figure>
      ) : null}

      {tokenHist.length > 0 ? (
        <figure className="bg-slate-900/50 border border-white/5 rounded-xl p-3 space-y-2 lg:col-span-2">
          <figcaption className="text-[9px] text-cyan-300/90 uppercase tracking-widest font-mono">
            {de ? "Coarse-Token-Verteilung (Top 12)" : "Coarse token distribution (top 12)"}
            {s2Ids?.length ? ` · ${s2Ids.length} fine ids` : ""}
          </figcaption>
          <div className="h-36">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={tokenHist} margin={{ top: 4, right: 4, left: 0, bottom: 0 }}>
                <XAxis dataKey="id" tick={{ fill: "#64748b", fontSize: 8 }} interval={0} angle={-35} textAnchor="end" height={36} />
                <YAxis tick={{ fill: "#64748b", fontSize: 9 }} width={28} allowDecimals={false} />
                <Tooltip
                  contentStyle={{
                    background: "#0f172a",
                    border: "1px solid rgba(255,255,255,0.08)",
                    fontSize: 10,
                    fontFamily: "monospace",
                  }}
                />
                <Bar dataKey="count" radius={[3, 3, 0, 0]}>
                  {tokenHist.map((_, idx) => (
                    <Cell key={idx} fill={`hsl(${190 + idx * 8}, 70%, 55%)`} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </figure>
      ) : null}

      {backtest ? (
        <figure className="bg-slate-900/50 border border-emerald-500/10 rounded-xl p-3 space-y-3 lg:col-span-2">
          <figcaption className="text-[9px] text-emerald-300/90 uppercase tracking-widest font-mono">
            {de ? "Paper-Backtest (vectorbt)" : "Paper backtest (vectorbt)"}
          </figcaption>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
            <Stat label={de ? "Strategie" : "Strategy"} value={backtest.strategy} />
            <Stat
              label={de ? "Rendite %" : "Return %"}
              value={`${fmtNum(backtest.total_return_pct)}%`}
              tone={backtest.total_return_pct >= 0 ? "up" : "down"}
            />
            <Stat label="Sharpe" value={fmtNum(backtest.sharpe, 3)} />
            <Stat
              label={de ? "Max DD %" : "Max DD %"}
              value={`${fmtNum(backtest.max_drawdown_pct)}%`}
              tone="down"
            />
          </div>
          <p className="text-[9px] text-slate-500 font-mono">
            {de ? "Trades" : "Trades"}: {backtest.trades} · {de ? "Nur Paper — keine Live-Orders" : "Paper only — no live orders"}
          </p>
        </figure>
      ) : null}
    </div>
  );
}

function Stat({
  label,
  value,
  tone,
}: {
  label: string;
  value: string;
  tone?: "up" | "down";
}) {
  const color =
    tone === "up" ? "text-emerald-400" : tone === "down" ? "text-rose-400" : "text-slate-100";
  return (
    <div className="rounded-lg border border-white/5 bg-slate-950/60 p-2">
      <div className="text-[8px] text-slate-500 uppercase tracking-wider">{label}</div>
      <div className={`text-sm font-bold tabular-nums mt-1 truncate ${color}`}>{value}</div>
    </div>
  );
}
