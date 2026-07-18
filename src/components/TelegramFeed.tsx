import React, { useState } from "react";
import { Send } from "lucide-react";

interface TelegramFeedProps {
  onSignalAction: (prompt: string) => void;
  onSimulateTradeSignal: (asset: string, type: "BUY" | "SELL") => void;
}

export default function TelegramFeed(_props: TelegramFeedProps) {
  const [inputText, setInputText] = useState("");
  const [notice, setNotice] = useState("Telegram backend is not configured; no message was sent.");

  const handleSendMessage = (event: React.FormEvent) => {
    event.preventDefault();
    if (!inputText.trim()) return;
    setNotice("Telegram backend is not configured; no message was sent.");
    setInputText("");
  };

  return (
    <div id="telegram-feed-card" className="flex flex-col bg-slate-900/40 border border-white/5 rounded-xl overflow-hidden h-[540px] font-mono">
      <div className="bg-slate-900/30 px-4 py-3 border-b border-white/10 flex items-center justify-between">
        <span className="text-white text-xs font-bold uppercase tracking-wider">Telegram integration</span>
        <span className="text-[9px] text-amber-400 border border-amber-500/20 px-1.5 py-0.5 rounded uppercase">Backend unavailable</span>
      </div>

      <div className="bg-slate-950/60 border-b border-white/5 p-3 text-[10px] text-amber-400">
        {notice}
      </div>

      <div className="flex-1 overflow-y-auto p-4">
        <div className="p-3 rounded border border-amber-500/20 bg-amber-950/20 text-xs text-amber-200">
          No Telegram signals are available from the backend.
        </div>
      </div>

      <form onSubmit={handleSendMessage} className="p-3 bg-slate-950/80 border-t border-white/10 flex gap-2">
        <input
          type="text"
          value={inputText}
          onChange={(event) => setInputText(event.target.value)}
          placeholder="Telegram integration is not configured"
          className="flex-1 bg-slate-900 border border-white/5 rounded-sm px-2.5 py-1.5 text-xs text-slate-200 focus:outline-none placeholder:text-slate-500 placeholder:text-[10px]"
          disabled
        />
        <button type="submit" disabled className="bg-white/5 text-white border border-white/10 p-2 rounded-sm opacity-50">
          <Send className="w-3.5 h-3.5 text-cyan-400" />
        </button>
      </form>
    </div>
  );
}
