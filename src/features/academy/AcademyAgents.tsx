import React from "react";
import type { AcademyAgent } from "../../api/academy";

interface AcademyAgentsProps {
  agents: AcademyAgent[];
  scout: string;
  setScout: (scout: string) => void;
}

export function AcademyAgents({ agents, scout, setScout }: AcademyAgentsProps) {
  return (
    <section className="xl:col-span-1 space-y-3">
      <h3 className="text-[11px] uppercase tracking-wider text-slate-400 font-bold">Agents</h3>
      <ul className="space-y-2 max-h-80 overflow-y-auto">
        {agents.map((a) => (
          <li key={a.name}>
            <button
              type="button"
              onClick={() => setScout(a.name)}
              className={`w-full text-left rounded-lg border px-3 py-2 transition-colors ${
                scout === a.name
                  ? "border-teal-500/40 bg-teal-500/10 text-white"
                  : "border-white/5 bg-slate-900/40 text-slate-300 hover:border-white/15"
              }`}
            >
              <div className="flex justify-between gap-2">
                <span className="font-bold">{a.name}</span>
                <span className="text-slate-500">{(a.accuracy * 100).toFixed(0)}%</span>
              </div>
              <div className="text-[10px] text-slate-500 mt-1">
                {a.archetype} · {a.total_calls} calls · streak {a.current_streak}
              </div>
            </button>
          </li>
        ))}
      </ul>
    </section>
  );
}
