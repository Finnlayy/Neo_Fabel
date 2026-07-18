import React, { useState } from "react";
import { SubAgentState, Trade } from "../types";
import { ShieldCheck, Activity, Brain, Cpu, BarChart2, TrendingUp, AlertCircle, RefreshCw, Terminal, CheckCircle2 } from "lucide-react";

interface SubAgentsSectionProps {
  agents: SubAgentState[];
  trades: Trade[];
  onUpdateAgentStatus: (id: string, status: SubAgentState["status"]) => void;
  onOptimizeThresholds: (multiplier: number) => void;
  isComplianceActive: boolean;
  onToggleCompliance: () => void;
  language?: "en" | "de";
}

const AGENT_DE: Record<string, { name: string; directive: string; lastAction: string }> = {
  orchestrator: {
    name: "HAUPT-ORCHESTRIERUNGS-AGENT",
    directive: "Zentrale Koordinierung der Multi-Agenten-Telemetrie, Validierung der Ausführungssicherheit und dynamische Allokation basierend auf neuronalen Signalen.",
    lastAction: "Zielallokation mit den primären Trading-Knoten synchronisiert."
  },
  market_data: {
    name: "Marktdaten-Agent",
    directive: "Verarbeitung von Ticks mehrerer Börsen, Berechnung des Echtzeit-VWAP und Bereitstellung von Orderbuchtiefenprofilen.",
    lastAction: "12.450 Handelsereignisse über 8 umsatzstarke Handelspaare verarbeitet."
  },
  adaptive: {
    name: "Adaptiver Agent",
    directive: "Kontinuierliche Optimierung von Parameterschwellenwerten, dynamische Skalierung des Hebels und Risikoprofil-Ausgleich.",
    lastAction: "Positionsgrößen-Multiplikator basierend auf Volumenspitze von 1,20x auf 1,35x neu kalibriert."
  },
  rna_smart: {
    name: "RNA Smartelligent-Agent",
    directive: "Ausführung des tiefen neuronalen Netzes zur Mustererkennung, Echtzeit-Fraktalerkennung und Anomalie-Filterung.",
    lastAction: "Bullish-Wedge-Formation auf dem SOL/USD 15-Minuten-Chart identifiziert."
  },
  risk_gov: {
    name: "Risiko-Governor-Agent",
    directive: "Erzwingung harter maximaler Drawdowns, Prüfung von Slippage-Abweichungen und Validierung von Gegenpartei-Marginparametern.",
    lastAction: "100%ige Einhaltung der sicheren Kapitalallokationsgrenzen verifiziert."
  },
  predictive: {
    name: "Prädiktiver Modellierungs-Agent",
    directive: "Generierung kurzfristiger Preisvektoren, Schätzung von Volatilitätskorridoren und Projektion von Liquidationskaskaden.",
    lastAction: "Kurzfristige prädiktive Vektoren für Top-5-Indexwerte aktualisiert."
  },
  analytic: {
    name: "Analytischer Analyse-Agent",
    directive: "Portfoliooptimierung über mehrere Assets, Zusammenstellung historischer Performances und Auswertung von Renditekurven.",
    lastAction: "Täglichen Ausführungsbericht generiert; zusammengesetzte Profitfaktor-Metriken berechnet."
  }
};

export default function SubAgentsSection({
  agents,
  trades,
  onUpdateAgentStatus,
  onOptimizeThresholds,
  isComplianceActive,
  onToggleCompliance,
  language = "en"
}: SubAgentsSectionProps) {
  const [riskMultiplier, setRiskMultiplier] = useState(1.35);
  const [activeDiagnosticId, setActiveDiagnosticId] = useState<string | null>(null);
  const [analysisResult, setAnalysisResult] = useState<string | null>(null);
  const [isAnalyzing, setIsAnalyzing] = useState(false);

  // Trigger Gemini API based Trade Diagnostic Report from the server-side proxy
  const handleAnalyzeTrades = async () => {
    setIsAnalyzing(true);
    setAnalysisResult(null);
    try {
      const response = await fetch("/api/gemini/analyze-trades", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ trades }),
      });
      const data = await response.json();
      if (response.ok) {
        setAnalysisResult(data.analysis || "Analysis complete.");
      } else {
        setAnalysisResult(`Error running analysis: ${data.error || "Unknown server error"}`);
      }
    } catch (err: any) {
      setAnalysisResult(`Failed to connect to full-stack analytics endpoint: ${err.message}`);
    } finally {
      setIsAnalyzing(false);
    }
  };

  // Helper to match icons
  const getAgentIcon = (id: string) => {
    switch (id) {
      case "orchestrator":
        return <Cpu className="w-4 h-4 text-cyan-400" />;
      case "market_data":
        return <Activity className="w-4 h-4 text-emerald-400" />;
      case "adaptive":
        return <RefreshCw className="w-4 h-4 text-amber-400" />;
      case "rna_smart":
        return <Brain className="w-4 h-4 text-purple-400 animate-pulse" />;
      case "risk_gov":
        return <ShieldCheck className="w-4 h-4 text-rose-400" />;
      case "predictive":
        return <TrendingUp className="w-4 h-4 text-blue-400" />;
      case "analytic":
        return <BarChart2 className="w-4 h-4 text-pink-400" />;
      default:
        return <Activity className="w-4 h-4 text-slate-400" />;
    }
  };

  const getStatusColor = (status: SubAgentState["status"]) => {
    switch (status) {
      case "ACTIVE":
        return "text-emerald-400 bg-emerald-500/10 border-emerald-500/20";
      case "OPTIMIZING":
        return "text-amber-400 bg-amber-500/10 border-amber-500/20 animate-pulse";
      case "STANDBY":
        return "text-slate-400 bg-slate-500/10 border-slate-500/20";
      case "ALERT":
        return "text-rose-400 bg-rose-500/10 border-rose-500/20 animate-bounce";
      default:
        return "text-slate-300";
    }
  };

  return (
    <div className="space-y-6">
      {/* Grid of Sub-Agents */}
      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
        {agents.map((agent) => {
          const isAdaptive = agent.id === "adaptive";
          const isRNA = agent.id === "rna_smart";
          const isRisk = agent.id === "risk_gov";
          const isAnalytic = agent.id === "analytic";

          return (
            <div
              key={agent.id}
              className={`p-5 rounded-xl border font-mono text-xs flex flex-col justify-between transition-all duration-300 ${
                isRisk && isComplianceActive
                  ? "bg-slate-900/40 border-rose-500/30 glow-rose"
                  : isRNA
                  ? "bg-slate-900/40 border-purple-500/30 glow-purple"
                  : "bg-slate-900/40 border-white/5 hover:border-white/10 hover:bg-slate-900/60"
              }`}
            >
              {/* Header */}
              <div className="flex items-center justify-between mb-3">
                <div className="flex items-center gap-2">
                  <div className="p-1.5 rounded bg-white/5 border border-white/5">
                    {getAgentIcon(agent.id)}
                  </div>
                  <div>
                    <h4 className="font-bold text-white uppercase tracking-tight text-[11px]">
                      {language === "de" && AGENT_DE[agent.id] ? AGENT_DE[agent.id].name : agent.name}
                    </h4>
                    <p className="text-[10px] text-slate-500">EFF: {agent.efficiency}%</p>
                  </div>
                </div>
                <span className={`px-2 py-0.5 rounded border text-[9px] font-mono font-bold ${getStatusColor(agent.status)}`}>
                  {agent.status}
                </span>
              </div>

              {/* Directives & Actions */}
              <div className="flex-1 space-y-2.5">
                <div className="p-2.5 bg-slate-950/45 rounded border border-white/5 text-[10px] text-slate-400">
                  <span className="text-[9px] text-slate-500 uppercase block font-semibold mb-1">
                    {language === "de" ? "// DIREKTIVEN-KANAL" : "// DIRECTIVE CHANNEL"}
                  </span>
                  {language === "de" && AGENT_DE[agent.id] ? AGENT_DE[agent.id].directive : agent.directive}
                </div>
                <div className="text-[10px] text-slate-300 flex items-start gap-1">
                  <span className="text-cyan-400 mt-0.5">»</span>
                  <span>{language === "de" && AGENT_DE[agent.id] ? AGENT_DE[agent.id].lastAction : agent.lastAction}</span>
                </div>
              </div>

              {/* Unique Interactive Overrides */}
              <div className="mt-4 pt-3 border-t border-white/15 space-y-2">
                {isAdaptive && (
                  <div className="space-y-2">
                    <div className="flex justify-between items-center text-[10px]">
                      <span className="text-amber-400">
                        {language === "de" ? "// MULTIPLIKATOR-KORRIDOR:" : "// MULTIPLIER CORRIDOR:"}
                      </span>
                      <span className="font-bold text-slate-200">{riskMultiplier.toFixed(2)}x</span>
                    </div>
                    <input
                      type="range"
                      min="0.5"
                      max="2.5"
                      step="0.05"
                      value={riskMultiplier}
                      onChange={(e) => {
                        const val = parseFloat(e.target.value);
                        setRiskMultiplier(val);
                        onOptimizeThresholds(val);
                      }}
                      className="w-full accent-cyan-400 bg-white/5 rounded h-1 cursor-pointer"
                    />
                  </div>
                )}

                {isRisk && (
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-1.5">
                      <ShieldCheck className="w-3.5 h-3.5 text-rose-400" />
                      <span className="text-[10px] text-rose-400">
                        {language === "de" ? "// COMPLIANCE-SCHUTZ:" : "// COMPLIANCE GUARD:"}
                      </span>
                    </div>
                    <button
                      onClick={onToggleCompliance}
                      className={`relative inline-flex h-4 w-8 items-center rounded-full transition-colors focus:outline-none cursor-pointer ${
                        isComplianceActive ? "bg-rose-500" : "bg-white/10"
                      }`}
                    >
                      <span
                        className={`inline-block h-2.5 w-2.5 transform rounded-full bg-white transition-transform ${
                          isComplianceActive ? "translate-x-4.5" : "translate-x-1"
                        }`}
                      />
                    </button>
                  </div>
                )}

                {isRNA && (
                  <div className="flex items-center justify-between text-[10px]">
                    <span className="text-purple-400 flex items-center gap-1">
                      <Brain className="w-3 h-3 text-purple-400" />
                      {language === "de" ? "NEURALER FOKUS-LOCK:" : "NEURAL FOCUS LOCK:"}
                    </span>
                    <span className="bg-purple-950/30 border border-purple-500/20 text-purple-300 px-1.5 py-0.5 rounded text-[9px] font-bold">
                      FRACTAL_WEDGE_LOCK
                    </span>
                  </div>
                )}

                {isAnalytic && (
                  <div>
                    <button
                      onClick={handleAnalyzeTrades}
                      disabled={isAnalyzing}
                      className="w-full text-center text-[9px] bg-white/5 hover:bg-white/10 text-white border border-white/10 rounded-sm py-1.5 cursor-pointer transition-all flex items-center justify-center gap-1 font-bold tracking-widest uppercase"
                    >
                      <Terminal className="w-3 h-3 text-cyan-400" />
                      {isAnalyzing 
                        ? (language === "de" ? "Analysiere Logs..." : "Analyzing logs...") 
                        : (language === "de" ? "KI-DIAGNOSTIK" : "AI Diagnostics")}
                    </button>
                  </div>
                )}

                {!isAdaptive && !isRisk && !isRNA && !isAnalytic && (
                  <div className="flex justify-end gap-1.5">
                    <button
                      onClick={() => onUpdateAgentStatus(agent.id, "ACTIVE")}
                      className={`px-2 py-0.5 rounded-sm text-[9px] font-semibold cursor-pointer border transition-all ${
                        agent.status === "ACTIVE"
                          ? "bg-emerald-500/10 border-emerald-500/30 text-emerald-400"
                          : "bg-white/5 border-white/10 text-slate-500 hover:text-slate-300"
                      }`}
                    >
                      START
                    </button>
                    <button
                      onClick={() => onUpdateAgentStatus(agent.id, "STANDBY")}
                      className={`px-2 py-0.5 rounded-sm text-[9px] font-semibold cursor-pointer border transition-all ${
                        agent.status === "STANDBY"
                          ? "bg-white/10 border-white/20 text-slate-300"
                          : "bg-white/5 border-white/10 text-slate-500 hover:text-slate-300"
                      }`}
                    >
                      STANDBY
                    </button>
                  </div>
                )}
              </div>
            </div>
          );
        })}
      </div>

      {/* Terminal popup display for analytical trades diagnosis */}
      {analysisResult && (
        <div className="bg-slate-900/90 border border-white/10 rounded-xl p-5 font-mono text-xs glow-rose space-y-3 relative backdrop-blur-md">
          <div className="flex items-center justify-between border-b border-white/10 pb-2">
            <div className="flex items-center gap-2">
              <span className="w-2 h-2 rounded-full bg-cyan-400 animate-pulse"></span>
              <span className="text-white font-bold uppercase tracking-wider text-[11px]">
                {language === "de" ? "ANALYTISCHER BERICHT-INDEX" : "ANALYTICAL REPORT INDEX"}
              </span>
            </div>
            <button
              onClick={() => setAnalysisResult(null)}
              className="text-slate-500 hover:text-white text-[9px] uppercase border border-white/10 px-2 py-1 rounded-sm cursor-pointer transition-all hover:bg-white/5"
            >
              {language === "de" ? "Konsole schließen" : "Close Console"}
            </button>
          </div>
          <div className="text-slate-300 leading-relaxed text-[11px] max-h-64 overflow-y-auto pr-2 space-y-2 whitespace-pre-wrap">
            {analysisResult}
          </div>
        </div>
      )}
    </div>
  );
}
