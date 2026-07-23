import { Activity, Database, ShieldCheck } from "lucide-react";
import type { TvapiOptimizationRun, TvapiOptimizeSuccess } from "../api/ai";
import {
  ParameterGridChart,
  RankedPerformanceChart,
  RunRobustnessChart,
} from "./OptimizationVisuals";

type OptimizationDashboardProps = {
  activeSymbol: string;
  strategyName: string;
  result: TvapiOptimizeSuccess;
};

export function numericParameterNames(runs: TvapiOptimizationRun[]): string[] {
  const values = new Map<string, Set<number>>();

  for (const run of runs) {
    for (const [key, value] of Object.entries(run.inputs ?? {})) {
      if (typeof value !== "number" || !Number.isFinite(value)) continue;
      const seen = values.get(key) ?? new Set<number>();
      seen.add(value);
      values.set(key, seen);
    }
  }

  return [...values.entries()]
    .filter(([, distinct]) => distinct.size > 1)
    .map(([name]) => name);
}

function metric(value: number | undefined, digits = 2): string {
  return typeof value === "number" && Number.isFinite(value) ? value.toFixed(digits) : "Unavailable";
}

export default function OptimizationDashboard({
  activeSymbol,
  strategyName,
  result,
}: OptimizationDashboardProps) {
  const validRuns = result.results.filter((run) => !run.isDisqualified);
  const parameters = numericParameterNames(result.results);
  const winner = result.winner;

  return (
    <section
      className="space-y-5 rounded-2xl border border-cyan-500/15 bg-slate-900/35 p-5 font-mono"
      data-testid="optimization-dashboard"
    >
      <header className="flex flex-col gap-3 border-b border-white/10 pb-4 md:flex-row md:items-center md:justify-between">
        <div>
          <div className="flex items-center gap-2 text-cyan-300">
            <Activity className="h-4 w-4" />
            <h2 className="text-sm font-bold uppercase tracking-wider">
              Optimization evidence
            </h2>
          </div>
          <p className="mt-1 text-[10px] text-slate-500">
            {strategyName} · {activeSymbol}
          </p>
        </div>
        <div className="flex flex-wrap gap-2 text-[9px] uppercase tracking-wider">
          <span className="rounded border border-cyan-500/20 bg-cyan-500/5 px-2 py-1 text-cyan-300">
            Source: {result.source}
          </span>
          <span className="rounded border border-white/10 bg-slate-950/60 px-2 py-1 text-slate-400">
            {result.candlesUsed ?? "?"} candles
          </span>
          <span className="rounded border border-white/10 bg-slate-950/60 px-2 py-1 text-slate-400">
            {result.tested ?? result.results.length} tested
          </span>
        </div>
      </header>

      <div className="grid grid-cols-2 gap-3 lg:grid-cols-5">
        <MetricCard label="Winner" value={winner?.label ?? "None"} />
        <MetricCard label="Profit factor" value={metric(winner?.profitFactor)} />
        <MetricCard label="Win rate" value={winner ? `${metric(winner.winRate, 1)}%` : "Unavailable"} />
        <MetricCard label="Net profit" value={winner ? metric(winner.netProfit) : "Unavailable"} />
        <MetricCard label="Max drawdown" value={winner ? metric(winner.maxDrawdown) : "Unavailable"} />
      </div>

      {result.results.length ? (
        <>
          <div className="grid grid-cols-1 gap-5 xl:grid-cols-2">
            <RankedPerformanceChart runs={result.results} />
            {parameters.length >= 2 ? (
              <ParameterGridChart
                runs={result.results}
                xParameter={parameters[0]}
                yParameter={parameters[1]}
              />
            ) : (
              <section className="flex min-h-72 items-center justify-center rounded-xl border border-white/10 bg-slate-950/45 p-6 text-center">
                <div>
                  <h3 className="text-xs font-bold uppercase tracking-wider text-amber-300">
                    Parameter grid unavailable
                  </h3>
                  <p className="mt-2 max-w-sm text-[10px] leading-relaxed text-slate-500">
                    This response does not expose two varying numeric input dimensions. No synthetic
                    grid is generated.
                  </p>
                </div>
              </section>
            )}
          </div>
          <RunRobustnessChart runs={result.results} />
        </>
      ) : (
        <div className="rounded-xl border border-white/10 bg-slate-950/40 p-8 text-center text-xs text-slate-500">
          The optimizer returned no ranked runs to visualize.
        </div>
      )}

      <footer className="flex flex-col gap-2 rounded-xl border border-emerald-500/15 bg-emerald-500/5 p-3 text-[10px] text-slate-400 sm:flex-row sm:items-center sm:justify-between">
        <span className="flex items-center gap-2">
          <Database className="h-3.5 w-3.5 text-emerald-400" />
          Showing {validRuns.length} valid of {result.results.length} returned runs.
        </span>
        <span className="flex items-center gap-2">
          <ShieldCheck className="h-3.5 w-3.5 text-emerald-400" />
          Read-only visualization · no strategy inputs are changed
        </span>
      </footer>
    </section>
  );
}

function MetricCard({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-xl border border-white/10 bg-slate-950/50 p-3">
      <div className="text-[9px] uppercase tracking-wider text-slate-500">{label}</div>
      <div className="mt-1 truncate text-sm font-bold text-slate-200" title={value}>
        {value}
      </div>
    </div>
  );
}
