import React from "react";
import { Trade } from "../types";
import { ResponsiveContainer, ComposedChart, Line, Bar, XAxis, YAxis, Tooltip, CartesianGrid } from "recharts";
import { FileText, TrendingUp, DollarSign, BarChart3, Clock, HelpCircle } from "lucide-react";

interface ExecutedTradesSectionProps {
  trades: Trade[];
  chartData: { time: string; pnl: number; volume: number }[];
}

export default function ExecutedTradesSection({ trades, chartData }: ExecutedTradesSectionProps) {
  // Calculate statistics
  const totalPnL = trades.reduce((acc, t) => acc + t.pnl, 0);
  const totalTrades = trades.length;
  const winningTrades = trades.filter((t) => t.pnl > 0).length;
  const winRate = totalTrades > 0 ? (winningTrades / totalTrades) * 100 : 0;
  const avgPnL = totalTrades > 0 ? totalPnL / totalTrades : 0;

  return (
    <div id="executed-trades-card" className="bg-slate-900/40 border border-white/5 hover:border-white/10 rounded-xl p-5 glow-cyan font-mono text-xs space-y-6 transition-all duration-300">
      {/* Header and statistics panel */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-white/10 pb-4">
        <div className="flex items-center gap-2">
          <span className="w-2 h-2 rounded-full bg-cyan-400 animate-pulse"></span>
          <h3 className="text-white font-bold uppercase tracking-wider text-[11px]">
            EXECUTED TRADE ANALYSIS / HISTORY
          </h3>
        </div>

        {/* Stats strip */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 flex-1 md:flex-none">
          <div className="bg-slate-950/60 border border-white/5 rounded-sm p-2 text-center">
            <span className="text-[9px] text-slate-500 uppercase block font-semibold">// Profit / Loss:</span>
            <span className={`text-[11px] font-extrabold ${totalPnL >= 0 ? "text-emerald-400" : "text-rose-400"}`}>
              ${totalPnL.toFixed(2)}
            </span>
          </div>
          <div className="bg-slate-950/60 border border-white/5 rounded-sm p-2 text-center">
            <span className="text-[9px] text-slate-500 uppercase block font-semibold">// Win Rate:</span>
            <span className="text-[11px] font-extrabold text-cyan-400">{winRate.toFixed(1)}%</span>
          </div>
          <div className="bg-slate-950/60 border border-white/5 rounded-sm p-2 text-center">
            <span className="text-[9px] text-slate-500 uppercase block font-semibold">// Executions:</span>
            <span className="text-[11px] font-extrabold text-slate-300">{totalTrades}</span>
          </div>
          <div className="bg-slate-950/60 border border-white/5 rounded-sm p-2 text-center">
            <span className="text-[9px] text-slate-500 uppercase block font-semibold">// Average PnL:</span>
            <span className={`text-[11px] font-extrabold ${avgPnL >= 0 ? "text-emerald-400" : "text-rose-400"}`}>
              ${avgPnL.toFixed(2)}
            </span>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Main combined Recharts graph */}
        <div className="lg:col-span-2 space-y-2">
          <h4 className="text-[10px] text-slate-400 uppercase tracking-wider flex items-center gap-1.5 font-semibold">
            <BarChart3 className="w-3.5 h-3.5 text-cyan-400" />
            COMPOSITE PNL & VOLUME VECTORS:
          </h4>
          <div className="h-64 bg-slate-950/60 rounded-xl p-2.5 border border-white/5">
            <ResponsiveContainer width="100%" height="100%">
              <ComposedChart data={chartData} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                <defs>
                  <linearGradient id="pnlGlow" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#10b981" stopOpacity={0.3} />
                    <stop offset="95%" stopColor="#10b981" stopOpacity={0.0} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
                <XAxis dataKey="time" stroke="#475569" fontSize={9} />
                <YAxis yAxisId="left" stroke="#475569" fontSize={9} />
                <YAxis yAxisId="right" orientation="right" stroke="#475569" fontSize={9} />
                <Tooltip
                  contentStyle={{ backgroundColor: "#0f172a", borderColor: "#334155", borderRadius: "8px", fontSize: "10px" }}
                  labelStyle={{ color: "#64748b" }}
                />
                <Bar yAxisId="right" dataKey="volume" fill="#06b6d4" radius={[2, 2, 0, 0]} opacity={0.3} barSize={20} />
                <Line yAxisId="left" type="monotone" dataKey="pnl" stroke="#10b981" strokeWidth={2} dot={{ r: 3, fill: "#10b981" }} activeDot={{ r: 5 }} />
              </ComposedChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Live Execution Ledger */}
        <div className="space-y-2 flex flex-col justify-between">
          <div>
            <h4 className="text-[10px] text-slate-400 uppercase tracking-wider flex items-center gap-1.5 mb-2 font-semibold">
              <Clock className="w-3.5 h-3.5 text-emerald-400" />
              LIVE EXECUTION LEDGER:
            </h4>
            <div className="bg-slate-950/60 border border-white/5 rounded-xl overflow-hidden h-52 overflow-y-auto">
              <div className="grid grid-cols-5 text-[9px] text-slate-500 uppercase font-semibold border-b border-white/5 p-2 bg-slate-900/20">
                <span>Time</span>
                <span>Asset</span>
                <span>Type</span>
                <span className="text-right">Size</span>
                <span className="text-right">P&L</span>
              </div>
              <div className="divide-y divide-white/5">
                {trades.slice().reverse().map((trade) => {
                  const isBuy = trade.type === "BUY";
                  return (
                    <div
                      key={trade.id}
                      className="grid grid-cols-5 items-center p-2.5 text-[10px] hover:bg-white/5 transition-colors"
                    >
                      <span className="text-slate-500">{trade.time}</span>
                      <span className="text-slate-200 font-bold">{trade.asset}</span>
                      <span className={`font-bold ${isBuy ? "text-emerald-400" : "text-rose-400"}`}>
                        {trade.type}
                      </span>
                      <span className="text-right text-slate-300">{trade.amount}</span>
                      <span className={`text-right font-extrabold ${trade.pnl >= 0 ? "text-emerald-400" : "text-rose-400"}`}>
                        {trade.pnl >= 0 ? "+" : ""}${trade.pnl.toFixed(2)}
                      </span>
                    </div>
                  );
                })}
              </div>
            </div>
          </div>

          <div className="pt-2">
            <div className="p-3 bg-slate-950/60 border border-white/5 rounded-lg flex items-center justify-between text-[10px] text-slate-500">
              <span className="uppercase font-mono">// Ledger Audit Status:</span>
              <span className="text-emerald-400 font-bold uppercase flex items-center gap-1">
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-400"></span>
                COMPLIANCE PASS
              </span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
