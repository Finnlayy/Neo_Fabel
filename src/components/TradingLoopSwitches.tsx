import React, {useCallback, useEffect, useState} from "react";
import {
  fetchLoopsStatus,
  killTradingLoops,
  startLiveLoop,
  startPaperLoop,
  stopLiveLoop,
  stopPaperLoop,
  type LiveStartConfig,
  type LoopsStatus,
} from "../api/loops";
import {ApiError} from "../api/client";
import {LiveStartConfirmModal} from "./LiveStartConfirmModal";

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
      aria-pressed={on}
      className={`relative flex flex-col items-stretch min-w-[118px] px-2.5 py-1.5 rounded-sm border font-mono text-left cursor-pointer transition-all disabled:opacity-40 disabled:cursor-not-allowed overflow-hidden ${
        on
          ? "bg-emerald-500/20 border-emerald-400/60 text-emerald-200 shadow-[0_0_18px_rgba(16,185,129,0.35)]"
          : "bg-white/5 border-white/10 text-slate-300 hover:border-cyan-500/30"
      }`}
    >
      {on ? (
        <span
          aria-hidden
          className="pointer-events-none absolute inset-0 rounded-sm border border-emerald-400/50 animate-pulse"
        />
      ) : null}
      <span className="text-[8px] uppercase tracking-widest text-slate-500 relative z-[1]">{label}</span>
      <span className="text-[11px] font-bold flex items-center gap-1.5 mt-0.5 relative z-[1]">
        <span className="relative flex h-2.5 w-2.5 items-center justify-center">
          {on ? (
            <span className="absolute inline-flex h-full w-full rounded-full bg-emerald-400/60 animate-ping" />
          ) : null}
          <span
            className={`relative inline-flex h-2 w-2 rounded-full ${
              on ? "bg-emerald-400 shadow-[0_0_10px_#34d399]" : "bg-slate-600"
            }`}
          />
        </span>
        {busy ? "…" : on ? "ONLINE" : "OFFLINE"}
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

  const formatErr = (err: unknown): string => {
    if (err instanceof ApiError) {
      if (err.code === "safety") {
        return de
          ? `Paper-Loop Sicherheit: ${err.message}`
          : `Paper loop safety: ${err.message}`;
      }
      if (err.code === "recent_auth_required") {
        return de ? "Bitte erneut anmelden (frische Auth nötig)" : "Re-authenticate to toggle loops";
      }
      return err.message;
    }
    if (err instanceof Error) return err.message;
    return String(err);
  };

  const onPaper = async () => {
    setBusyPaper(true);
    setError("");
    try {
      if (status?.paper.running) await stopPaperLoop();
      else await startPaperLoop();
      await reload();
    } catch (err) {
      setError(formatErr(err));
      await reload();
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
        setError(formatErr(err));
      } finally {
        setBusyLive(false);
      }
      return;
    }
    setConfirmLive(true);
  };

  const confirmStartLive = async (config: LiveStartConfig) => {
    setConfirmLive(false);
    setBusyLive(true);
    setError("");
    try {
      await startLiveLoop(config);
      await reload();
    } catch (err) {
      setError(formatErr(err));
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
      setError(formatErr(err));
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

  const paperHint =
    status?.paper.last_error && !status.paper.running
      ? status.paper.last_error
      : null;

  return (
    <div className="flex flex-col gap-1">
      <div className="flex items-center gap-2">
        <SwitchPill
          label={de ? "Paper-Loop" : "Paper loop"}
          on={Boolean(status?.paper.running)}
          busy={busyPaper}
          onToggle={() => void onPaper()}
          title={
            paperHint ||
            (de ? "Paper-Algo-Loop starten/stoppen (dry-run)" : "Start/stop paper algo loop (dry-run)")
          }
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
          {status?.live.supervised_manual
            ? de
              ? " — Manual Positions OK"
              : " — manual Positions OK"
            : null}
        </span>
      ) : null}
      {status?.live.running && status.live.session ? (
        <span className="text-[8px] font-mono text-rose-300/90 max-w-[320px] leading-tight">
          {status.live.session.session_name} · €{status.live.session.max_margin_eur} · ≤
          {status.live.session.max_concurrent_trades} trades ·{" "}
          {status.live.session.position_sizing?.mode || "half_kelly"}
          {status.live.session.symbol_allowlist?.length
            ? ` · ${status.live.session.symbol_allowlist.join(",")}`
            : ""}
        </span>
      ) : null}
      {error ? (
        <span className="text-[8px] font-mono text-rose-400 max-w-[280px] leading-tight">{error}</span>
      ) : null}
      {paperHint && !error ? (
        <span className="text-[8px] font-mono text-amber-400/90 max-w-[280px] leading-tight">{paperHint}</span>
      ) : null}

      {confirmLive ? (
        <LiveStartConfirmModal
          de={de}
          onCancel={() => setConfirmLive(false)}
          onConfirm={(config) => void confirmStartLive(config)}
        />
      ) : null}
    </div>
  );
}
