import React, {useCallback, useEffect, useState} from "react";
import {
  fetchLoopsStatus,
  killTradingLoops,
  startLiveLoop,
  startPaperLoop,
  stopLiveLoop,
  stopPaperLoop,
  type LoopsStatus,
} from "../api/loops";
import {ApiError} from "../api/client";

type Props = {
  language?: "en" | "de";
};

function SwitchPill({
  label,
  on,
  busy,
  disabled,
  title,
  onToggle,
}: {
  label: string;
  on: boolean;
  busy: boolean;
  disabled?: boolean;
  title?: string;
  onToggle: () => void;
}) {
  return (
    <button
      type="button"
      title={title}
      disabled={busy || disabled}
      onClick={onToggle}
      className={`flex flex-col items-stretch min-w-[108px] px-2.5 py-1.5 rounded-sm border font-mono text-left cursor-pointer transition-all disabled:opacity-40 disabled:cursor-not-allowed ${
        on
          ? "bg-emerald-500/15 border-emerald-500/40 text-emerald-300"
          : "bg-white/5 border-white/10 text-slate-300 hover:border-cyan-500/30"
      }`}
    >
      <span className="text-[8px] uppercase tracking-widest text-slate-500">{label}</span>
      <span className="text-[11px] font-bold flex items-center gap-1.5 mt-0.5">
        <span className={`w-1.5 h-1.5 rounded-full ${on ? "bg-emerald-400 animate-pulse" : "bg-slate-600"}`} />
        {busy ? "…" : on ? "ON" : "OFF"}
      </span>
    </button>
  );
}

export default function TradingLoopSwitches({language = "en"}: Props) {
  const de = language === "de";
  const [status, setStatus] = useState<LoopsStatus | null>(null);
  const [error, setError] = useState("");
  const [busyPaper, setBusyPaper] = useState(false);
  const [busyLive, setBusyLive] = useState(false);
  const [confirmLive, setConfirmLive] = useState(false);

  const reload = useCallback(async () => {
    try {
      const data = await fetchLoopsStatus();
      setStatus(data);
      setError("");
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    }
  }, []);

  useEffect(() => {
    void reload();
    const id = window.setInterval(() => void reload(), 5000);
    return () => window.clearInterval(id);
  }, [reload]);

  const onPaper = async () => {
    setBusyPaper(true);
    setError("");
    try {
      if (status?.paper.running) await stopPaperLoop();
      else await startPaperLoop();
      await reload();
    } catch (err) {
      const msg =
        err instanceof ApiError
          ? err.message
          : err instanceof Error
            ? err.message
            : String(err);
      setError(msg);
    } finally {
      setBusyPaper(false);
    }
  };

  const onLive = async () => {
    if (status?.live.running) {
      setBusyLive(true);
      setError("");
      try {
        await stopLiveLoop();
        await reload();
      } catch (err) {
        setError(err instanceof Error ? err.message : String(err));
      } finally {
        setBusyLive(false);
      }
      return;
    }
    setConfirmLive(true);
  };

  const confirmStartLive = async () => {
    setConfirmLive(false);
    setBusyLive(true);
    setError("");
    try {
      await startLiveLoop();
      await reload();
    } catch (err) {
      const msg =
        err instanceof ApiError
          ? err.message
          : err instanceof Error
            ? err.message
            : String(err);
      setError(msg);
      await reload();
    } finally {
      setBusyLive(false);
    }
  };

  const onKill = async () => {
    if (
      !window.confirm(
        de
          ? "KILL: Paper+Live stoppen und alle offenen Orders stornieren?"
          : "KILL: Stop paper+live and cancel-all open orders?",
      )
    ) {
      return;
    }
    setBusyLive(true);
    setBusyPaper(true);
    setError("");
    try {
      await killTradingLoops();
      await reload();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusyLive(false);
      setBusyPaper(false);
    }
  };

  const liveBlocked = Boolean(status && !status.live.can_start && !status.live.running);
  const liveTitle = liveBlocked
    ? status?.live.blocked_reason ||
      (de ? "Live-Gates fehlen (Env)" : "Live gates missing (env)")
    : de
      ? "Live-Algo via Orchestrator (Level 4)"
      : "Live algo via orchestrator (Level 4)";

  return (
    <div className="flex flex-col gap-1">
      <div className="flex items-center gap-2">
        <SwitchPill
          label={de ? "Paper-Loop" : "Paper loop"}
          on={Boolean(status?.paper.running)}
          busy={busyPaper}
          onToggle={() => void onPaper()}
          title={de ? "Paper-Algo-Loop starten/stoppen" : "Start/stop paper algo loop"}
        />
        <SwitchPill
          label={de ? "Live-Algo" : "Live algo"}
          on={Boolean(status?.live.running)}
          busy={busyLive}
          disabled={liveBlocked}
          onToggle={() => void onLive()}
          title={liveTitle}
        />
        <button
          type="button"
          title={de ? "Notfall: Loops stoppen + Cancel-All" : "Emergency: stop loops + cancel-all"}
          disabled={busyPaper || busyLive}
          onClick={() => void onKill()}
          className="px-2 py-1.5 rounded-sm border border-rose-500/50 bg-rose-500/15 text-rose-300 font-mono text-[10px] font-bold uppercase tracking-wider cursor-pointer disabled:opacity-40"
        >
          Kill
        </button>
      </div>
      {liveBlocked ? (
        <span className="text-[8px] font-mono text-amber-400/90 max-w-[280px] leading-tight">
          {de ? "Algo gesperrt: " : "Algo blocked: "}
          {status?.live.blocked_reason}
          {(status?.live.supervised_manual
            ? de
              ? " — Manual Positions OK"
              : " — manual Positions OK"
            : null)}
        </span>
      ) : null}
      {error ? (
        <span className="text-[8px] font-mono text-rose-400 max-w-[240px] leading-tight">{error}</span>
      ) : null}

      {confirmLive ? (
        <div className="fixed inset-0 z-[80] flex items-center justify-center bg-black/70 p-4">
          <div className="bg-slate-950 border border-rose-500/40 rounded-lg p-4 max-w-md w-full font-mono space-y-3 shadow-xl">
            <h3 className="text-sm font-bold text-rose-300 uppercase tracking-widest">
              {de ? "Live-Algo bestätigen" : "Confirm live algo"}
            </h3>
            <p className="text-[11px] text-slate-300 leading-relaxed">
              {de
                ? "Startet die Live-Session (Deadman + Orchestrator-Loop). Echte Orders erfordern weiterhin KRAKEN_LIVE_TRADING_ENABLED und Autonomy ≥ 4 in der Umgebung — dieser Schalter schaltet Live-Trading nicht selbst frei."
                : "Starts the live session (deadman + orchestrator loop). Real orders still require KRAKEN_LIVE_TRADING_ENABLED and autonomy ≥ 4 in the environment — this switch does not enable live trading by itself."}
            </p>
            <div className="flex justify-end gap-2 pt-1">
              <button
                type="button"
                className="px-3 py-1.5 text-[10px] border border-white/15 text-slate-300 rounded cursor-pointer"
                onClick={() => setConfirmLive(false)}
              >
                {de ? "Abbrechen" : "Cancel"}
              </button>
              <button
                type="button"
                className="px-3 py-1.5 text-[10px] bg-rose-500/20 border border-rose-500/40 text-rose-200 rounded cursor-pointer font-bold"
                onClick={() => void confirmStartLive()}
              >
                {de ? "Live starten" : "Start live"}
              </button>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
}
