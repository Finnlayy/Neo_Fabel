import React, {useCallback, useEffect, useRef, useState} from "react";
import {AlertTriangle, MessageSquare, Send, Sparkles, TrendingUp} from "lucide-react";
import {ApiError} from "../api/client";
import {useAuth} from "../auth/AuthProvider";
import {
  fetchTelegramConfig,
  fetchTelegramDaemonStatus,
  fetchTelegramMessages,
  sendTelegramMessage,
  type TelegramConfig,
  type TelegramDaemonStatus,
} from "../api/telegram";
import type {TelegramSignal} from "../types";

interface TelegramFeedProps {
  onSignalAction: (prompt: string) => void;
  onSimulateTradeSignal: (asset: string, type: "BUY" | "SELL", isManual?: boolean) => void;
  autoExecute?: boolean;
  setAutoExecute?: (val: boolean) => void;
}

const TRACKED_ASSETS = ["BTC", "ETH", "SOL", "MATIC", "AVAX", "XRP", "DOT", "ADA"];

const extractAsset = (msg: string): string => {
  const found = TRACKED_ASSETS.find((asset) => msg.toUpperCase().includes(asset));
  return found || "BTC";
};

const extractType = (msg: string): "BUY" | "SELL" => {
  const upper = msg.toUpperCase();
  if (upper.includes("SELL") || upper.includes("SHORT") || upper.includes("BEAR")) {
    return "SELL";
  }
  return "BUY";
};

export default function TelegramFeed({
  onSignalAction,
  onSimulateTradeSignal,
  autoExecute: controlledAutoExecute,
  setAutoExecute: controlledSetAutoExecute,
}: TelegramFeedProps) {
  const auth = useAuth();
  const [signals, setSignals] = useState<TelegramSignal[]>([]);
  const [inputText, setInputText] = useState("");
  const [config, setConfig] = useState<TelegramConfig | null>(null);
  const [isSending, setIsSending] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);
  const [authBlocked, setAuthBlocked] = useState(false);

  const [localAutoExecute, setLocalAutoExecute] = useState(false);
  const autoExecute = controlledAutoExecute ?? localAutoExecute;
  const setAutoExecute = controlledSetAutoExecute ?? setLocalAutoExecute;

  const executedSignalsRef = useRef<Set<string>>(new Set());
  const [daemonState, setDaemonState] = useState<TelegramDaemonStatus | null>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const prevLengthRef = useRef(0);

  const reload = useCallback(async () => {
    try {
      const [nextMessages, status, nextConfig] = await Promise.all([
        fetchTelegramMessages(),
        fetchTelegramDaemonStatus(),
        fetchTelegramConfig(),
      ]);
      setSignals(nextMessages);
      setDaemonState(status);
      setConfig(nextConfig);
      setAuthBlocked(false);
      setNotice(null);
    } catch (error) {
      const needsSignIn =
        error instanceof ApiError && (error.status === 401 || error.code === "session_expired");
      setAuthBlocked(needsSignIn);
      if (needsSignIn) {
        setDaemonState(null);
        setNotice("API auth rejected. Restart the API (AUTH_DEV_BYPASS) or sign in with Google.");
        return;
      }
      setNotice(
        error instanceof ApiError ? `${error.code}: ${error.message}` : "Telegram API unavailable.",
      );
    }
  }, [auth.uid]);

  useEffect(() => {
    void reload();
    const timer = window.setInterval(() => void reload(), 4000);
    return () => window.clearInterval(timer);
  }, [reload]);

  useEffect(() => {
    if (signals.length > prevLengthRef.current) {
      containerRef.current?.scrollTo({top: containerRef.current.scrollHeight, behavior: "smooth"});
      if (autoExecute) {
        const newSignals = signals.slice(prevLengthRef.current);
        newSignals.forEach((signal) => {
          if (signal.actionable && !executedSignalsRef.current.has(signal.id)) {
            executedSignalsRef.current.add(signal.id);
            onSimulateTradeSignal(extractAsset(signal.message), extractType(signal.message), false);
          }
        });
      }
    }
    prevLengthRef.current = signals.length;
  }, [signals, autoExecute, onSimulateTradeSignal]);

  const handleSendMessage = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!inputText.trim() || isSending) return;

    setIsSending(true);
    try {
      await sendTelegramMessage(inputText.trim());
      setInputText("");
      setNotice("Message broadcast to Telegram.");
      await reload();
    } catch (error) {
      const text = inputText.trim();
      const lower = text.toLowerCase();
      const sentiment =
        lower.includes("bull") || lower.includes("buy") || lower.includes("long")
          ? "BULLISH"
          : lower.includes("bear") || lower.includes("sell") || lower.includes("short")
            ? "BEARISH"
            : "NEUTRAL";
      const hasAsset = TRACKED_ASSETS.some((asset) => text.toUpperCase().includes(asset));
      const fallbackSignal: TelegramSignal = {
        id: `TS-USER-${Date.now()}`,
        timestamp: new Date().toLocaleTimeString([], {hour: "2-digit", minute: "2-digit", second: "2-digit"}),
        channel: "OFFLINE CONSOLE",
        message: text,
        sentiment,
        actionable: hasAsset,
      };
      setSignals((prev) => [...prev, fallbackSignal]);
      setInputText("");
      setNotice(
        error instanceof ApiError
          ? `${error.code}: ${error.message} — injected locally.`
          : "Send failed — injected locally.",
      );
    } finally {
      setIsSending(false);
    }
  };

  const statusLabel = authBlocked ? "AUTH" : daemonState?.status ?? "UNKNOWN";
  const statusClass =
    statusLabel === "ACTIVE"
      ? "text-emerald-400 border-emerald-500/20"
      : statusLabel === "THROTTLED" || statusLabel === "AUTH"
        ? "text-amber-400 border-amber-500/20"
        : "text-slate-400 border-white/10";

  return (
    <div
      id="telegram-feed-card"
      className="flex flex-col bg-slate-900/40 border border-white/5 hover:border-white/10 rounded-xl glow-cyan overflow-hidden h-[540px] font-mono transition-all duration-300"
    >
      <div className="bg-slate-900/30 px-4 py-3 border-b border-white/10 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="w-2 h-2 rounded-full bg-cyan-400 animate-pulse" />
          <span className="text-white text-xs font-bold uppercase tracking-wider">
            {config?.botUsername ? `@${config.botUsername}` : "LIVE TRADE EBP TELEGRAM"}
          </span>
        </div>
        <div className="flex items-center gap-3">
          <button
            type="button"
            onClick={() => setAutoExecute(!autoExecute)}
            className={`flex items-center gap-1.5 text-[9px] px-2 py-1 rounded-sm border transition-all cursor-pointer font-bold tracking-wider uppercase font-mono ${
              autoExecute
                ? "bg-emerald-500/20 text-emerald-400 border-emerald-500/30"
                : "bg-white/5 text-slate-400 border-white/10 hover:bg-white/10"
            }`}
          >
            <TrendingUp className="w-3 h-3" />
            {autoExecute ? "AUTO-EXEC ON" : "AUTO-EXEC OFF"}
          </button>
          <span className={`text-[9px] border px-1.5 py-0.5 rounded font-mono uppercase hidden sm:block ${statusClass}`}>
            {config?.chatId ? `CHAT: ${config.chatId}` : statusLabel}
          </span>
        </div>
      </div>

      {notice && (
        <div className="bg-slate-950/60 border-b border-white/5 px-3 py-2 text-[10px] text-amber-400 flex items-center gap-2">
          <AlertTriangle className="w-3 h-3 shrink-0" />
          {notice}
        </div>
      )}

      {daemonState && (
        <div className="bg-slate-950/40 border-b border-white/5 px-3 py-1.5 text-[9px] text-slate-500 flex justify-between">
          <span className="flex items-center gap-1">
            <MessageSquare className="w-3 h-3" />
            polls {daemonState.totalPollsCount} · synced {daemonState.totalMessagesProcessed}
          </span>
          <span>
            {daemonState.isThrottled ? "throttled" : "active"} · next {daemonState.nextPollTime?.slice(11, 19) ?? "—"}
          </span>
        </div>
      )}

      <div ref={containerRef} className="flex-1 overflow-y-auto p-4 space-y-3 scrollbar-thin">
        {authBlocked ? (
          <div className="p-3 rounded border border-amber-500/20 bg-amber-950/20 text-xs text-amber-200/90">
            Waiting for API auth. Localhost should unlock automatically after API restart.
          </div>
        ) : signals.length === 0 ? (
          <div className="p-3 rounded border border-white/10 bg-slate-950/40 text-xs text-slate-400">
            Daemon running — message the bot or wait for channel updates. Refreshes every 4s.
          </div>
        ) : (
          signals.map((signal) => {
            const isBull = signal.sentiment === "BULLISH";
            const isBear = signal.sentiment === "BEARISH";
            return (
              <div
                key={signal.id}
                className={`p-3 rounded border text-xs transition-all duration-300 ${
                  isBull
                    ? "bg-emerald-950/20 border-emerald-500/20 text-emerald-200"
                    : isBear
                      ? "bg-rose-950/20 border-rose-500/20 text-rose-200"
                      : "bg-slate-900/40 border-white/5 text-slate-300"
                }`}
              >
                <div className="flex justify-between items-center mb-1 text-[10px] text-slate-400">
                  <span className="font-semibold text-cyan-400/80">{signal.channel}</span>
                  <span>{signal.timestamp}</span>
                </div>
                <p className="leading-relaxed mb-2 text-[11px] whitespace-pre-wrap">{signal.message}</p>
                {signal.actionable && (
                  <div className="flex items-center gap-2 mt-2 pt-2 border-t border-dashed border-white/10">
                    <button
                      type="button"
                      onClick={() =>
                        onSimulateTradeSignal(extractAsset(signal.message), extractType(signal.message), true)
                      }
                      className="flex items-center gap-1.5 text-[9px] bg-white/5 hover:bg-white/10 text-white px-2 py-1 rounded-sm border border-white/10 transition-all cursor-pointer font-bold tracking-wider uppercase font-mono"
                    >
                      <TrendingUp className="w-3 h-3 text-cyan-400" />
                      Auto-Execute
                    </button>
                    <button
                      type="button"
                      onClick={() => onSignalAction(`Orchestrate strategy optimized for: ${signal.message}`)}
                      className="flex items-center gap-1.5 text-[9px] bg-white/5 hover:bg-white/10 text-white px-2 py-1 rounded-sm border border-white/10 transition-all cursor-pointer font-bold tracking-wider uppercase font-mono"
                    >
                      <Sparkles className="w-3 h-3 text-purple-400" />
                      Orchestrate Plan
                    </button>
                  </div>
                )}
              </div>
            );
          })
        )}
      </div>

      <form onSubmit={handleSendMessage} className="p-3 bg-slate-950/80 border-t border-white/10 flex gap-2">
        <input
          type="text"
          value={inputText}
          onChange={(event) => setInputText(event.target.value)}
          placeholder="Inject manual telegram advisory signal..."
          className="flex-1 bg-slate-900 border border-white/5 focus:border-cyan-500/50 rounded-sm px-2.5 py-1.5 text-xs text-slate-200 focus:outline-none placeholder:text-slate-500 placeholder:text-[10px]"
          disabled={isSending}
        />
        <button
          type="submit"
          disabled={isSending || !inputText.trim()}
          className="bg-white/5 hover:bg-white/10 text-white border border-white/10 p-2 rounded-sm cursor-pointer transition-all disabled:opacity-50"
        >
          <Send className="w-3.5 h-3.5 text-cyan-400" />
        </button>
      </form>
    </div>
  );
}
