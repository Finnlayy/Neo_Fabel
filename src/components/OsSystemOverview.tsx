import {useCallback, useEffect, useState} from "react";
import {Sparkles} from "lucide-react";
import {fetchAiHealth, type AiHealth} from "../api/ai";
import {
  fetchLoopsStatus,
  startPaperLoop,
  stopPaperLoop,
  type LoopsStatus,
} from "../api/loops";
import {ApiError} from "../api/client";
import type {MainTab} from "../types";

export type OsSpend = NonNullable<AiHealth["spend"]>;

type TelemetryRow = {
  id: string;
  label: string;
  value: string;
  tone: string;
  title?: string;
  onClick?: () => void;
};

type Props = {
  language: "en" | "de";
  marketLive: boolean;
  marketSource?: string | null;
  tickerCount: number;
  orderBookOnline: boolean;
  aiStatusLabel: string;
  execLabel: string;
  agentsActive: number;
  agentsTotal: number;
  agentsOptimizing: number;
  agentsAlert: number;
  isComplianceActive: boolean;
  onToggleCompliance: () => void;
  footer: string;
  planActive: boolean;
  onNavigate?: (tab: MainTab) => void;
  onAiStatus?: (label: string) => void;
};

function formatTokens(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(2)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}k`;
  return String(n);
}

function TokenMeter({spend, de}: {spend: OsSpend | null; de: boolean}) {
  const pct = Math.max(0, Math.min(100, spend?.budget_used_pct ?? 0));
  const tracked = Boolean(spend?.tracked);
  const radius = 28;
  const circ = 2 * Math.PI * radius;
  const offset = circ * (1 - pct / 100);
  const hot = pct >= 85;
  const warn = pct >= 60 && pct < 85;
  const stroke = hot ? "#f43f5e" : warn ? "#f59e0b" : "#a855f7";
  const prompt = spend?.prompt_tokens ?? 0;
  const completion = spend?.completion_tokens ?? 0;
  const total = spend?.total_tokens ?? prompt + completion;
  const promptShare = total > 0 ? (prompt / total) * 100 : 50;

  return (
    <div className="flex items-center gap-3 min-w-0">
      <div className="relative w-[72px] h-[72px] shrink-0">
        <svg className="w-full h-full -rotate-90" viewBox="0 0 72 72" aria-hidden="true">
          <circle cx="36" cy="36" r={radius} stroke="rgba(255,255,255,0.06)" strokeWidth="7" fill="none" />
          <circle
            cx="36"
            cy="36"
            r={radius}
            stroke={tracked ? stroke : "rgba(148,163,184,0.35)"}
            strokeWidth="7"
            fill="none"
            strokeLinecap="round"
            strokeDasharray={`${circ} ${circ}`}
            strokeDashoffset={tracked ? offset : circ * 0.92}
            className={tracked && pct > 0 ? "transition-[stroke-dashoffset] duration-700 ease-out" : ""}
          />
        </svg>
        <div className="absolute inset-0 flex flex-col items-center justify-center">
          <span className={`text-[11px] font-extrabold tabular-nums leading-none ${hot ? "text-rose-300" : "text-purple-200"}`}>
            {tracked ? `${pct.toFixed(0)}%` : "—"}
          </span>
          <span className="text-[6px] uppercase tracking-wider text-slate-500 mt-0.5">
            {de ? "Budget" : "Budget"}
          </span>
        </div>
      </div>

      <div className="flex-1 min-w-0 space-y-1.5">
        <div className="flex justify-between gap-2 text-[8px] uppercase tracking-wider">
          <span className="text-slate-500">{de ? "Token-Meter" : "Token meter"}</span>
          <span className="text-purple-300 font-semibold tabular-nums">
            {tracked ? formatTokens(total) : de ? "nicht erfasst" : "untracked"}
          </span>
        </div>

        {/* stacked prompt / completion bar */}
        <div
          className="h-2 rounded-full bg-white/5 overflow-hidden flex border border-white/10"
          title={de ? "Prompt vs Completion" : "Prompt vs completion"}
        >
          <div
            className="h-full bg-gradient-to-r from-fuchsia-500 to-purple-400 transition-all duration-500"
            style={{width: `${promptShare}%`}}
          />
          <div
            className="h-full bg-gradient-to-r from-cyan-500/80 to-sky-400/70 transition-all duration-500"
            style={{width: `${100 - promptShare}%`}}
          />
        </div>
        <div className="flex justify-between text-[7px] font-mono text-slate-500">
          <span>
            <span className="text-fuchsia-400/90">IN</span> {formatTokens(prompt)}
          </span>
          <span>
            <span className="text-cyan-400/90">OUT</span> {formatTokens(completion)}
          </span>
        </div>

        <div className="flex justify-between gap-2 text-[8px] font-mono">
          <span className="text-slate-400 tabular-nums">
            €{(spend?.spent_eur ?? 0).toFixed(4)}
            <span className="text-slate-600">
              {" "}
              / €{(spend?.limit_eur ?? 0).toFixed(2) || "—"}
            </span>
          </span>
          <span className="text-slate-500 tabular-nums">
            {spend?.calls_today ?? 0} {de ? "calls" : "calls"}
          </span>
        </div>
      </div>
    </div>
  );
}

export default function OsSystemOverview({
  language,
  marketLive,
  marketSource,
  tickerCount,
  orderBookOnline,
  aiStatusLabel,
  execLabel,
  agentsActive,
  agentsTotal,
  agentsOptimizing,
  agentsAlert,
  isComplianceActive,
  onToggleCompliance,
  footer,
  planActive,
  onNavigate,
  onAiStatus,
}: Props) {
  const de = language === "de";
  const [spend, setSpend] = useState<OsSpend | null>(null);
  const [loops, setLoops] = useState<LoopsStatus | null>(null);
  const [busyPaper, setBusyPaper] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      const [health, loopSt] = await Promise.all([fetchAiHealth(), fetchLoopsStatus()]);
      setSpend(health.spend ?? health.aiprimetech ?? null);
      setLoops(loopSt);
      if (onAiStatus) {
        onAiStatus(
          health.configured
            ? `AI: ${String(health.provider).toUpperCase()}`
            : health.deterministic_fallback
              ? "AI: FALLBACK"
              : "AI: OFFLINE",
        );
      }
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    }
  }, [onAiStatus]);

  useEffect(() => {
    void refresh();
    const id = window.setInterval(() => void refresh(), 15000);
    return () => window.clearInterval(id);
  }, [refresh]);

  const onPaper = async () => {
    setBusyPaper(true);
    setError(null);
    try {
      if (loops?.paper.running) await stopPaperLoop();
      else await startPaperLoop();
      await refresh();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : err instanceof Error ? err.message : String(err));
    } finally {
      setBusyPaper(false);
    }
  };

  const paperOn = Boolean(loops?.paper.running);
  const liveOn = Boolean(loops?.live.running);

  const rows: TelemetryRow[] = [
    {
      id: "market",
      label: de ? "Markt" : "Market",
      value: marketLive
        ? `LIVE · ${marketSource ?? "stream"} · ${tickerCount} tkr`
        : de
          ? "STALE / kein Stream"
          : "STALE / no stream",
      tone: marketLive ? "text-emerald-400" : "text-amber-400",
      title: de ? "Zum Terminal" : "Open terminal",
      onClick: () => onNavigate?.("terminal"),
    },
    {
      id: "depth",
      label: de ? "Orderbuch" : "Depth",
      value: orderBookOnline ? "ONLINE" : "OFFLINE",
      tone: orderBookOnline ? "text-emerald-400" : "text-slate-500",
      title: de ? "Zum Terminal / Orderbuch" : "Open terminal / book",
      onClick: () => onNavigate?.("terminal"),
    },
    {
      id: "ai",
      label: "AI",
      value: aiStatusLabel,
      tone: aiStatusLabel.includes("OFFLINE") ? "text-rose-400" : "text-cyan-400",
      title: de ? "AI-Status aktualisieren" : "Refresh AI status",
      onClick: () => void refresh(),
    },
    {
      id: "paper",
      label: de ? "Paper" : "Paper",
      value: busyPaper ? "…" : paperOn ? "ONLINE" : "OFFLINE",
      tone: paperOn ? "text-emerald-300" : "text-slate-500",
      title: de ? "Paper-Loop umschalten" : "Toggle paper loop",
      onClick: () => void onPaper(),
    },
    {
      id: "live",
      label: de ? "Live" : "Live",
      value: liveOn ? "ONLINE" : loops?.live.can_start ? "READY" : "BLOCKED",
      tone: liveOn ? "text-emerald-300" : loops?.live.can_start ? "text-amber-300" : "text-slate-500",
      title: loops?.live.blocked_reason || (de ? "Live-Algo (Header-Schalter)" : "Live algo (header switch)"),
      onClick: () => onNavigate?.("swarm"),
    },
    {
      id: "exec",
      label: de ? "Ausführung" : "Exec",
      value: execLabel,
      tone: "text-slate-300",
      title: de ? "Paper-Performance" : "Paper performance",
      onClick: () => onNavigate?.("paper"),
    },
    {
      id: "agents",
      label: de ? "Agenten" : "Agents",
      value: `${agentsActive}/${agentsTotal} ACTIVE${agentsOptimizing ? ` · ${agentsOptimizing} OPT` : ""}${agentsAlert ? ` · ${agentsAlert} ALERT` : ""}`,
      tone: agentsAlert ? "text-rose-400" : agentsOptimizing ? "text-amber-400" : "text-emerald-400",
      title: de ? "Zum Schwarm" : "Open swarm",
      onClick: () => onNavigate?.("swarm"),
    },
    {
      id: "compliance",
      label: de ? "Compliance" : "Compliance",
      value: isComplianceActive ? (de ? "ON · Paper only" : "ON · paper only") : "OFF",
      tone: isComplianceActive ? "text-rose-300" : "text-amber-400",
      title: de ? "Compliance umschalten" : "Toggle compliance",
      onClick: onToggleCompliance,
    },
  ];

  return (
    <div className="bg-slate-900/40 border border-white/5 rounded-xl p-5 glow-rose flex flex-col justify-between min-h-56 transition-all duration-300 hover:border-white/10 hover:bg-slate-900/60">
      <div className="space-y-2.5 min-h-0">
        <div className="flex items-center justify-between border-b border-white/10 pb-2">
          <span className="text-purple-400 font-bold uppercase tracking-wider text-[11px]">
            {de ? "OS-SYSTEMÜBERSICHT" : "OS SYSTEM OVERVIEW"}
          </span>
          <span className="text-[9px] text-purple-500/70 border border-purple-500/30 px-1.5 py-0.5 rounded">
            {de ? "OS TELEMETRIE" : "OS TELEMETRY"}
          </span>
        </div>

        <TokenMeter spend={spend} de={de} />

        <div className="grid grid-cols-2 gap-1 text-[9px] font-mono">
          {rows.map((row) => (
            <button
              key={row.id}
              type="button"
              title={row.title}
              onClick={row.onClick}
              className="flex justify-between gap-1 border border-white/5 bg-black/20 hover:border-purple-400/30 hover:bg-purple-500/5 rounded px-1.5 py-1 text-left cursor-pointer transition-colors"
            >
              <span className="text-slate-500 uppercase shrink-0">{row.label}</span>
              <span className={`text-right truncate font-semibold ${row.tone}`}>{row.value}</span>
            </button>
          ))}
        </div>
      </div>

      {error ? <p className="text-[8px] text-rose-400 font-mono mt-1 truncate">{error}</p> : null}

      <div className="pt-2 mt-2 bg-slate-950/40 border border-white/5 p-2.5 rounded-lg text-[9px] text-slate-300 flex items-start gap-2">
        <Sparkles
          className={`w-4 h-4 text-purple-400 shrink-0 mt-0.5 ${planActive || agentsOptimizing ? "animate-pulse" : ""}`}
        />
        <span className="leading-relaxed line-clamp-3">{footer}</span>
      </div>
    </div>
  );
}
