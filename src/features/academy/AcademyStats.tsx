import React from "react";
import type { AcademyStatus } from "../../api/academy";

export function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-white/5 bg-slate-900/50 px-3 py-2.5">
      <div className="text-[9px] uppercase text-slate-500 tracking-wider">{label}</div>
      <div className="text-sm font-bold text-slate-100 mt-1">{value}</div>
    </div>
  );
}

export function AcademyStats({ status }: { status: AcademyStatus | null }) {
  return (
    <>
      <section className="grid grid-cols-2 md:grid-cols-6 gap-3">
        <Stat label="Loop" value={status?.is_running ? "RUNNING" : "IDLE"} />
        <Stat
          label="Enabled"
          value={status?.enabled ? (status.session_enabled ? "SESSION" : "ENV") : "OFF"}
        />
        <Stat label="Cycles" value={String(status?.cycles_completed ?? 0)} />
        <Stat label="Data" value={(status?.drill_market_source ?? "fixture").toUpperCase()} />
        <Stat
          label="Night window"
          value={status?.night_mode === false ? "OFF" : status?.is_night_time ? "YES" : "WAIT"}
        />
        <Stat label="Diversity" value={status?.diversity?.status?.toUpperCase() ?? "—"} />
      </section>
      {status && !status.enabled && status.hint ? (
        <div className="rounded-lg border border-amber-500/30 bg-amber-500/10 text-amber-200 px-3 py-2">
          {status.hint}
        </div>
      ) : null}
      {status?.last_skip_reason === "WAITING_FOR_NIGHT_WINDOW" ? (
        <div className="rounded-lg border border-amber-500/30 bg-amber-500/10 text-amber-200 px-3 py-2">
          Auto-cycles paused until night window. Use <span className="font-bold">Run cycle</span> anytime,
          or set TRAINING_LOOP_NIGHT_MODE=false.
        </div>
      ) : null}
    </>
  );
}
