import React from "react";
import type { SignalAutomationStatus } from "./types";

function Pill({ ok, label }: { ok: boolean; label: string }) {
  return (
    <span
      className={`inline-flex items-center min-h-11 px-3 text-xs font-semibold rounded border ${
        ok
          ? "border-emerald-600/40 text-emerald-700 bg-emerald-50"
          : "border-slate-300 text-slate-600 bg-slate-50"
      }`}
      aria-label={`${label}: ${ok ? "ready" : "off"}`}
    >
      <span className={`mr-2 h-2 w-2 rounded-sm ${ok ? "bg-emerald-600" : "bg-slate-400"}`} aria-hidden />
      {label}
    </span>
  );
}

export default function SignalSafetyHeader({ status }: { status: SignalAutomationStatus | null }) {
  return (
    <header className="mb-6 border-b border-slate-200 pb-4" aria-live="polite">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <p className="text-xs font-bold tracking-[0.2em] text-rose-700 uppercase">Paper only</p>
          <h2 className="text-xl font-semibold text-slate-900 mt-1">Signal Routes</h2>
          <p className="text-sm text-slate-600 mt-1">
            TradingView webhook and MCP ingress. Live Kraken execution is not available on this page.
          </p>
        </div>
        <div className="text-right text-xs text-slate-500">
          Target: <span className="font-mono text-slate-800">kraken_paper</span>
        </div>
      </div>
      <div className="mt-4 flex flex-wrap gap-2">
        <Pill ok={Boolean(status?.signal_routes_enabled)} label="Global gate" />
        <Pill ok={Boolean(status?.signal_worker_enabled)} label="Worker" />
        <Pill ok={Boolean(status?.tradingview_ingress_enabled)} label="TV ingress" />
        <Pill ok={Boolean(status?.mcp_signal_adapter_enabled)} label="MCP" />
        <Pill ok={Boolean(status?.ai_advisory_enabled || status?.advisory_ready)} label="AI advisory" />
        <Pill ok={Boolean(status?.signal_execution_enabled)} label="Paper dispatch" />
        <span className="inline-flex items-center min-h-11 px-3 text-xs font-mono text-slate-700 border border-slate-200 rounded bg-white">
          Queue: {status?.queue_depth ?? "—"}
        </span>
      </div>
    </header>
  );
}
