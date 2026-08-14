import React from "react";
import type { AcademyAgent, AcademyStatus } from "../../api/academy";

interface AcademyAgentsProps {
  agents: AcademyAgent[];
  status: AcademyStatus | null;
  scout: string;
  setScout: (scout: string) => void;
}

export function AcademyAgents({ agents, status, scout, setScout }: AcademyAgentsProps) {
  const visibleAgents = status?.agents?.length
    ? agents.filter((agent) => status.agents.includes(agent.name))
    : agents;

  return (
    <section className="xl:col-span-1 space-y-3">
      <h3 className="text-[11px] uppercase tracking-wider text-slate-400 font-bold">
        Agents
        {status?.train_trading_only ? (
          <span className="ml-2 font-normal text-slate-600 normal-case tracking-normal">
            · trading path only
          </span>
        ) : null}
      </h3>
      <ul className="space-y-2 max-h-80 overflow-y-auto">
        {visibleAgents.map((agent) => (
          <li key={agent.name}>
            <button
              type="button"
              onClick={() => setScout(agent.name)}
              className={`w-full text-left rounded-lg border px-3 py-2 transition-colors ${
                scout === agent.name
                  ? "border-teal-500/40 bg-teal-500/10 text-white"
                  : "border-white/5 bg-slate-900/40 text-slate-300 hover:border-white/15"
              }`}
            >
              <div className="flex justify-between gap-2">
                <span className="font-bold">{agent.name}</span>
                <span className="text-slate-500">{(agent.accuracy * 100).toFixed(0)}%</span>
              </div>
              <div className="text-[10px] text-slate-500 mt-1">
                {agent.archetype} · {agent.total_calls} calls · streak {agent.current_streak}
              </div>
            </button>
          </li>
        ))}
      </ul>
    </section>
  );
}
