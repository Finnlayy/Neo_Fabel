import React, { useCallback, useEffect, useState } from "react";
import { Briefcase, RefreshCw } from "lucide-react";
import { ApiError } from "../../api/client";
import { fetchAgencyRoster, type AgencyAgentCard, type AgencyRosterResponse } from "../../api/agency";
import { useAuth } from "../../auth/AuthProvider";
import AuthPanel from "../../auth/AuthPanel";

type Props = {
  language?: "en" | "de";
};

function pct(n: number): string {
  return `${(n * 100).toFixed(0)}%`;
}

function ConfidenceBar({ value }: { value: number }) {
  const w = Math.max(0, Math.min(100, value * 100));
  return (
    <div className="h-1.5 rounded-full bg-slate-800 overflow-hidden">
      <div
        className="h-full rounded-full bg-amber-400/80 transition-all duration-500"
        style={{ width: `${w}%` }}
      />
    </div>
  );
}

function AgentJobCard({ agent, de }: { agent: AgencyAgentCard; de: boolean; key?: React.Key }) {
  return (
    <article
      data-testid={`agency-card-${agent.id}`}
      className="bg-slate-950/60 border border-white/5 rounded-xl p-4 font-mono text-xs space-y-3 hover:border-amber-500/25 transition-colors"
    >
      <header className="flex items-start justify-between gap-3">
        <div>
          <div className="text-[8px] text-slate-500 uppercase tracking-widest">
            {agent.profession}
          </div>
          <h3 className="text-white font-bold text-sm mt-0.5">{agent.name}</h3>
          <p className="text-[10px] text-slate-500 mt-0.5">
            {agent.code_name} · {agent.archetype}
          </p>
        </div>
        <div className="text-right shrink-0">
          <div className="text-[8px] text-slate-500 uppercase tracking-widest">
            {de ? "Stufe" : "Level"}
          </div>
          <div className="text-amber-300 font-black text-lg leading-none mt-0.5" data-testid="agency-level">
            {agent.level}
          </div>
          <div className="text-[9px] text-slate-400 mt-1">{agent.experience_title}</div>
        </div>
      </header>

      <div className="grid grid-cols-3 gap-2 text-[10px]">
        <div className="rounded-lg border border-white/5 bg-slate-900/50 px-2 py-1.5">
          <div className="text-[8px] text-slate-500 uppercase">{de ? "Erfahrung" : "Experience"}</div>
          <div className="text-slate-200 font-bold mt-0.5" data-testid="agency-xp">
            {agent.experience} XP
          </div>
          {agent.experience_to_next != null ? (
            <div className="text-[8px] text-slate-600 mt-0.5">→ {agent.experience_to_next}</div>
          ) : (
            <div className="text-[8px] text-slate-600 mt-0.5">{de ? "Max" : "Max"}</div>
          )}
        </div>
        <div className="rounded-lg border border-white/5 bg-slate-900/50 px-2 py-1.5 col-span-2">
          <div className="flex justify-between gap-2">
            <span className="text-[8px] text-slate-500 uppercase">
              {de ? "Konfidenz" : "Confidence"}
            </span>
            <span className="text-amber-300 font-bold" data-testid="agency-confidence">
              {pct(agent.confidence)}
            </span>
          </div>
          <div className="mt-1.5">
            <ConfidenceBar value={agent.confidence} />
          </div>
          <div className="text-[8px] text-slate-600 mt-1">
            {de ? "Genauigkeit" : "Accuracy"} {pct(agent.accuracy)} · streak {agent.current_streak}
          </div>
        </div>
      </div>

      <div>
        <div className="text-[8px] text-slate-500 uppercase tracking-widest mb-1">
          {de ? "Agenda" : "Agenda"}
        </div>
        <p className="text-[11px] text-slate-300 leading-relaxed">{agent.agenda}</p>
      </div>

      <div className="border-t border-white/5 pt-3">
        <div className="text-[8px] text-amber-500/80 uppercase tracking-widest mb-1">
          {de ? "Lebensaufgabe" : "Life task"}
        </div>
        <p className="text-[11px] text-slate-400 leading-relaxed">{agent.lifetask}</p>
      </div>
    </article>
  );
}

export default function AgencyPage({ language = "en" }: Props) {
  const de = language === "de";
  const auth = useAuth();
  const [data, setData] = useState<AgencyRosterResponse | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const reload = useCallback(async () => {
    setBusy(true);
    setError("");
    try {
      setData(await fetchAgencyRoster());
    } catch (err) {
      setError(err instanceof ApiError ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }, []);

  useEffect(() => {
    if (!auth.ready || !auth.uid) return;
    void reload();
    const id = window.setInterval(() => void reload(), 15000);
    return () => window.clearInterval(id);
  }, [auth.ready, auth.uid, reload]);

  if (!auth.ready) {
    return <div className="text-slate-400 font-mono text-sm p-6">Loading auth…</div>;
  }
  if (!auth.uid) {
    return (
      <div className="space-y-4">
        <AuthPanel />
        <p className="text-slate-500 font-mono text-xs">
          {de
            ? "Anmelden, um die Agency-Roster zu sehen."
            : "Sign in to view the agency roster."}
        </p>
      </div>
    );
  }

  const summary = data?.summary;

  return (
    <div role="tabpanel" aria-labelledby="tab-agency" className="space-y-4 max-w-[1200px] mx-auto">
      <header className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 bg-slate-950/60 border border-white/5 rounded-xl p-3 font-mono text-xs">
        <div className="flex items-start gap-3">
          <Briefcase className="w-5 h-5 text-amber-400 shrink-0 mt-0.5" aria-hidden />
          <div>
            <div className="text-[8px] text-slate-500 uppercase tracking-widest">
              {de ? "Organisation" : "Organization"}
            </div>
            <h2 className="text-white font-bold text-sm mt-0.5" data-testid="agency-title">
              {data?.agency ?? "Neo Fabel Agency"}
            </h2>
            <p className="text-[10px] text-slate-500 mt-1 max-w-xl">
              {de
                ? "Stellenkarte jedes Agenten: Stufe, Erfahrung, Konfidenz, Agenda und Lebensaufgabe. Paper only."
                : "Each agent's job card: level, experience, confidence, agenda, and life task. Paper only."}
            </p>
          </div>
        </div>
        <button
          type="button"
          onClick={() => void reload()}
          disabled={busy}
          className="inline-flex items-center gap-1.5 px-3 py-2 rounded-lg border border-white/10 text-slate-300 hover:text-white cursor-pointer disabled:opacity-50"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${busy ? "animate-spin" : ""}`} />
          {de ? "Aktualisieren" : "Refresh"}
        </button>
      </header>

      {error ? (
        <div className="text-xs font-mono text-rose-300 border border-rose-500/30 bg-rose-500/10 rounded-lg px-3 py-2">
          {error}
        </div>
      ) : null}

      {summary ? (
        <section className="grid grid-cols-2 md:grid-cols-4 gap-3 font-mono text-xs">
          <div className="rounded-xl border border-white/5 bg-slate-950/50 px-3 py-2">
            <div className="text-[8px] text-slate-500 uppercase">{de ? "Köpfe" : "Headcount"}</div>
            <div className="text-white font-bold mt-0.5">{summary.headcount}</div>
          </div>
          <div className="rounded-xl border border-white/5 bg-slate-950/50 px-3 py-2">
            <div className="text-[8px] text-slate-500 uppercase">{de ? "Ø Stufe" : "Avg level"}</div>
            <div className="text-amber-300 font-bold mt-0.5">{summary.avg_level}</div>
          </div>
          <div className="rounded-xl border border-white/5 bg-slate-950/50 px-3 py-2">
            <div className="text-[8px] text-slate-500 uppercase">
              {de ? "Ø Konfidenz" : "Avg confidence"}
            </div>
            <div className="text-amber-300 font-bold mt-0.5">{pct(summary.avg_confidence)}</div>
          </div>
          <div className="rounded-xl border border-white/5 bg-slate-950/50 px-3 py-2">
            <div className="text-[8px] text-slate-500 uppercase">{de ? "XP gesamt" : "Total XP"}</div>
            <div className="text-slate-200 font-bold mt-0.5">{summary.total_experience}</div>
          </div>
        </section>
      ) : null}

      <section className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
        {(data?.agents ?? []).map((agent) => (
          <AgentJobCard key={agent.id} agent={agent} de={de} />
        ))}
      </section>
    </div>
  );
}
