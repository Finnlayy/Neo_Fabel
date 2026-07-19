import React, { useCallback, useEffect, useState } from "react";
import { GraduationCap, Play, Square, RefreshCw } from "lucide-react";
import { ApiError } from "../../api/client";
import {
  evaluateDrill,
  fetchAcademyAgents,
  fetchAcademyLeaderboard,
  fetchAcademyStatus,
  fetchAvailableDrills,
  fetchCurriculum,
  runTrainingCycle,
  startTraining,
  stopTraining,
  type AcademyAgent,
  type AcademyStatus,
  type DrillResult,
  type LeaderboardEntry,
  type SyntheticDrill,
} from "../../api/academy";
import { useAuth } from "../../auth/AuthProvider";
import AuthPanel from "../../auth/AuthPanel";

export default function AcademyPage() {
  const auth = useAuth();
  const [status, setStatus] = useState<AcademyStatus | null>(null);
  const [agents, setAgents] = useState<AcademyAgent[]>([]);
  const [leaderboard, setLeaderboard] = useState<LeaderboardEntry[]>([]);
  const [scout, setScout] = useState("rna_smart");
  const [drills, setDrills] = useState<SyntheticDrill[]>([]);
  const [lastResult, setLastResult] = useState<DrillResult | null>(null);
  const [curriculum, setCurriculum] = useState<string>("");
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);

  const reload = useCallback(async () => {
    setError("");
    try {
      const [st, ag, lb] = await Promise.all([
        fetchAcademyStatus(),
        fetchAcademyAgents(),
        fetchAcademyLeaderboard(),
      ]);
      setStatus(st);
      setAgents(ag.agents);
      setLeaderboard(lb.leaderboard);
      if (st.agents?.length && !st.agents.includes(scout)) {
        setScout(st.agents[0]);
      }
    } catch (err) {
      setError((err as ApiError).message || "Failed to load academy");
    }
  }, [scout]);

  useEffect(() => {
    if (!auth.ready || !auth.uid) return;
    void reload();
    const id = window.setInterval(() => void reload(), 12000);
    return () => window.clearInterval(id);
  }, [auth.ready, auth.uid, reload]);

  async function onCycle() {
    setBusy(true);
    setMessage("");
    try {
      const res = await runTrainingCycle();
      setStatus(res.status);
      setMessage(`Training cycle complete · ${res.status.cycles_completed} cycles`);
      await reload();
    } catch (err) {
      setError((err as ApiError).message);
    } finally {
      setBusy(false);
    }
  }

  async function onStartStop() {
    setBusy(true);
    try {
      if (status?.is_running) {
        await stopTraining();
        setMessage("Training loop stopped");
      } else {
        const res = await startTraining();
        setMessage(res.started ? "Training loop started" : `Not started: ${res.reason}`);
      }
      await reload();
    } catch (err) {
      setError((err as ApiError).message);
    } finally {
      setBusy(false);
    }
  }

  async function onLoadDrills() {
    setBusy(true);
    setLastResult(null);
    try {
      const res = await fetchAvailableDrills(scout, 3);
      setDrills(res.drills);
      const cur = await fetchCurriculum(scout);
      const row = cur.curriculum[0];
      setCurriculum(
        row
          ? `${row.curriculum_level}: ${row.passed_drills}/${row.completed_drills} passed (need ${row.required_drills})`
          : "No curriculum yet",
      );
      setMessage(`Loaded ${res.drills.length} drills for ${scout}`);
    } catch (err) {
      setError((err as ApiError).message);
    } finally {
      setBusy(false);
    }
  }

  async function onEvaluate(drill: SyntheticDrill, decision: "PROCEED" | "REJECT") {
    setBusy(true);
    try {
      const result = await evaluateDrill({
        drill,
        scout_decision: decision,
        confidence: 0.75,
      });
      setLastResult(result);
      setMessage(result.is_correct ? "Correct" : "Incorrect — see feedback");
      await reload();
    } catch (err) {
      setError((err as ApiError).message);
    } finally {
      setBusy(false);
    }
  }

  if (!auth.ready) {
    return <div className="text-slate-400 font-mono text-sm p-6">Loading auth…</div>;
  }
  if (!auth.uid) {
    return (
      <div className="space-y-4">
        <AuthPanel />
        <p className="text-slate-500 font-mono text-xs">Sign in to use the Academy (dev bypass works on loopback).</p>
      </div>
    );
  }

  return (
    <div className="space-y-6 font-mono text-xs" role="tabpanel" aria-labelledby="tab-academy">
      <header className="flex flex-wrap items-start justify-between gap-4 border-b border-white/10 pb-4">
        <div className="flex items-start gap-3">
          <GraduationCap className="w-6 h-6 text-teal-400 shrink-0 mt-0.5" />
          <div>
            <h2 className="text-lg font-bold text-white tracking-tight">Agent Academy</h2>
            <p className="text-slate-500 mt-1 max-w-xl">
              Synthetic drills and career tracking for Neo sub-agents. Paper / training only — no live orders.
            </p>
          </div>
        </div>
        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            disabled={busy}
            onClick={() => void onStartStop()}
            className="inline-flex items-center gap-2 px-3 py-2 rounded-lg border border-white/10 bg-slate-900/80 text-slate-200 hover:border-teal-500/40 disabled:opacity-50"
          >
            {status?.is_running ? <Square className="w-3.5 h-3.5" /> : <Play className="w-3.5 h-3.5" />}
            {status?.is_running ? "Stop loop" : "Start loop"}
          </button>
          <button
            type="button"
            disabled={busy}
            onClick={() => void onCycle()}
            className="inline-flex items-center gap-2 px-3 py-2 rounded-lg border border-teal-500/30 bg-teal-500/10 text-teal-300 hover:bg-teal-500/20 disabled:opacity-50"
          >
            <RefreshCw className="w-3.5 h-3.5" />
            Run cycle
          </button>
        </div>
      </header>

      {error && (
        <div className="rounded-lg border border-rose-500/30 bg-rose-500/10 text-rose-300 px-3 py-2">{error}</div>
      )}
      {message && (
        <div className="rounded-lg border border-teal-500/20 bg-teal-500/5 text-teal-200/90 px-3 py-2">{message}</div>
      )}

      <section className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <Stat label="Loop" value={status?.is_running ? "RUNNING" : "IDLE"} />
        <Stat label="Cycles" value={String(status?.cycles_completed ?? 0)} />
        <Stat label="Night window" value={status?.is_night_time ? "YES" : "NO"} />
        <Stat
          label="Diversity"
          value={status?.diversity?.status?.toUpperCase() ?? "—"}
        />
      </section>

      <div className="grid grid-cols-1 xl:grid-cols-3 gap-6">
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
            {drills.map((d) => (
              <li key={d.drill_id} className="rounded-lg border border-white/5 bg-slate-900/50 p-3 space-y-2">
                <div className="flex justify-between text-[10px] text-slate-400">
                  <span>{d.drill_type}</span>
                  <span>diff {d.difficulty}</span>
                </div>
                <p className="text-slate-300 text-[11px] leading-relaxed">
                  {String(d.scenario_data.context ?? "Synthetic scenario")}
                </p>
                {d.scenario_data.mode === "blind_geometry" && (
                  <p className="text-[10px] text-amber-400/80 uppercase tracking-wide">
                    Pattern geometry only
                  </p>
                )}
                <div className="flex gap-2">
                  <button
                    type="button"
                    disabled={busy}
                    onClick={() => void onEvaluate(d, "PROCEED")}
                    className="flex-1 py-1.5 rounded border border-emerald-500/30 text-emerald-400 hover:bg-emerald-500/10"
                  >
                    PROCEED
                  </button>
                  <button
                    type="button"
                    disabled={busy}
                    onClick={() => void onEvaluate(d, "REJECT")}
                    className="flex-1 py-1.5 rounded border border-rose-500/30 text-rose-400 hover:bg-rose-500/10"
                  >
                    REJECT
                  </button>
                </div>
              </li>
            ))}
            {!drills.length && (
              <li className="text-slate-600">Load drills to practice this agent.</li>
            )}
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

        <section className="xl:col-span-1 space-y-3">
          <h3 className="text-[11px] uppercase tracking-wider text-slate-400 font-bold">Leaderboard</h3>
          <ol className="space-y-2">
            {leaderboard.map((row, i) => (
              <li
                key={row.scout_name}
                className="flex items-center justify-between rounded-lg border border-white/5 bg-slate-900/40 px-3 py-2"
              >
                <span>
                  <span className="text-slate-600 mr-2">{i + 1}.</span>
                  {row.scout_name}
                </span>
                <span className="text-slate-400">
                  {(row.accuracy * 100).toFixed(0)}% · {row.experience}xp
                </span>
              </li>
            ))}
          </ol>
          {status?.recent_drills?.length ? (
            <>
              <h3 className="text-[11px] uppercase tracking-wider text-slate-400 font-bold pt-2">
                Recent cycle drills
              </h3>
              <ul className="space-y-1 max-h-48 overflow-y-auto text-[10px] text-slate-500">
                {status.recent_drills.slice(0, 12).map((d, i) => (
                  <li key={i}>
                    {String(d.scout_name)} · {d.is_correct ? "OK" : "MISS"} ·{" "}
                    {String(d.drill_type ?? "")}
                  </li>
                ))}
              </ul>
            </>
          ) : null}
        </section>
      </div>
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-white/5 bg-slate-900/50 px-3 py-2.5">
      <div className="text-[9px] uppercase text-slate-500 tracking-wider">{label}</div>
      <div className="text-sm font-bold text-slate-100 mt-1">{value}</div>
    </div>
  );
}
