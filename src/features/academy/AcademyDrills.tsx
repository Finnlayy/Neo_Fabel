import React from "react";
import type { DrillResult, SyntheticDrill } from "../../api/academy";

interface AcademyDrillsProps {
  scout: string;
  busy: boolean;
  curriculum: string;
  drills: SyntheticDrill[];
  lastResult: DrillResult | null;
  onLoadDrills: () => void;
  onEvaluate: (drill: SyntheticDrill, decision: string) => void;
}

function actionTone(action: string) {
  const normalized = action.toUpperCase();
  if (["PROCEED", "ALLOW", "APPROVE", "BULLISH_BRIEF"].includes(normalized)) {
    return "border-emerald-500/30 text-emerald-400 hover:bg-emerald-500/10";
  }
  if (
    ["REJECT", "STALE", "INCOMPLETE", "REJECT_FILL", "BLOCK", "BLOCKED", "FORCE_FLAT", "BEARISH_BRIEF", "VETO_TO_RISK"].includes(
      normalized,
    )
  ) {
    return "border-rose-500/30 text-rose-400 hover:bg-rose-500/10";
  }
  return "border-amber-500/30 text-amber-300 hover:bg-amber-500/10";
}

function Chip({ label }: { label: string }) {
  return (
    <span className="rounded-full px-2 py-0.5 text-[9px] font-medium bg-slate-800 text-slate-300 border border-white/10">
      {label}
    </span>
  );
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
        {drills.map((drill) => {
          const actions =
            Array.isArray(drill.scenario_data.actions) && drill.scenario_data.actions.length > 0
              ? (drill.scenario_data.actions as string[])
              : ["PROCEED", "REJECT"];
          const provenance = drill.scenario_data.data_provenance;
          const freshness = drill.scenario_data.freshness as
            | { last_bar_age_sec?: number; gaps?: number; received_bars?: number; expected_bars?: number }
            | undefined;
          const metrics = drill.scenario_data.metrics as
            | { slippage_bps?: number; fill_ratio?: number; spread_bps?: number }
            | undefined;
          return (
            <li
              key={drill.drill_id}
              className="rounded-lg border border-white/5 bg-slate-900/50 p-3 space-y-2"
            >
              <div className="flex justify-between text-[10px] text-slate-400">
                <span>{drill.drill_type}</span>
                <span>diff {drill.difficulty}</span>
              </div>
              <p className="text-slate-300 text-[11px] leading-relaxed">
                {String(drill.scenario_data.context ?? "Synthetic scenario")}
              </p>
              {provenance ? (
                <div className="flex flex-wrap gap-1">
                  <Chip label={String(provenance.primary ?? "fixture")} />
                  {provenance.fallback_used ? <Chip label="fallback" /> : null}
                  {(provenance.secondary_sources || []).map((source) => (
                    <Chip key={source} label={source} />
                  ))}
                </div>
              ) : null}
              {drill.scenario_data.mode === "blind_geometry" ? (
                <p className="text-[10px] text-amber-400/80 uppercase tracking-wide">
                  Pattern geometry only
                </p>
              ) : null}
              {drill.scenario_data.mode === "chronos_kline" ? (
                <p className="text-[10px] text-cyan-400/90">
                  Chronos · bias={String(drill.scenario_data.planted_bias ?? "—")} · L=
                  {String(drill.scenario_data.lookback ?? "—")} · pred=
                  {String(drill.scenario_data.pred_len ?? "—")}
                </p>
              ) : null}
              {drill.scenario_data.mode === "market_tape" && freshness ? (
                <p className="text-[10px] text-slate-500">
                  age={freshness.last_bar_age_sec}s · gaps={freshness.gaps} · bars{" "}
                  {freshness.received_bars}/{freshness.expected_bars}
                </p>
              ) : null}
              {drill.scenario_data.mode === "paper_execution" && metrics ? (
                <p className="text-[10px] text-slate-500">
                  slip={metrics.slippage_bps}bps · fill={metrics.fill_ratio} · spread={metrics.spread_bps}bps
                </p>
              ) : null}
              <div className="flex flex-wrap gap-2">
                {actions.map((action) => (
                  <button
                    key={action}
                    type="button"
                    disabled={busy}
                    onClick={() => void onEvaluate(drill, action)}
                    className={`flex-1 min-w-[5.5rem] py-1.5 rounded border text-[10px] ${actionTone(action)}`}
                  >
                    {action}
                  </button>
                ))}
              </div>
            </li>
          );
        })}
        {!drills.length && <li className="text-slate-600">Load drills to practice this agent.</li>}
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
