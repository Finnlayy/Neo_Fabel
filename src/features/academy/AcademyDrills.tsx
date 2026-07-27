import React from "react";
import type { SyntheticDrill, DrillResult } from "../../api/academy";

interface AcademyDrillsProps {
  scout: string;
  busy: boolean;
  curriculum: string;
  drills: SyntheticDrill[];
  lastResult: DrillResult | null;
  onLoadDrills: () => void;
  onEvaluate: (drill: SyntheticDrill, decision: "PROCEED" | "REJECT") => void;
}

export function AcademyDrills({
  scout,
  busy,
  curriculum,
  drills,
  lastResult,
  onLoadDrills,
  onEvaluate,
}: AcademyDrillsProps) {
  return (
    <section className="xl:col-span-1 space-y-3">
      <div className="flex items-center justify-between gap-2">
        <h3 className="text-[11px] uppercase tracking-wider text-slate-400 font-bold">Drills · {scout}</h3>
        <button
          type="button"
          disabled={busy}
          onClick={() => void onLoadDrills()}
          className="text-teal-400 hover:text-teal-300 disabled:opacity-50"
        >
          Load drills
        </button>
      </div>
      {curriculum && <p className="text-slate-500">{curriculum}</p>}
      <ul className="space-y-3">
        {drills.map((d) => (
          <li key={d.drill_id} className="rounded-lg border border-white/5 bg-slate-900/50 p-3 space-y-2">
            <div className="flex justify-between text-[10px] text-slate-400">
              <span>{d.drill_type}</span>
              <span>diff {d.difficulty}</span>
            </div>
            <p className="text-slate-300 text-[11px] leading-relaxed">
              {String(d.scenario_data.context ?? "Synthetic scenario")}
            </p>
            {d.scenario_data.mode === "blind_geometry" && (
              <p className="text-[10px] text-amber-400/80 uppercase tracking-wide">
                Pattern geometry only
              </p>
            )}
            <div className="flex gap-2">
              <button
                type="button"
                disabled={busy}
                onClick={() => void onEvaluate(d, "PROCEED")}
                className="flex-1 py-1.5 rounded border border-emerald-500/30 text-emerald-400 hover:bg-emerald-500/10"
              >
                PROCEED
              </button>
              <button
                type="button"
                disabled={busy}
                onClick={() => void onEvaluate(d, "REJECT")}
                className="flex-1 py-1.5 rounded border border-rose-500/30 text-rose-400 hover:bg-rose-500/10"
              >
                REJECT
              </button>
            </div>
          </li>
        ))}
        {!drills.length && (
          <li className="text-slate-600">Load drills to practice this agent.</li>
        )}
      </ul>
      {lastResult && (
        <div
          className={`rounded-lg border px-3 py-2 ${
            lastResult.is_correct
              ? "border-emerald-500/30 text-emerald-300"
              : "border-rose-500/30 text-rose-300"
          }`}
        >
          {lastResult.feedback_notes}
        </div>
      )}
    </section>
  );
}
