import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Scatter,
  ScatterChart,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { TvapiOptimizationRun } from "../api/ai";

type RankedPerformanceChartProps = {
  runs: TvapiOptimizationRun[];
};

type ParameterGridChartProps = {
  runs: TvapiOptimizationRun[];
  xParameter: string;
  yParameter: string;
};

const chartFrameClass = "rounded-xl border border-white/10 bg-slate-950/45 p-4";

function numericInput(run: TvapiOptimizationRun, key: string): number | null {
  const value = run.inputs?.[key];
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

export function RankedPerformanceChart({ runs }: RankedPerformanceChartProps) {
  const data = runs.map((run) => ({
    rank: run.rank,
    profitFactor: run.profitFactor,
    winRate: run.winRate,
    disqualified: run.isDisqualified,
  }));

  return (
    <section className={chartFrameClass} data-testid="ranked-performance-chart">
      <header className="mb-4">
        <h3 className="text-xs font-bold uppercase tracking-wider text-cyan-300">
          Ranked performance
        </h3>
        <p className="mt-1 text-[10px] text-slate-500">
          Profit factor and win rate from the evaluated parameter combinations.
        </p>
      </header>
      <div className="h-64">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={data}>
            <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
            <XAxis dataKey="rank" stroke="#64748b" tick={{ fontSize: 10 }} />
            <YAxis
              yAxisId="pf"
              stroke="#22d3ee"
              tick={{ fontSize: 10 }}
              label={{ value: "Profit factor", angle: -90, position: "insideLeft", fill: "#64748b" }}
            />
            <YAxis
              yAxisId="wr"
              orientation="right"
              stroke="#34d399"
              tick={{ fontSize: 10 }}
              domain={[0, 100]}
              label={{ value: "Win rate %", angle: 90, position: "insideRight", fill: "#64748b" }}
            />
            <Tooltip
              contentStyle={{ background: "#020617", border: "1px solid #334155", fontSize: 11 }}
            />
            <Legend wrapperStyle={{ fontSize: 10 }} />
            <Line
              yAxisId="pf"
              type="monotone"
              dataKey="profitFactor"
              name="Profit factor"
              stroke="#22d3ee"
              dot={false}
            />
            <Line
              yAxisId="wr"
              type="monotone"
              dataKey="winRate"
              name="Win rate %"
              stroke="#34d399"
              dot={false}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </section>
  );
}

export function ParameterGridChart({
  runs,
  xParameter,
  yParameter,
}: ParameterGridChartProps) {
  const data = runs.flatMap((run) => {
    const x = numericInput(run, xParameter);
    const y = numericInput(run, yParameter);
    return x == null || y == null
      ? []
      : [
          {
            x,
            y,
            label: run.label,
            profitFactor: run.profitFactor,
            winRate: run.winRate,
          },
        ];
  });

  return (
    <section className={chartFrameClass} data-testid="parameter-grid-chart">
      <header className="mb-4">
        <h3 className="text-xs font-bold uppercase tracking-wider text-amber-300">
          Parameter grid
        </h3>
        <p className="mt-1 text-[10px] text-slate-500">
          {xParameter} versus {yParameter}; every point is a real evaluated run.
        </p>
      </header>
      {data.length ? (
        <div className="h-64">
          <ResponsiveContainer width="100%" height="100%">
            <ScatterChart>
              <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
              <XAxis
                type="number"
                dataKey="x"
                name={xParameter}
                stroke="#64748b"
                tick={{ fontSize: 10 }}
              />
              <YAxis
                type="number"
                dataKey="y"
                name={yParameter}
                stroke="#64748b"
                tick={{ fontSize: 10 }}
              />
              <Tooltip
                cursor={{ strokeDasharray: "3 3" }}
                contentStyle={{ background: "#020617", border: "1px solid #334155", fontSize: 11 }}
              />
              <Scatter name="Evaluated runs" data={data} fill="#f59e0b" />
            </ScatterChart>
          </ResponsiveContainer>
        </div>
      ) : (
        <div className="flex h-64 items-center justify-center text-center text-xs text-slate-500">
          The optimizer response does not contain two numeric input dimensions.
        </div>
      )}
    </section>
  );
}

export function RunRobustnessChart({ runs }: RankedPerformanceChartProps) {
  const data = runs.map((run) => ({
    trades: run.trades,
    profitFactor: run.profitFactor,
    label: run.label,
    winRate: run.winRate,
    netProfit: run.netProfit,
  }));

  return (
    <section className={chartFrameClass} data-testid="run-robustness-chart">
      <header className="mb-4">
        <h3 className="text-xs font-bold uppercase tracking-wider text-purple-300">
          Run robustness
        </h3>
        <p className="mt-1 text-[10px] text-slate-500">
          Trade count versus profit factor. This is a run comparison, not a Monte-Carlo simulation.
        </p>
      </header>
      <div className="h-64">
        <ResponsiveContainer width="100%" height="100%">
          <ScatterChart>
            <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
            <XAxis
              type="number"
              dataKey="trades"
              name="Trades"
              stroke="#64748b"
              tick={{ fontSize: 10 }}
            />
            <YAxis
              type="number"
              dataKey="profitFactor"
              name="Profit factor"
              stroke="#64748b"
              tick={{ fontSize: 10 }}
            />
            <Tooltip
              cursor={{ strokeDasharray: "3 3" }}
              contentStyle={{ background: "#020617", border: "1px solid #334155", fontSize: 11 }}
            />
            <Scatter name="Optimization runs" data={data} fill="#a78bfa" />
          </ScatterChart>
        </ResponsiveContainer>
      </div>
    </section>
  );
}
