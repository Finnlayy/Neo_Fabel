/* =========================================================
   Datei:      FableEnginePanel.tsx
   Zweck:      Read-only Fable Engine Status + Dry-Run-Feed (Grid/DCA, paper-only)
   Abhängig.:  ./api (fetchEngineStatus, fetchEngineDryRuns), React
   ========================================================= */
import React, { useCallback, useEffect, useState } from "react";
import {
  fetchEngineDryRuns,
  fetchEngineStatus,
  type FableEngineDryRun,
  type FableEngineStatus,
} from "./api";

const POLL_MS = 15000;

function Chip({ label, tone }: { label: string; tone: "ok" | "warn" | "muted" }) {
  const cls =
    tone === "ok"
      ? "bg-emerald-100 text-emerald-800"
      : tone === "warn"
        ? "bg-amber-100 text-amber-800"
        : "bg-slate-100 text-slate-600";
  return <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${cls}`}>{label}</span>;
}

export default function FableEnginePanel() {
  const [status, setStatus] = useState<FableEngineStatus | null>(null);
  const [dryRuns, setDryRuns] = useState<FableEngineDryRun[]>([]);
  const [error, setError] = useState<string>("");

  const reload = useCallback(async () => {
    try {
      const [st, runs] = await Promise.all([fetchEngineStatus(), fetchEngineDryRuns(50)]);
      setStatus(st);
      // newest first for display
      setDryRuns([...runs].reverse());
      setError("");
    } catch (err) {
      setError((err as Error).message || "Fable Engine status unavailable");
    }
  }, []);

  useEffect(() => {
    void reload();
    const id = window.setInterval(() => void reload(), POLL_MS);
    return () => window.clearInterval(id);
  }, [reload]);

  return (
    <section className="mb-4 rounded-lg border border-slate-200 bg-slate-50 p-3">
      <div className="flex flex-wrap items-center gap-2">
        <h3 className="mr-2 text-sm font-semibold text-slate-800">Fable Engine</h3>
        {status === null ? (
          <Chip label={error ? "unavailable" : "loading…"} tone="muted" />
        ) : (
          <>
            <Chip
              label={status.started ? "running" : status.enabled ? "enabled (not started)" : "disabled"}
              tone={status.started ? "ok" : "muted"}
            />
            <Chip label={status.dry_run ? "DRY-RUN" : "paper-intake"} tone={status.dry_run ? "ok" : "warn"} />
            <Chip label={`candles: ${status.candle_source} ${status.interval}`} tone="muted" />
            <Chip label={`${status.strategy_count} strategies`} tone="muted" />
            <Chip label={`${status.ticks} ticks`} tone="muted" />
            {status.last_error ? <Chip label={`err: ${status.last_error.slice(0, 40)}`} tone="warn" /> : null}
          </>
        )}
      </div>
      {status?.note ? <p className="mt-2 text-xs text-slate-500">{status.note}</p> : null}
      {error ? <p className="mt-2 text-xs text-amber-700">{error}</p> : null}

      {dryRuns.length > 0 ? (
        <div className="mt-3 max-h-64 overflow-auto rounded border border-slate-200 bg-white">
          <table className="w-full text-left text-xs">
            <thead className="sticky top-0 bg-slate-100 text-slate-600">
              <tr>
                <th className="px-2 py-1">Zeit (UTC)</th>
                <th className="px-2 py-1">Strategie</th>
                <th className="px-2 py-1">Pair</th>
                <th className="px-2 py-1">Seite</th>
                <th className="px-2 py-1">Volumen</th>
                <th className="px-2 py-1">Preis</th>
                <th className="px-2 py-1">Grund</th>
              </tr>
            </thead>
            <tbody>
              {dryRuns.map((run, idx) => (
                <tr key={`${run.strategy_id}-${run.recorded_at}-${idx}`} className="border-t border-slate-100">
                  <td className="px-2 py-1 font-mono text-slate-500">
                    {run.recorded_at.replace("T", " ").slice(0, 19)}
                  </td>
                  <td className="px-2 py-1">
                    {run.strategy_id}
                    <span className="ml-1 text-slate-400">({run.kind}{run.zone !== null ? ` z${run.zone}` : ""})</span>
                  </td>
                  <td className="px-2 py-1">{run.pair}</td>
                  <td className={`px-2 py-1 font-semibold ${run.side === "buy" ? "text-emerald-700" : "text-rose-700"}`}>
                    {run.side}
                  </td>
                  <td className="px-2 py-1 font-mono">{run.volume}</td>
                  <td className="px-2 py-1 font-mono">{run.price !== null ? run.price : "—"}</td>
                  <td className="px-2 py-1 text-slate-500">{run.reason}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <p className="mt-2 text-xs text-slate-400">
          Keine Dry-Run-Signale bisher{status?.started ? " — Engine läuft, wartet auf Trigger." : "."}
        </p>
      )}
    </section>
  );
}
