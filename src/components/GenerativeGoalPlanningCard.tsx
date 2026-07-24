import React, { useState } from "react";
import { AgentStatusPacket, GenerativePlan } from "../types";
import { Sparkles, AlertCircle, Check, Loader2 } from "lucide-react";
import { ApiError } from "../api/client";
import { postOrchestrate } from "../api/ai";

interface GenerativeGoalPlanningCardProps {
  activePlan: GenerativePlan | null;
  onDeployPlan: (plan: GenerativePlan) => void;
  agentStatusPackets?: AgentStatusPacket[];
}

export default function GenerativeGoalPlanningCard({
  activePlan,
  onDeployPlan,
  agentStatusPackets = [],
}: GenerativeGoalPlanningCardProps) {
  const [prompt, setPrompt] = useState("");
  const [isGenerating, setIsGenerating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleOrchestratePlan = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!prompt.trim() || isGenerating) return;

    setIsGenerating(true);
    setError(null);

    try {
      const plan = await postOrchestrate(prompt, agentStatusPackets);
      onDeployPlan(plan);
    } catch (err: unknown) {
      const message =
        err instanceof ApiError ? `${err.code}: ${err.message}` : err instanceof Error ? err.message : "Unknown error";
      setError(`Orchestrator unavailable: ${message}`);
    } finally {
      setIsGenerating(false);
    }
  };

  return (
      <div id="generative-goal-planning-card" className="bg-slate-900/40 border border-white/5 hover:border-white/10 rounded-xl p-5 glow-purple flex flex-col justify-between transition-all duration-300">
        <div className="space-y-4">
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
  );
}
