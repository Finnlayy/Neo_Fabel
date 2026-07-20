import React, { useCallback, useEffect, useMemo, useState } from "react";
import { Download, RefreshCw, TrendingUp } from "lucide-react";
import {
  fetchPaperPerformance,
  performanceFillsToCsv,
  type PaperPerformanceResponse,
} from "../../api/paper";

type Props = {
  language?: "en" | "de";
};

function fmtUsd(value: string | number | null | undefined, digits = 2): string {
  const n = Number(value);
  if (!Number.isFinite(n)) return "—";
  return n.toLocaleString(undefined, { minimumFractionDigits: digits, maximumFractionDigits: digits });
}

function pnlClass(value: string | number | null | undefined): string {
  const n = Number(value);
  if (!Number.isFinite(n) || n === 0) return "text-slate-300";
  return n > 0 ? "text-emerald-400" : "text-rose-400";
}

type BookTab = "combined" | "spot" | "futures";

export default function PaperPerformancePage({ language = "en" }: Props) {
  const de = language === "de";
  const [perf, setPerf] = useState<PaperPerformanceResponse | null>(null);
  const [bookTab, setBookTab] = useState<BookTab>("combined");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const activeBook = useMemo(() => {
    if (!perf) return null;
    if (bookTab === "spot") return perf.spot ?? perf;
    if (bookTab === "futures") return perf.futures ?? null;
    return perf;
  }, [bookTab, perf]);

  const reload = useCallback(async () => {
    setBusy(true);
    setError("");
    try {
      const data = await fetchPaperPerformance();
      setPerf(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }, []);

  useEffect(() => {
    void reload();
    const id = window.setInterval(() => void reload(), 15000);
    return () => window.clearInterval(id);
  }, [reload]);

  const equityPoints = useMemo(() => {
    const curve = activeBook?.equity_curve ?? [];
    return curve
      .map((p) => Number(p.equity_usd))
      .filter((n) => Number.isFinite(n));
  }, [activeBook]);

  const equitySpark = useMemo(() => {
    if (equityPoints.length < 2) return null;
    const min = Math.min(...equityPoints);
    const max = Math.max(...equityPoints);
    const span = max - min || 1;
    const w = 320;
    const h = 64;
    const pts = equityPoints.map((v, i) => {
      const x = (i / (equityPoints.length - 1)) * w;
      const y = h - ((v - min) / span) * h;
      return `${x},${y}`;
    });
    return { polyline: pts.join(" "), w, h };
  }, [equityPoints]);

  const onExportCsv = () => {
    const fills = activeBook?.fills ?? perf?.fills ?? [];
    if (!fills.length) return;
    const blob = new Blob([performanceFillsToCsv(fills)], { type: "text/csv;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `paper-fills-${new Date().toISOString().slice(0, 10)}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div role="tabpanel" aria-labelledby="tab-paper" className="space-y-4 max-w-[1200px] mx-auto">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 bg-slate-950/60 border border-white/5 rounded-xl p-3 font-mono text-xs">
        <div className="flex flex-wrap items-center gap-4">
          <div>
            <div className="text-[8px] text-slate-500 uppercase tracking-widest">
              {de ? "Paper-Modus" : "Paper mode"}
            </div>
            <div className="text-lime-300 font-bold mt-0.5">{de ? "Nur Simulation" : "Simulation only"}</div>
          </div>
          <div>
            <div className="text-[8px] text-slate-500 uppercase tracking-widest">
              {de ? "Gebührenmodell" : "Fee model"}
            </div>
            <div className="text-slate-200 font-bold mt-0.5">{perf?.fee_model ?? "—"}</div>
          </div>
          <div>
            <div className="text-[8px] text-slate-500 uppercase tracking-widest">
              {de ? "Quelle" : "Source"}
            </div>
            <div className="text-slate-200 font-bold mt-0.5">{perf?.router_source ?? perf?.source ?? "—"}</div>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <div className="inline-flex rounded-lg border border-white/10 overflow-hidden text-[10px] font-mono">
            {(
              [
                ["combined", de ? "Kombi" : "Combined"],
                ["spot", "Spot"],
                ["futures", "Futures"],
              ] as const
            ).map(([id, label]) => (
              <button
                key={id}
                type="button"
                onClick={() => setBookTab(id)}
                className={`px-3 py-2 ${bookTab === id ? "bg-white/10 text-white" : "text-slate-400 hover:text-white"}`}
              >
                {label}
              </button>
            ))}
          </div>
          <button
            type="button"
            onClick={onExportCsv}
            disabled={!(activeBook?.fills?.length || perf?.fills?.length)}
            className="inline-flex items-center gap-1.5 px-3 py-2 rounded-lg border border-white/10 text-slate-300 hover:text-white cursor-pointer disabled:opacity-40"
          >
            <Download className="w-3.5 h-3.5" />
            CSV
          </button>
          <button
            type="button"
            onClick={() => void reload()}
            disabled={busy}
            className="inline-flex items-center gap-1.5 px-3 py-2 rounded-lg border border-white/10 text-slate-300 hover:text-white cursor-pointer"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${busy ? "animate-spin" : ""}`} />
            {de ? "Aktualisieren" : "Refresh"}
          </button>
        </div>
      </div>

      {error ? (
        <div className="text-xs font-mono text-rose-300 border border-rose-500/30 bg-rose-500/10 rounded-lg px-3 py-2">
          {error}
        </div>
      ) : null}

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        {[
          {
            label: bookTab === "futures" ? (de ? "Margin" : "Margin") : de ? "Eigenkapital" : "Equity",
            value: fmtUsd(activeBook?.equity_usd ?? perf?.equity_usd),
            cls: "text-white",
          },
          { label: de ? "Realisiert" : "Realized", value: fmtUsd(activeBook?.realized_pnl_usd), cls: pnlClass(activeBook?.realized_pnl_usd) },
          { label: de ? "Unrealisiert" : "Unrealized", value: fmtUsd(activeBook?.unrealized_pnl_usd), cls: pnlClass(activeBook?.unrealized_pnl_usd) },
          { label: de ? "Gebühren" : "Fees", value: fmtUsd(activeBook?.fees_paid_usd), cls: "text-amber-300" },
          {
            label: bookTab === "futures" ? (de ? "Margin USD" : "Margin USD") : de ? "Cash USD" : "Cash USD",
            value: fmtUsd(activeBook?.usd_balance ?? activeBook?.margin_balance_usd ?? perf?.usd_balance),
            cls: "text-slate-200",
          },
          { label: de ? "Positionen" : "Positions", value: fmtUsd(activeBook?.position_value_usd), cls: "text-sky-300" },
          {
            label: de ? "Gewinnquote" : "Win rate",
            value: activeBook?.win_rate != null ? `${(activeBook.win_rate * 100).toFixed(1)}%` : "—",
            cls: "text-emerald-300",
          },
          {
            label: de ? "Max Drawdown" : "Max drawdown",
            value: activeBook?.max_drawdown_pct != null ? `${Number(activeBook.max_drawdown_pct).toFixed(2)}%` : "—",
            cls: "text-rose-300",
          },
        ].map((kpi) => (
          <div key={kpi.label} className="bg-slate-900/50 border border-white/5 rounded-xl p-3 font-mono">
            <div className="text-[8px] text-slate-500 uppercase tracking-widest">{kpi.label}</div>
            <div className={`text-lg font-bold mt-1 tabular-nums ${kpi.cls}`}>{kpi.value}</div>
          </div>
        ))}
      </div>

      <div className="grid lg:grid-cols-2 gap-4">
        <div className="bg-slate-900/40 border border-white/5 rounded-xl p-4 space-y-3">
          <div className="flex items-center gap-2 text-xs font-mono text-slate-400 uppercase tracking-widest">
            <TrendingUp className="w-4 h-4 text-lime-400" />
            {de ? "Equity-Kurve" : "Equity curve"}
          </div>
          {equitySpark ? (
            <svg viewBox={`0 0 ${equitySpark.w} ${equitySpark.h}`} className="w-full h-16 text-lime-400">
              <polyline
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                points={equitySpark.polyline}
              />
            </svg>
          ) : (
            <p className="text-[10px] font-mono text-slate-500">
              {de ? "Noch keine Fills — platziere Paper-Orders im Terminal." : "No fills yet — place paper orders in the terminal."}
            </p>
          )}
        </div>

        <div className="bg-slate-900/40 border border-white/5 rounded-xl p-4 overflow-x-auto">
          <div className="text-xs font-mono text-slate-400 uppercase tracking-widest mb-2">
            {de ? "Offene Positionen" : "Open positions"}
          </div>
          <table className="w-full text-[10px] font-mono text-slate-300">
            <thead>
              <tr className="text-slate-500 border-b border-white/5">
                <th className="text-left py-1">Pair</th>
                <th className="text-right py-1">Vol</th>
                <th className="text-right py-1">Entry</th>
                <th className="text-right py-1">Mark</th>
                <th className="text-right py-1">uPnL</th>
              </tr>
            </thead>
            <tbody>
              {(activeBook?.positions ?? []).map((p) => (
                <tr key={`${p.market_type ?? "spot"}-${p.pair}`} className="border-b border-white/5">
                  <td className="py-1">
                    {p.pair}
                    {p.market_type === "futures" ? (
                      <span className="ml-1 text-[8px] text-cyan-400 uppercase">{p.side ?? "perp"}</span>
                    ) : null}
                  </td>
                  <td className="text-right py-1">{p.volume}</td>
                  <td className="text-right py-1">{fmtUsd(p.avg_entry)}</td>
                  <td className="text-right py-1">{fmtUsd(p.mark_price)}</td>
                  <td className={`text-right py-1 ${pnlClass(p.unrealized_pnl_usd)}`}>
                    {fmtUsd(p.unrealized_pnl_usd)}
                  </td>
                </tr>
              ))}
              {!activeBook?.positions?.length ? (
                <tr>
                  <td colSpan={5} className="py-3 text-slate-500">
                    {de ? "Keine offenen Positionen" : "No open positions"}
                  </td>
                </tr>
              ) : null}
            </tbody>
          </table>
        </div>
      </div>

      <div className="bg-slate-900/40 border border-white/5 rounded-xl p-4 overflow-x-auto">
        <div className="text-xs font-mono text-slate-400 uppercase tracking-widest mb-2">
          {de ? "Letzte Fills" : "Recent fills"} ({activeBook?.fill_count ?? perf?.fill_count ?? 0})
        </div>
        <table className="w-full text-[10px] font-mono text-slate-300">
          <thead>
            <tr className="text-slate-500 border-b border-white/5">
              <th className="text-left py-1">Time</th>
              <th className="text-left py-1">Pair</th>
              <th className="text-left py-1">Side</th>
              <th className="text-right py-1">Vol</th>
              <th className="text-right py-1">Price</th>
              <th className="text-right py-1">Fee</th>
              <th className="text-right py-1">PnL</th>
            </tr>
          </thead>
          <tbody>
            {(activeBook?.fills ?? perf?.fills ?? []).slice(0, 50).map((f) => (
              <tr key={f.txid} className="border-b border-white/5">
                <td className="py-1 whitespace-nowrap">{f.time?.slice(11, 19) ?? "—"}</td>
                <td className="py-1">
                  {f.pair}
                  {f.market_type === "futures" ? (
                    <span className="ml-1 text-[8px] text-cyan-400">F</span>
                  ) : null}
                </td>
                <td className="py-1 uppercase">{f.side}</td>
                <td className="text-right py-1">{f.volume}</td>
                <td className="text-right py-1">{fmtUsd(f.price)}</td>
                <td className="text-right py-1">{fmtUsd(f.fee, 4)}</td>
                <td className={`text-right py-1 ${pnlClass(f.realized_pnl)}`}>{fmtUsd(f.realized_pnl, 4)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {(activeBook?.by_symbol ?? perf?.by_symbol ?? []).length > 0 ? (
        <div className="bg-slate-900/40 border border-white/5 rounded-xl p-4 overflow-x-auto">
          <div className="text-xs font-mono text-slate-400 uppercase tracking-widest mb-2">
            {de ? "Nach Symbol" : "By symbol"}
          </div>
          <table className="w-full text-[10px] font-mono text-slate-300">
            <thead>
              <tr className="text-slate-500 border-b border-white/5">
                <th className="text-left py-1">Pair</th>
                <th className="text-right py-1">Fills</th>
                <th className="text-right py-1">Buy vol</th>
                <th className="text-right py-1">Sell vol</th>
                <th className="text-right py-1">Realized</th>
                <th className="text-right py-1">Fees</th>
              </tr>
            </thead>
            <tbody>
              {(activeBook?.by_symbol ?? perf?.by_symbol ?? []).map((s) => (
                <tr key={s.pair} className="border-b border-white/5">
                  <td className="py-1">{s.pair}</td>
                  <td className="text-right py-1">{s.fills}</td>
                  <td className="text-right py-1">{s.buy_volume}</td>
                  <td className="text-right py-1">{s.sell_volume}</td>
                  <td className={`text-right py-1 ${pnlClass(s.realized_pnl_usd)}`}>
                    {fmtUsd(s.realized_pnl_usd)}
                  </td>
                  <td className="text-right py-1">{fmtUsd(s.fees_usd, 4)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}
    </div>
  );
}
