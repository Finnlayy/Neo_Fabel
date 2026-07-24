import React, { useCallback, useEffect, useState } from "react";
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

import { AcademyHeader } from "./AcademyHeader";
import { AcademyStats } from "./AcademyStats";
import { AcademyAgents } from "./AcademyAgents";
import { AcademyDrills } from "./AcademyDrills";
import { AcademyLeaderboard } from "./AcademyLeaderboard";

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
      <AcademyHeader busy={busy} status={status} onStartStop={onStartStop} onCycle={onCycle} />

      {error && (
        <div className="rounded-lg border border-rose-500/30 bg-rose-500/10 text-rose-300 px-3 py-2">{error}</div>
      )}
      {message && (
        <div className="rounded-lg border border-teal-500/20 bg-teal-500/5 text-teal-200/90 px-3 py-2">{message}</div>
      )}

      <AcademyStats status={status} />

      <div className="grid grid-cols-1 xl:grid-cols-3 gap-6">
        <AcademyAgents agents={agents} scout={scout} setScout={setScout} />

        <AcademyDrills
          scout={scout}
          busy={busy}
          curriculum={curriculum}
          drills={drills}
          lastResult={lastResult}
          onLoadDrills={onLoadDrills}
          onEvaluate={onEvaluate}
        />

        <AcademyLeaderboard leaderboard={leaderboard} status={status} />
      </div>
    </div>
  );
}

