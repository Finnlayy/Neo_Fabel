import React, {useCallback, useEffect, useState} from "react";
import {Send} from "lucide-react";
import {ApiError} from "../api/client";
import {useAuth} from "../auth/AuthProvider";
import {
  fetchTelegramDaemonStatus,
  fetchTelegramMessages,
  sendTelegramMessage,
  type TelegramDaemonStatus,
} from "../api/telegram";
import type {TelegramSignal} from "../types";

interface TelegramFeedProps {
  onSignalAction: (prompt: string) => void;
  onSimulateTradeSignal: (asset: string, type: "BUY" | "SELL") => void;
}

export default function TelegramFeed({onSignalAction}: TelegramFeedProps) {
  const auth = useAuth();
  const [inputText, setInputText] = useState("");
  const [notice, setNotice] = useState<string | null>(null);
  const [messages, setMessages] = useState<TelegramSignal[]>([]);
  const [daemon, setDaemon] = useState<TelegramDaemonStatus | null>(null);
  const [authBlocked, setAuthBlocked] = useState(false);
  const [busy, setBusy] = useState(false);

  const reload = useCallback(async () => {
    try {
      const [nextMessages, status] = await Promise.all([
        fetchTelegramMessages(),
        fetchTelegramDaemonStatus(),
      ]);
      setMessages(nextMessages);
      setDaemon(status);
      setAuthBlocked(false);
      setNotice(null);
    } catch (error) {
      const needsSignIn =
        error instanceof ApiError && (error.status === 401 || error.code === "session_expired");
      setAuthBlocked(needsSignIn);
      if (needsSignIn) {
        setDaemon(null);
        setNotice("API auth rejected the request. On localhost, restart the API (AUTH_DEV_BYPASS) or sign in with Google.");
        return;
      }
      setNotice(
        error instanceof ApiError
          ? `${error.code}: ${error.message}`
          : "Telegram API unavailable.",
      );
    }
  }, [auth.uid]);

  useEffect(() => {
    void reload();
    const timer = window.setInterval(() => void reload(), 15000);
    return () => window.clearInterval(timer);
  }, [reload]);

  const handleSendMessage = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!inputText.trim() || busy) return;
    setBusy(true);
    try {
      await sendTelegramMessage(inputText.trim());
      setInputText("");
      setNotice("Message sent via Telegram Bot API.");
      await reload();
    } catch (error) {
      setNotice(
        error instanceof ApiError ? `${error.code}: ${error.message}` : "Failed to send Telegram message.",
      );
    } finally {
      setBusy(false);
    }
  };

  const statusLabel = authBlocked ? "AUTH" : daemon?.status ?? "UNKNOWN";
  const statusClass =
    statusLabel === "ACTIVE"
      ? "text-emerald-400 border-emerald-500/20"
      : statusLabel === "THROTTLED" || statusLabel === "AUTH"
        ? "text-amber-400 border-amber-500/20"
        : "text-slate-400 border-white/10";

  return (
    <div id="telegram-feed-card" className="flex flex-col bg-slate-900/40 border border-white/5 rounded-xl overflow-hidden h-[540px] font-mono">
      <div className="bg-slate-900/30 px-4 py-3 border-b border-white/10 flex items-center justify-between">
        <span className="text-white text-xs font-bold uppercase tracking-wider">Telegram integration</span>
        <span className={`text-[9px] border px-1.5 py-0.5 rounded uppercase ${statusClass}`}>
          {statusLabel}
        </span>
      </div>

      {notice && (
        <div className="bg-slate-950/60 border-b border-white/5 p-3 text-[10px] text-amber-400">{notice}</div>
      )}

      <div className="flex-1 overflow-y-auto p-4 space-y-2">
        {authBlocked ? (
          <div className="p-3 rounded border border-amber-500/20 bg-amber-950/20 text-xs text-amber-200/90">
            Waiting for API auth. Localhost should unlock automatically after API restart.
          </div>
        ) : messages.length === 0 ? (
          <div className="p-3 rounded border border-white/10 bg-slate-950/40 text-xs text-slate-400">
            Connected — waiting for Bot API updates. Message the bot in the configured chat; this panel
            refreshes about every 15s.
          </div>
        ) : (
          messages.map((signal) => (
            <button
              key={signal.id}
              type="button"
              onClick={() => onSignalAction(signal.message)}
              className="w-full text-left p-3 rounded border border-white/5 bg-slate-950/50 hover:border-cyan-500/30 space-y-1"
            >
              <div className="flex justify-between text-[9px] text-slate-500 uppercase">
                <span>{signal.channel}</span>
                <span className={signal.sentiment === "BULLISH" ? "text-emerald-400" : signal.sentiment === "BEARISH" ? "text-rose-400" : "text-slate-400"}>
                  {signal.sentiment}
                </span>
              </div>
              <p className="text-xs text-slate-200 whitespace-pre-wrap">{signal.message}</p>
              <p className="text-[9px] text-slate-600">{signal.timestamp}</p>
            </button>
          ))
        )}
      </div>

      <form onSubmit={handleSendMessage} className="p-3 bg-slate-950/80 border-t border-white/10 flex gap-2">
        <input
          type="text"
          value={inputText}
          onChange={(event) => setInputText(event.target.value)}
          placeholder="Send to configured Telegram chat"
          className="flex-1 bg-slate-900 border border-white/5 rounded-sm px-2.5 py-1.5 text-xs text-slate-200 focus:outline-none placeholder:text-slate-500"
          disabled={busy}
        />
        <button
          type="submit"
          disabled={busy || !inputText.trim()}
          className="bg-white/5 text-white border border-white/10 p-2 rounded-sm disabled:opacity-50"
        >
          <Send className="w-3.5 h-3.5 text-cyan-400" />
        </button>
      </form>
    </div>
  );
}
