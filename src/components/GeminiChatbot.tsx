import React, { useState, useEffect, useRef } from "react";
import { 
  Send, 
  Cpu, 
  Sparkles, 
  RefreshCw, 
  Globe, 
  Bot, 
  User, 
  MessageSquare, 
  Plus, 
  ArrowRight,
  ShieldAlert,
  ChevronRight,
  FileCode,
  LineChart
} from "lucide-react";
import { ApiError } from "../api/client";
import { postChat } from "../api/ai";
import { toWireMessages } from "../api/chatWire";
import type { AgentStatusPacket } from "../types";

interface Message {
  role: "user" | "assistant";
  content: string;
  modelUsed?: string;
  routeLabel?: string;
  citations?: { title: string; uri: string }[];
  timestamp: string;
  /** Welcome / system fluff — kept in UI, excluded from Gemini wire payload. */
  ephemeral?: boolean;
}

type ChatMode = "assistant" | "orchestrator";

export default function GeminiChatbot({
  agentStatusPackets = [],
}: {
  agentStatusPackets?: AgentStatusPacket[];
}) {
  const [messages, setMessages] = useState<Message[]>([
    {
      role: "assistant",
      content: "Welcome to the Fable 5 Neural Core. I am your CMT & Pine Script co-pilot, powered by adaptive Gemini 3 series routing.\n\nAsk me to construct strategies, explain market traps, or evaluate order blocks in real-time.",
      modelUsed: "gemini-3.5-flash",
      routeLabel: "General Intelligence [Init]",
      timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
      ephemeral: true,
    }
  ]);

  const [input, setInput] = useState("");
  const [modelSelection, setModelSelection] = useState<"auto" | "pro-preview" | "flash" | "flash-lite">("auto");
  const [enableSearch, setEnableSearch] = useState(false);
  const [chatMode, setChatMode] = useState<ChatMode>("assistant");
  const [isLoading, setIsLoading] = useState(false);
  
  const chatEndRef = useRef<HTMLDivElement>(null);

  // Auto-scroll on fresh messages
  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isLoading]);

  const handleSendMessage = async (textToSend?: string) => {
    const promptText = (textToSend || input).trim();
    if (!promptText || isLoading) return;

    if (!textToSend) {
      setInput("");
    }

    const timestamp = new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
    const userMsg: Message = {
      role: "user",
      content: promptText,
      timestamp
    };

    const updatedHistory = [...messages, userMsg];
    setMessages(updatedHistory);
    setIsLoading(true);

    try {
      // Wire protocol: sliding window only — do not resend full UI history / welcome.
      const data = await postChat({
        messages: toWireMessages(updatedHistory),
        modelSelection,
        enableSearch,
        mode: chatMode,
        agentStatusPackets: chatMode === "orchestrator" ? agentStatusPackets : [],
      });
      if (data.success) {
        setMessages(prev => [
          ...prev,
          {
            role: "assistant",
            content: data.reply ?? "",
            modelUsed: data.modelUsed,
            routeLabel: data.routeLabel,
            citations: data.citations,
            timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })
          }
        ]);
      } else {
        setMessages(prev => [
          ...prev,
          {
            role: "assistant",
            content: `⚠️ System Error: ${data.error || "Failed to fetch response."}`,
            timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })
          }
        ]);
      }
    } catch (err: unknown) {
      const message =
        err instanceof ApiError ? `${err.code}: ${err.message}` : err instanceof Error ? err.message : "Failed to reach backend core.";
      setMessages(prev => [
          ...prev,
          {
            role: "assistant",
            content: `⚠️ Connectivity Error: ${message}`,
            timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })
          }
      ]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleClearChat = () => {
    setMessages([
      {
        role: "assistant",
        content: "Core dialogue ledger reset. Standby for fresh prompt inputs.",
        modelUsed: "gemini-3.1-flash-lite",
        routeLabel: "Low-Latency Core",
        timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
        ephemeral: true,
      }
    ]);
  };

  const promptSuggestions = [
    { label: "SMC Breaker Code", prompt: "Write a high-quality Pinescript v5 indicator displaying Breaker Blocks and sweeps", icon: FileCode },
    { label: "Explain OB Sweeps", prompt: "What is a liquidity sweep of a double top? Explain how an institutional trader spots it.", icon: LineChart },
    { label: "Trailing Stop script", prompt: "Explain how to program a dynamic Trailing Stop Loss offset inside TradingView Pine v5.", icon: FileCode }
  ];

  return (
    <div id="gemini-chatbot-panel" className="bg-slate-900/40 border border-white/5 rounded-2xl p-5 space-y-4 transition-all duration-300 hover:border-white/10 hover:bg-slate-900/50 flex flex-col h-[520px]">
      
      {/* Header */}
      <div className="flex items-center justify-between border-b border-white/5 pb-3">
        <div className="flex items-center gap-2">
          <div className="bg-cyan-500/10 border border-cyan-500/20 p-1.5 rounded-lg text-cyan-400">
            <MessageSquare className="w-4 h-4" />
          </div>
          <div>
            <h3 className="text-sm font-bold uppercase tracking-wider text-slate-100 flex items-center gap-1.5">
              Neural Grounded Co-Pilot
              <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse"></span>
            </h3>
            <p className="text-[10px] text-slate-500 leading-none">
              Adaptive Routing & Google Search Grounding Engine
            </p>
          </div>
        </div>

        {/* Header Actions */}
        <div className="flex items-center gap-2">
          <button
            onClick={() => setChatMode((m) => (m === "assistant" ? "orchestrator" : "assistant"))}
            className={`p-1.5 rounded-lg border text-[10px] font-bold uppercase flex items-center gap-1 transition-all ${
              chatMode === "orchestrator"
                ? "bg-emerald-500/10 border-emerald-500/30 text-emerald-400"
                : "bg-slate-950/60 border-white/5 text-slate-500 hover:text-slate-300"
            }`}
            title="Toggle Master Orchestrator mode (doctrine + prompt shots)"
          >
            <Cpu className="w-3.5 h-3.5" />
            <span className="hidden sm:inline">{chatMode === "orchestrator" ? "Orchestrator" : "Assistant"}</span>
          </button>

          {/* Grounding Toggle */}
          <button
            onClick={() => setEnableSearch(!enableSearch)}
            className={`p-1.5 rounded-lg border text-[10px] font-bold uppercase flex items-center gap-1 transition-all ${
              enableSearch 
                ? "bg-cyan-500/10 border-cyan-500/30 text-cyan-400" 
                : "bg-slate-950/60 border-white/5 text-slate-500 hover:text-slate-300"
            }`}
            title="Toggle Google Search Grounding"
          >
            <Globe className="w-3.5 h-3.5" />
            <span className="hidden sm:inline">{enableSearch ? "Grounding Active" : "Web Off"}</span>
          </button>

          {/* Model selection dropdown */}
          <select
            value={modelSelection}
            onChange={(e: any) => setModelSelection(e.target.value)}
            className="bg-slate-950/80 border border-white/5 text-[9px] text-slate-300 p-1.5 rounded-lg font-mono focus:border-cyan-500 outline-none"
          >
            <option value="auto">🧠 Auto-Route Core</option>
            <option value="pro-preview">🔬 3.1 Pro (Thinking)</option>
            <option value="flash">⚡ 3.5 Flash (General)</option>
            <option value="flash-lite">🚀 3.1 Flash-Lite (Fast)</option>
          </select>

          {/* Clear dialog ledger */}
          <button
            onClick={handleClearChat}
            className="p-1.5 bg-slate-950/60 hover:bg-red-500/10 border border-white/5 text-slate-500 hover:text-red-400 rounded-lg transition-colors"
            title="Reset Chat Log"
          >
            <Plus className="w-3.5 h-3.5 rotate-45" />
          </button>
        </div>
      </div>

      {/* Message Feed Grid */}
      <div className="flex-1 overflow-y-auto scrollbar-thin space-y-3 pr-1.5">
        {messages.map((msg, i) => (
          <div 
            key={i} 
            className={`flex gap-2.5 ${msg.role === "user" ? "justify-end" : "justify-start"}`}
          >
            {/* Assistant avatar */}
            {msg.role === "assistant" && (
              <div className="w-6 h-6 rounded-lg bg-cyan-500/10 border border-cyan-500/20 text-cyan-400 flex items-center justify-center shrink-0 mt-1">
                <Bot className="w-3.5 h-3.5" />
              </div>
            )}

            <div className={`max-w-[85%] rounded-xl p-3 text-[11px] leading-relaxed relative ${
              msg.role === "user"
                ? "bg-slate-800/80 border border-cyan-500/20 text-slate-100"
                : "bg-slate-950/40 border border-white/5 text-slate-300"
            }`}>
              
              {/* Content formatted */}
              <div className="whitespace-pre-wrap font-sans">
                {msg.content.split("\n").map((line, idx) => {
                  if (line.startsWith("```")) return null; // Simple code block hiding helper
                  if (line.startsWith("###") || line.startsWith("- ")) {
                    return <div key={idx} className="font-bold text-slate-200 mt-1 mb-0.5">{line.replace("###", "")}</div>;
                  }
                  return <p key={idx} className={line.startsWith("//") ? "font-mono text-[10px] text-emerald-400 bg-slate-950/40 p-1 rounded" : ""}>{line}</p>;
                })}
              </div>

              {/* Citations block */}
              {msg.citations && msg.citations.length > 0 && (
                <div className="mt-2.5 pt-2 border-t border-white/5 space-y-1">
                  <div className="text-[8px] font-bold text-slate-500 tracking-wider uppercase flex items-center gap-1">
                    <Globe className="w-3 h-3 text-cyan-500" />
                    Web Grounding Sources:
                  </div>
                  <div className="flex flex-wrap gap-1">
                    {msg.citations.map((cite, cIdx) => (
                      <a
                        key={cIdx}
                        href={cite.uri}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-[9px] bg-cyan-500/5 hover:bg-cyan-500/15 border border-cyan-500/10 hover:border-cyan-500/30 px-1.5 py-0.5 rounded text-cyan-400 transition-colors inline-flex items-center gap-1"
                      >
                        {cite.title.length > 20 ? `${cite.title.slice(0, 20)}...` : cite.title}
                        <ChevronRight className="w-2 h-2 text-cyan-500" />
                      </a>
                    ))}
                  </div>
                </div>
              )}

              {/* Model Tag indicator */}
              {msg.role === "assistant" && (msg.modelUsed || msg.routeLabel) && (
                <div className="mt-2 flex items-center gap-1 text-[8px] text-slate-500 font-mono">
                  <Cpu className="w-2.5 h-2.5" />
                  <span>Model:</span>
                  <span className="text-cyan-500/70">{msg.modelUsed}</span>
                  <span>({msg.routeLabel})</span>
                </div>
              )}
            </div>

            {/* User avatar */}
            {msg.role === "user" && (
              <div className="w-6 h-6 rounded-lg bg-slate-800 border border-white/10 text-slate-300 flex items-center justify-center shrink-0 mt-1">
                <User className="w-3.5 h-3.5" />
              </div>
            )}
          </div>
        ))}

        {/* Loading Spinner */}
        {isLoading && (
          <div className="flex gap-2.5 justify-start">
            <div className="w-6 h-6 rounded-lg bg-purple-500/10 border border-purple-500/20 text-purple-400 flex items-center justify-center shrink-0 animate-pulse">
              <Bot className="w-3.5 h-3.5" />
            </div>
            <div className="bg-slate-950/40 border border-white/5 rounded-xl p-3 text-[11px] text-slate-400 italic flex items-center gap-2">
              <RefreshCw className="w-3 h-3 animate-spin text-purple-400" />
              Smartelligent core aligning parameters...
            </div>
          </div>
        )}
        <div ref={chatEndRef} />
      </div>

      {/* Prompt suggestions row */}
      {messages.length === 1 && !isLoading && (
        <div className="space-y-1.5">
          <span className="text-[9px] font-bold text-slate-500 uppercase tracking-widest block">Quick Prompts:</span>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-2">
            {promptSuggestions.map((s, idx) => {
              const IconComp = s.icon;
              return (
                <button
                  key={idx}
                  onClick={() => handleSendMessage(s.prompt)}
                  className="bg-slate-950/60 hover:bg-slate-900 border border-white/5 hover:border-cyan-500/20 p-2 rounded-lg text-left transition-all text-[9px] text-slate-300 flex items-start gap-1.5 group"
                >
                  <IconComp className="w-3.5 h-3.5 text-cyan-400 group-hover:text-cyan-300 shrink-0 mt-0.5" />
                  <span className="group-hover:text-slate-100 font-medium leading-normal">{s.label}</span>
                </button>
              );
            })}
          </div>
        </div>
      )}

      {/* Prompt Input Box */}
      <form 
        onSubmit={(e) => {
          e.preventDefault();
          handleSendMessage();
        }}
        className="flex gap-2"
      >
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder={isLoading ? "Thinking..." : "Consult Neural Core / Ask for Pine Code..."}
          disabled={isLoading}
          className="flex-1 bg-slate-950/80 border border-white/5 text-[11px] text-slate-300 p-2.5 rounded-xl focus:border-cyan-500 focus:ring-1 focus:ring-cyan-500/20 outline-none transition-all disabled:opacity-50"
        />
        <button
          type="submit"
          disabled={!input.trim() || isLoading}
          className="bg-cyan-500 hover:bg-cyan-400 disabled:bg-slate-950 disabled:text-slate-600 disabled:border-white/5 border border-transparent text-slate-950 p-2.5 rounded-xl font-bold transition-all flex items-center justify-center shrink-0"
        >
          <Send className="w-4 h-4" />
        </button>
      </form>

    </div>
  );
}
