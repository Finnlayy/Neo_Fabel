import React, { useState } from "react";
import { 
  GitCommit, Activity, Search, AlertCircle, RefreshCw, Sparkles, 
  Terminal, ShieldCheck, HeartPulse, Send, Brain
} from "lucide-react";

interface TimelineEvent {
  id: string;
  time: string;
  agentName: string;
  agentId: string;
  type: "INFO" | "SUCCESS" | "WARNING" | "CRITICAL";
  message: string;
  impactScore?: number; // 0-100
}

export default function AgentTimeline() {
  // Manual / future agent-stream events only — no simulated injectors.
  const [events, setEvents] = useState<TimelineEvent[]>([]);

  // Filters
  const [selectedAgentId, setSelectedAgentId] = useState<string>("ALL");
  const [searchQuery, setSearchQuery] = useState("");

  // Input states for custom event injection
  const [customAgent, setCustomAgent] = useState("orchestrator");
  const [customMessage, setCustomMessage] = useState("");
  const [customType, setCustomType] = useState<TimelineEvent["type"]>("INFO");
  const [customImpact, setCustomImpact] = useState<number>(75);

  const agentsList = [
    { id: "orchestrator", name: "Master Orchestrator" },
    { id: "market_data", name: "Market Data Agent" },
    { id: "adaptive", name: "Adaptive Agent" },
    { id: "rna_smart", name: "RNA Smartelligent" },
    { id: "risk_gov", name: "Risk Governor" },
    { id: "predictive", name: "Predictive Modeling" },
    { id: "analytic", name: "Analytical Analysis" }
  ];

  // Handle manual injection
  const handleInjectEvent = (e: React.FormEvent) => {
    e.preventDefault();
    if (!customMessage.trim()) return;

    const matchedAgent = agentsList.find(a => a.id === customAgent);
    const agentName = matchedAgent ? matchedAgent.name.toUpperCase() : "CUSTOM AGENT";

    const newEvent: TimelineEvent = {
      id: `ev-${Date.now()}`,
      time: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" }),
      agentName,
      agentId: customAgent,
      type: customType,
      message: customMessage.trim(),
      impactScore: Number(customImpact)
    };

    setEvents((prev) => [newEvent, ...prev]);
    setCustomMessage("");
  };

  // Get type color
  const getTypeColor = (type: TimelineEvent["type"]) => {
    switch (type) {
      case "CRITICAL": return { text: "text-red-400", border: "border-red-500", bg: "bg-red-500/10" };
      case "WARNING": return { text: "text-amber-400", border: "border-amber-500", bg: "bg-amber-500/10" };
      case "SUCCESS": return { text: "text-emerald-400", border: "border-emerald-500", bg: "bg-emerald-500/10" };
      default: return { text: "text-cyan-400", border: "border-cyan-500", bg: "bg-cyan-500/10" };
    }
  };

  // Filtered list
  const filteredEvents = events.filter((ev) => {
    const matchesAgent = selectedAgentId === "ALL" || ev.agentId === selectedAgentId;
    const matchesSearch = ev.message.toLowerCase().includes(searchQuery.toLowerCase()) || 
                          ev.agentName.toLowerCase().includes(searchQuery.toLowerCase());
    return matchesAgent && matchesSearch;
  });

  return (
    <div id="agent-timeline-card" className="bg-slate-900/40 border border-white/5 hover:border-white/10 rounded-xl p-5 font-mono text-xs space-y-4 transition-all duration-300">
      
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-3 border-b border-white/10 pb-4">
        <div className="flex items-center gap-2">
          <Brain className="w-4 h-4 text-cyan-400 animate-pulse" />
          <div>
            <h3 className="text-white font-bold uppercase tracking-wider text-[11px]">
              Multi-Agent Neural Timeline // Ledger
            </h3>
            <p className="text-[9px] text-slate-500">
              Trace chronological decision sequences, status updates, and dynamic parameter logs across Fable 5.
            </p>
          </div>
        </div>

        {/* Real-time Indicator */}
        <span className="text-[9px] text-emerald-400 font-bold flex items-center gap-1">
          <HeartPulse className="w-3.5 h-3.5 animate-bounce" />
          NO AGENT STREAM
        </span>
      </div>

      {/* Control Filters and Search Row */}
      <div className="flex flex-col sm:flex-row items-center gap-2.5">
        
        {/* Agent Filter Select */}
        <div className="w-full sm:w-auto flex items-center gap-1.5 bg-slate-950/40 border border-white/5 rounded-lg px-2.5 py-1.5">
          <span className="text-[9px] text-slate-500 uppercase font-bold shrink-0">Node:</span>
          <select
            value={selectedAgentId}
            onChange={(e) => setSelectedAgentId(e.target.value)}
            className="bg-transparent text-slate-300 text-[10px] focus:outline-none border-none font-bold"
          >
            <option value="ALL">All Active Nodes</option>
            {agentsList.map((a) => (
              <option key={a.id} value={a.id}>{a.name}</option>
            ))}
          </select>
        </div>

        {/* Search Input */}
        <div className="w-full sm:flex-grow relative">
          <Search className="w-3.5 h-3.5 text-slate-500 absolute left-2.5 top-1/2 -translate-y-1/2" />
          <input
            type="text"
            placeholder="Search timeline events..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full bg-slate-950/40 border border-white/5 rounded-lg text-[10px] text-slate-300 pl-8 pr-3 py-1.5 focus:border-cyan-500/50 focus:outline-none placeholder:text-slate-600 transition-colors"
          />
        </div>
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-4 gap-5">
        
        {/* Timeline Log Feed */}
        <div className="xl:col-span-3 space-y-3.5 max-h-[360px] overflow-y-auto pr-1 scrollbar-thin">
          {filteredEvents.length > 0 ? (
            <div className="relative border-l border-white/10 ml-3 pl-5 space-y-4 pt-1.5">
              {filteredEvents.map((ev) => {
                const colors = getTypeColor(ev.type);

                return (
                  <div key={ev.id} className="relative group">
                    {/* Circle Bullet */}
                    <div className={`absolute -left-[25.5px] top-1 w-2.5 h-2.5 rounded-full border-2 ${colors.border} bg-slate-950 group-hover:scale-125 transition-transform`} />

                    {/* Timeline Event Details */}
                    <div className="bg-slate-950/30 border border-white/5 hover:border-white/15 p-3 rounded-lg space-y-1.5 transition-all duration-300">
                      <div className="flex flex-wrap items-center justify-between gap-1.5 text-[10px]">
                        
                        {/* Time & Agent */}
                        <div className="flex items-center gap-2">
                          <span className="text-slate-500 font-mono text-[9px]">{ev.time}</span>
                          <span className="text-slate-600">|</span>
                          <span className="text-white font-bold tracking-tight">{ev.agentName}</span>
                        </div>

                        {/* Impact Level Badge */}
                        <div className="flex items-center gap-2">
                          {ev.impactScore && (
                            <span className="text-[8px] font-mono text-slate-500">
                              Impact: <span className="text-white font-bold">{ev.impactScore}%</span>
                            </span>
                          )}
                          <span className={`text-[7px] font-black px-1 rounded uppercase tracking-widest ${colors.text} ${colors.bg}`}>
                            {ev.type}
                          </span>
                        </div>

                      </div>

                      {/* Log Message */}
                      <p className="text-[10px] text-slate-400 leading-normal font-sans">
                        {ev.message}
                      </p>
                    </div>
                  </div>
                );
              })}
            </div>
          ) : (
            <div className="border border-dashed border-white/5 bg-slate-950/20 rounded-xl py-12 text-center text-slate-500">
              <AlertCircle className="w-7 h-7 mx-auto text-slate-600 mb-2" />
              <span className="text-[10px] font-bold text-slate-400 block">No Neural Events Matches Filters</span>
              <span className="text-[8px] text-slate-600">Try modifying your text search query or node selection.</span>
            </div>
          )}
        </div>

        {/* Dynamic Event Injection Side-Form */}
        <div className="bg-slate-950/30 border border-white/5 rounded-xl p-4 flex flex-col justify-between space-y-3">
          <form onSubmit={handleInjectEvent} className="space-y-3.5">
            <span className="text-[9px] text-slate-500 font-bold block border-b border-white/5 pb-1.5 uppercase tracking-wider">
              📥 Inject Neural Parameter
            </span>

            {/* Target Agent Selection */}
            <div className="space-y-1">
              <label className="text-[8px] text-slate-500 font-bold uppercase tracking-wider block">Target Node</label>
              <select
                value={customAgent}
                onChange={(e) => setCustomAgent(e.target.value)}
                className="w-full bg-slate-900 border border-white/5 rounded p-1.5 text-[9.5px] text-slate-300 font-bold focus:outline-none focus:border-cyan-500/50"
              >
                {agentsList.map((a) => (
                  <option key={a.id} value={a.id}>{a.name}</option>
                ))}
              </select>
            </div>

            {/* Event Severity/Type */}
            <div className="space-y-1">
              <label className="text-[8px] text-slate-500 font-bold uppercase tracking-wider block">Log Type</label>
              <div className="grid grid-cols-2 gap-1.5">
                {(["INFO", "SUCCESS", "WARNING", "CRITICAL"] as const).map((t) => (
                  <button
                    key={t}
                    type="button"
                    onClick={() => setCustomType(t)}
                    className={`px-1 py-1 rounded text-[8px] font-extrabold uppercase tracking-widest text-center border cursor-pointer ${
                      customType === t
                        ? t === "CRITICAL" ? "bg-red-950/40 border-red-500 text-red-300"
                        : t === "WARNING" ? "bg-amber-950/40 border-amber-500 text-amber-300"
                        : t === "SUCCESS" ? "bg-emerald-950/40 border-emerald-500 text-emerald-300"
                        : "bg-cyan-950/40 border-cyan-500 text-cyan-300"
                        : "bg-slate-900 border-transparent text-slate-500"
                    }`}
                  >
                    {t}
                  </button>
                ))}
              </div>
            </div>

            {/* Impact score slider */}
            <div className="space-y-1">
              <div className="flex justify-between items-center text-[8px] text-slate-500 uppercase tracking-wider font-bold">
                <span>IMPACT SCORE</span>
                <span className="text-white font-mono">{customImpact}%</span>
              </div>
              <input
                type="range"
                min="10"
                max="100"
                value={customImpact}
                onChange={(e) => setCustomImpact(Number(e.target.value))}
                className="w-full accent-cyan-500 h-1 bg-slate-900 rounded"
              />
            </div>

            {/* Event Message */}
            <div className="space-y-1">
              <label className="text-[8px] text-slate-500 font-bold uppercase tracking-wider block">Log Directive Message</label>
              <textarea
                placeholder="Type dynamic system override message..."
                value={customMessage}
                onChange={(e) => setCustomMessage(e.target.value)}
                rows={3}
                className="w-full bg-slate-900 border border-white/5 rounded p-1.5 text-[9.5px] text-slate-300 placeholder:text-slate-700 focus:outline-none focus:border-cyan-500/50 resize-none font-sans"
              />
            </div>

            <button
              type="submit"
              disabled={!customMessage.trim()}
              className="w-full bg-cyan-600 hover:bg-cyan-500 disabled:bg-slate-900 disabled:text-slate-600 text-white font-black text-[9px] uppercase tracking-wider py-2 rounded transition-colors flex items-center justify-center gap-1 cursor-pointer"
            >
              <Send className="w-3 h-3" />
              Inject Node Log
            </button>
          </form>

          <div className="pt-2 border-t border-white/5 text-[8px] text-slate-600 leading-normal">
            ⚙️ Real-time manual logs simulate local parameter calibration inputs for testing Fable 5 models.
          </div>
        </div>

      </div>

    </div>
  );
}
