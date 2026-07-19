import React, { useEffect } from "react";
import {
  LayoutDashboard, Terminal, BrainCircuit, Users, Route, GraduationCap, Cpu, Hourglass, Briefcase
} from "lucide-react";
import type { MainTab } from "../types";

interface NavigationMenuProps {
  activeTab: MainTab;
  setActiveTab: (tab: MainTab) => void;
  isComplianceActive: boolean;
  activeSymbol: string;
  winLossRatio: string;
  executedCount: number;
  language?: "en" | "de";
}

function isEditableTarget(target: EventTarget | null): boolean {
  if (!(target instanceof HTMLElement)) return false;
  const tag = target.tagName;
  if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT") return true;
  if (target.isContentEditable) return true;
  if (target.closest('[role="dialog"]')) return true;
  return false;
}

export default function NavigationMenu({ 
  activeTab, 
  setActiveTab, 
  isComplianceActive, 
  activeSymbol,
  winLossRatio,
  executedCount,
  language = "en"
}: NavigationMenuProps) {

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (isEditableTarget(e.target)) return;
      
      switch (e.key) {
        case "1":
          setActiveTab("dashboard");
          break;
        case "2":
          setActiveTab("terminal");
          break;
        case "3":
          setActiveTab("strategy");
          break;
        case "4":
          setActiveTab("swarm");
          break;
        case "5":
          setActiveTab("signals");
          break;
        case "6":
          setActiveTab("academy");
          break;
        case "7":
          setActiveTab("onnx");
          break;
        case "8":
          setActiveTab("chronos");
          break;
        case "9":
          setActiveTab("agency");
          break;
        default:
          break;
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [setActiveTab]);

  const tabs: Array<{
    id: MainTab;
    label: string;
    icon: typeof LayoutDashboard;
    desc: string;
    accent: string;
  }> = [
    {
      id: "dashboard",
      label: "Omni-Dashboard",
      icon: LayoutDashboard,
      accent: "emerald",
      desc: language === "de" ? "Live-Arbeitsbereich-Übersicht" : "Live workspace overview"
    },
    {
      id: "terminal",
      label: language === "de" ? "Handels-Terminal" : "Trading Terminal",
      icon: Terminal,
      accent: "cyan",
      desc: language === "de" ? "Orderbuch & Ausführungen" : "Order book & executions"
    },
    {
      id: "strategy",
      label: language === "de" ? "KI-Strategiestudio" : "AI Strategy Studio",
      icon: BrainCircuit,
      accent: "violet",
      desc: language === "de" ? "Generativer Co-Pilot & Ziele" : "Generative co-pilot & goals"
    },
    {
      id: "swarm",
      label: language === "de" ? "Schwarm-Verwaltung" : "Swarm Governance",
      icon: Users,
      accent: "amber",
      desc: language === "de" ? "Risikoüberwachung & Node-Status" : "Risk governing & node state"
    },
    {
      id: "signals",
      label: language === "de" ? "Signal-Routen" : "Signal Routes",
      icon: Route,
      accent: "sky",
      desc: language === "de" ? "TradingView & MCP-Eingang" : "TradingView & MCP ingress"
    },
    {
      id: "academy",
      label: language === "de" ? "Akademie" : "Academy",
      icon: GraduationCap,
      accent: "teal",
      desc: language === "de" ? "Agenten-Training & Drills" : "Agent training & drills"
    },
    {
      id: "onnx",
      label: language === "de" ? "ONNX-Neuronales Kernmodul" : "ONNX Neural Core",
      icon: Cpu,
      accent: "lime",
      desc: language === "de" ? "LSTM-Inferenz & Modell-Graph" : "LSTM inference & model graph"
    },
    {
      id: "chronos",
      label: language === "de" ? "Chronos-Agent" : "Chronos Agent",
      icon: Hourglass,
      accent: "cyan",
      desc: language === "de" ? "K-Line-Sprachmodell & Optionen" : "K-Line language model & options"
    },
    {
      id: "agency",
      label: language === "de" ? "Agency" : "Agency",
      icon: Briefcase,
      accent: "amber",
      desc: language === "de" ? "Rollen, Stufe & Lebensaufgaben" : "Roles, level & life tasks"
    },
  ];

  const accentBar: Record<string, string> = {
    emerald: "bg-emerald-400",
    cyan: "bg-cyan-400",
    violet: "bg-purple-400",
    amber: "bg-amber-400",
    sky: "bg-sky-400",
    teal: "bg-teal-400",
    lime: "bg-lime-400",
  };
  const accentText: Record<string, string> = {
    emerald: "text-emerald-400",
    cyan: "text-cyan-400",
    violet: "text-purple-400",
    amber: "text-amber-400",
    sky: "text-sky-400",
    teal: "text-teal-400",
    lime: "text-lime-400",
  };

  return (
    <nav className="w-full bg-[#090d16]/80 border border-white/5 rounded-xl p-2.5 backdrop-blur-md mb-6 shadow-[0_4px_25px_rgba(0,0,0,0.4)]" aria-label="Main">
      <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4 font-mono text-xs">
        <div className="flex flex-wrap items-center gap-2" role="tablist" aria-label="Workspace tabs">
          {tabs.map((tab, idx) => {
            const Icon = tab.icon;
            const isActive = activeTab === tab.id;
            
            return (
              <button
                key={tab.id}
                role="tab"
                aria-selected={isActive}
                id={`tab-${tab.id}`}
                onClick={() => setActiveTab(tab.id)}
                className={`relative flex items-center gap-3 px-4 py-2.5 min-h-11 rounded-lg border text-left transition-all duration-200 group overflow-hidden cursor-pointer ${
                  isActive 
                    ? "bg-slate-900/90 border-white/10 text-white shadow-[0_0_15px_rgba(56,189,248,0.12)]" 
                    : "bg-transparent border-white/5 hover:border-white/15 text-slate-400 hover:text-slate-200"
                }`}
                title={tab.desc}
              >
                {isActive && (
                  <div className={`absolute top-0 left-0 right-0 h-[2px] ${accentBar[tab.accent]}`} />
                )}

                <Icon className={`w-4.5 h-4.5 transition-transform duration-300 group-hover:scale-110 shrink-0 ${
                  isActive ? accentText[tab.accent] : "text-slate-500 group-hover:text-slate-400"
                }`} />

                <div className="flex flex-col">
                  <span className="font-bold text-[11px] tracking-tight leading-none text-slate-300 group-hover:text-white">
                    {tab.label}
                  </span>
                  <span className="text-[8px] text-slate-500 font-normal leading-none mt-1 uppercase tracking-wider hidden sm:block">
                    {language === "de" ? "Taste" : "Key"} {idx + 1}
                  </span>
                </div>
              </button>
            );
          })}
        </div>

        <div className="flex flex-wrap items-center gap-4 bg-slate-950/40 border border-white/5 rounded-lg px-4 py-2.5">
          <div className="flex flex-col">
            <span className="text-[8px] text-slate-500 uppercase leading-none">{language === "de" ? "AKTIVES PAAR" : "ACTIVE PAIR"}</span>
            <span className="text-white font-black leading-none mt-1">{activeSymbol}/USD</span>
          </div>
          <div className="h-6 w-[1px] bg-white/10" />
          <div className="flex flex-col">
            <span className="text-[8px] text-slate-500 uppercase leading-none">{language === "de" ? "GEWINNQUOTE" : "WIN RATIO"}</span>
            <span className="text-emerald-400 font-extrabold leading-none mt-1">{winLossRatio}</span>
          </div>
          <div className="h-6 w-[1px] bg-white/10" />
          <div className="flex flex-col">
            <span className="text-[8px] text-slate-500 uppercase leading-none">{language === "de" ? "AUSFÜHRUNGEN" : "EXECUTIONS"}</span>
            <span className="text-slate-300 font-bold leading-none mt-1">{executedCount}</span>
          </div>
          <div className="h-6 w-[1px] bg-white/10" />
          <div className="flex items-center gap-1.5">
            <span className="text-[8px] text-slate-500 uppercase">{language === "de" ? "REGLER" : "RIG"}</span>
            <span className={`text-[9px] font-bold px-1.5 py-0.5 rounded ${
              isComplianceActive 
                ? "bg-rose-500/15 border border-rose-500/20 text-rose-400" 
                : "bg-slate-500/15 border border-slate-500/20 text-slate-400"
            }`}>
              {isComplianceActive ? (language === "de" ? "SCHILD" : "SHIELD") : (language === "de" ? "LOKAL" : "LOCAL")}
            </span>
          </div>
        </div>
      </div>
    </nav>
  );
}
