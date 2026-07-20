import React, { useCallback, useEffect, useState } from "react";
import { AlertTriangle, RefreshCw, XCircle } from "lucide-react";
import { closePosition, fetchPositions, type PositionsSnapshot } from "../../api/positions";

type Props = {
  language?: "en" | "de";
};

function fmtUsd(value: string | number | null | undefined): string {
  const n = Number(value);
  if (!Number.isFinite(n)) return "—";
  return n.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function pnlClass(value: string | number | null | undefined): string {
  const n = Number(value);
  if (!Number.isFinite(n) || n === 0) return "text-slate-300";
  return n > 0 ? "text-emerald-400" : "text-rose-400";
}

export default function PositionsPage({ language = "en" }: Props) {
  const de = language === "de";
  const [snap, setSnap] = useState<PositionsSnapshot | null>(null);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);
  const [closing, setClosing] = useState<string | null>(null);

  const reload = useCallback(async () => {
    setBusy(true);
    setError("");
    try {
      const data = await fetchPositions();
      setSnap(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }, []);

  useEffect(() => {
    void reload();
    const id = window.setInterval(() => void reload(), 12000);
    return () => window.clearInterval(id);
  }, [reload]);

  const paperSpot = (snap?.paper ?? []).filter((p) => (p.market_type ?? "spot") === "spot");
  const paperFutures = (snap?.paper ?? []).filter((p) => p.market_type === "futures");

  const onClose = async (
    pair: string,
    mode: "paper" | "live",
    marketType: "spot" | "futures" = "spot",
    volume?: string,
  ) => {
    const key = `${mode}:${marketType}:${pair}`;
    setClosing(key);
    setNotice("");
    setError("");
    try {
      const res = await closePosition({
        pair,
        mode,
        market_type: marketType,
        volume,
        order_type: "market",
        idempotency_key: crypto.randomUUID(),
      });
      setNotice(
        de
          ? `Position ${pair} geschlossen (${res.status}).`
          : `Closed ${pair} position (${res.status}).`,
      );
      await reload();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setClosing(null);
    }
  };

  const onCloseAllPaper = async (marketType: "spot" | "futures") => {
    const rows = marketType === "futures" ? paperFutures : paperSpot;
    if (!rows.length) return;
    setBusy(true);
    for (const row of rows) {
      await onClose(row.pair, "paper", marketType, row.volume);
    }
    setBusy(false);
  };

  return (
    <div role="tabpanel" aria-labelledby="tab-positions" className="space-y-4 max-w-[1200px] mx-auto">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 bg-slate-950/60 border border-white/5 rounded-xl p-3 font-mono text-xs">
        <div className="flex flex-wrap items-center gap-4">
          <div>
            <div className="text-[8px] text-slate-500 uppercase tracking-widest">
              {de ? "Offene Positionen" : "Open positions"}
            </div>
            <div className="text-white font-bold mt-0.5">{snap?.total_open ?? 0}</div>
          </div>
          <div>
            <div className="text-[8px] text-slate-500 uppercase tracking-widest">
              {de ? "Modus" : "Execution"}
            </div>
            <div className="text-lime-300 font-bold mt-0.5">{snap?.execution ?? "—"}</div>
          </div>
          <div>
            <div className="text-[8px] text-slate-500 uppercase tracking-widest">
              {de ? "Live schließen" : "Live close"}
            </div>
            <div className={snap?.live_close_available ? "text-emerald-400 font-bold mt-0.5" : "text-slate-500 font-bold mt-0.5"}>
              {snap?.live_close_available ? (de ? "Aktiv" : "Enabled") : de ? "Nur Anzeige" : "View only"}
            </div>
          </div>
        </div>
        <div className="flex items-center gap-2">
          {paperSpot.length ? (
            <button
              type="button"
              onClick={() => void onCloseAllPaper("spot")}
              disabled={busy || Boolean(closing)}
              className="px-3 py-2 rounded-lg border border-rose-500/30 text-[10px] font-mono text-rose-300 hover:bg-rose-500/10 cursor-pointer disabled:opacity-40"
            >
              {de ? "Spot schließen" : "Close spot"}
            </button>
          ) : null}
          {paperFutures.length ? (
            <button
              type="button"
              onClick={() => void onCloseAllPaper("futures")}
              disabled={busy || Boolean(closing)}
              className="px-3 py-2 rounded-lg border border-rose-500/30 text-[10px] font-mono text-rose-300 hover:bg-rose-500/10 cursor-pointer disabled:opacity-40"
            >
              {de ? "Futures schließen" : "Close futures"}
            </button>
          ) : null}
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
        <div className="text-xs font-mono text-rose-300 border border-rose-500/30 bg-rose-500/10 rounded-lg px-3 py-2 flex items-center gap-2">
          <AlertTriangle className="w-4 h-4 shrink-0" />
          {error}
        </div>
      ) : null}
      {notice ? (
        <div className="text-xs font-mono text-emerald-300 border border-emerald-500/30 bg-emerald-500/10 rounded-lg px-3 py-2">
          {notice}
        </div>
      ) : null}

      {(snap?.errors ?? []).length > 0 ? (
        <div className="text-[10px] font-mono text-amber-300 border border-amber-500/20 bg-amber-500/5 rounded-lg px-3 py-2 space-y-1">
          {snap!.errors.map((e) => (
            <div key={`${e.source}-${e.message}`}>
              {e.source}: {e.message}
            </div>
          ))}
        </div>
      ) : null}

      <section className="bg-slate-900/40 border border-amber-500/20 rounded-xl p-4 overflow-x-auto">
        <h2 className="text-xs font-mono text-amber-300 uppercase tracking-widest mb-3">
          {de ? "Paper Spot" : "Paper spot"}
        </h2>
        <table className="w-full text-[10px] font-mono text-slate-300">
          <thead>
            <tr className="text-slate-500 border-b border-white/5">
              <th className="text-left py-1">Pair</th>
              <th className="text-right py-1">Vol</th>
              <th className="text-right py-1">Entry</th>
              <th className="text-right py-1">Mark</th>
              <th className="text-right py-1">Value</th>
              <th className="text-right py-1">uPnL</th>
              <th className="text-right py-1">{de ? "Aktion" : "Action"}</th>
            </tr>
          </thead>
          <tbody>
            {paperSpot.map((p) => (
              <tr key={`spot-${p.pair}`} className="border-b border-white/5">
                <td className="py-1.5">{p.pair}</td>
                <td className="text-right py-1.5">{p.volume}</td>
                <td className="text-right py-1.5">{fmtUsd(p.avg_entry)}</td>
                <td className="text-right py-1.5">{fmtUsd(p.mark_price)}</td>
                <td className="text-right py-1.5">{fmtUsd(p.market_value_usd)}</td>
                <td className={`text-right py-1.5 ${pnlClass(p.unrealized_pnl_usd)}`}>
                  {fmtUsd(p.unrealized_pnl_usd)}
                </td>
                <td className="text-right py-1.5">
                  <button
                    type="button"
                    disabled={closing === `paper:spot:${p.pair}`}
                    onClick={() => void onClose(p.pair, "paper", "spot", p.volume)}
                    className="inline-flex items-center gap-1 px-2 py-1 rounded border border-rose-500/30 text-rose-300 hover:bg-rose-500/10 cursor-pointer disabled:opacity-40"
                  >
                    <XCircle className="w-3 h-3" />
                    {de ? "Schließen" : "Close"}
                  </button>
                </td>
              </tr>
            ))}
            {!paperSpot.length ? (
              <tr>
                <td colSpan={7} className="py-4 text-slate-500 text-center">
                  {de ? "Keine Spot-Positionen" : "No spot positions"}
                </td>
              </tr>
            ) : null}
          </tbody>
        </table>
      </section>

      <section className="bg-slate-900/40 border border-cyan-500/20 rounded-xl p-4 overflow-x-auto">
        <h2 className="text-xs font-mono text-cyan-300 uppercase tracking-widest mb-3">
          {de ? "Paper Futures" : "Paper futures"}
        </h2>
        <table className="w-full text-[10px] font-mono text-slate-300">
          <thead>
            <tr className="text-slate-500 border-b border-white/5">
              <th className="text-left py-1">Pair</th>
              <th className="text-left py-1">Side</th>
              <th className="text-right py-1">Lev</th>
              <th className="text-right py-1">Vol</th>
              <th className="text-right py-1">Entry</th>
              <th className="text-right py-1">Mark</th>
              <th className="text-right py-1">uPnL</th>
              <th className="text-right py-1">{de ? "Aktion" : "Action"}</th>
            </tr>
          </thead>
          <tbody>
            {paperFutures.map((p) => (
              <tr key={`fut-${p.pair}`} className="border-b border-white/5">
                <td className="py-1.5">{p.pair}</td>
                <td className="py-1.5 uppercase">{p.side ?? "—"}</td>
                <td className="text-right py-1.5">{p.leverage ?? "—"}</td>
                <td className="text-right py-1.5">{p.volume}</td>
                <td className="text-right py-1.5">{fmtUsd(p.avg_entry)}</td>
                <td className="text-right py-1.5">{fmtUsd(p.mark_price)}</td>
                <td className={`text-right py-1.5 ${pnlClass(p.unrealized_pnl_usd)}`}>
                  {fmtUsd(p.unrealized_pnl_usd)}
                </td>
                <td className="text-right py-1.5">
                  <button
                    type="button"
                    disabled={closing === `paper:futures:${p.pair}`}
                    onClick={() => void onClose(p.pair, "paper", "futures", p.volume)}
                    className="inline-flex items-center gap-1 px-2 py-1 rounded border border-rose-500/30 text-rose-300 hover:bg-rose-500/10 cursor-pointer disabled:opacity-40"
                  >
                    <XCircle className="w-3 h-3" />
                    {de ? "Schließen" : "Close"}
                  </button>
                </td>
              </tr>
            ))}
            {!paperFutures.length ? (
              <tr>
                <td colSpan={8} className="py-4 text-slate-500 text-center">
                  {de ? "Keine Futures-Positionen" : "No futures positions"}
                </td>
              </tr>
            ) : null}
          </tbody>
        </table>
      </section>

      <section className="bg-slate-900/40 border border-cyan-500/20 rounded-xl p-4 overflow-x-auto">
        <h2 className="text-xs font-mono text-cyan-300 uppercase tracking-widest mb-3">
          {de ? "Live-Positionen (Kraken Balance)" : "Live positions (Kraken balance)"}
        </h2>
        {!snap?.live_trading_enabled ? (
          <p className="text-[10px] font-mono text-slate-500 mb-3">
            {de
              ? "Live-Trading ist deaktiviert — Balances werden nur angezeigt, wenn Kraken CLI erreichbar ist."
              : "Live trading is disabled — balances shown when Kraken CLI is available (read-only)."}
          </p>
        ) : null}
        <table className="w-full text-[10px] font-mono text-slate-300">
          <thead>
            <tr className="text-slate-500 border-b border-white/5">
              <th className="text-left py-1">Asset</th>
              <th className="text-left py-1">Pair</th>
              <th className="text-right py-1">Vol</th>
              <th className="text-right py-1">Mark</th>
              <th className="text-right py-1">Value</th>
              <th className="text-right py-1">{de ? "Aktion" : "Action"}</th>
            </tr>
          </thead>
          <tbody>
            {(snap?.live ?? []).map((p) => (
              <tr key={`${p.asset}-${p.pair}`} className="border-b border-white/5">
                <td className="py-1.5">{p.asset}</td>
                <td className="py-1.5">{p.pair}</td>
                <td className="text-right py-1.5">{p.volume}</td>
                <td className="text-right py-1.5">{fmtUsd(p.mark_price)}</td>
                <td className="text-right py-1.5">{fmtUsd(p.market_value_usd)}</td>
                <td className="text-right py-1.5">
                  <button
                    type="button"
                    disabled={!snap?.live_close_available || closing === `live:${p.pair}`}
                    onClick={() => void onClose(p.pair, "live", "spot", p.volume)}
                    className="inline-flex items-center gap-1 px-2 py-1 rounded border border-rose-500/30 text-rose-300 hover:bg-rose-500/10 cursor-pointer disabled:opacity-40"
                    title={
                      snap?.live_close_available
                        ? undefined
                        : de
                          ? "Live-Schließen erfordert KRAKEN_LIVE_TRADING_ENABLED + Autonomy ≥ 3"
                          : "Live close requires KRAKEN_LIVE_TRADING_ENABLED + autonomy ≥ 3"
                    }
                  >
                    <XCircle className="w-3 h-3" />
                    {de ? "Schließen" : "Close"}
                  </button>
                </td>
              </tr>
            ))}
            {!snap?.live?.length ? (
              <tr>
                <td colSpan={6} className="py-4 text-slate-500 text-center">
                  {de ? "Keine Live-Bestände erkannt" : "No live holdings detected"}
                </td>
              </tr>
            ) : null}
          </tbody>
        </table>
      </section>

      {(snap?.open_orders ?? []).length > 0 ? (
        <section className="bg-slate-900/40 border border-white/5 rounded-xl p-4 overflow-x-auto">
          <h2 className="text-xs font-mono text-slate-400 uppercase tracking-widest mb-3">
            {de ? "Offene Live-Orders" : "Open live orders"}
          </h2>
          <table className="w-full text-[10px] font-mono text-slate-300">
            <thead>
              <tr className="text-slate-500 border-b border-white/5">
                <th className="text-left py-1">Pair</th>
                <th className="text-left py-1">Side</th>
                <th className="text-right py-1">Vol</th>
                <th className="text-right py-1">Price</th>
                <th className="text-left py-1">Status</th>
              </tr>
            </thead>
            <tbody>
              {snap!.open_orders.map((o) => (
                <tr key={o.order_id || `${o.pair}-${o.side}`} className="border-b border-white/5">
                  <td className="py-1">{o.pair}</td>
                  <td className="py-1 uppercase">{o.side}</td>
                  <td className="text-right py-1">{o.volume}</td>
                  <td className="text-right py-1">{o.price}</td>
                  <td className="py-1">{o.status}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      ) : null}
    </div>
  );
}
