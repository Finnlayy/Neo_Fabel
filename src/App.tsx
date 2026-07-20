import React, { useCallback, useEffect, useMemo, useState } from "react";
import { TickerData, Trade, SubAgentState, GenerativePlan, MainTab, AgentStatusPacket } from "./types";
import SignalRoutesPage from "./features/signalRoutes/SignalRoutesPage";
import AcademyPage from "./features/academy/AcademyPage";
import OnnxPage from "./features/onnx/OnnxPage";
import ChronosPage from "./features/chronos/ChronosPage";
import AgencyPage from "./features/agency/AgencyPage";
import PaperPerformancePage from "./features/paper/PaperPerformancePage";
import PositionsPage from "./features/positions/PositionsPage";
import AuthPanel from "./auth/AuthPanel";
import IntegrationsSettingsPanel from "./features/settings/IntegrationsSettingsPanel";
import CommandOverview from "./components/CommandOverview";
import OrderbookHeatmap3D from "./components/OrderbookHeatmap3D";
import { fetchCryptoTickers, fetchEquityTickers, fetchOrderBook, upsertTickerHistory } from "./api/market";
import { connectMarketStream } from "./api/marketStream";
import { fetchAiHealth } from "./api/ai";
import { fetchReadyStatus, type ReadyStatus } from "./api/health";
import { fetchPaperStatus, mapPaperStatusToTrades } from "./api/paper";
import { pushRnaContext } from "./api/rnaContext";
import { INITIAL_SUB_AGENTS } from "./data";
import { closesToBlindCandles, scanBlindPatterns } from "./services/blindPatternScan";

// Components
import TelegramFeed from "./components/TelegramFeed";
import SubAgentsSection from "./components/SubAgentsSection";
import SimulatedTrading from "./components/SimulatedTrading";
import ExecutedTradesSection from "./components/ExecutedTradesSection";
import ResourceAllocation from "./components/ResourceAllocation";
import LiveMarketHeatmap from "./components/LiveMarketHeatmap";
import IntegratedConnectors from "./components/IntegratedConnectors";
import TradingLoopSwitches from "./components/TradingLoopSwitches";
import TvapiOptimizer from "./components/TvapiOptimizer";
import GeminiChatbot from "./components/GeminiChatbot";
import RiskAssessmentHeatmap from "./components/RiskAssessmentHeatmap";
import CircularGauge from "./components/CircularGauge";
import AgentTimeline from "./components/AgentTimeline";
import NavigationMenu from "./components/NavigationMenu";
import NeuralVectorAnalyzer from "./components/NeuralVectorAnalyzer";
import { announceTradeOutcome } from "./services/casinoAudio";
import { AnimatePresence, motion } from "motion/react";

// Icons
import { 
  Shield, Cpu, AlertCircle, RefreshCw, Layers, CheckCircle2, 
  HelpCircle, Sparkles, Network, Info, Terminal, FileText, Lock, Settings
} from "lucide-react";

const TRANSLATIONS = {
  en: {
    systemTime: "SYSTEM TIME",
    systemStatus: "SYSTEM STATUS",
    connectedGemini: "AI: CHECKING",
    complianceRig: "COMPLIANCE RIG",
    enforced: "⚠️ ENFORCED",
    unguarded: "⚡ UNGUARDED",
    toggleGuard: "Toggle Guard",
    activePair: "ACTIVE PAIR",
    winRatio: "WIN RATIO",
    executions: "EXECUTIONS",
    rig: "RIG",
    shield: "SHIELD",
    unsafe: "UNSAFE",
    settings: "Settings",
    language: "Language",
    english: "English",
    german: "German (Deutsch)",
    selectLanguageDesc: "Choose your preferred system display and audio announcer language.",
    close: "Close",
    soundVolume: "Sound volume",
    keyboardShortcuts: "Keyboard Shortcuts",
    keyDesc: "Use hotkeys [1-7] to switch workspaces.",
    auditoryFeedback: "Acoustic Telemetry",
    voicePack: "HoN Announcer",
    saveSettings: "Save Settings",
    masterOrchestrator: "MASTER ORCHESTRATOR AGENT",
    masterOrchestratorDesc: "Central execution block driving tactical directive alignment. Continuously audits signal weights across sub-nodes to maximize drawdown defenses.",
    score: "SCORE",
    activeDirectives: "Active Directives",
    queueLatency: "Queue Latency",
    safetyCompliance: "Safety Compliance",
    hardOverride: "Hard Override",
    fableConsole: "FABLE 5 MASTER CONSOLE",
    fableConsoleDesc: "Aggregates order depth profiles, trading volume vectors, and real-time social sentiments into a single unified telemetry flow.",
    index: "INDEX",
    sentimentWeight: "Sentiment weight",
    signalAnomaly: "Signal Anomaly",
    noneDetected: "None detected",
    telemetryFeed: "Telemetry Feed",
    active: "ACTIVE",
    systemOverview: "OS SYSTEM OVERVIEW",
    systemOverviewDesc: "Tactical execution aligns directly with user directives. Leverage the 'Generative Goal Planning' below to override configurations and deploy custom-tailored multi-agent rules!",
    standardAutomated: "Standard automated market-scanning strategy active. All core sub-agent nodes green.",
    activeDirectiveInit: "Active directive initialized across active sub-nodes.",
  },
  de: {
    systemTime: "SYSTEMZEIT",
    systemStatus: "SYSTEMSTATUS",
    connectedGemini: "KI: PRÜFE",
    complianceRig: "SICHERHEITS-REGLER",
    enforced: "⚠️ ERZWUNGEN",
    unguarded: "⚡ UNGESCHÜTZT",
    toggleGuard: "Schutz umschalten",
    activePair: "AKTIVES PAAR",
    winRatio: "GEWINNQUOTE",
    executions: "AUSFÜHRUNGEN",
    rig: "REGLER",
    shield: "SCHILD",
    unsafe: "UNSICHER",
    settings: "Einstellungen",
    language: "Sprache",
    english: "Englisch",
    german: "Deutsch",
    selectLanguageDesc: "Wählen Sie die gewünschte Sprache für die Anzeige und Sprachansagen.",
    close: "Schließen",
    soundVolume: "Audio-Lautstärke",
    keyboardShortcuts: "Tastatur-Kurzbefehle",
    keyDesc: "Verwenden Sie Hotkeys [1-7], um Arbeitsbereiche zu wechseln.",
    auditoryFeedback: "Akustische Telemetrie",
    voicePack: "HoN-Sprecher",
    saveSettings: "Einstellungen speichern",
    masterOrchestrator: "HAUPT-ORCHESTRIERUNGS-AGENT",
    masterOrchestratorDesc: "Zentrale Ausführungseinheit zur Ausrichtung taktischer Direktiven. Überprüft kontinuierlich die Signalgewichte aller Sub-Knoten zur Maximierung des Drawdown-Schutzes.",
    score: "BEWERTUNG",
    activeDirectives: "Aktive Direktiven",
    queueLatency: "Warteschlangen-Latenz",
    safetyCompliance: "Sicherheitskonformität",
    hardOverride: "Harter Override",
    fableConsole: "FABLE 5 MASTER-KONSOLE",
    fableConsoleDesc: "Aggregiert Orderbuchtiefenprofile, Handelsvolumenvektoren und Echtzeit-Social-Sentiment in einem einzigen, einheitlichen Telemetriefluss.",
    index: "INDEX",
    sentimentWeight: "Sentiment-Gewicht",
    signalAnomaly: "Signalanomalie",
    noneDetected: "Keine erkannt",
    telemetryFeed: "Telemetriefluss",
    active: "AKTIV",
    systemOverview: "OS-SYSTEMÜBERSICHT",
    systemOverviewDesc: "Die taktische Ausführung richtet sich direkt nach den Benutzer-Vorgaben. Nutzen Sie die 'Generative Zielplanung' unten, um Konfigurationen zu überschreiben!",
    standardAutomated: "Standardmäßige automatisierte Marktscannungs-Strategie aktiv. Alle Kern-Subagenten-Knoten im grünen Bereich.",
    activeDirectiveInit: "Aktive Direktive wurde auf allen aktiven Sub-Knoten initialisiert.",
  }
};

export default function App() {
  const [tickers, setTickers] = useState<TickerData[]>([]);
  const [marketAsOf, setMarketAsOf] = useState<string | null>(null);
  const [marketLive, setMarketLive] = useState(false);
  const [marketSource, setMarketSource] = useState<string | null>(null);
  const [orderBookOnline, setOrderBookOnline] = useState(false);
  const [queueLatencyMs, setQueueLatencyMs] = useState<number | null>(null);
  const [trades, setTrades] = useState<Trade[]>([]);
  const [subAgents, setSubAgents] = useState<SubAgentState[]>(INITIAL_SUB_AGENTS);
  const [activePlan, setActivePlan] = useState<GenerativePlan | null>(null);
  const [allocation, setAllocation] = useState<{ name: string; value: number }[]>([]);
  const [aiStatusLabel, setAiStatusLabel] = useState("AI: OFFLINE");
  const [readyStatus, setReadyStatus] = useState<ReadyStatus | null>(null);
  const [isComplianceActive, setIsComplianceActive] = useState(true);
  const [activeSymbol, setActiveSymbol] = useState("BTC");
  const [currentTime, setCurrentTime] = useState(new Date().toLocaleTimeString());
  const [tradingExchange, setTradingExchange] = useState("simulated");
  const [streak, setStreak] = useState({ wins: 0, losses: 0 });
  const [announcement, setAnnouncement] = useState<{ text: string; type: "kill" | "death" | "assist" | "humiliation" | "nemesis" | "immortal"; id: number } | null>(null);
  const [activeTab, setActiveTab] = useState<MainTab>("dashboard");
  const [strategySubTab, setStrategySubTab] = useState<"optimizer" | "vector">("optimizer");

  const [language, setLanguage] = useState<"en" | "de">(() => {
    if (typeof window !== "undefined") {
      return (localStorage.getItem("app_language") as "en" | "de") || "en";
    }
    return "en";
  });
  const [isSettingsOpen, setIsSettingsOpen] = useState(false);

  const t = (key: keyof typeof TRANSLATIONS.en) => {
    return TRANSLATIONS[language][key] || TRANSLATIONS.en[key];
  };

  const wins = trades.filter(t => t.pnl > 0).length;
  const losses = trades.filter(t => t.pnl < 0).length;
  const totalClosed = wins + losses;
  const winLossRatio = totalClosed > 0 
    ? `${Math.round((wins / totalClosed) * 100)}% (${wins}/${totalClosed})`
    : "100% (0/0)";

  const allTimeRealizedPnL = trades.reduce((acc, t) => acc + t.pnl, 0);

  const avgEfficiency =
    subAgents.length > 0
      ? subAgents.reduce((acc, agent) => acc + agent.efficiency, 0) / subAgents.length
      : 0;
  const avgAbsChange =
    tickers.length > 0
      ? tickers.reduce((acc, ticker) => acc + Math.abs(ticker.change), 0) / tickers.length
      : 0;
  const bullishPct =
    tickers.length > 0
      ? (tickers.filter((ticker) => ticker.change >= 0).length / tickers.length) * 100
      : 50;
  // Orchestrator score: agent efficiency + market stability (updates with 15s ticker poll).
  const orchestratorScore = Math.round(
    Math.max(0, Math.min(100, avgEfficiency * 0.65 + Math.max(0, 100 - avgAbsChange * 10) * 0.35)),
  );
  // Composite index: live breadth / sentiment from ticker changes.
  const compositeIndex = Math.round(Math.max(0, Math.min(100, bullishPct)));
  const sentimentLabel =
    bullishPct >= 55 ? `${bullishPct.toFixed(1)}% Bullish` : bullishPct <= 45 ? `${(100 - bullishPct).toFixed(1)}% Bearish` : `${bullishPct.toFixed(1)}% Mixed`;
  const anomalyLabel = avgAbsChange >= 8 ? (language === "de" ? "Volatilität hoch" : "High volatility") : t("noneDetected");
  const latencyLabel = queueLatencyMs !== null ? `${queueLatencyMs}ms` : "—";

  const agentsActive = subAgents.filter((a) => a.status === "ACTIVE").length;
  const agentsOptimizing = subAgents.filter((a) => a.status === "OPTIMIZING").length;
  const agentsAlert = subAgents.filter((a) => a.status === "ALERT").length;
  const rnaBlindSummary =
    subAgents.find((a) => a.id === "rna_smart")?.lastAction ??
    (language === "de" ? "Blind-Scan idle" : "Blind scan idle");

  const rnaPattern = useMemo(() => {
    const focus = tickers.find((t) => t.symbol === activeSymbol);
    const focusHist = (focus?.history ?? []).filter((n) => n > 0);
    const closes =
      focusHist.length >= 2 ? focusHist : focus && focus.price > 0 ? [focus.price] : [];
    if (closes.length < 2) return null;
    const blind = scanBlindPatterns(closesToBlindCandles(closes));
    if (blind.candleCount < 2 || blind.hits.length === 0) return null;
    const top = blind.hits[0];
    return { bias: top.bias, confidence: top.confidence };
  }, [tickers, activeSymbol]);

  useEffect(() => {
    if (!rnaPattern) return;
    void pushRnaContext({
      bias: rnaPattern.bias,
      confidence: rnaPattern.confidence,
      symbol: activeSymbol,
    }).catch(() => {
      // Signal routes may be disabled; RNA context is best-effort.
    });
  }, [rnaPattern, activeSymbol]);

  const osTelemetryRows = [
    {
      label: language === "de" ? "Markt" : "Market",
      value: marketLive
        ? `LIVE · ${marketSource ?? "stream"} · ${tickers.length} tkr`
        : language === "de"
          ? "STALE / kein Stream"
          : "STALE / no stream",
      tone: marketLive ? "text-emerald-400" : "text-amber-400",
    },
    {
      label: language === "de" ? "Orderbuch" : "Depth",
      value: orderBookOnline
        ? language === "de"
          ? "ONLINE"
          : "ONLINE"
        : language === "de"
          ? "OFFLINE"
          : "OFFLINE",
      tone: orderBookOnline ? "text-emerald-400" : "text-slate-500",
    },
    {
      label: "AI",
      value: aiStatusLabel,
      tone: aiStatusLabel.includes("OFFLINE") ? "text-rose-400" : "text-cyan-400",
    },
    {
      label: language === "de" ? "Ausführung" : "Exec",
      value: `${readyStatus?.execution ?? "unknown"} · L${readyStatus?.autonomy_level ?? "—"}`,
      tone: "text-slate-300",
    },
    {
      label: language === "de" ? "Agenten" : "Agents",
      value: `${agentsActive}/${subAgents.length} ACTIVE${agentsOptimizing ? ` · ${agentsOptimizing} OPT` : ""}${agentsAlert ? ` · ${agentsAlert} ALERT` : ""}`,
      tone: agentsAlert ? "text-rose-400" : agentsOptimizing ? "text-amber-400" : "text-emerald-400",
    },
    {
      label: language === "de" ? "Compliance" : "Compliance",
      value: isComplianceActive
        ? language === "de"
          ? "ON · Paper only"
          : "ON · paper only"
        : language === "de"
          ? "OFF"
          : "OFF",
      tone: isComplianceActive ? "text-rose-300" : "text-amber-400",
    },
  ] as const;
  const osFooter = activePlan
    ? language === "de"
      ? `Aktive Direktive: "${activePlan.planTitle}" · ${allocation.length} Allokations-Knoten · ${trades.length} Paper-Rows.`
      : `Active directive: "${activePlan.planTitle}" · ${allocation.length} alloc nodes · ${trades.length} paper rows.`
    : language === "de"
      ? `Kein Custom-Plan · Standard-Schwarm · RNA: ${rnaBlindSummary}`
      : `No custom plan · default swarm · RNA: ${rnaBlindSummary}`;

  // Clock tick
  useEffect(() => {
    const timer = setInterval(() => {
      setCurrentTime(new Date().toLocaleTimeString());
    }, 1000);
    return () => clearInterval(timer);
  }, []);

  // Phase 2: prefer WebSocket market stream; fall back to HTTP batch polling.
  useEffect(() => {
    let cancelled = false;
    let streamHealthy = false;
    let pollTimer: ReturnType<typeof setInterval> | null = null;

    const pollHttp = async () => {
      if (cancelled || streamHealthy) return;
      const started = performance.now();
      try {
        const {tickers: live, asOf} = await fetchCryptoTickers();
        if (cancelled || streamHealthy) return;
        setQueueLatencyMs(Math.round(performance.now() - started));
        if (live.length === 0) {
          setMarketLive(false);
          return;
        }
        setTickers((prev) => upsertTickerHistory(prev, live));
        setMarketAsOf(asOf);
        setMarketLive(true);
        setMarketSource("http-batch");
      } catch {
        if (!cancelled && !streamHealthy) {
          setMarketLive(false);
          setMarketSource(null);
          setQueueLatencyMs(Math.round(performance.now() - started));
        }
      }
    };

    const disconnect = connectMarketStream({
      onTickers: (live, asOf, source) => {
        if (cancelled) return;
        streamHealthy = true;
        setTickers((prev) => upsertTickerHistory(prev, live));
        setMarketAsOf(asOf);
        setMarketLive(true);
        setMarketSource(source || "websocket");
        setQueueLatencyMs(source.startsWith("ccxt") ? 5 : 15);
        if (pollTimer !== null) {
          clearInterval(pollTimer);
          pollTimer = null;
        }
      },
      onStatus: (status) => {
        if (cancelled) return;
        if (status === "open") {
          streamHealthy = true;
          return;
        }
        if (status === "closed" || status === "error") {
          streamHealthy = false;
          if (pollTimer === null) {
            void pollHttp();
            pollTimer = setInterval(() => void pollHttp(), 15000);
          }
        }
      },
    });

    // Immediate HTTP seed until the first WS snapshot arrives.
    void pollHttp();
    pollTimer = setInterval(() => void pollHttp(), 15000);

    return () => {
      cancelled = true;
      disconnect();
      if (pollTimer !== null) clearInterval(pollTimer);
    };
  }, []);

  // Probe order-book depth once market ticks are live (same Kraken public path).
  useEffect(() => {
    if (!marketLive) {
      setOrderBookOnline(false);
      return;
    }
    let cancelled = false;
    void fetchOrderBook("BTC", 5)
      .then((book) => {
        if (cancelled) return;
        setOrderBookOnline((book.bids?.length ?? 0) > 0 || (book.asks?.length ?? 0) > 0);
      })
      .catch(() => {
        if (!cancelled) setOrderBookOnline(false);
      });
    return () => {
      cancelled = true;
    };
  }, [marketLive]);

  // Keep sub-agent lastAction tied to live telemetry (not static roster copy).
  useEffect(() => {
    const source = marketSource ?? "market";
    const allocationNodes = allocation.length;
    const paperRows = trades.length;
    const execMode = readyStatus?.execution ?? "unknown";
    const autonomyLevel = readyStatus?.autonomy_level ?? "—";
    const liveTrading = readyStatus?.live_trading_enabled === true;
    const focus = tickers.find((t) => t.symbol === activeSymbol);
    const focusHist = (focus?.history ?? []).filter((n) => n > 0);
    const topMovers = [...tickers]
      .filter((t) => t.price > 0)
      .sort((a, b) => Math.abs(b.change) - Math.abs(a.change))
      .slice(0, 3)
      .map((t) => `${t.symbol} ${t.change >= 0 ? "+" : ""}${t.change.toFixed(1)}%`)
      .join(", ");
    const paperPnl = trades.reduce((sum, trade) => sum + (Number.isFinite(trade.pnl) ? trade.pnl : 0), 0);

    setSubAgents((prev) =>
      prev.map((agent) => {
        // Don't clobber in-flight plan injection / adaptive calibrate animations.
        if (agent.status === "OPTIMIZING") return agent;

        if (agent.id === "market_data") {
          if (!marketLive) {
            return {
              ...agent,
              lastAction:
                language === "de"
                  ? "Warte auf CCXT/WebSocket-Marktstream."
                  : "Waiting for CCXT/WebSocket market stream.",
            };
          }
          const depthEn = orderBookOnline
            ? " Order-book depth online."
            : " Probing order-book depth…";
          const depthDe = orderBookOnline
            ? " Orderbuch-Tiefe online."
            : " Orderbuch wird geprüft…";
          return {
            ...agent,
            status: agent.status === "STANDBY" ? "ACTIVE" : agent.status,
            lastAction:
              language === "de"
                ? `${tickers.length} Live-Ticker über ${source}.${depthDe}`
                : `Streaming ${tickers.length} live tickers via ${source}.${depthEn}`,
          };
        }

        if (agent.id === "orchestrator") {
          if (!marketLive && !activePlan) {
            return {
              ...agent,
              lastAction:
                language === "de"
                  ? "Warte auf Live-Markt und Allokations-Sync."
                  : "Awaiting live market + allocation sync.",
            };
          }

          if (activePlan) {
            return {
              ...agent,
              status: agent.status === "STANDBY" ? "ACTIVE" : agent.status,
              lastAction:
                language === "de"
                  ? `Plan "${activePlan.planTitle}" auf ${allocationNodes || "—"} Knoten · Markt ${marketLive ? "LIVE" : "STALE"} · ${aiStatusLabel} · ${paperRows} Paper-Rows · ${execMode}.`
                  : `Synced "${activePlan.planTitle}" across ${allocationNodes || "—"} nodes · market ${marketLive ? "LIVE" : "STALE"} · ${aiStatusLabel} · ${paperRows} paper rows · ${execMode}.`,
            };
          }

          return {
            ...agent,
            status: agent.status === "STANDBY" ? "ACTIVE" : agent.status,
            lastAction:
              language === "de"
                ? `Standard-Orchestrierung aktiv · ${tickers.length} Ticker via ${source}${orderBookOnline ? " · Orderbuch online" : ""} · ${aiStatusLabel} · ${paperRows} Paper-Rows.`
                : `Coordinating default swarm · ${tickers.length} tickers via ${source}${orderBookOnline ? " · order book online" : ""} · ${aiStatusLabel} · ${paperRows} paper rows.`,
          };
        }

        if (agent.id === "rna_smart") {
          // Blindfold: feed only relative candle geometry — never symbol / TF / absolute prices in output.
          const closes = focusHist.length >= 2 ? focusHist : focus && focus.price > 0 ? [focus.price] : [];
          const blind = scanBlindPatterns(closesToBlindCandles(closes));
          if (blind.candleCount < 2) {
            return {
              ...agent,
              lastAction:
                language === "de"
                  ? "Blind-Pattern-Scan idle — warte auf relative Kerzen-Geometrie (ohne Symbol/TF/Preis)."
                  : "Blind pattern scan idle — awaiting relative candle geometry (no symbol/TF/price).",
            };
          }
          const deSummary = blind.hits.length
            ? `Blind-Pattern-Scan · ${blind.hits
                .slice(0, 3)
                .map((h) => `${h.name} (${h.bias}, ${h.confidence}%)`)
                .join(" · ")} · kein Symbol/TF/Preis-Kontext.`
            : `Blind-Pattern-Scan · ${blind.candleCount} relative Kerzen · kein Katalog-Treffer (nur Geometrie).`;
          return {
            ...agent,
            status: "ACTIVE",
            lastAction: language === "de" ? deSummary : blind.summary,
          };
        }

        if (agent.id === "adaptive") {
          return {
            ...agent,
            status: marketLive ? "ACTIVE" : agent.status,
            lastAction:
              language === "de"
                ? marketLive
                  ? `Sizing-Korridor folgt Live-Tape (${source}) · Fokus ${activeSymbol}${focus ? ` Δ ${focus.change >= 0 ? "+" : ""}${focus.change.toFixed(2)}%` : ""}.`
                  : "Warte auf Live-Tape für Sizing-Neukalibrierung."
                : marketLive
                  ? `Sizing corridor tracking live tape (${source}) · focus ${activeSymbol}${focus ? ` Δ ${focus.change >= 0 ? "+" : ""}${focus.change.toFixed(2)}%` : ""}.`
                  : "Awaiting live tape for sizing recalibration.",
          };
        }

        if (agent.id === "risk_gov") {
          return {
            ...agent,
            status: "ACTIVE",
            lastAction:
              language === "de"
                ? `Compliance ${isComplianceActive ? "ON" : "OFF"} · Ausführung ${execMode} · Paper-Rows ${paperRows}.`
                : `Compliance guard ${isComplianceActive ? "ON" : "OFF"} · execution ${execMode} · ${paperRows} paper rows.`,
          };
        }

        if (agent.id === "kraken_broker") {
          const pending = trades.filter((t) => t.status === "PENDING").length;
          const completed = trades.filter((t) => t.status === "COMPLETED").length;
          const liveGate = liveTrading ? "LIVE GATE ON" : "PAPER ONLY";
          const liveGateDe = liveTrading ? "LIVE-GATE AN" : "NUR PAPER";
          return {
            ...agent,
            status: paperRows > 0 || execMode !== "unknown" ? "ACTIVE" : agent.status,
            lastAction:
              language === "de"
                ? `Kraken-Broker · ${execMode} · L${autonomyLevel} · ${liveGateDe} · ${completed} Fills / ${pending} pending · ${paperRows} Rows.`
                : `Kraken broker · ${execMode} · L${autonomyLevel} · ${liveGate} · ${completed} fills / ${pending} pending · ${paperRows} rows.`,
          };
        }

        if (agent.id === "predictive") {
          if (!marketLive || !topMovers) {
            return {
              ...agent,
              status: "STANDBY",
              lastAction:
                language === "de"
                  ? "Warte auf Live-Mover für Vektor-Refresh."
                  : "Awaiting live movers for vector refresh.",
            };
          }
          return {
            ...agent,
            status: "ACTIVE",
            lastAction:
              language === "de"
                ? `Top-Mover: ${topMovers} · Fokus ${activeSymbol}/USD.`
                : `Top movers: ${topMovers} · focus ${activeSymbol}/USD.`,
          };
        }

        if (agent.id === "analytic") {
          return {
            ...agent,
            status: paperRows > 0 ? "ACTIVE" : agent.status,
            lastAction:
              language === "de"
                ? paperRows > 0
                  ? `Paper-Ledger ${paperRows} Rows · Σ PnL ${paperPnl.toFixed(2)} · ${aiStatusLabel}.`
                  : "Warte auf Paper-Ledger-Rows für Analyse."
                : paperRows > 0
                  ? `Paper ledger ${paperRows} rows · Σ PnL ${paperPnl.toFixed(2)} · ${aiStatusLabel}.`
                  : "Awaiting paper ledger rows for analysis.",
          };
        }

        return agent;
      }),
    );
  }, [
    marketLive,
    marketSource,
    orderBookOnline,
    tickers,
    language,
    activePlan,
    allocation.length,
    trades,
    aiStatusLabel,
    readyStatus?.execution,
    readyStatus?.autonomy_level,
    readyStatus?.live_trading_enabled,
    activeSymbol,
    isComplianceActive,
  ]);

  // Alpha Vantage equity batch for risk heatmap — once per hour (rate-limit friendly).
  useEffect(() => {
    let cancelled = false;
    const refreshEquities = async () => {
      try {
        const {tickers: equities, asOf} = await fetchEquityTickers(["NIO"]);
        if (cancelled || equities.length === 0) return;
        setTickers((prev) => upsertTickerHistory(prev, equities));
        setMarketAsOf(asOf);
      } catch {
        // Keep crypto live state; equities stay at last known price.
      }
    };
    void refreshEquities();
    const timer = setInterval(() => void refreshEquities(), 60 * 60 * 1000);
    return () => {
      cancelled = true;
      clearInterval(timer);
    };
  }, []);

  // Paper ledger + AI health + ready status
  const refreshPaperTrades = useCallback(async () => {
    try {
      const paper = await fetchPaperStatus();
      const mapped = mapPaperStatusToTrades(paper.data);
      if (mapped.length > 0) setTrades(mapped);
    } catch {
      // Auth may be missing; keep existing rows.
    }
  }, []);

  useEffect(() => {
    let cancelled = false;
    const refresh = async () => {
      try {
        const health = await fetchAiHealth();
        if (!cancelled) {
          setAiStatusLabel(
            health.configured
              ? `AI: ${String(health.provider).toUpperCase()}`
              : health.deterministic_fallback
                ? "AI: FALLBACK"
                : "AI: OFFLINE",
          );
        }
      } catch {
        if (!cancelled) setAiStatusLabel("AI: OFFLINE");
      }
      try {
        const ready = await fetchReadyStatus();
        if (!cancelled) setReadyStatus(ready);
      } catch {
        if (!cancelled) setReadyStatus(null);
      }
      if (!cancelled) await refreshPaperTrades();
    };
    void refresh();
    const timer = setInterval(() => void refresh(), 20000);
    return () => {
      cancelled = true;
      clearInterval(timer);
    };
  }, [refreshPaperTrades]);

  // Clear trade announcement after 4 seconds
  useEffect(() => {
    if (announcement) {
      const timer = setTimeout(() => {
        setAnnouncement(null);
      }, 4000);
      return () => clearTimeout(timer);
    }
  }, [announcement]);

  // A paper order is recorded as pending until a real backend execution result
  // supplies fills and realized P&L. The client never invents a win/loss.
  const handleExecuteTrade = (newTradeData: Omit<Trade, "id" | "time" | "pnl" | "status">) => {
    void refreshPaperTrades();
    setSubAgents((prev) =>
      prev.map((agent) =>
        agent.id === "kraken_broker"
          ? {
              ...agent,
              status: "OPTIMIZING",
              lastAction:
                language === "de"
                  ? `Kraken-Broker · Paper-Order ${newTradeData.type} ${newTradeData.asset} @ ${newTradeData.price} eingereiht.`
                  : `Kraken broker · queued paper ${newTradeData.type} ${newTradeData.asset} @ ${newTradeData.price}.`,
            }
          : agent,
      ),
    );
  };

  const agentStatusPackets = (): AgentStatusPacket[] =>
    subAgents.map((agent) => ({
      id: agent.id,
      status: agent.status,
      lastAction: (agent.lastAction || "").slice(0, 200),
      directive: (agent.directive || "").slice(0, 280),
    }));

  // Handle Deployment of Gemini-Generated Trading Plan
  const handleDeployPlan = (plan: GenerativePlan) => {
    setActivePlan(plan);
    if (plan.resourceAllocation) {
      setAllocation(plan.resourceAllocation);
    }

    // Update active sub-agent directives based on Gemini results!
    const dirs = plan.subAgentDirectives;
    setSubAgents((prevAgents) =>
      prevAgents.map((agent) => {
        let directive = agent.directive;
        if (agent.id === "market_data") directive = dirs.marketData;
        if (agent.id === "adaptive") directive = dirs.adaptiveAgent;
        if (agent.id === "rna_smart") directive = dirs.rnaSmartelligent;
        if (agent.id === "risk_gov") directive = dirs.riskGovernor;
        if (agent.id === "kraken_broker" && dirs.krakenBroker) directive = dirs.krakenBroker;
        if (agent.id === "predictive" && dirs.predictive) directive = dirs.predictive;
        if (agent.id === "analytic" && dirs.analytic) directive = dirs.analytic;
        if (agent.id === "orchestrator" && dirs.orchestrator) directive = dirs.orchestrator;

        return {
          ...agent,
          directive,
          status: "OPTIMIZING",
          lastAction: `Orchestrator injected fresh tactical parameters. Re-optimizing...`
        };
      })
    );

    // Turn standby sub-agents back to active for maximum execution!
    setTimeout(() => {
      setSubAgents((prev) =>
        prev.map((a) => ({
          ...a,
          status: a.status === "OPTIMIZING" ? "ACTIVE" : a.status
        }))
      );
    }, 4000);

    // External notifications are intentionally not synthesized here. They must
    // be implemented as an authenticated backend capability with delivery status.
  };

  const handleUpdateAgentStatus = (id: string, status: SubAgentState["status"]) => {
    setSubAgents((prev) =>
      prev.map((agent) => (agent.id === id ? { ...agent, status } : agent))
    );
  };

  const handleOptimizeThresholds = (multiplier: number) => {
    // update adaptive agent status to optimizing and then active
    setSubAgents((prev) =>
      prev.map((agent) => {
        if (agent.id === "adaptive") {
          return {
            ...agent,
            status: "OPTIMIZING",
            lastAction: `Multiplier manually modified to ${multiplier.toFixed(2)}x. Calibrating corridors...`
          };
        }
        return agent;
      })
    );

    setTimeout(() => {
      setSubAgents((prev) =>
        prev.map((agent) => {
          if (agent.id === "adaptive") {
            return {
              ...agent,
              status: "ACTIVE",
              lastAction: `Recalibration complete. Volatility parameters locked at ${multiplier.toFixed(2)}x.`
            };
          }
          return agent;
        })
      );
    }, 2000);
  };

  // Construct cumulative equity data for Recharts
  const chartData = trades.reduce((acc, trade) => {
    const lastVal = acc.length > 0 ? acc[acc.length - 1].pnl : 0;
    acc.push({
      time: trade.time,
      pnl: Number((lastVal + trade.pnl).toFixed(2)),
      volume: Number((trade.amount * trade.price * 0.045).toFixed(2)),
    });
    return acc;
  }, [] as { time: string; pnl: number; volume: number }[]);

  return (
    <div className="min-h-screen bg-[#050608] text-slate-200 font-sans cyber-grid-blue flex flex-col justify-between selection:bg-cyan-500/30 selection:text-cyan-200 relative overflow-x-hidden">
      {/* Dynamic Heroes of Newerth Announcer Overlay */}
      <AnimatePresence>
        {announcement && (
          <motion.div
            initial={{ opacity: 0, y: -100, scale: 0.9, x: "-50%" }}
            animate={{ opacity: 1, y: 0, scale: 1, x: "-50%" }}
            exit={{ opacity: 0, y: -60, scale: 0.95, x: "-50%" }}
            transition={{ type: "spring", stiffness: 140, damping: 15 }}
            className="fixed top-8 left-1/2 z-50 w-full max-w-md px-4"
          >
            <div className={`relative overflow-hidden rounded-xl border p-4 shadow-[0_0_40px_rgba(0,0,0,0.85)] backdrop-blur-lg ${
              announcement.type === "kill" 
                ? "bg-rose-950/90 border-rose-500/50 shadow-rose-950/50" 
                : announcement.type === "death"
                ? "bg-purple-950/90 border-purple-500/50 shadow-purple-950/50"
                : announcement.type === "humiliation"
                ? "bg-amber-950/90 border-amber-500/50 shadow-amber-950/50"
                : announcement.type === "nemesis"
                ? "bg-red-950/95 border-red-500/60 shadow-red-950/60"
                : announcement.type === "immortal"
                ? "bg-slate-950/95 border-teal-400/60 shadow-teal-950/80 border-2"
                : "bg-slate-900/95 border-cyan-500/50 shadow-cyan-950/50"
            }`}>
              {/* Stylized corner markers */}
              <div className="absolute top-0 left-0 w-2.5 h-2.5 border-t-2 border-l-2 border-white/30" />
              <div className="absolute top-0 right-0 w-2.5 h-2.5 border-t-2 border-r-2 border-white/30" />
              <div className="absolute bottom-0 left-0 w-2.5 h-2.5 border-b-2 border-l-2 border-white/30" />
              <div className="absolute bottom-0 right-0 w-2.5 h-2.5 border-b-2 border-r-2 border-white/30" />

              <div className="flex items-center gap-4 relative z-10">
                {/* Visual Icon Badge */}
                <div className={`w-12 h-12 rounded-full border-2 flex items-center justify-center shrink-0 text-2xl shadow-[inset_0_0_15px_rgba(0,0,0,0.6)] ${
                  announcement.type === "kill"
                    ? "bg-rose-500/20 border-rose-400 text-rose-400 animate-pulse"
                    : announcement.type === "death"
                    ? "bg-purple-500/20 border-purple-400 text-purple-400"
                    : announcement.type === "humiliation"
                    ? "bg-amber-500/20 border-amber-400 text-amber-400 animate-bounce"
                    : announcement.type === "nemesis"
                    ? "bg-red-500/20 border-red-500 text-red-500 animate-pulse"
                    : announcement.type === "immortal"
                    ? "bg-teal-500/25 border-teal-300 text-teal-300 animate-pulse"
                    : "bg-cyan-500/20 border-cyan-400 text-cyan-400"
                }`}>
                  {announcement.type === "kill" 
                    ? "⚔️" 
                    : announcement.type === "death" 
                    ? "💀" 
                    : announcement.type === "humiliation"
                    ? "🤡"
                    : announcement.type === "nemesis"
                    ? "👹"
                    : announcement.type === "immortal"
                    ? "👑"
                    : "🤝"}
                </div>

                {/* Notification Text details */}
                <div className="flex-1 min-w-0">
                  <div className="flex items-center justify-between gap-2">
                    <span className={`text-[9px] font-mono tracking-widest uppercase font-extrabold ${
                      announcement.type === "kill"
                        ? "text-rose-400"
                        : announcement.type === "death"
                        ? "text-purple-300"
                        : announcement.type === "humiliation"
                        ? "text-amber-400"
                        : announcement.type === "nemesis"
                        ? "text-red-400"
                        : announcement.type === "immortal"
                        ? "text-teal-300"
                        : "text-cyan-400"
                    }`}>
                      {announcement.type === "kill" 
                        ? `TRADE WON // KILL (STREAK: ${streak.wins})` 
                        : announcement.type === "death"
                        ? `TRADE LOST // DEATH (STREAK: ${streak.losses})`
                        : announcement.type === "humiliation"
                        ? "HUMILIATION // INSTANT BACKFIRE!"
                        : announcement.type === "nemesis"
                        ? "NEMESIS // TRIPLE SYMBOL LOSS!"
                        : announcement.type === "immortal"
                        ? "WOLF OF WALL STREET // IMMORTAL!"
                        : "TRADE BREAKEVEN // ASSIST"}
                    </span>
                    <span className={`text-[8px] font-mono font-bold px-1.5 py-0.5 rounded border uppercase shrink-0 ${
                      announcement.type === "kill"
                        ? "bg-emerald-500/15 border-emerald-500/30 text-emerald-400"
                        : announcement.type === "death"
                        ? "bg-rose-500/15 border-rose-500/30 text-rose-400"
                        : announcement.type === "humiliation"
                        ? "bg-amber-500/15 border-amber-500/30 text-amber-400"
                        : announcement.type === "nemesis"
                        ? "bg-red-500/15 border-red-500/30 text-red-400"
                        : announcement.type === "immortal"
                        ? "bg-teal-500/20 border-teal-400/40 text-teal-300"
                        : "bg-cyan-500/15 border-cyan-500/30 text-cyan-400"
                    }`}>
                      {announcement.type === "kill" 
                        ? "won" 
                        : announcement.type === "death" 
                        ? "loss" 
                        : announcement.type === "humiliation"
                        ? "backfired"
                        : announcement.type === "nemesis"
                        ? "nemesis"
                        : announcement.type === "immortal"
                        ? "immortal"
                        : "breakeven"}
                    </span>
                  </div>

                  {/* HoN Announcer text line */}
                  <h2 className="text-xl font-black tracking-tighter text-white uppercase mt-1 select-none font-sans drop-shadow-[0_2px_5px_rgba(0,0,0,0.9)]">
                    {announcement.text}
                  </h2>
                </div>
              </div>

              {/* Progress visual line */}
              <div className="absolute bottom-0 left-0 right-0 h-1 bg-white/5">
                <motion.div 
                  initial={{ width: "100%" }}
                  animate={{ width: "0%" }}
                  transition={{ duration: 4, ease: "linear" }}
                  className={`h-full ${
                    announcement.type === "kill"
                      ? "bg-rose-500"
                      : announcement.type === "death"
                      ? "bg-purple-500"
                      : announcement.type === "humiliation"
                      ? "bg-amber-500"
                      : announcement.type === "nemesis"
                      ? "bg-red-500"
                      : announcement.type === "immortal"
                      ? "bg-teal-400"
                      : "bg-cyan-500"
                  }`}
                />
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      <div className="flex-1 p-4 lg:p-6 space-y-6 max-w-[1700px] mx-auto w-full">
        
        {/* Header - Styled precisely like FABLE 5 MASTERPROMPT OS V3.0 (Bento Grid Theme) */}
        <header className="flex flex-col lg:flex-row lg:items-center justify-between gap-4 border-b border-white/10 pb-4 mb-6">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 bg-cyan-500 rounded-sm flex items-center justify-center shadow-[0_0_15px_rgba(6,182,212,0.4)]">
              <span className="text-black font-black text-xl">Ω</span>
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h1 className="text-xl lg:text-2xl font-black tracking-tighter text-white uppercase">
                  FABLE 5 MASTERPROMPT OS
                </h1>
                <span className="bg-cyan-500/10 border border-cyan-500/30 text-cyan-400 px-2 py-0.5 rounded text-[9px] font-mono tracking-wider">
                  V3.0 DEPLOYED
                </span>
              </div>
              <p className="text-[10px] text-cyan-400 font-mono tracking-widest uppercase">
                Alpaca Table 5 Agent OS // RNA Smartelligent Protocol
              </p>
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-6 font-mono text-[11px]">
            <div className="flex flex-col lg:items-end">
              <span className="text-slate-500 uppercase tracking-wider text-[9px]">{t("systemTime")}</span>
              <span className="text-white font-bold">{currentTime}</span>
            </div>
            <div className="hidden sm:flex flex-col lg:items-end">
              <span className="text-slate-500 uppercase tracking-wider text-[9px]">{t("systemStatus")}</span>
              <span className={`font-bold flex items-center gap-1 ${aiStatusLabel.includes("OFFLINE") ? "text-amber-400" : "text-emerald-400"}`}>
                <span className={`w-1.5 h-1.5 rounded-full ${aiStatusLabel.includes("OFFLINE") ? "bg-amber-400" : "bg-emerald-400 animate-pulse"}`}></span>
                {aiStatusLabel}
              </span>
            </div>
            <div className="flex flex-col lg:items-end">
              <span className="text-slate-500 uppercase tracking-wider text-[9px]">{t("complianceRig")}</span>
              <span className={`font-bold ${isComplianceActive ? "text-rose-400" : "text-amber-400"}`}>
                {isComplianceActive ? t("enforced") : t("unguarded")}
              </span>
            </div>

            <TradingLoopSwitches language={language} />
            
            {/* All-Time Realized P&L Widget */}
            <div id="all-time-pnl-widget" className="flex flex-col lg:items-end bg-white/5 border border-white/10 px-3 py-1 rounded-sm shadow-[0_0_15px_rgba(0,0,0,0.4)] min-w-[125px] transition-all hover:border-white/20">
              <span className="text-slate-500 uppercase tracking-wider text-[8px] font-bold font-mono">
                All-Time Realized P&L
              </span>
              <span className={`font-bold font-mono text-[13px] flex items-center gap-1.5 ${
                allTimeRealizedPnL >= 0 ? "text-emerald-400" : "text-rose-500"
              }`}>
                <span className={`w-1.5 h-1.5 rounded-full ${
                  allTimeRealizedPnL >= 0 ? "bg-emerald-400 animate-pulse shadow-[0_0_8px_#10b981]" : "bg-rose-500 animate-pulse shadow-[0_0_8px_#f43f5e]"
                }`}></span>
                {allTimeRealizedPnL >= 0 ? "+" : ""}${allTimeRealizedPnL.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
              </span>
            </div>
            <span className="px-4 py-2 bg-rose-500/10 border border-rose-500/20 text-rose-300 uppercase text-[10px] font-bold tracking-widest rounded-sm">
              Backend safety policy enforced
            </span>
            <div className="shrink-0 text-left normal-case tracking-normal">
              <AuthPanel compact />
            </div>
            <button
              onClick={() => setIsSettingsOpen(true)}
              className="p-2 bg-white/5 border border-white/10 hover:bg-cyan-500/10 hover:border-cyan-500/30 text-cyan-400 transition-all cursor-pointer rounded-sm flex items-center gap-1.5"
              title={language === "de" ? "Einstellungen öffnen" : "Open Settings"}
            >
              <Settings className="w-3.5 h-3.5" />
              <span className="uppercase text-[10px] font-bold tracking-widest">
                {language === "de" ? "Einstellungen" : "Settings"}
              </span>
            </button>
          </div>
        </header>

        {/* Interactive Workspace Navigation Menu */}
        <NavigationMenu 
          activeTab={activeTab} 
          setActiveTab={setActiveTab} 
          isComplianceActive={isComplianceActive}
          activeSymbol={activeSymbol}
          winLossRatio={winLossRatio}
          executedCount={trades.length}
          language={language}
        />

        {/* Dynamic Workspace Container */}
        <AnimatePresence mode="wait">
          <motion.div
            key={activeTab}
            initial={{ opacity: 0, y: 15 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -15 }}
            transition={{ duration: 0.22, ease: "easeInOut" }}
            className="space-y-6"
          >
            {/* WORKSPACE A: OMNI-DASHBOARD */}
            {activeTab === "dashboard" && (
              <>
                <CommandOverview
                  language={language}
                  onNavigate={(tab) => setActiveTab(tab)}
                />
                {/* Master Control and Signal Dial Row - Bento Styled */}
                <div className="grid grid-cols-1 xl:grid-cols-3 gap-6 font-mono text-xs">
                  {/* Master Orchestrator Agent Panel */}
                  <div className="bg-slate-900/40 border border-white/5 rounded-xl p-5 glow-emerald flex flex-col justify-between h-56 relative overflow-hidden transition-all duration-300 hover:border-white/10 hover:bg-slate-900/60">
                    <div className="space-y-3">
                      <div className="flex items-center justify-between border-b border-white/10 pb-2">
                        <span className="text-emerald-400 font-bold uppercase tracking-wider text-[11px]">
                          {t("masterOrchestrator")}
                        </span>
                        <span className="text-[9px] text-emerald-500/70 border border-emerald-500/30 px-1.5 py-0.5 rounded">
                          {language === "de" ? "OS REGLER" : "OS CONTROLLER"}
                        </span>
                      </div>
                      <p className="text-[10px] text-slate-400 leading-relaxed">
                        {t("masterOrchestratorDesc")}
                      </p>
                    </div>

                    {/* Circular Gauge Meter */}
                    <div className="flex items-center justify-between mt-3">
                      <CircularGauge
                        score={orchestratorScore}
                        label={t("score")}
                        stroke="#10b981"
                        textClass="text-emerald-400"
                      />

                      <div className="flex-1 space-y-1 pl-4 text-[10px]">
                        <div className="flex justify-between border-b border-white/5 pb-0.5">
                          <span className="text-slate-500">{t("activeDirectives")}:</span>
                          <span className="text-emerald-400 font-semibold">{activePlan ? (language === "de" ? "Eigene" : "Custom") : (language === "de" ? "Standard" : "Standard")}</span>
                        </div>
                        <div className="flex justify-between border-b border-white/5 pb-0.5">
                          <span className="text-slate-500">{t("queueLatency")}:</span>
                          <span className="text-slate-300 font-semibold">{latencyLabel}</span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-slate-500">{t("safetyCompliance")}:</span>
                          <span className={`font-semibold ${isComplianceActive ? "text-emerald-400" : "text-rose-400"}`}>
                            {isComplianceActive ? (language === "de" ? "Aktiv" : "Active") : t("hardOverride")}
                          </span>
                        </div>
                      </div>
                    </div>
                  </div>

                  {/* Fable 5 Master Console Panel */}
                  <div className="bg-slate-900/40 border border-white/5 rounded-xl p-5 glow-cyan flex flex-col justify-between h-56 relative overflow-hidden transition-all duration-300 hover:border-white/10 hover:bg-slate-900/60">
                    <div className="space-y-3">
                      <div className="flex items-center justify-between border-b border-white/10 pb-2">
                        <span className="text-cyan-400 font-bold uppercase tracking-wider text-[11px]">
                          {t("fableConsole")}
                        </span>
                        <span className="text-[9px] text-cyan-500/70 border border-cyan-500/30 px-1.5 py-0.5 rounded">
                          {language === "de" ? "KOMPOSIT-SPEICHER" : "COMPOSITE STORES"}
                        </span>
                      </div>
                      <p className="text-[10px] text-slate-400 leading-relaxed">
                        {t("fableConsoleDesc")}
                      </p>
                    </div>

                    {/* Composite signal meter */}
                    <div className="flex items-center justify-between mt-3">
                      <CircularGauge
                        score={compositeIndex}
                        label={t("index")}
                        stroke="#06b6d4"
                        textClass="text-cyan-400"
                      />

                      <div className="flex-1 space-y-1 pl-4 text-[10px]">
                        <div className="flex justify-between border-b border-white/5 pb-0.5">
                          <span className="text-slate-500">{t("sentimentWeight")}:</span>
                          <span className="text-cyan-400 font-semibold">{sentimentLabel}</span>
                        </div>
                        <div className="flex justify-between border-b border-white/5 pb-0.5">
                          <span className="text-slate-500">{t("signalAnomaly")}:</span>
                          <span className="text-slate-300 font-semibold">{anomalyLabel}</span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-slate-500">{t("telemetryFeed")}:</span>
                          <span className={`font-semibold uppercase flex items-center gap-1 ${marketLive ? "text-emerald-400" : "text-amber-400"}`}>
                            <span className={`w-1.5 h-1.5 rounded-full ${marketLive ? "bg-emerald-400 animate-ping" : "bg-amber-400"}`}></span>
                            {marketLive ? t("active") : (language === "de" ? "Cache" : "Cached")}
                          </span>
                        </div>
                      </div>
                    </div>
                  </div>

                  {/* OS telemetry — live backend/agent state, not marketing copy */}
                  <div className="bg-slate-900/40 border border-white/5 rounded-xl p-5 glow-rose flex flex-col justify-between h-56 transition-all duration-300 hover:border-white/10 hover:bg-slate-900/60">
                    <div className="space-y-2.5 min-h-0">
                      <div className="flex items-center justify-between border-b border-white/10 pb-2">
                        <span className="text-purple-400 font-bold uppercase tracking-wider text-[11px]">
                          {t("systemOverview")}
                        </span>
                        <span className="text-[9px] text-purple-500/70 border border-purple-500/30 px-1.5 py-0.5 rounded">
                          {language === "de" ? "OS TELEMETRIE" : "OS TELEMETRY"}
                        </span>
                      </div>
                      <div className="space-y-1 text-[9px] font-mono overflow-y-auto max-h-[7.5rem] pr-1">
                        {osTelemetryRows.map((row) => (
                          <div key={row.label} className="flex justify-between gap-2 border-b border-white/5 pb-0.5">
                            <span className="text-slate-500 uppercase shrink-0">{row.label}</span>
                            <span className={`text-right truncate ${row.tone}`}>{row.value}</span>
                          </div>
                        ))}
                      </div>
                    </div>

                    <div className="pt-2 bg-slate-950/40 border border-white/5 p-2.5 rounded-lg text-[9px] text-slate-300 flex items-start gap-2">
                      <Sparkles className={`w-4 h-4 text-purple-400 shrink-0 mt-0.5 ${activePlan || agentsOptimizing ? "animate-pulse" : ""}`} />
                      <span className="leading-relaxed line-clamp-3">{osFooter}</span>
                    </div>
                  </div>
                </div>

                {/* SubAgentsSection Overview */}
                <SubAgentsSection 
                  agents={subAgents}
                  trades={trades}
                  onUpdateAgentStatus={handleUpdateAgentStatus}
                  onOptimizeThresholds={handleOptimizeThresholds}
                  isComplianceActive={isComplianceActive}
                  onToggleCompliance={() => {
                    setIsComplianceActive(!isComplianceActive);
                    setSubAgents(prev => prev.map(a => a.id === "risk_gov" ? { ...a, lastAction: `Manually toggled safe override compliance rig to ${!isComplianceActive ? "ON" : "OFF"}.` } : a));
                  }}
                  language={language}
                />

                {/* Simulated Quick Trading Sandbox */}
                <SimulatedTrading 
                  tickers={tickers}
                  onExecuteTrade={handleExecuteTrade}
                  onPaperRefresh={refreshPaperTrades}
                  isComplianceActive={isComplianceActive}
                  tradingExchange={tradingExchange}
                />

                {/* Ledger & Live Feeds */}
                <div className="grid grid-cols-1 xl:grid-cols-3 gap-6">
                  <div className="xl:col-span-2">
                    <ExecutedTradesSection trades={trades} chartData={chartData} />
                  </div>
                  <div>
                    <TelegramFeed 
                      onSignalAction={(prompt) => {
                        setActiveTab("strategy");
                        setTimeout(() => {
                          const el = document.getElementById("generative-goal-planning-card");
                          if (el) el.scrollIntoView({ behavior: "smooth" });
                        }, 300);
                        handleDeployPlan({
                          planTitle: "AI Signal Ingestion Blueprint",
                          summary: `Orchestrating adaptive strategy optimized for alert directive: "${prompt}".`,
                          subAgentDirectives: {
                            marketData: `Scan volume corridors for confirmation matching the Telegram signal.`,
                            adaptiveAgent: `Elevate multipliers if token momentum vectors match sentiment spikes.`,
                            rnaSmartelligent: `Audit fractal pattern integrity to reject noise and bypass fake traps.`,
                            riskGovernor: `Enforce a strict trailing drawdown constraint at 2.0% maximum allocation.`
                          },
                          resourceAllocation: [
                            { name: "BTC", value: 30 },
                            { name: "ETH", value: 25 },
                            { name: "SOL", value: 30 },
                            { name: "MATIC", value: 15 }
                          ],
                          suggestedRules: [
                            "Verify signal authenticity across dual aggregated Telegram streams",
                            "Suspend long positions instantly if composite signal score collapses below +40",
                            "Scale execution volume dynamically with respect to active support walls"
                          ]
                        });
                      }}
                      onSimulateTradeSignal={(asset, type) => {
                        const ticker = tickers.find(t => t.symbol === asset);
                        const price = ticker ? ticker.price : 100;
                        const size = asset === "BTC" ? 0.25 : asset === "ETH" ? 2.5 : 25;
                        handleExecuteTrade({ asset, type, price, amount: size });
                      }}
                    />
                  </div>
                </div>
              </>
            )}

            {/* WORKSPACE B: TRADING TERMINAL */}
            {activeTab === "terminal" && (
              <>
                <IntegratedConnectors 
                  tradingExchange={tradingExchange}
                  setTradingExchange={setTradingExchange}
                />

                <LiveMarketHeatmap 
                  tickers={tickers} 
                  onSelectTicker={(symbol) => {
                    setActiveSymbol(symbol);
                    setSubAgents(prev => prev.map(a => a.id === "market_data" ? { ...a, lastAction: `Incepted index focus update for ${symbol}/USD tickers.` } : a));
                  }}
                  activeSymbol={activeSymbol}
                  marketLive={marketLive}
                />

                <OrderbookHeatmap3D
                  pair={
                    activeSymbol === "ADA" || activeSymbol === "XRP"
                      ? `${activeSymbol}USD`
                      : "ADAUSD"
                  }
                  language={language}
                />

                <SimulatedTrading 
                  tickers={tickers}
                  onExecuteTrade={handleExecuteTrade}
                  onPaperRefresh={refreshPaperTrades}
                  isComplianceActive={isComplianceActive}
                  tradingExchange={tradingExchange}
                />

                <div className="grid grid-cols-1 xl:grid-cols-3 gap-6">
                  <div className="xl:col-span-2">
                    <ExecutedTradesSection trades={trades} chartData={chartData} />
                  </div>
                  <div>
                    <TelegramFeed 
                      onSignalAction={(prompt) => {
                        setActiveTab("strategy");
                        setTimeout(() => {
                          const el = document.getElementById("generative-goal-planning-card");
                          if (el) el.scrollIntoView({ behavior: "smooth" });
                        }, 300);
                        handleDeployPlan({
                          planTitle: "AI Signal Ingestion Blueprint",
                          summary: `Orchestrating adaptive strategy optimized for alert directive: "${prompt}".`,
                          subAgentDirectives: {
                            marketData: `Scan volume corridors for confirmation matching the Telegram signal.`,
                            adaptiveAgent: `Elevate multipliers if token momentum vectors match sentiment spikes.`,
                            rnaSmartelligent: `Audit fractal pattern integrity to reject noise and bypass fake traps.`,
                            riskGovernor: `Enforce a strict trailing drawdown constraint at 2.0% maximum allocation.`
                          },
                          resourceAllocation: [
                            { name: "BTC", value: 30 },
                            { name: "ETH", value: 25 },
                            { name: "SOL", value: 30 },
                            { name: "MATIC", value: 15 }
                          ],
                          suggestedRules: [
                            "Verify signal authenticity across dual aggregated Telegram streams",
                            "Suspend long positions instantly if composite signal score collapses below +40",
                            "Scale execution volume dynamically with respect to active support walls"
                          ]
                        });
                      }}
                      onSimulateTradeSignal={(asset, type) => {
                        const ticker = tickers.find(t => t.symbol === asset);
                        const price = ticker ? ticker.price : 100;
                        const size = asset === "BTC" ? 0.25 : asset === "ETH" ? 2.5 : 25;
                        handleExecuteTrade({ asset, type, price, amount: size });
                      }}
                    />
                  </div>
                </div>
              </>
            )}

            {/* WORKSPACE C: AI STRATEGY STUDIO */}
            {activeTab === "strategy" && (
              <>
                <ResourceAllocation 
                  allocation={allocation}
                  activePlan={activePlan}
                  onDeployPlan={handleDeployPlan}
                  agentStatusPackets={agentStatusPackets()}
                />

                {/* Sub-workspace selector */}
                <div className="flex flex-col sm:flex-row items-stretch sm:items-center justify-between bg-slate-950/60 border border-white/5 rounded-xl p-2 gap-2 mb-6">
                  <div className="flex flex-wrap gap-2">
                    <button
                      onClick={() => setStrategySubTab("optimizer")}
                      className={`px-4 py-2 rounded-lg text-xs font-bold font-mono transition-all flex items-center gap-1.5 cursor-pointer ${
                        strategySubTab === "optimizer" 
                          ? "bg-purple-500/15 border border-purple-500/25 text-purple-400 shadow-[0_0_12px_rgba(168,85,247,0.15)]" 
                          : "bg-transparent border border-transparent text-slate-400 hover:text-slate-200"
                      }`}
                    >
                      <Sparkles className="w-3.5 h-3.5" />
                      PINE OPTIMIZER SWEEP
                    </button>
                    <button
                      onClick={() => setStrategySubTab("vector")}
                      className={`px-4 py-2 rounded-lg text-xs font-bold font-mono transition-all flex items-center gap-1.5 cursor-pointer ${
                        strategySubTab === "vector" 
                          ? "bg-cyan-500/15 border border-cyan-500/25 text-cyan-400 shadow-[0_0_12px_rgba(6,182,212,0.15)]" 
                          : "bg-transparent border border-transparent text-slate-400 hover:text-slate-200"
                      }`}
                    >
                      <Layers className="w-3.5 h-3.5 animate-pulse" />
                      NEURAL VECTOR DATABASE
                    </button>
                  </div>
                  <span className="text-[9px] text-slate-500 font-mono px-2 uppercase tracking-widest">
                    Telemetry: Vector Core Enabled
                  </span>
                </div>

                {strategySubTab === "optimizer" ? (
                  <div className="grid grid-cols-1 xl:grid-cols-3 gap-6">
                    <div className="xl:col-span-2">
                      <TvapiOptimizer activeSymbol={activeSymbol} />
                    </div>
                    <div className="space-y-6">
                      <GeminiChatbot agentStatusPackets={agentStatusPackets()} />
                      <button
                        type="button"
                        onClick={() => setActiveTab("onnx")}
                        className="w-full text-left bg-slate-900/50 border border-lime-500/20 hover:border-lime-400/40 rounded-xl p-4 font-mono transition-colors cursor-pointer"
                      >
                        <div className="text-[10px] uppercase tracking-widest text-lime-400 font-bold">
                          {language === "de" ? "ONNX-Neuronales Kernmodul" : "ONNX Neural Core"}
                        </div>
                        <p className="text-[11px] text-slate-400 mt-2 leading-relaxed">
                          {language === "de"
                            ? "LSTM-Inferenz, Training und Netron-Graph sind in Tab 7 ausgelagert."
                            : "LSTM inference, training, and Netron graph live in dedicated Tab 7."}
                        </p>
                        <span className="inline-block mt-3 text-[10px] text-lime-300 font-bold">
                          {language === "de" ? "Tab 7 öffnen →" : "Open Tab 7 →"}
                        </span>
                      </button>
                    </div>
                  </div>
                ) : (
                  <NeuralVectorAnalyzer />
                )}
              </>
            )}

            {activeTab === "paper" && <PaperPerformancePage language={language} />}

            {activeTab === "positions" && <PositionsPage language={language} />}

            {activeTab === "onnx" && (
              <OnnxPage
                currentPrice={tickers.find((t) => t.symbol === activeSymbol)?.price ?? 64250}
                activeSymbol={activeSymbol}
                marketLive={marketLive}
                language={language}
              />
            )}

            {activeTab === "chronos" && (
              <ChronosPage
                activeSymbol={activeSymbol}
                language={language}
                marketLive={marketLive}
                subAgents={subAgents}
                onUpdateAgentStatus={handleUpdateAgentStatus}
                rnaPattern={rnaPattern}
              />
            )}

            {activeTab === "agency" && <AgencyPage language={language} />}

            {/* WORKSPACE D: SWARM GOVERNANCE */}
            {activeTab === "signals" && (
              <div role="tabpanel" aria-labelledby="tab-signals" className="space-y-4">
                <SignalRoutesPage />
              </div>
            )}

            {activeTab === "academy" && (
              <div role="tabpanel" aria-labelledby="tab-academy" className="space-y-4">
                <AcademyPage />
              </div>
            )}

            {activeTab === "swarm" && (
              <>
                {/* Master Control and Signal Dial Row - Bento Styled */}
                <div className="grid grid-cols-1 xl:grid-cols-3 gap-6 font-mono text-xs">
                  {/* Master Orchestrator Agent Panel */}
                  <div className="bg-slate-900/40 border border-white/5 rounded-xl p-5 glow-emerald flex flex-col justify-between h-56 relative overflow-hidden transition-all duration-300 hover:border-white/10 hover:bg-slate-900/60">
                    <div className="space-y-3">
                      <div className="flex items-center justify-between border-b border-white/10 pb-2">
                        <span className="text-emerald-400 font-bold uppercase tracking-wider text-[11px]">
                          MASTER ORCHESTRATOR AGENT
                        </span>
                        <span className="text-[9px] text-emerald-500/70 border border-emerald-500/30 px-1.5 py-0.5 rounded">
                          OS CONTROLLER
                        </span>
                      </div>
                      <p className="text-[10px] text-slate-400 leading-relaxed">
                        Central execution block driving tactical directive alignment. Continuously audits signal weights across sub-nodes to maximize drawdown defenses.
                      </p>
                    </div>

                    {/* Circular Gauge Meter */}
                    <div className="flex items-center justify-between mt-3">
                      <CircularGauge
                        score={orchestratorScore}
                        label={t("score")}
                        stroke="#10b981"
                        textClass="text-emerald-400"
                      />

                      <div className="flex-1 space-y-1 pl-4 text-[10px]">
                        <div className="flex justify-between border-b border-white/5 pb-0.5">
                          <span className="text-slate-500">Active Directives:</span>
                          <span className="text-emerald-400 font-semibold">{activePlan ? "Custom" : "Standard"}</span>
                        </div>
                        <div className="flex justify-between border-b border-white/5 pb-0.5">
                          <span className="text-slate-500">Queue Latency:</span>
                          <span className="text-slate-300 font-semibold">{latencyLabel}</span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-slate-500">Safety Compliance:</span>
                          <span className={`font-semibold ${isComplianceActive ? "text-emerald-400" : "text-rose-400"}`}>
                            {isComplianceActive ? "Active" : "Hard Override"}
                          </span>
                        </div>
                      </div>
                    </div>
                  </div>

                  {/* Fable 5 Master Console Panel */}
                  <div className="bg-slate-900/40 border border-white/5 rounded-xl p-5 glow-cyan flex flex-col justify-between h-56 relative overflow-hidden transition-all duration-300 hover:border-white/10 hover:bg-slate-900/60">
                    <div className="space-y-3">
                      <div className="flex items-center justify-between border-b border-white/10 pb-2">
                        <span className="text-cyan-400 font-bold uppercase tracking-wider text-[11px]">
                          FABLE 5 MASTER CONSOLE
                        </span>
                        <span className="text-[9px] text-cyan-500/70 border border-cyan-500/30 px-1.5 py-0.5 rounded">
                          COMPOSITE STORES
                        </span>
                      </div>
                      <p className="text-[10px] text-slate-400 leading-relaxed">
                        Aggregates order depth profiles, trading volume vectors, and real-time social sentiments into a single unified telemetry flow.
                      </p>
                    </div>

                    {/* Composite signal meter */}
                    <div className="flex items-center justify-between mt-3">
                      <CircularGauge
                        score={compositeIndex}
                        label={t("index")}
                        stroke="#06b6d4"
                        textClass="text-cyan-400"
                      />

                      <div className="flex-1 space-y-1 pl-4 text-[10px]">
                        <div className="flex justify-between border-b border-white/5 pb-0.5">
                          <span className="text-slate-500">Sentiment weight:</span>
                          <span className="text-cyan-400 font-semibold">{sentimentLabel}</span>
                        </div>
                        <div className="flex justify-between border-b border-white/5 pb-0.5">
                          <span className="text-slate-500">Signal Anomaly:</span>
                          <span className="text-slate-300 font-semibold">{anomalyLabel}</span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-slate-500">Telemetry Feed:</span>
                          <span className={`font-semibold uppercase flex items-center gap-1 ${marketLive ? "text-emerald-400" : "text-amber-400"}`}>
                            <span className={`w-1.5 h-1.5 rounded-full ${marketLive ? "bg-emerald-400 animate-ping" : "bg-amber-400"}`}></span>
                            {marketLive ? "ACTIVE" : "CACHED"}
                          </span>
                        </div>
                      </div>
                    </div>
                  </div>

                  <div className="bg-slate-900/40 border border-white/5 rounded-xl p-5 glow-rose flex flex-col justify-between h-56 transition-all duration-300 hover:border-white/10 hover:bg-slate-900/60">
                    <div className="space-y-2.5 min-h-0">
                      <div className="flex items-center justify-between border-b border-white/10 pb-2">
                        <span className="text-purple-400 font-bold uppercase tracking-wider text-[11px]">
                          OS SYSTEM OVERVIEW
                        </span>
                        <span className="text-[9px] text-purple-500/70 border border-purple-500/30 px-1.5 py-0.5 rounded">
                          OS TELEMETRY
                        </span>
                      </div>
                      <div className="space-y-1 text-[9px] font-mono overflow-y-auto max-h-[7.5rem] pr-1">
                        {osTelemetryRows.map((row) => (
                          <div key={row.label} className="flex justify-between gap-2 border-b border-white/5 pb-0.5">
                            <span className="text-slate-500 uppercase shrink-0">{row.label}</span>
                            <span className={`text-right truncate ${row.tone}`}>{row.value}</span>
                          </div>
                        ))}
                      </div>
                    </div>

                    <div className="pt-2 bg-slate-950/40 border border-white/5 p-2.5 rounded-lg text-[9px] text-slate-300 flex items-start gap-2">
                      <Sparkles className={`w-4 h-4 text-purple-400 shrink-0 mt-0.5 ${activePlan || agentsOptimizing ? "animate-pulse" : ""}`} />
                      <span className="leading-relaxed line-clamp-3">{osFooter}</span>
                    </div>
                  </div>
                </div>

                <SubAgentsSection 
                  agents={subAgents}
                  trades={trades}
                  onUpdateAgentStatus={handleUpdateAgentStatus}
                  onOptimizeThresholds={handleOptimizeThresholds}
                  isComplianceActive={isComplianceActive}
                  onToggleCompliance={() => {
                    setIsComplianceActive(!isComplianceActive);
                    setSubAgents(prev => prev.map(a => a.id === "risk_gov" ? { ...a, lastAction: `Manually toggled safe override compliance rig to ${!isComplianceActive ? "ON" : "OFF"}.` } : a));
                  }}
                />

                <div className="grid grid-cols-1 gap-6">
                  <RiskAssessmentHeatmap tickers={tickers} marketLive={marketLive} marketAsOf={marketAsOf} />
                  <AgentTimeline />
                </div>
              </>
            )}

          </motion.div>
        </AnimatePresence>

      </div>

      {/* Cybernetic operating principles and footer panels (Bento Grid Theme) */}
      <footer className="mt-12 space-y-4 font-mono text-xs">
        {/* Rules & Principles bento-cards row */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div className="bg-slate-900/30 border border-white/5 hover:border-white/10 rounded-lg p-4 transition-all duration-300">
            <span className="text-[10px] text-emerald-400 font-bold uppercase block tracking-wider mb-2">
              // BUILD RULES
            </span>
            <ul className="text-[10px] text-slate-400 space-y-1 leading-relaxed list-decimal pl-4">
              <li>Optimize position values under active drawdowns dynamically.</li>
              <li>Halt executions immediately if counterparty slippage scales past 0.75%.</li>
              <li>Verify structural pipeline boundaries before submitting ledger trades.</li>
            </ul>
          </div>
          
          <div className="bg-slate-900/30 border border-white/5 hover:border-white/10 rounded-lg p-4 transition-all duration-300">
            <span className="text-[10px] text-cyan-400 font-bold uppercase block tracking-wider mb-2">
              // KNOWLEDGE RULES
            </span>
            <ul className="text-[10px] text-slate-400 space-y-1 leading-relaxed list-disc pl-4">
              <li>Aggregate deep multi-exchange VWAP vectors continuously.</li>
              <li>Maintain comprehensive performance reports in the Analytical logs.</li>
              <li>Sync resources across standard decentralized custody grids safely.</li>
            </ul>
          </div>

          <div className="bg-slate-900/30 border border-white/5 hover:border-white/10 rounded-lg p-4 transition-all duration-300">
            <span className="text-[10px] text-rose-400 font-bold uppercase block tracking-wider mb-2">
              // SAFETY & RESPONSIBILITY
            </span>
            <p className="text-[10px] text-slate-400 leading-relaxed">
              The platform operates under high-fidelity simulated guidelines. Risk metrics are calculated under mock algorithms. Trading parameters should be monitored carefully under continuous oversight.
            </p>
          </div>
        </div>

        {/* Beautiful Bento Footer Bar */}
        <div className="flex flex-col md:flex-row justify-between items-center bg-white/5 border border-white/10 rounded-lg p-3 text-[10px] tracking-wide gap-4">
          <div className="flex flex-wrap gap-4 items-center">
            <span className="text-cyan-400 flex items-center gap-1.5">
              <span className="w-1.5 h-1.5 rounded-full bg-cyan-400 animate-pulse"></span> 
              ENGINE: {readyStatus?.execution ?? "unreachable"}
            </span>
            <span className="text-slate-700">|</span>
            <span className="text-slate-400">
              AUTONOMY L{readyStatus?.autonomy_level ?? "—"} · LIVE={String(readyStatus?.live_trading_enabled ?? "—")}
            </span>
            <span className="text-slate-700">|</span>
            <span className="text-slate-400 uppercase">DB: {readyStatus?.database ?? "n/a"}</span>
          </div>
          <div className="flex items-center gap-4 text-slate-400">
            <span className="uppercase text-[9px]">Market: {marketLive ? "LIVE" : "STALE"}{marketAsOf ? ` · ${new Date(marketAsOf).toLocaleTimeString()}` : ""}</span>
            <span className="text-white bg-white/10 px-2 py-0.5 rounded-sm text-[9px]">{currentTime}</span>
          </div>
        </div>

        {/* Minor credit attribution */}
        <div className="text-[8px] text-slate-600 text-center pt-2">
          DEVELOPED BY DEEP CYBERNETICS LABS © 2026 // FABLE 5 MASTERPROMPT OS v3.0 // ALPACA AGENT SHELL
        </div>
      </footer>

      {/* Settings Dialog Overlay */}
      <AnimatePresence>
        {isSettingsOpen && (
          <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/85 backdrop-blur-md">
            <motion.div
              initial={{ opacity: 0, scale: 0.95 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0, scale: 0.95 }}
              transition={{ duration: 0.2 }}
              className="w-full max-w-2xl max-h-[90vh] flex flex-col bg-slate-950 border border-cyan-500/30 rounded-xl overflow-hidden font-mono text-xs text-slate-300 shadow-2xl shadow-cyan-950/20"
            >
              {/* Header */}
              <div className="flex items-center justify-between bg-slate-900/60 px-5 py-4 border-b border-white/10">
                <div className="flex items-center gap-2 text-cyan-400">
                  <Settings className="w-4 h-4 animate-[spin_10s_linear_infinite]" />
                  <span className="font-extrabold uppercase tracking-widest text-[11px]">
                    {language === "de" ? "OS SYSTEM-CONFIG / OPTIONEN" : "OS SYSTEM-CONFIG / OPTIONS"}
                  </span>
                </div>
                <button
                  onClick={() => setIsSettingsOpen(false)}
                  className="text-slate-500 hover:text-white border border-white/15 px-2 py-1 rounded hover:bg-white/5 uppercase text-[9px] cursor-pointer transition-all"
                >
                  {t("close")}
                </button>
              </div>

              {/* Body */}
              <div className="p-6 space-y-5 overflow-y-auto flex-1 min-h-0">
                <div className="bg-slate-900/30 border border-white/5 p-4 rounded-lg space-y-3 normal-case tracking-normal">
                  <div className="flex justify-between items-center">
                    <span className="text-white font-bold uppercase tracking-wider text-[10px]">
                      {language === "de" ? "Konto" : "Account"}
                    </span>
                    <span className="text-cyan-400 text-[9px]">FIREBASE AUTH</span>
                  </div>
                  <AuthPanel />
                </div>

                <IntegrationsSettingsPanel language={language} />

                {/* Language selection card */}
                <div className="bg-slate-900/30 border border-white/5 p-4 rounded-lg space-y-3">
                  <div className="flex justify-between items-center">
                    <span className="text-white font-bold uppercase tracking-wider text-[10px]">
                      {t("language")}
                    </span>
                    <span className="text-cyan-400 text-[9px]">SYSTEM LOCALIZATION</span>
                  </div>
                  <p className="text-[10px] text-slate-500 leading-relaxed">
                    {t("selectLanguageDesc")}
                  </p>
                  <div className="grid grid-cols-2 gap-3 pt-1">
                    <button
                      onClick={() => {
                        setLanguage("en");
                        localStorage.setItem("app_language", "en");
                      }}
                      className={`py-2 px-3 border rounded text-center transition-all cursor-pointer font-bold uppercase text-[10px] ${
                        language === "en"
                          ? "bg-cyan-500/10 border-cyan-400 text-cyan-400 shadow-sm"
                          : "bg-white/5 border-white/10 text-slate-500 hover:text-slate-300"
                      }`}
                    >
                      {t("english")}
                    </button>
                    <button
                      onClick={() => {
                        setLanguage("de");
                        localStorage.setItem("app_language", "de");
                      }}
                      className={`py-2 px-3 border rounded text-center transition-all cursor-pointer font-bold uppercase text-[10px] ${
                        language === "de"
                          ? "bg-cyan-500/10 border-cyan-400 text-cyan-400 shadow-sm"
                          : "bg-white/5 border-white/10 text-slate-500 hover:text-slate-300"
                      }`}
                    >
                      {t("german")}
                    </button>
                  </div>
                </div>

                {/* Acoustic Telemetry Card */}
                <div className="bg-slate-900/30 border border-white/5 p-4 rounded-lg space-y-3">
                  <div className="flex justify-between items-center">
                    <span className="text-amber-400 font-bold uppercase tracking-wider text-[10px]">
                      {t("auditoryFeedback")}
                    </span>
                    <span className="text-amber-500/50 border border-amber-500/20 px-1.5 py-0.5 rounded text-[8px]">
                      {t("voicePack")}
                    </span>
                  </div>

                  <div className="space-y-2">
                    <div className="flex justify-between text-[10px]">
                      <span className="text-slate-500 uppercase">{t("soundVolume")}</span>
                      <span className="text-slate-200 font-semibold">100% (MAX)</span>
                    </div>
                    <div className="h-1.5 w-full bg-white/5 rounded overflow-hidden relative">
                      <div className="h-full bg-amber-400 w-full"></div>
                    </div>
                  </div>

                  <div className="pt-2">
                    <button
                      onClick={() => {
                        // Trigger test sound line
                        const testStreak = { wins: 3, losses: 0 };
                        announceTradeOutcome(150.0, testStreak, language);
                      }}
                      className="w-full py-2 bg-amber-500/10 hover:bg-amber-500/20 border border-amber-500/30 text-amber-400 hover:text-amber-300 font-bold uppercase tracking-widest text-[9px] rounded transition-all cursor-pointer text-center"
                    >
                      {language === "de" ? "» SOUND TESTEN «" : "» TEST SOUND EFFECT «"}
                    </button>
                  </div>
                </div>

                {/* Keyboard Shortcuts Guide */}
                <div className="bg-slate-900/30 border border-white/5 p-4 rounded-lg space-y-2">
                  <span className="text-purple-400 font-bold uppercase tracking-wider text-[10px] block">
                    {t("keyboardShortcuts")}
                  </span>
                  <p className="text-[10px] text-slate-500 leading-relaxed">
                    {t("keyDesc")}
                  </p>
                  <div className="flex gap-2 pt-1 flex-wrap">
                    {["1", "2", "3", "4", "5"].map((k, idx) => {
                      const label = ["DASH", "TERM", "STRAT", "SWARM", "OS"][idx];
                      return (
                        <div key={k} className="flex items-center gap-1 bg-white/5 border border-white/10 px-2 py-1 rounded text-[9px]">
                          <kbd className="bg-slate-950 border border-white/20 px-1 rounded font-bold text-cyan-400">{k}</kbd>
                          <span className="text-slate-400 font-semibold">{label}</span>
                        </div>
                      );
                    })}
                  </div>
                </div>
              </div>

              {/* Footer */}
              <div className="bg-slate-900/60 px-5 py-4 border-t border-white/10 flex justify-end">
                <button
                  onClick={() => setIsSettingsOpen(false)}
                  className="px-5 py-2 bg-cyan-500/15 border border-cyan-400/40 text-cyan-400 hover:bg-cyan-500/25 transition-all cursor-pointer font-bold uppercase text-[10px] rounded-sm"
                >
                  {t("saveSettings")}
                </button>
              </div>
            </motion.div>
          </div>
        )}
      </AnimatePresence>
    </div>
  );
}
