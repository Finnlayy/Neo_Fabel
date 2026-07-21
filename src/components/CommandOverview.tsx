import { useCallback, useEffect, useMemo, useState, type ReactNode } from "react";
import { Area, AreaChart, ResponsiveContainer, Tooltip, YAxis } from "recharts";
import {
  fetchLoopsStatus,
  startLiveLoop,
  startPaperLoop,
  stopLiveLoop,
  stopPaperLoop,
  type LoopsStatus,
} from "../api/loops";
import { fetchPaperPerformance, fetchPaperStatus } from "../api/paper";
import { fetchCryptoTickers } from "../api/market";
import { ApiError, apiRequest } from "../api/client";
import { fetchSignalStatus, fetchSubmissions } from "../features/signalRoutes/api";
import type { MainTab } from "../types";

type Props = {
  language: "en" | "de";
  onNavigate?: (tab: MainTab) => void;
};

type EquityPoint = { t: string; equity: number };

function Pill({
  ok,
  label,
  title,
  busy,
  disabled,
  onClick,
}: {
  ok: boolean;
  label: string;
  title?: string;
  busy?: boolean;
  disabled?: boolean;
  onClick?: () => void;
}) {
  const interactive = Boolean(onClick);
  const className = `inline-flex items-center gap-1.5 px-2 py-0.5 rounded border text-[9px] uppercase tracking-wider transition-all ${
    ok
      ? "border-emerald-400/60 text-emerald-200 bg-emerald-500/15 shadow-[0_0_12px_rgba(16,185,129,0.3)]"
      : "border-slate-600 text-slate-400 bg-white/5"
  } ${interactive ? "cursor-pointer hover:border-cyan-400/40" : ""} ${
    disabled || busy ? "opacity-40 cursor-not-allowed" : ""
  }`;

  const body = (
    <>
      <span className="relative flex h-2 w-2 items-center justify-center">
        {ok ? <span className="absolute inline-flex h-full w-full rounded-full bg-emerald-400/50 animate-ping" /> : null}
        <span className={`relative inline-flex h-1.5 w-1.5 rounded-full ${ok ? "bg-emerald-400" : "bg-slate-500"}`} />
      </span>
      {busy ? "…" : label}
    </>
  );

  if (interactive) {
    return (
      <button
        type="button"
        title={title}
        disabled={busy || disabled}
        onClick={onClick}
        aria-pressed={ok}
        className={className}
      >
        {body}
      </button>
    );
  }

  return (
    <span title={title} className={className}>
      {body}
    </span>
  );
}

function ageLabel(iso: string | null | undefined, de: boolean): string {
  if (!iso) return de ? "nie" : "never";
  const ms = Date.now() - new Date(iso).getTime();
  if (!Number.isFinite(ms) || ms < 0) return iso.slice(11, 19);
  const s = Math.floor(ms / 1000);
  if (s < 60) return de ? `vor ${s}s` : `${s}s ago`;
  const m = Math.floor(s / 60);
  if (m < 60) return de ? `vor ${m}m` : `${m}m ago`;
  return de ? `vor ${Math.floor(m / 60)}h` : `${Math.floor(m / 60)}h ago`;
}

export default function CommandOverview({ language, onNavigate }: Props) {
  const de = language === "de";
  const [loops, setLoops] = useState<LoopsStatus | null>(null);
  const [cash, setCash] = useState<string>("—");
  const [equityUsd, setEquityUsd] = useState<string>("—");
  const [sessionPnl, setSessionPnl] = useState<string>("—");
  const [openPos, setOpenPos] = useState<number>(0);
  const [equity, setEquity] = useState<EquityPoint[]>([]);
  const [ada, setAda] = useState<number | null>(null);
  const [xrp, setXrp] = useState<number | null>(null);
  const [krakenStatus, setKrakenStatus] = useState<string>("—");
  const [lastSignal, setLastSignal] = useState<string>(de ? "keine" : "none");
  const [queueDepth, setQueueDepth] = useState<number>(0);
  const [error, setError] = useState<string | null>(null);
  const [busyPaper, setBusyPaper] = useState(false);
  const [busyLive, setBusyLive] = useState(false);
  const [confirmLive, setConfirmLive] = useState(false);

  const reloadLoops = useCallback(async () => {
    const data = await fetchLoopsStatus();
    setLoops(data);
    return data;
  }, []);

  useEffect(() => {
    let cancelled = false;
    async function tick() {
      try {
        const [loopSt, paperSt, perf, tickers, kstat, sigSt, subs] = await Promise.allSettled([
          fetchLoopsStatus(),
          fetchPaperStatus(),
          fetchPaperPerformance(),
          fetchCryptoTickers(["ADA", "XRP"]),
          apiRequest<{ indicator?: string; description?: string }>("/api/v1/kraken/status").catch(() => null),
          fetchSignalStatus(),
          fetchSubmissions(),
        ]);
        if (cancelled) return;
        if (loopSt.status === "fulfilled") setLoops(loopSt.value);
        if (paperSt.status === "fulfilled") {
          const d = paperSt.value.data;
          setCash(d.spot?.usd_balance ?? d.usd_balance ?? "—");
          setOpenPos(Number(d.spot?.open_positions ?? 0));
        }
        if (perf.status === "fulfilled") {
          const p = perf.value;
          setEquityUsd(p.combined_equity_usd ?? p.equity_usd ?? "—");
          setSessionPnl(p.total_pnl_usd ?? "—");
          const series = p.equity_curve;
          if (Array.isArray(series)) {
            setEquity(
              series.slice(-48).map((pt, i) => ({
                t: String(pt.time ?? i),
                equity: Number(pt.equity_usd ?? 0),
              })),
            );
          }
        }
        if (tickers.status === "fulfilled") {
          for (const t of tickers.value.tickers) {
            if (t.symbol === "ADA") setAda(t.price);
            if (t.symbol === "XRP") setXrp(t.price);
          }
        }
        if (kstat.status === "fulfilled" && kstat.value) {
          setKrakenStatus(String(kstat.value.indicator ?? kstat.value.description ?? "ok"));
        }
        if (sigSt.status === "fulfilled") setQueueDepth(sigSt.value.queue_depth ?? 0);
        if (subs.status === "fulfilled" && subs.value[0]) {
          const s = subs.value[0];
          setLastSignal(`${s.status} · ${s.pair} · ${ageLabel(s.created_at, de)}`);
        }
        setError(null);
      } catch (err) {
        if (!cancelled) setError(String(err));
      }
    }
    void tick();
    const id = window.setInterval(() => void tick(), 8000);
    return () => {
      cancelled = true;
      window.clearInterval(id);
    };
  }, [de]);

  const spark = useMemo(() => equity.filter((p) => Number.isFinite(p.equity)), [equity]);
  const krakenOk =
    krakenStatus === "none" ||
    krakenStatus === "operational" ||
    krakenStatus === "minor" ||
    krakenStatus === "ok";

  const formatErr = (err: unknown): string => {
    if (err instanceof ApiError) {
      if (err.code === "recent_auth_required") {
        return de ? "Bitte erneut anmelden (frische Auth nötig)" : "Re-authenticate to toggle loops";
      }
      return err.message;
    }
    if (err instanceof Error) return err.message;
    return String(err);
  };

  const onPaperToggle = async () => {
    setBusyPaper(true);
    setError(null);
    try {
      if (loops?.paper.running) await stopPaperLoop();
      else await startPaperLoop();
      await reloadLoops();
    } catch (err) {
      setError(formatErr(err));
      try {
        await reloadLoops();
      } catch {
        /* ignore */
      }
    } finally {
      setBusyPaper(false);
    }
  };

  const onLiveToggle = async () => {
    if (loops?.live.running) {
      setBusyLive(true);
      setError(null);
      try {
        await stopLiveLoop();
        await reloadLoops();
      } catch (err) {
        setError(formatErr(err));
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
    setError(null);
    try {
      await startLiveLoop();
      await reloadLoops();
    } catch (err) {
      setError(formatErr(err));
      try {
        await reloadLoops();
      } catch {
        /* ignore */
      }
    } finally {
      setBusyLive(false);
    }
  };

  const liveBlocked = Boolean(loops && !loops.live.can_start && !loops.live.running);
  const paperOn = Boolean(loops?.paper.running);
  const liveOn = Boolean(loops?.live.running);

  return (
    <section className="rounded-xl border border-cyan-500/20 bg-slate-950/70 p-4 space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 className="text-[11px] font-bold uppercase tracking-widest text-cyan-300">
          {de ? "Kommando-Übersicht" : "Command Overview"}
        </h2>
        <div className="flex flex-wrap gap-2">
          <Pill
            ok={paperOn}
            busy={busyPaper}
            label={paperOn ? (de ? "Paper ONLINE" : "Paper ONLINE") : de ? "Paper-Loop" : "Paper loop"}
            title={de ? "Paper-Algo-Loop starten/stoppen" : "Start/stop paper algo loop"}
            onClick={() => void onPaperToggle()}
          />
          <Pill
            ok={liveOn}
            busy={busyLive}
            disabled={liveBlocked}
            label={liveOn ? (de ? "Live ONLINE" : "Live ONLINE") : de ? "Live-Algo" : "Live algo"}
            title={
              liveBlocked
                ? loops?.live.blocked_reason || (de ? "Live-Gates fehlen" : "Live gates missing")
                : de
                  ? "Live-Algo starten/stoppen"
                  : "Start/stop live algo"
            }
            onClick={() => void onLiveToggle()}
          />
          <Pill
            ok={(loops?.live.autonomy ?? 0) >= 3}
            label={`L${loops?.live.autonomy ?? "—"}`}
            title={de ? "Autonomy-Level (Env)" : "Autonomy level (env)"}
          />
          <Pill
            ok={krakenOk}
            label={`Kraken ${krakenStatus}`}
            title={de ? "Kraken Systemstatus" : "Kraken system status"}
            onClick={() => onNavigate?.("terminal")}
          />
        </div>
      </div>

      {liveBlocked ? (
        <p className="text-[9px] font-mono text-amber-400/90">
          {de ? "Live gesperrt: " : "Live blocked: "}
          {loops?.live.blocked_reason}
        </p>
      ) : null}
      {error && <p className="text-[10px] text-rose-400">{error}</p>}

      {confirmLive ? (
        <div className="fixed inset-0 z-[80] flex items-center justify-center bg-black/70 p-4">
          <div className="bg-slate-950 border border-rose-500/40 rounded-lg p-4 max-w-md w-full font-mono space-y-3 shadow-xl">
            <h3 className="text-sm font-bold text-rose-300 uppercase tracking-widest">
              {de ? "Live-Algo bestätigen" : "Confirm live algo"}
            </h3>
            <p className="text-[11px] text-slate-300 leading-relaxed">
              {de
                ? "Startet die Live-Session (Deadman). Echte Orders brauchen weiterhin die Env-Gates."
                : "Starts the live session (deadman). Real orders still require env gates."}
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

      <div className="grid grid-cols-1 lg:grid-cols-5 gap-3">
        <div className="lg:col-span-3 h-28 rounded-lg border border-white/5 bg-black/30 overflow-hidden relative">
          <div className="absolute top-2 left-3 z-10 text-[9px] uppercase tracking-widest text-slate-500">
            {de ? "Paper Equity" : "Paper equity"}{" "}
            <span className="text-cyan-300 font-mono text-[11px] ml-1">${equityUsd}</span>
          </div>
          {spark.length > 1 ? (
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={spark}>
                <defs>
                  <linearGradient id="eqFill" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="#22d3ee" stopOpacity={0.35} />
                    <stop offset="100%" stopColor="#22d3ee" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <YAxis domain={["auto", "auto"]} hide />
                <Tooltip contentStyle={{ background: "#0f172a", border: "1px solid #334155", fontSize: 10 }} />
                <Area type="monotone" dataKey="equity" stroke="#22d3ee" fill="url(#eqFill)" strokeWidth={1.5} />
              </AreaChart>
            </ResponsiveContainer>
          ) : (
            <div className="h-full flex items-center justify-center text-[10px] text-slate-500 uppercase tracking-widest">
              {de ? "Equity-Kurve lädt…" : "Equity curve loading…"}
            </div>
          )}
        </div>
        <div className="lg:col-span-2 grid grid-cols-2 gap-2">
          <Fact label={de ? "Cash" : "Cash"} value={cash === "—" ? "—" : `$${cash}`} />
          <Fact label={de ? "Session PnL" : "Session PnL"} value={sessionPnl === "—" ? "—" : `$${sessionPnl}`} />
          <Fact label={de ? "Offene Pos." : "Open pos."} value={String(openPos)} />
          <Fact label={de ? "Signal-Queue" : "Signal queue"} value={String(queueDepth)} />
          <Fact label="ADA" value={ada != null ? ada.toFixed(4) : "—"} />
          <Fact label="XRP" value={xrp != null ? xrp.toFixed(4) : "—"} />
        </div>
      </div>

      <div className="rounded-lg border border-white/10 bg-slate-900/40 px-3 py-2 flex flex-wrap items-center justify-between gap-2">
        <div className="text-[10px] text-slate-400">
          <span className="uppercase tracking-widest text-slate-500 mr-2">
            {de ? "Letztes Signal" : "Last signal"}
          </span>
          <span className="font-mono text-slate-200">{lastSignal}</span>
        </div>
        <div className="flex flex-wrap gap-2">
          <Cta onClick={() => onNavigate?.("signals")}>{de ? "Signal einrichten" : "Set up signal"}</Cta>
          <Cta onClick={() => onNavigate?.("paper")}>{de ? "Paper-Fill prüfen" : "Check paper fill"}</Cta>
          <Cta onClick={() => onNavigate?.("terminal")}>{de ? "Terminal / Orderbuch" : "Terminal / book"}</Cta>
        </div>
      </div>
    </section>
  );
}

function Fact({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-white/10 bg-slate-900/50 px-3 py-2">
      <div className="text-[8px] uppercase tracking-widest text-slate-500">{label}</div>
      <div className="text-sm font-semibold text-slate-100 font-mono tabular-nums mt-0.5 truncate">{value}</div>
    </div>
  );
}

function Cta({ children, onClick }: { children: ReactNode; onClick?: () => void }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="px-2.5 py-1 rounded border border-cyan-500/30 text-cyan-300 text-[9px] uppercase tracking-wider hover:bg-cyan-500/10 cursor-pointer"
    >
      {children}
    </button>
  );
}
