import React, { useEffect, useMemo, useRef, useState } from "react";
import { TickerData } from "../types";
import {
  ShieldAlert, ShieldCheck, Trash2, Activity, Play, RefreshCw,
} from "lucide-react";
import { ApiError } from "../api/client";
import { fetchOrderBook, type OrderBookResponse } from "../api/market";

interface RiskMetrics {
  volatility: number; // 0-100%
  leverageLimit: number; // e.g. 5x, 10x, 20x
  drawdownFactor: number; // 0-100%
  sentimentStress: number; // 0-100%
  compositeScore: number; // 0-100
}

interface WatchlistItem {
  symbol: string;
  name: string;
  basePrice: number;
  custom: boolean;
}

function historyVolatilityPct(history: number[]): number {
  if (history.length < 2) return 0;
  const returns: number[] = [];
  for (let i = 1; i < history.length; i++) {
    const prev = history[i - 1];
    const cur = history[i];
    if (prev > 0) returns.push((cur - prev) / prev);
  }
  if (returns.length === 0) return 0;
  const mean = returns.reduce((a, b) => a + b, 0) / returns.length;
  const variance = returns.reduce((a, b) => a + (b - mean) ** 2, 0) / returns.length;
  const std = Math.sqrt(variance);
  return Math.max(0, Math.min(99, std * 100 * 12));
}

function metricsFromTicker(ticker: TickerData | undefined, fallbackPrice: number): RiskMetrics | null {
  const price = ticker?.price ?? fallbackPrice;
  if (!price || price <= 0) return null;

  const change = Math.abs(ticker?.change ?? 0);
  const history = ticker?.history?.filter((n) => n > 0) ?? [];
  const series = history.length >= 2 ? history : [price];
  const vol = historyVolatilityPct(series);
  const rangePct =
    series.length >= 2
      ? ((Math.max(...series) - Math.min(...series)) / Math.max(...series)) * 100
      : change;
  const drawdownFactor = Math.max(0, Math.min(95, Math.max(change * 1.4, rangePct)));
  const sentimentStress = Math.max(0, Math.min(99, change * 2.2 + vol * 0.35));
  let levLimit = 20;
  if (vol > 60 || drawdownFactor > 40) levLimit = 3;
  else if (vol > 45 || drawdownFactor > 25) levLimit = 5;
  else if (vol > 30 || drawdownFactor > 15) levLimit = 10;
  const composite = Math.round(
    Math.min(100, vol * 0.4 + drawdownFactor * 0.3 + sentimentStress * 0.3),
  );
  return {
    volatility: Number(vol.toFixed(1)),
    leverageLimit: levLimit,
    drawdownFactor: Number(drawdownFactor.toFixed(1)),
    sentimentStress: Number(sentimentStress.toFixed(1)),
    compositeScore: composite,
  };
}

function bookImbalance(book: OrderBookResponse): { bidVol: number; askVol: number; ratio: number } {
  const bidVol = book.bids.slice(0, 10).reduce((sum, level) => sum + level.volume, 0);
  const askVol = book.asks.slice(0, 10).reduce((sum, level) => sum + level.volume, 0);
  const total = bidVol + askVol;
  return { bidVol, askVol, ratio: total > 0 ? bidVol / total : 0.5 };
}

export default function RiskAssessmentHeatmap({
  tickers,
  marketLive = false,
  marketAsOf = null,
}: {
  tickers: TickerData[];
  marketLive?: boolean;
  marketAsOf?: string | null;
}) {
  const [watchlist, setWatchlist] = useState<WatchlistItem[]>([
    { symbol: "BTC", name: "Bitcoin", basePrice: 0, custom: false },
    { symbol: "ETH", name: "Ethereum", basePrice: 0, custom: false },
    { symbol: "SOL", name: "Solana", basePrice: 0, custom: false },
    { symbol: "MATIC", name: "Polygon", basePrice: 0, custom: false },
    { symbol: "AVAX", name: "Avalanche", basePrice: 0, custom: false },
    { symbol: "DOT", name: "Polkadot", basePrice: 0, custom: false },
    { symbol: "XRP", name: "Ripple", basePrice: 0, custom: false },
    { symbol: "ADA", name: "Cardano", basePrice: 0, custom: false },
    { symbol: "NIO", name: "NIO Inc. (EV)", basePrice: 0, custom: false },
  ]);

  const [newSymbol, setNewSymbol] = useState("");
  const [newName, setNewName] = useState("");
  const [addError, setAddError] = useState<string | null>(null);
  const [riskFilter, setRiskFilter] = useState<"ALL" | "LOW" | "MODERATE" | "HIGH" | "EXTREME">("ALL");
  const [auditingSymbol, setAuditingSymbol] = useState<string | null>(null);
  const [auditProgress, setAuditProgress] = useState(0);
  const [auditLogs, setAuditLogs] = useState<string[]>([]);
  const [selectedAuditSymbol, setSelectedAuditSymbol] = useState<string | null>("BTC");
  const [riskData, setRiskData] = useState<Record<string, RiskMetrics>>({});
  const auditTokenRef = useRef(0);

  useEffect(() => {
    setWatchlist((prev) => {
      const next = prev.map((item) => {
        const live = tickers.find((t) => t.symbol === item.symbol);
        if (!live) return item;
        return { ...item, name: live.name || item.name, basePrice: live.price };
      });
      const updated: Record<string, RiskMetrics> = {};
      for (const item of next) {
        const live = tickers.find((t) => t.symbol === item.symbol);
        const metrics = metricsFromTicker(live, item.basePrice);
        if (metrics) updated[item.symbol] = metrics;
      }
      setRiskData(updated);
      return next;
    });
  }, [tickers]);

  const selectedTicker = useMemo(
    () => tickers.find((t) => t.symbol === selectedAuditSymbol),
    [tickers, selectedAuditSymbol],
  );
  const selectedMetrics = selectedAuditSymbol ? riskData[selectedAuditSymbol] : undefined;
  const canAudit = Boolean(selectedAuditSymbol && selectedTicker && selectedTicker.price > 0 && selectedMetrics);

  const handleAddWatchlist = (e: React.FormEvent) => {
    e.preventDefault();
    setAddError(null);

    const symbol = newSymbol.trim().toUpperCase();
    const name = newName.trim();

    if (!symbol || !name) {
      setAddError("Please fill both Symbol and Name.");
      return;
    }
    if (watchlist.some((item) => item.symbol === symbol)) {
      setAddError("Asset is already in the risk assessment database.");
      return;
    }

    const live = tickers.find((t) => t.symbol === symbol);
    if (!live || live.price <= 0) {
      setAddError(`No live ticker for ${symbol}. Wait for market stream or pick a streamed symbol.`);
      return;
    }

    const newItem: WatchlistItem = {
      symbol,
      name: live.name || name,
      basePrice: live.price,
      custom: true,
    };
    const metrics = metricsFromTicker(live, live.price);
    setWatchlist((prev) => [...prev, newItem]);
    if (metrics) {
      setRiskData((prev) => ({ ...prev, [symbol]: metrics }));
    }
    setNewSymbol("");
    setNewName("");
  };

  const handleRemoveWatchlist = (symbol: string, e: React.MouseEvent) => {
    e.stopPropagation();
    setWatchlist((prev) => {
      const next = prev.filter((item) => item.symbol !== symbol);
      if (selectedAuditSymbol === symbol) {
        setSelectedAuditSymbol(next[0]?.symbol || null);
      }
      return next;
    });
  };

  const getRiskClassification = (score: number) => {
    if (score >= 70) return { label: "EXTREME", color: "text-red-400 bg-red-950/40 border-red-500/50", bg: "bg-red-950/20" };
    if (score >= 50) return { label: "HIGH", color: "text-amber-400 bg-amber-950/40 border-amber-500/50", bg: "bg-amber-950/20" };
    if (score >= 30) return { label: "MODERATE", color: "text-yellow-300 bg-yellow-950/30 border-yellow-500/30", bg: "bg-yellow-950/15" };
    return { label: "LOW", color: "text-emerald-400 bg-emerald-950/40 border-emerald-500/40", bg: "bg-emerald-950/10" };
  };

  const runDeepRiskAudit = async (symbol: string) => {
    if (auditingSymbol) return;

    const ticker = tickers.find((t) => t.symbol === symbol);
    const metrics = riskData[symbol] ?? metricsFromTicker(ticker, ticker?.price ?? 0);
    if (!ticker || ticker.price <= 0 || !metrics) {
      setAuditLogs([
        `[FAIL] No live price for ${symbol}.`,
        "Risk audit needs a streamed ticker (Kraken/CCXT) before leverage checks can run.",
      ]);
      return;
    }

    const token = ++auditTokenRef.current;
    setAuditingSymbol(symbol);
    setAuditProgress(0);
    setAuditLogs([`[START] Local risk audit for ${symbol} @ $${ticker.price.toLocaleString()}`]);

    const push = (line: string, progress: number) => {
      if (auditTokenRef.current !== token) return;
      setAuditLogs((prev) => [...prev, line]);
      setAuditProgress(progress);
    };

    const sleep = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));

    try {
      await sleep(250);
      const riskInfo = getRiskClassification(metrics.compositeScore);
      push(
        `[1/4] Ticker metrics · vol=${metrics.volatility}% dd=${metrics.drawdownFactor}% stress=${metrics.sentimentStress}% composite=${metrics.compositeScore} (${riskInfo.label})`,
        25,
      );

      await sleep(300);
      push(`[2/4] Leverage gate · max recommended ${metrics.leverageLimit}x from vol/drawdown bands`, 45);

      await sleep(200);
      push(`[3/4] Fetching order-book depth for ${symbol}…`, 60);

      let bookLine = "[3/4] Order book unavailable — leverage check uses ticker metrics only.";
      let imbalanceWarn = false;
      try {
        const book = await fetchOrderBook(symbol, 12);
        if (auditTokenRef.current !== token) return;
        const { bidVol, askVol, ratio } = bookImbalance(book);
        imbalanceWarn = ratio < 0.35 || ratio > 0.65;
        const spread =
          book.bids[0] && book.asks[0]
            ? ((book.asks[0].price - book.bids[0].price) / book.asks[0].price) * 100
            : null;
        bookLine = `[3/4] Depth ${book.source} · bidVol=${bidVol.toFixed(3)} askVol=${askVol.toFixed(3)} imbalance=${(ratio * 100).toFixed(1)}%${
          spread != null ? ` spread=${spread.toFixed(3)}%` : ""
        }`;
        push(bookLine, 80);
        if (imbalanceWarn) {
          push(`[WARN] Book imbalance outside 35–65% band — reduce size / widen stops.`, 85);
        }
      } catch (error) {
        push(
          `${bookLine} (${error instanceof ApiError ? error.message : "fetch failed"})`,
          80,
        );
      }

      await sleep(250);
      const checks = [
        {
          ok: metrics.compositeScore < 70,
          pass: `Composite ${metrics.compositeScore} < 70 EXTREME threshold`,
          fail: `Composite ${metrics.compositeScore} ≥ 70 — block aggressive size`,
        },
        {
          ok: metrics.volatility < 55,
          pass: `Volatility ${metrics.volatility}% within paper-safe band`,
          fail: `Volatility ${metrics.volatility}% elevated — cap leverage at ${metrics.leverageLimit}x`,
        },
        {
          ok: metrics.drawdownFactor < 30,
          pass: `Range/drawdown ${metrics.drawdownFactor}% acceptable`,
          fail: `Range/drawdown ${metrics.drawdownFactor}% stress — tighten risk`,
        },
        {
          ok: !imbalanceWarn,
          pass: "Order-book imbalance within band (or unavailable)",
          fail: "Order-book imbalance stress active",
        },
      ];

      for (const check of checks) {
        push(check.ok ? `[PASS] ${check.pass}` : `[FAIL] ${check.fail}`, 90);
      }

      const failed = checks.filter((c) => !c.ok).length;
      const verdict =
        failed === 0
          ? `[DONE] ${symbol} CLEAR for paper sizing ≤ ${metrics.leverageLimit}x`
          : failed === 1
            ? `[DONE] ${symbol} CAUTION — ${failed} gate failed; keep size small (≤ ${Math.max(1, Math.floor(metrics.leverageLimit / 2))}x)`
            : `[DONE] ${symbol} BLOCK — ${failed} gates failed; do not increase risk`;
      push(verdict, 100);
    } finally {
      if (auditTokenRef.current === token) {
        setAuditingSymbol(null);
      }
    }
  };

  useEffect(() => {
    return () => {
      auditTokenRef.current += 1;
    };
  }, []);

  return (
    <div id="risk-assessment-heatmap-card" className="bg-slate-900/40 border border-white/5 hover:border-white/10 rounded-xl p-5 font-mono text-xs space-y-5 transition-all duration-300">
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-3 border-b border-white/10 pb-4">
        <div className="flex items-center gap-2">
          <ShieldAlert className="w-4 h-4 text-rose-500" />
          <div>
            <h3 className="text-white font-bold uppercase tracking-wider text-[11px]">
              Fable 5 Risk Assessment Heatmap // Tiles
            </h3>
            <p className="text-[9px] text-slate-500">
              Metrics from live tickers + order-book depth. Local leverage gates — not a remote Monte Carlo service.
            </p>
          </div>
          <span
            className={`text-[8px] font-bold px-1.5 py-0.5 rounded border uppercase ${
              marketLive
                ? "text-emerald-400 border-emerald-500/30 bg-emerald-950/30"
                : "text-amber-400 border-amber-500/30 bg-amber-950/30"
            }`}
            title={marketAsOf ?? undefined}
          >
            {marketLive ? `LIVE${marketAsOf ? ` · ${new Date(marketAsOf).toLocaleTimeString()}` : ""}` : "STALE / CACHED"}
          </span>
        </div>

        <div className="flex flex-wrap items-center gap-1">
          <span className="text-[9px] text-slate-500 mr-1.5 uppercase font-bold">Risk Level:</span>
          {(["ALL", "LOW", "MODERATE", "HIGH", "EXTREME"] as const).map((lvl) => (
            <button
              key={lvl}
              onClick={() => setRiskFilter(lvl)}
              className={`px-2 py-1 rounded text-[8px] font-bold uppercase tracking-wider transition-all cursor-pointer ${
                riskFilter === lvl
                  ? "bg-rose-500/20 border border-rose-500/40 text-rose-300 shadow-[0_0_8px_rgba(239,68,68,0.2)]"
                  : "bg-white/5 hover:bg-white/10 text-slate-400 border border-transparent"
              }`}
            >
              {lvl}
            </button>
          ))}
        </div>
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-4 gap-5">
        <div className="xl:col-span-3 space-y-4">
          <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-3">
            {watchlist
              .filter((item) => {
                const data = riskData[item.symbol];
                if (!data) return riskFilter === "ALL";
                if (riskFilter === "ALL") return true;
                return getRiskClassification(data.compositeScore).label === riskFilter;
              })
              .map((item) => {
                const liveTicker = tickers.find((t) => t.symbol === item.symbol);
                const price = liveTicker?.price ?? item.basePrice;
                const change = liveTicker?.change ?? 0;
                const metrics = riskData[item.symbol];
                const hasLive = Boolean(liveTicker && liveTicker.price > 0);
                const isUp = change >= 0;
                const riskInfo = metrics
                  ? getRiskClassification(metrics.compositeScore)
                  : { label: "NO DATA", color: "text-slate-400 bg-slate-800/40 border-white/10", bg: "bg-slate-950/40" };
                const isSelected = selectedAuditSymbol === item.symbol;

                return (
                  <div
                    key={item.symbol}
                    onClick={() => setSelectedAuditSymbol(item.symbol)}
                    className={`p-4 rounded-lg border flex flex-col justify-between h-[155px] cursor-pointer transition-all duration-300 relative group overflow-hidden ${
                      isSelected
                        ? "bg-slate-900 border-rose-500 glow-rose"
                        : "bg-slate-950/60 border-white/5 hover:border-white/15 hover:bg-slate-900/40"
                    } ${riskInfo.bg}`}
                  >
                    <div className="flex items-center justify-between mb-1.5 relative z-10">
                      <div className="flex items-center gap-1.5">
                        <span className="font-black text-white text-[13px] tracking-tight">{item.symbol}</span>
                        <span className="text-[9px] text-slate-500 uppercase truncate max-w-[80px]">{item.name}</span>
                      </div>
                      <div className="flex items-center gap-1">
                        {item.custom && (
                          <span className="bg-purple-500/10 border border-purple-500/20 text-purple-400 text-[7px] font-bold px-1 rounded">
                            CUSTOM
                          </span>
                        )}
                        <span className={`text-[8px] font-bold px-1.5 py-0.5 rounded border uppercase ${riskInfo.color}`}>
                          {riskInfo.label}
                        </span>
                      </div>
                    </div>

                    <div className="my-1.5 relative z-10">
                      <div className="flex items-baseline gap-1.5">
                        <span className="text-[13px] font-bold text-white">
                          {hasLive
                            ? `$${price.toLocaleString(undefined, { minimumFractionDigits: price > 1 ? 2 : 4 })}`
                            : "Awaiting ticker"}
                        </span>
                        {hasLive && (
                          <span className={`text-[8px] font-bold flex items-center ${isUp ? "text-emerald-400" : "text-rose-400"}`}>
                            {isUp ? "+" : ""}{change.toFixed(1)}%
                          </span>
                        )}
                      </div>
                    </div>

                    <div className="grid grid-cols-2 gap-1.5 pt-2 border-t border-white/5 text-[9px] text-slate-400 mt-auto relative z-10">
                      <div className="flex flex-col">
                        <span className="text-slate-500 uppercase text-[7px] tracking-wider font-bold">VOLATILITY</span>
                        <span className="text-white font-mono font-bold">{metrics ? `${metrics.volatility}%` : "—"}</span>
                      </div>
                      <div className="flex flex-col">
                        <span className="text-slate-500 uppercase text-[7px] tracking-wider font-bold">MAX LEVERAGE</span>
                        <span className="text-rose-400 font-mono font-bold">{metrics ? `${metrics.leverageLimit}x limit` : "—"}</span>
                      </div>
                      <div className="flex flex-col">
                        <span className="text-slate-500 uppercase text-[7px] tracking-wider font-bold">DRAWDOWN</span>
                        <span className="text-amber-400 font-mono font-bold">{metrics ? `${metrics.drawdownFactor}%` : "—"}</span>
                      </div>
                      <div className="flex flex-col">
                        <span className="text-slate-500 uppercase text-[7px] tracking-wider font-bold">STRESS IDX</span>
                        <span className="text-purple-400 font-mono font-bold">{metrics ? `${metrics.sentimentStress}%` : "—"}</span>
                      </div>
                    </div>

                    {item.custom && (
                      <button
                        onClick={(e) => handleRemoveWatchlist(item.symbol, e)}
                        className="absolute right-3 bottom-3 p-1 rounded hover:bg-red-500/10 text-slate-600 hover:text-red-400 opacity-0 group-hover:opacity-100 transition-opacity z-20"
                        title="Remove from Watchlist"
                      >
                        <Trash2 className="w-3 h-3" />
                      </button>
                    )}

                    {metrics && (
                      <div
                        className={`absolute bottom-0 left-0 h-1.5 transition-all duration-300 ${
                          metrics.compositeScore >= 70
                            ? "bg-red-500"
                            : metrics.compositeScore >= 50
                              ? "bg-amber-500"
                              : metrics.compositeScore >= 30
                                ? "bg-yellow-500"
                                : "bg-emerald-500"
                        }`}
                        style={{ width: `${metrics.compositeScore}%` }}
                      />
                    )}
                  </div>
                );
              })}

            {watchlist.filter((item) => {
              const data = riskData[item.symbol];
              if (!data) return riskFilter === "ALL";
              if (riskFilter === "ALL") return true;
              return getRiskClassification(data.compositeScore).label === riskFilter;
            }).length === 0 && (
              <div className="col-span-full border border-dashed border-white/5 rounded-xl h-[155px] flex flex-col items-center justify-center p-6 text-center text-slate-500">
                <ShieldCheck className="w-7 h-7 text-emerald-500/40 mb-2" />
                <span className="text-[10px] font-bold text-slate-400 block">No Assets match Risk Level: {riskFilter}</span>
                <span className="text-[8px] text-slate-600">Modify your filter selection or add a new custom asset.</span>
              </div>
            )}
          </div>

          <form onSubmit={handleAddWatchlist} className="bg-slate-950/30 border border-white/5 rounded-lg p-3.5 flex flex-wrap items-center gap-3">
            <div className="text-[9px] text-slate-400 font-bold uppercase tracking-wider shrink-0">
              Add custom watchlist member:
            </div>
            <div className="flex gap-2 flex-grow min-w-[200px]">
              <input
                type="text"
                placeholder="SYM (e.g. SOL)"
                value={newSymbol}
                onChange={(e) => setNewSymbol(e.target.value)}
                maxLength={8}
                className="w-1/3 bg-slate-900 border border-white/5 rounded px-2.5 py-1.5 text-[10px] text-white focus:outline-none focus:border-rose-500/50"
              />
              <input
                type="text"
                placeholder="Asset Name (e.g. Solana)"
                value={newName}
                onChange={(e) => setNewName(e.target.value)}
                className="w-2/3 bg-slate-900 border border-white/5 rounded px-2.5 py-1.5 text-[10px] text-white focus:outline-none focus:border-rose-500/50"
              />
            </div>
            <button
              type="submit"
              className="bg-rose-600 hover:bg-rose-500 text-white font-bold text-[9px] uppercase tracking-wider px-3 py-2 rounded transition-colors shrink-0 cursor-pointer"
            >
              Add Tile
            </button>
            {addError && (
              <span className="text-[9px] text-rose-400 font-semibold block w-full mt-1">
                {addError}
              </span>
            )}
          </form>
        </div>

        <div className="bg-slate-950/40 border border-white/5 rounded-xl p-4 flex flex-col justify-between space-y-4">
          <div className="space-y-3.5">
            <span className="text-[9px] text-slate-500 font-bold block border-b border-white/5 pb-1.5 uppercase tracking-wider">
              Active Risk Auditor
            </span>

            {selectedAuditSymbol ? (
              <div className="space-y-3">
                <div className="flex items-center justify-between gap-2">
                  <span className="text-white font-black text-[13px]">{selectedAuditSymbol} risk audit</span>
                  <button
                    onClick={() => void runDeepRiskAudit(selectedAuditSymbol)}
                    disabled={!!auditingSymbol || !canAudit}
                    className={`flex items-center gap-1 text-[8px] font-bold px-2 py-1 rounded tracking-wider uppercase border cursor-pointer transition-all ${
                      auditingSymbol || !canAudit
                        ? "bg-slate-900 text-slate-600 border-white/5 cursor-not-allowed"
                        : "bg-rose-500/10 border-rose-500/30 text-rose-300 hover:bg-rose-500/20"
                    }`}
                    title={!canAudit ? "Needs a live ticker price first" : "Run local risk + depth audit"}
                  >
                    {auditingSymbol ? <RefreshCw className="w-2.5 h-2.5 animate-spin" /> : <Play className="w-2 h-2 fill-current" />}
                    {auditingSymbol ? "Auditing" : "Run audit"}
                  </button>
                </div>

                {!canAudit && (
                  <div className="text-[8px] text-amber-400/90 border border-amber-500/20 bg-amber-950/20 rounded px-2 py-1.5">
                    Waiting for live {selectedAuditSymbol} ticker before audit can run.
                  </div>
                )}

                {(auditingSymbol || auditProgress > 0) && (
                  <div className="space-y-1">
                    <div className="flex justify-between text-[8px] font-mono text-slate-500">
                      <span>AUDIT PROG:</span>
                      <span>{auditProgress}%</span>
                    </div>
                    <div className="w-full bg-slate-900 h-1.5 rounded-full overflow-hidden">
                      <div
                        className="bg-rose-500 h-full transition-all duration-300"
                        style={{ width: `${auditProgress}%` }}
                      />
                    </div>
                  </div>
                )}

                <div className="bg-slate-950/95 rounded-lg p-2.5 h-[220px] overflow-y-auto font-mono text-[8px] leading-relaxed text-slate-400 space-y-1.5 border border-white/5 scrollbar-thin">
                  {auditLogs.length > 0 ? (
                    auditLogs.map((log, idx) => (
                      <div
                        key={`${idx}-${log.slice(0, 24)}`}
                        className={
                          log.includes("[DONE]") && log.includes("CLEAR")
                            ? "text-emerald-400 font-bold"
                            : log.includes("[DONE]") && log.includes("CAUTION")
                              ? "text-amber-300 font-bold"
                              : log.includes("[DONE]") || log.includes("[FAIL]")
                                ? "text-rose-300 font-bold"
                              : log.includes("[PASS]")
                                ? "text-emerald-400/90"
                                : log.includes("[WARN]")
                                  ? "text-amber-400"
                                  : ""
                        }
                      >
                        {log}
                      </div>
                    ))
                  ) : (
                    <div className="text-slate-600 italic">
                      Select a tile with a live price, then Run audit for ticker + order-book leverage gates.
                    </div>
                  )}
                </div>
              </div>
            ) : (
              <div className="text-center text-slate-600 italic text-[9px] py-12">
                Select any ticker tile to run a local risk audit.
              </div>
            )}
          </div>

          <div className="pt-2 border-t border-white/5 text-[8px] text-slate-500 leading-normal flex gap-1.5">
            <Activity className="w-3.5 h-3.5 text-slate-600 shrink-0 mt-0.5" />
            <span>
              Local auditor: streamed ticker metrics + Kraken depth imbalance. Paper sizing guidance only.
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}
