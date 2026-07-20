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
  fetchRecentCareers,
  runTrainingCycle,
  startTraining,
  stopTraining,
  type AcademyAgent,
  type AcademyStatus,
  type CareerEntry,
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
  const [careers, setCareers] = useState<CareerEntry[]>([]);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);

  const reload = useCallback(async () => {
    setError("");
    try {
      const [st, ag, lb, cr] = await Promise.all([
        fetchAcademyStatus(),
        fetchAcademyAgents(),
        fetchAcademyLeaderboard(),
        fetchRecentCareers(16),
      ]);
      setStatus(st);
      setAgents(ag.agents);
      setLeaderboard(lb.leaderboard);
      setCareers(cr.career);
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
        if (res.started) {
          const nightNote =
            res.night_mode && res.is_night_time === false
              ? " (night mode on — further auto-cycles wait for the night window; use Run cycle anytime)"
              : "";
          setMessage(
            res.session_enabled
              ? `Training loop started (dev session-enabled)${nightNote}`
              : `Training loop started${nightNote}`,
          );
        } else {
          const hint =
            res.hint ||
            (res.reason === "TRAINING_LOOP_DISABLED"
              ? "Set TRAINING_LOOP_ENABLED=true in .env.local and restart the API."
              : "");
          setError(
            `Loop not started: ${res.reason || "unknown"}${res.error ? ` — ${res.error}` : ""}${
              hint ? ` · ${hint}` : ""
            }`,
          );
          setMessage("");
        }
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

  async function onEvaluate(drill: SyntheticDrill, decision: string) {
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

  function actionTone(action: string): string {
    const a = action.toUpperCase();
    if (
      ["PROCEED", "FRESH", "ACCEPT_FILL", "ALLOW_PAPER", "HANDOFF", "CONCLUSION", "BULLISH_BRIEF", "LOOSEN", "HOLD_PARAMS", "TREND"].includes(
        a,
      )
    ) {
      return "border-emerald-500/30 text-emerald-400 hover:bg-emerald-500/10";
    }
    if (
      ["REJECT", "STALE", "INCOMPLETE", "REJECT_FILL", "BLOCK", "BLOCKED", "FORCE_FLAT", "BEARISH_BRIEF", "VETO_TO_RISK"].includes(
        a,
      )
    ) {
      return "border-rose-500/30 text-rose-400 hover:bg-rose-500/10";
    }
    return "border-amber-500/30 text-amber-300 hover:bg-amber-500/10";
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

      <section className="grid grid-cols-2 md:grid-cols-6 gap-3">
        <Stat label="Loop" value={status?.is_running ? "RUNNING" : "IDLE"} />
        <Stat
          label="Enabled"
          value={
            status?.enabled
              ? status.session_enabled
                ? "SESSION"
                : "ENV"
              : "OFF"
          }
        />
        <Stat label="Cycles" value={String(status?.cycles_completed ?? 0)} />
        <Stat label="Data" value={(status?.drill_market_source ?? "fixture").toUpperCase()} />
        <Stat
          label="Night window"
          value={
            status?.night_mode === false
              ? "OFF"
              : status?.is_night_time
                ? "YES"
                : "WAIT"
          }
        />
        <Stat
          label="Diversity"
          value={status?.diversity?.status?.toUpperCase() ?? "—"}
        />
      </section>
      {status && !status.enabled && status.hint ? (
        <div className="rounded-lg border border-amber-500/30 bg-amber-500/10 text-amber-200 px-3 py-2">
          {status.hint}
        </div>
      ) : null}
      {status?.last_skip_reason === "WAITING_FOR_NIGHT_WINDOW" ? (
        <div className="rounded-lg border border-amber-500/30 bg-amber-500/10 text-amber-200 px-3 py-2">
          Auto-cycles paused until night window. Use <span className="font-bold">Run cycle</span> anytime,
          or set TRAINING_LOOP_NIGHT_MODE=false.
        </div>
      ) : null}

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
            {drills.map((d) => {
              const actions =
                Array.isArray(d.scenario_data.actions) && d.scenario_data.actions.length > 0
                  ? (d.scenario_data.actions as string[])
                  : ["PROCEED", "REJECT"];
              const prov = d.scenario_data.data_provenance;
              const freshness = d.scenario_data.freshness as
                | {
                    last_bar_age_sec?: number;
                    gaps?: number;
                    received_bars?: number;
                    expected_bars?: number;
                  }
                | undefined;
              const metrics = d.scenario_data.metrics as
                | { slippage_bps?: number; fill_ratio?: number; spread_bps?: number }
                | undefined;
              const packets = d.scenario_data.packets as
                | Array<{ id?: string; status?: string }>
                | undefined;
              const uiOutcome = d.scenario_data.ui_outcome as { title?: string } | undefined;
              const state = d.scenario_data.state as
                | { session_dd_pct?: number; live_gate_requested?: boolean }
                | undefined;
              const policy = d.scenario_data.policy as { max_session_dd_pct?: number } | undefined;
              const headlines = d.scenario_data.headlines as Array<{ title?: string }> | undefined;
              return (
                <li
                  key={d.drill_id}
                  className="rounded-lg border border-white/5 bg-slate-900/50 p-3 space-y-2"
                >
                  <div className="flex justify-between text-[10px] text-slate-400">
                    <span>{d.drill_type}</span>
                    <span>diff {d.difficulty}</span>
                  </div>
                  <p className="text-slate-300 text-[11px] leading-relaxed">
                    {String(d.scenario_data.context ?? "Synthetic scenario")}
                  </p>
                  {prov ? (
                    <div className="flex flex-wrap gap-1">
                      <Chip label={String(prov.primary ?? "fixture")} />
                      {prov.fallback_used ? <Chip label="fallback" /> : null}
                      {(prov.secondary_sources || []).map((s) => (
                        <Chip key={s} label={s} />
                      ))}
                    </div>
                  ) : null}
                  {d.scenario_data.mode === "blind_geometry" && (
                    <p className="text-[10px] text-amber-400/80 uppercase tracking-wide">
                      Pattern geometry only
                    </p>
                  )}
                  {d.scenario_data.mode === "chronos_kline" && (
                    <div className="text-[10px] text-cyan-400/90 space-y-1 border border-cyan-500/15 rounded-md px-2 py-1.5 bg-cyan-500/5">
                      <p className="uppercase tracking-wide text-cyan-300/80">Chronos K-line language</p>
                      <p className="text-slate-400">
                        bias={String(d.scenario_data.planted_bias ?? "—")} · L=
                        {String(d.scenario_data.lookback ?? "—")} · pred=
                        {String(d.scenario_data.pred_len ?? "—")}
                      </p>
                    </div>
                  )}
                  {d.scenario_data.mode === "market_tape" && freshness ? (
                    <p className="text-[10px] text-slate-500">
                      age={freshness.last_bar_age_sec}s · gaps={freshness.gaps} · bars{" "}
                      {freshness.received_bars}/{freshness.expected_bars}
                    </p>
                  ) : null}
                  {d.scenario_data.mode === "paper_execution" && metrics ? (
                    <p className="text-[10px] text-slate-500">
                      slip={metrics.slippage_bps}bps · fill={metrics.fill_ratio} · spread=
                      {metrics.spread_bps}bps
                    </p>
                  ) : null}
                  {d.scenario_data.mode === "regime_forecast" ? (
                    <p className="text-[10px] text-slate-500">
                      alignment=
                      {String(
                        (d.scenario_data.mtf as { alignment_score?: number } | undefined)
                          ?.alignment_score ?? "—",
                      )}
                    </p>
                  ) : null}
                  {d.scenario_data.mode === "market_brief" && headlines?.length ? (
                    <ul className="text-[10px] text-slate-500 list-disc pl-4">
                      {headlines.slice(0, 3).map((h, i) => (
                        <li key={i}>{h.title}</li>
                      ))}
                    </ul>
                  ) : null}
                  {d.scenario_data.mode === "param_adapt" ? (
                    <p className="text-[10px] text-slate-500">
                      regime={String(d.scenario_data.regime)} · DD=
                      {String(d.scenario_data.session_dd_pct)}% /{" "}
                      {String(d.scenario_data.dd_limit_pct)}%
                    </p>
                  ) : null}
                  {d.scenario_data.mode === "teamwork" ? (
                    <div className="text-[10px] text-slate-500 space-y-1">
                      {uiOutcome?.title ? <p className="text-teal-300/80">{uiOutcome.title}</p> : null}
                      <p>{(packets || []).map((p) => `${p.id}:${p.status}`).join(" · ")}</p>
                    </div>
                  ) : null}
                  {d.scenario_data.mode === "risk_policy" && state ? (
                    <p className="text-[10px] text-slate-500">
                      DD={state.session_dd_pct}% / {policy?.max_session_dd_pct}% · live_gate=
                      {String(state.live_gate_requested)}
                    </p>
                  ) : null}
                  <div className="flex flex-wrap gap-2">
                    {actions.map((action) => (
                      <button
                        key={action}
                        type="button"
                        disabled={busy}
                        onClick={() => void onEvaluate(d, action)}
                        className={`flex-1 min-w-[5.5rem] py-1.5 rounded border text-[10px] ${actionTone(action)}`}
                      >
                        {action}
                      </button>
                    ))}
                  </div>
                </li>
              );
            })}
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
              <ul className="space-y-1 max-h-40 overflow-y-auto text-[10px] text-slate-500">
                {status.recent_drills.slice(0, 12).map((d, i) => (
                  <li key={i}>
                    {String(d.scout_name)} · {d.is_correct ? "OK" : "MISS"} ·{" "}
                    {String(d.drill_type ?? "")}
                  </li>
                ))}
              </ul>
            </>
          ) : null}
          {careers.length > 0 && (
            <>
              <h3 className="text-[11px] uppercase tracking-wider text-slate-400 font-bold pt-2">
                Career log
              </h3>
              <ul className="space-y-1 max-h-40 overflow-y-auto text-[10px] text-slate-500">
                {careers.slice(0, 12).map((c) => (
                  <li key={c.entry_id}>
                    {c.scout_name} · {c.event_type}
                    {c.details?.is_correct === true
                      ? " · OK"
                      : c.details?.is_correct === false
                        ? " · MISS"
                        : ""}
                  </li>
                ))}
              </ul>
            </>
          )}
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

function Chip({ label }: { label: string }) {
  return (
    <span className="rounded-full px-2 py-0.5 text-[9px] font-medium bg-slate-800 text-slate-300 border border-white/10">
      {label}
    </span>
  );
}
