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

interface AcademyStatsProps {
  status: AcademyStatus | null;
}

export function AcademyStats({ status }: AcademyStatsProps) {
  return (
    <section className="grid grid-cols-2 md:grid-cols-4 gap-3">
      <Stat label="Loop" value={status?.is_running ? "RUNNING" : "IDLE"} />
      <Stat label="Cycles" value={String(status?.cycles_completed ?? 0)} />
      <Stat label="Night window" value={status?.is_night_time ? "YES" : "NO"} />
      <Stat
        label="Diversity"
        value={status?.diversity?.status?.toUpperCase() ?? "—"}
      />
    </section>
  );
}
