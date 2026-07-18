import React, { useState } from "react";
import { GenerativePlan } from "../types";
import { ResponsiveContainer, PieChart, Pie, Cell, Tooltip } from "recharts";
import { Sparkles, Compass, AlertCircle, Check, Loader2, HelpCircle } from "lucide-react";

interface ResourceAllocationProps {
  allocation: { name: string; value: number }[];
  activePlan: GenerativePlan | null;
  onDeployPlan: (plan: GenerativePlan) => void;
}

const ALLOCATION_COLORS = ["#10b981", "#3b82f6", "#a855f7", "#eab308", "#ec4899", "#f43f5e"];

export default function ResourceAllocation({ allocation, activePlan, onDeployPlan }: ResourceAllocationProps) {
  const [prompt, setPrompt] = useState("");
  const [isGenerating, setIsGenerating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Trigger server-side Gemini Orchestration API
  const handleOrchestratePlan = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!prompt.trim() || isGenerating) return;

    setIsGenerating(true);
    setError(null);

    try {
      const response = await fetch("/api/gemini/orchestrate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ prompt }),
      });

      const data = await response.json();
      if (response.ok) {
        onDeployPlan(data);
      } else {
        setError(data.error || "Failed to generate plan.");
      }
    } catch (err: any) {
      setError(`Failed to connect to full-stack orchestrator endpoint: ${err.message}`);
    } finally {
      setIsGenerating(false);
    }
  };

  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 font-mono text-xs">
      {/* Generative Goal Planning */}
      <div id="generative-goal-planning-card" className="bg-slate-900/40 border border-white/5 hover:border-white/10 rounded-xl p-5 glow-purple flex flex-col justify-between transition-all duration-300">
        <div className="space-y-4">
          {/* Header */}
          <div className="flex items-center justify-between border-b border-white/10 pb-3">
            <div className="flex items-center gap-2">
              <span className="w-2 h-2 rounded-full bg-purple-400 animate-pulse"></span>
              <h3 className="text-white font-bold uppercase tracking-wider text-[11px]">
                GENERATIVE GOAL PLANNING
              </h3>
            </div>
            <span className="text-[9px] text-purple-400/80 border border-purple-500/20 px-1.5 py-0.5 rounded font-mono">
              GEMINI AI ORCHESTRATOR
            </span>
          </div>

          <form onSubmit={handleOrchestratePlan} className="space-y-3">
            <label className="text-[10px] text-slate-400 uppercase leading-relaxed block font-mono">
              Enter custom trading goal, risk preferences, or market scenario directive to generate a cybernetic strategy:
            </label>
            <div className="flex gap-2">
              <input
                type="text"
                value={prompt}
                onChange={(e) => setPrompt(e.target.value)}
                placeholder="e.g. Optimize for aggressive short-term SOL momentum while hedging against ETH volatility..."
                className="flex-1 bg-slate-950 border border-white/5 focus:border-purple-500/50 rounded-sm px-3 py-2 text-slate-200 focus:outline-none placeholder:text-slate-600 placeholder:text-[10px]"
              />
              <button
                type="submit"
                disabled={isGenerating || !prompt.trim()}
                className="bg-white/5 hover:bg-white/10 border border-white/10 hover:border-white/20 text-white px-4 py-2 rounded-sm font-bold tracking-widest uppercase text-[10px] transition-all flex items-center gap-2 cursor-pointer disabled:opacity-40"
              >
                {isGenerating ? (
                  <Loader2 className="w-3.5 h-3.5 animate-spin" />
                ) : (
                  <Sparkles className="w-3.5 h-3.5 text-purple-400" />
                )}
                ORCHESTRATE
              </button>
            </div>
          </form>

          {/* Prompt presets */}
          <div className="flex flex-wrap gap-2 text-[9px]">
            <span className="text-slate-500 self-center">Presets:</span>
            {[
              "Aggressive Momentum",
              "Low Volatility Stable Yield",
              "SOL Outperformance Catalyst",
              "Whale Squeeze Protection"
            ].map((p, idx) => (
              <button
                key={idx}
                type="button"
                onClick={() => setPrompt(p)}
                className="bg-slate-950 hover:bg-white/5 border border-white/5 hover:border-white/10 px-2 py-1 rounded-sm text-slate-400 cursor-pointer transition-all"
              >
                {p}
              </button>
            ))}
          </div>

          {/* Active generated plan result panel */}
          {activePlan && (
            <div className="p-3.5 bg-purple-950/20 border border-purple-500/20 rounded-lg space-y-2.5 animate-fade-in">
              <div className="flex items-center justify-between">
                <span className="text-[10px] font-bold text-purple-300 uppercase">{activePlan.planTitle}</span>
                <span className="text-[9px] bg-purple-500/20 text-purple-400 border border-purple-500/30 px-1.5 rounded flex items-center gap-1 font-semibold">
                  <Check className="w-2.5 h-2.5 text-purple-300" />
                  Deployed
                </span>
              </div>
              <p className="text-[10px] text-slate-300 leading-relaxed">{activePlan.summary}</p>
              
              {/* Dynamic Rules guidelines */}
              {activePlan.suggestedRules && activePlan.suggestedRules.length > 0 && (
                <div className="pt-1.5 border-t border-dashed border-purple-500/10">
                  <span className="text-[9px] text-slate-400 uppercase font-semibold block mb-1">SUGGESTED ACTIVE RULES:</span>
                  <ul className="list-disc pl-3 text-[9px] text-slate-300 space-y-0.5">
                    {activePlan.suggestedRules.map((rule, rid) => (
                      <li key={rid}>{rule}</li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          )}

          {error && (
            <div className="p-2.5 bg-rose-950/20 border border-rose-500/30 rounded-sm text-rose-300 flex items-center gap-2">
              <AlertCircle className="w-4 h-4 shrink-0 text-rose-400" />
              <span>{error}</span>
            </div>
          )}
        </div>

        <div className="pt-3.5 border-t border-white/10 text-[10px] text-slate-500 flex justify-between items-center">
          <span>Active strategic model: Gemini 2.5 Flash</span>
          <span className="text-purple-400 uppercase flex items-center gap-1.5">
            <span className="w-1.5 h-1.5 rounded-full bg-purple-400 animate-ping"></span>
            Orchestrator feedback active
          </span>
        </div>
      </div>

      {/* Resource Allocation View */}
      <div id="resource-allocation-card" className="bg-slate-900/40 border border-white/5 hover:border-white/10 rounded-xl p-5 glow-emerald flex flex-col justify-between transition-all duration-300">
        <div className="space-y-4">
          {/* Header */}
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
            {/* Pie Chart display */}
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

            {/* Visual indicators class lists */}
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
    </div>
  );
}
