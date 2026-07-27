import React from "react";
import { GraduationCap, Play, Square, RefreshCw } from "lucide-react";
import type { AcademyStatus } from "../../api/academy";

interface AcademyHeaderProps {
  busy: boolean;
  status: AcademyStatus | null;
  onStartStop: () => void;
  onCycle: () => void;
}

export function AcademyHeader({ busy, status, onStartStop, onCycle }: AcademyHeaderProps) {
  return (
    <header className="flex flex-wrap items-start justify-between gap-4 border-b border-white/10 pb-4">
      <div className="flex items-start gap-3">
        <GraduationCap className="w-6 h-6 text-teal-400 shrink-0 mt-0.5" />
        <div>
          <h2 className="text-lg font-bold text-white tracking-tight">Agent Academy</h2>
          <p className="text-slate-500 mt-1 max-w-xl">
            Synthetic drills and career tracking for Neo sub-agents. Paper / training only — no live orders.
          </p>
        </div>
      </div>
      <div className="flex flex-wrap gap-2">
        <button
          type="button"
          disabled={busy}
          onClick={() => void onStartStop()}
          className="inline-flex items-center gap-2 px-3 py-2 rounded-lg border border-white/10 bg-slate-900/80 text-slate-200 hover:border-teal-500/40 disabled:opacity-50"
        >
          {status?.is_running ? <Square className="w-3.5 h-3.5" /> : <Play className="w-3.5 h-3.5" />}
          {status?.is_running ? "Stop loop" : "Start loop"}
        </button>
        <button
          type="button"
          disabled={busy}
          onClick={() => void onCycle()}
          className="inline-flex items-center gap-2 px-3 py-2 rounded-lg border border-teal-500/30 bg-teal-500/10 text-teal-300 hover:bg-teal-500/20 disabled:opacity-50"
        >
          <RefreshCw className="w-3.5 h-3.5" />
          Run cycle
        </button>
      </div>
    </header>
  );
}
