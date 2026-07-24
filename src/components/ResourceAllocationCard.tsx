import React from "react";
import { ResponsiveContainer, PieChart, Pie, Cell, Tooltip } from "recharts";

interface ResourceAllocationCardProps {
  allocation: { name: string; value: number }[];
}

const ALLOCATION_COLORS = ["#10b981", "#3b82f6", "#a855f7", "#eab308", "#ec4899", "#f43f5e"];

export default function ResourceAllocationCard({ allocation }: ResourceAllocationCardProps) {
  return (
      <div id="resource-allocation-card" className="bg-slate-900/40 border border-white/5 hover:border-white/10 rounded-xl p-5 glow-emerald flex flex-col justify-between transition-all duration-300">
        <div className="space-y-4">
          <div className="flex items-center justify-between border-b border-white/10 pb-3">
            <div className="flex items-center gap-2">
              <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse"></span>
              <h3 className="text-white font-bold uppercase tracking-wider text-[11px]">
                RESOURCE ALLOCATION
              </h3>
            </div>
            <span className="text-[9px] text-emerald-400/80 border border-emerald-500/20 px-1.5 py-0.5 rounded font-mono">
              DURABLE CAPITAL WEIGHTS
            </span>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 items-center">
            <div className="h-40 relative flex items-center justify-center">
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie
                    data={allocation}
                    innerRadius={50}
                    outerRadius={65}
                    paddingAngle={3}
                    dataKey="value"
                  >
                    {allocation.map((entry, index) => (
                      <Cell key={`cell-${index}`} fill={ALLOCATION_COLORS[index % ALLOCATION_COLORS.length]} />
                    ))}
                  </Pie>
                  <Tooltip
                    contentStyle={{ backgroundColor: "#0f172a", borderColor: "#334155", borderRadius: "8px", fontSize: "10px" }}
                  />
                </PieChart>
              </ResponsiveContainer>
              <div className="absolute flex flex-col items-center">
                <span className="text-slate-400 text-[9px] uppercase">Assets Weighted:</span>
                <span className="text-white font-extrabold text-sm">{allocation.length}</span>
              </div>
            </div>

            <div className="space-y-2">
              <span className="text-[10px] text-slate-500 uppercase font-semibold block mb-1">Active Capital Multipliers:</span>
              <div className="space-y-1.5 max-h-36 overflow-y-auto pr-1">
                {allocation.map((item, index) => (
                  <div key={item.name} className="space-y-1">
                    <div className="flex justify-between items-center text-[10px]">
                      <span className="flex items-center gap-1 text-slate-300 font-semibold">
                        <span
                          className="w-2 h-2 rounded-full"
                          style={{ backgroundColor: ALLOCATION_COLORS[index % ALLOCATION_COLORS.length] }}
                        />
                        {item.name}
                      </span>
                      <span className="text-white font-bold">{item.value}%</span>
                    </div>
                    <div className="w-full bg-slate-950 rounded-full h-1">
                      <div
                        className="rounded-full h-1 transition-all duration-1000"
                        style={{
                          width: `${item.value}%`,
                          backgroundColor: ALLOCATION_COLORS[index % ALLOCATION_COLORS.length]
                        }}
                      />
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>

        <div className="pt-3.5 border-t border-white/10 text-[10px] text-slate-500 flex justify-between items-center">
          <span>Capital Limit Cap: $250,000 Safe Drawdown</span>
          <span className="text-emerald-400 uppercase flex items-center gap-1.5 font-mono">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse"></span>
            Asset pools synced
          </span>
        </div>
      </div>
  );
}
