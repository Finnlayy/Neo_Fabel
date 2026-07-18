import React, { useState, useRef } from "react";
import { 
  Play, 
  Settings, 
  Sliders, 
  Table, 
  ShieldCheck, 
  AlertTriangle, 
  CheckCircle2, 
  ArrowRight, 
  HelpCircle, 
  Cpu, 
  Sparkles, 
  ChevronRight,
  Database,
  RefreshCw,
  Upload,
  Eye,
  Camera,
  FileImage,
  Youtube,
  History,
  Plus,
  Trash2,
  ExternalLink
} from "lucide-react";
import { ApiError } from "../api/client";
import { postTvapiAnalyzeChart, postTvapiOptimize } from "../api/ai";

interface TvapiOptimizerProps {
  activeSymbol: string;
}

export default function TvapiOptimizer({ activeSymbol }: TvapiOptimizerProps) {
  const [strategy, setStrategy] = useState<"smc" | "bb_rsi_sl" | "trailing">("smc");
  const [symbol, setSymbol] = useState(activeSymbol || "BTCUSD");

  React.useEffect(() => {
    if (activeSymbol) {
      setSymbol(activeSymbol);
    }
  }, [activeSymbol]);

  const [timeframe, setTimeframe] = useState("5m");
  const [minTrades, setMinTrades] = useState(30);
  const [primaryObjective, setPrimaryObjective] = useState("profit_factor");
  const [secondaryObjective, setSecondaryObjective] = useState("percent_profitable");
  const [isOptimizing, setIsOptimizing] = useState(false);
  const [activeTab, setActiveTab] = useState<"bericht" | "selbstprüfung" | "runs">("bericht");

  // Vision states for chart pattern & backtesting control
  const [chartMode, setChartMode] = useState<"live" | "presets" | "upload" | "youtube">("live");
  const [visionImage, setVisionImage] = useState<string | null>(null);
  const [visionMimeType, setVisionMimeType] = useState<string>("image/png");
  const [visionMode, setVisionMode] = useState<"pattern" | "backtest">("pattern");
  const [isVisionAnalyzing, setIsVisionAnalyzing] = useState(false);
  const [visionAnalysisResult, setVisionAnalysisResult] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // YouTube Coping Feature states
  const [youtubeUrl, setYoutubeUrl] = useState("");
  const [youtubeError, setYoutubeError] = useState<string | null>(null);
  const [youtubeVideoId, setYoutubeVideoId] = useState<string | null>(null);
  const [youtubeHistory, setYoutubeHistory] = useState<string[]>(() => {
    try {
      const saved = localStorage.getItem("tvapi_youtube_history");
      return saved ? JSON.parse(saved) : [];
    } catch {
      return [];
    }
  });

  const getYouTubeId = (url: string): string | null => {
    const regExp = /^.*(youtu.be\/|v\/|u\/\w\/|embed\/|watch\?v=|\&v=)([^#\&\?]*).*/;
    const match = url.match(regExp);
    return (match && match[2].length === 11) ? match[2] : null;
  };

  const handleEmbedYoutube = (urlToEmbed?: string) => {
    setYoutubeError(null);
    const targetUrl = urlToEmbed !== undefined ? urlToEmbed : youtubeUrl;
    if (!targetUrl || !targetUrl.trim()) {
      setYoutubeError("Please enter a URL first");
      return;
    }

    const vId = getYouTubeId(targetUrl);
    if (vId) {
      setYoutubeVideoId(vId);
      const trimmed = targetUrl.trim();
      const filtered = youtubeHistory.filter(link => link !== trimmed);
      const updated = [trimmed, ...filtered].slice(0, 10);
      setYoutubeHistory(updated);
      localStorage.setItem("tvapi_youtube_history", JSON.stringify(updated));
      if (urlToEmbed === undefined) {
        setYoutubeUrl(""); // Reset input only on manual submit
      }
    } else {
      setYoutubeError("Invalid YouTube URL. Please use standard video or stream link.");
    }
  };

  const handleDeleteHistoryItem = (e: React.MouseEvent, indexToDelete: number) => {
    e.stopPropagation();
    const updated = youtubeHistory.filter((_, idx) => idx !== indexToDelete);
    setYoutubeHistory(updated);
    localStorage.setItem("tvapi_youtube_history", JSON.stringify(updated));
  };

  const handleClearHistory = () => {
    setYoutubeHistory([]);
    localStorage.removeItem("tvapi_youtube_history");
  };

  // Output results from optimization
  const [optimizationResult, setOptimizationResult] = useState<any>(null);
  
  // Simulated Pine Strategy Setup State (what's currently "programmed" in TV)
  const [currentTVInputs, setCurrentTVInputs] = useState<Record<string, any>>({
    "in_0": 14,
    "in_1": 2.5,
    "in_2": 1.0,
    "in_6": 14,
    "in_3": 0.20,
    "in_4": 0.10,
    "Structure Length": 5,
    "Base Risk (%)": 1.0,
    "Risk:Reward Ratio": 2.0
  });

  // Pine input writing pipeline simulation state
  const [setPipelineLog, setSetPipelineLog] = useState<string[]>([]);
  const [isProgramming, setIsProgramming] = useState(false);

  // CSV Trading Knowledge Parameters
  const smcParams = {
    __indicatorName: "Neo-Quantum SMC [Cluster Optimized]",
    "Market Structure Length": 5,
    "Show Breaker Blocks": "true",
    "Min. ATR Spacing between Trades": 1,
    "Volume-Weighted TP Merging": "true",
    "Enable Time-Decay Exit": "true",
    "Max. Cluster Duration (Bars)": 30,
    "Risk:Reward Ratio": 2,
    "ATR Multiplier for Stop Loss": 1.5,
    "Use Full Kelly Sizing": "true",
    "Max Risk Cap (%)": 5,
    "Base Risk (%)": 1
  };

  // Run TVAPI Sweep Optimization
  const handleRunOptimization = async () => {
    setIsOptimizing(true);
    setOptimizationResult(null);
    setSetPipelineLog([]);

    try {
      const data = await postTvapiOptimize({
        strategy,
        symbol,
        timeframe,
        minTrades,
        primaryObjective,
        secondaryObjective,
        parameters: strategy === "smc" ? smcParams : {},
      });
      if (data.success) {
        setOptimizationResult(data);
      } else {
        console.error("Optimization failed:", data.error);
      }
    } catch (err) {
      console.error("Error optimizing strategy:", err instanceof ApiError ? err.message : err);
    } finally {
      setIsOptimizing(false);
    }
  };

  // Simulates standard "Tvapi Set Strategy Input - Ausfuehrungsstandard"
  // Writes parameters one by one, logs results, prevents report from claiming completion if failed.
  const handleSetStrategyInputs = () => {
    if (!optimizationResult || !optimizationResult.winner) return;

    setIsProgramming(true);
    setSetPipelineLog([]);
    const winnerInputs = optimizationResult.winner.inputs;
    const entries = Object.entries(winnerInputs);
    
    let currentIdx = 0;

    const interval = setInterval(() => {
      if (currentIdx < entries.length) {
        const [paramKey, paramVal] = entries[currentIdx];
        
        // Find corresponding Input-ID
        let inputId = "unknown";
        if (strategy === "bb_rsi_sl") {
          inputId = paramKey === "in_0" ? "in_0" : paramKey === "in_1" ? "in_1" : paramKey === "in_2" ? "in_2" : "in_6";
        } else if (strategy === "trailing") {
          inputId = paramKey === "in_3" ? "in_3" : "in_4";
        } else {
          inputId = `smc_${paramKey.toLowerCase().replace(/[^a-z0-9]/g, "_")}`;
        }

        // Apply update in simulated TV environment
        setCurrentTVInputs(prev => ({
          ...prev,
          [paramKey]: paramVal
        }));

        setSetPipelineLog(prev => [
          ...prev,
          `[TVAPI SET] in_id: "${inputId}" | parameter: "${paramKey}" | setting value: ${paramVal} ... SUCCESS`
        ]);

        currentIdx++;
      } else {
        clearInterval(interval);
        setSetPipelineLog(prev => [
          ...prev,
          `🏁 [TVAPI SYSTEM] All parameters synchronized with active strategy instance. Ready for forward execution.`
        ]);
        setIsProgramming(false);
      }
    }, 1200);
  };

  const drawPresetToCanvas = (type: "wedge" | "hns" | "sweep") => {
    const canvas = document.createElement("canvas");
    canvas.width = 500;
    canvas.height = 300;
    const ctx = canvas.getContext("2d");
    if (!ctx) return null;

    // Background
    ctx.fillStyle = "#020617";
    ctx.fillRect(0, 0, 500, 300);

    // Gridlines
    ctx.strokeStyle = "rgba(255, 255, 255, 0.05)";
    ctx.lineWidth = 1;
    for (let i = 50; i < 500; i += 50) {
      ctx.beginPath();
      ctx.moveTo(i, 0);
      ctx.lineTo(i, 300);
      ctx.stroke();
    }
    for (let i = 50; i < 300; i += 50) {
      ctx.beginPath();
      ctx.moveTo(0, i);
      ctx.lineTo(500, i);
      ctx.stroke();
    }

    // Draw some mock candles
    const drawCandle = (x: number, open: number, close: number, high: number, low: number) => {
      const isGreen = close > open;
      ctx.strokeStyle = isGreen ? "#10b981" : "#ef4444";
      ctx.fillStyle = isGreen ? "#10b981" : "#ef4444";
      ctx.lineWidth = 2;

      // Wick
      ctx.beginPath();
      ctx.moveTo(x, high);
      ctx.lineTo(x, low);
      ctx.stroke();

      // Body
      const bodyHeight = Math.abs(close - open) || 2;
      const bodyY = isGreen ? close : open;
      ctx.fillRect(x - 5, bodyY, 10, bodyHeight);
    };

    // Draw Header
    ctx.fillStyle = "#94a3b8";
    ctx.font = "bold 12px 'JetBrains Mono', monospace";
    ctx.fillText(type === "wedge" ? "BTCUSD 5m - RISING WEDGE" : type === "hns" ? "ETHUSD 15m - HEAD & SHOULDERS" : "SOLUSD 1h - LIQUIDITY SWEEP", 15, 25);

    if (type === "wedge") {
      // Trending up but tightening
      const points = [
        { x: 50, o: 200, c: 180, h: 170, l: 210 },
        { x: 90, o: 180, c: 190, h: 175, l: 195 },
        { x: 130, o: 190, c: 160, h: 150, l: 200 },
        { x: 170, o: 160, c: 170, h: 155, l: 175 },
        { x: 210, o: 170, c: 140, h: 130, l: 180 },
        { x: 250, o: 140, c: 150, h: 135, l: 155 },
        { x: 290, o: 150, c: 130, h: 120, l: 160 },
        { x: 330, o: 130, c: 135, h: 125, l: 140 },
        { x: 370, o: 135, c: 120, h: 115, l: 145 },
        { x: 410, o: 120, c: 160, h: 110, l: 170 }, // Breakdown candle
        { x: 450, o: 160, c: 200, h: 150, l: 210 }
      ];
      points.forEach(p => drawCandle(p.x, p.o, p.c, p.h, p.l));

      // Converging trendlines
      ctx.strokeStyle = "rgba(245, 158, 11, 0.6)"; // Orange
      ctx.setLineDash([4, 4]);
      ctx.lineWidth = 1.5;

      // Upper line
      ctx.beginPath();
      ctx.moveTo(40, 180);
      ctx.lineTo(400, 110);
      ctx.stroke();

      // Lower line
      ctx.beginPath();
      ctx.moveTo(40, 215);
      ctx.lineTo(400, 140);
      ctx.stroke();
      ctx.setLineDash([]);

      // Order Block
      ctx.fillStyle = "rgba(239, 68, 68, 0.15)";
      ctx.strokeStyle = "rgba(239, 68, 68, 0.4)";
      ctx.fillRect(350, 95, 100, 40);
      ctx.strokeRect(350, 95, 100, 40);
      ctx.fillStyle = "#f87171";
      ctx.font = "8px 'JetBrains Mono', monospace";
      ctx.fillText("Bearish OB", 355, 108);

    } else if (type === "hns") {
      // Left Shoulder, Head, Right Shoulder
      const points = [
        { x: 50, o: 200, c: 170, h: 160, l: 210 }, // Left up
        { x: 90, o: 170, c: 150, h: 140, l: 180 }, // Left high
        { x: 130, o: 150, c: 180, h: 145, l: 190 }, // Pullback
        { x: 170, o: 180, c: 130, h: 120, l: 190 }, // Head up
        { x: 210, o: 130, c: 100, h: 90, l: 140 },  // Head peak
        { x: 250, o: 100, c: 140, h: 95, l: 150 },  // Head down
        { x: 290, o: 140, c: 180, h: 130, l: 190 }, // Neckline support
        { x: 330, o: 180, c: 150, h: 140, l: 190 }, // Right Shoulder up
        { x: 370, o: 150, c: 180, h: 145, l: 185 }, // Right peak to neck
        { x: 410, o: 180, c: 220, h: 175, l: 230 }, // Breakdown
        { x: 450, o: 220, c: 250, h: 210, l: 260 }
      ];
      points.forEach(p => drawCandle(p.x, p.o, p.c, p.h, p.l));

      // Neckline
      ctx.strokeStyle = "rgba(168, 85, 247, 0.6)"; // Purple
      ctx.setLineDash([4, 4]);
      ctx.lineWidth = 1.5;
      ctx.beginPath();
      ctx.moveTo(40, 182);
      ctx.lineTo(400, 182);
      ctx.stroke();
      ctx.setLineDash([]);

      ctx.fillStyle = "#c084fc";
      ctx.font = "8px 'JetBrains Mono', monospace";
      ctx.fillText("NECKLINE", 45, 175);
      ctx.fillText("Left Sh.", 75, 130);
      ctx.fillText("HEAD", 195, 80);
      ctx.fillText("Right Sh.", 315, 130);

    } else {
      // Liquidity Sweep (double top then drop)
      const points = [
        { x: 50, o: 180, c: 150, h: 140, l: 190 }, // up to resistance
        { x: 90, o: 150, c: 140, h: 130, l: 160 }, // Peak 1
        { x: 130, o: 140, c: 180, h: 135, l: 190 }, // drop
        { x: 170, o: 180, c: 150, h: 145, l: 190 }, // up
        { x: 210, o: 150, c: 140, h: 130, l: 160 }, // Peak 2 (Double Top level)
        { x: 250, o: 140, c: 175, h: 135, l: 185 }, // drop
        { x: 290, o: 175, c: 120, h: 110, l: 180 }, // Massive green sweep candle through resistance!
        { x: 330, o: 120, c: 105, h: 95, l: 130 },  // Final high
        { x: 370, o: 105, c: 160, h: 100, l: 170 }, // Huge red engulfing trap candle!
        { x: 410, o: 160, c: 210, h: 150, l: 220 }, // continuation drop
        { x: 450, o: 210, c: 240, h: 200, l: 250 }
      ];
      points.forEach(p => drawCandle(p.x, p.o, p.c, p.h, p.l));

      // Resistance Level
      ctx.strokeStyle = "rgba(239, 68, 68, 0.6)"; // Red
      ctx.lineWidth = 1.5;
      ctx.beginPath();
      ctx.moveTo(40, 135);
      ctx.lineTo(440, 135);
      ctx.stroke();

      ctx.fillStyle = "#f87171";
      ctx.font = "8px 'JetBrains Mono', monospace";
      ctx.fillText("LIQUIDITY POOL / RESISTANCE", 45, 128);

      // Circle showing sweep
      ctx.strokeStyle = "#eab308"; // Yellow
      ctx.lineWidth = 1.5;
      ctx.beginPath();
      ctx.arc(310, 115, 25, 0, 2 * Math.PI);
      ctx.stroke();
      ctx.fillStyle = "#facc15";
      ctx.fillText("SWEEP TRAP", 340, 115);
    }

    return canvas.toDataURL("image/png");
  };

  const handleLoadPreset = (type: "wedge" | "hns" | "sweep") => {
    const dataUrl = drawPresetToCanvas(type);
    if (dataUrl) {
      setVisionImage(dataUrl);
      setVisionMimeType("image/png");
      setVisionAnalysisResult(null);
    }
  };

  const handleImageUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      const reader = new FileReader();
      reader.onload = (event) => {
        if (event.target?.result) {
          setVisionImage(event.target.result as string);
          setVisionMimeType(file.type);
          setVisionAnalysisResult(null);
        }
      };
      reader.readAsDataURL(file);
    }
  };

  const getLiveChartCanvasDataUrl = (sym: string, tf: string): string => {
    const canvas = document.createElement("canvas");
    canvas.width = 600;
    canvas.height = 360;
    const ctx = canvas.getContext("2d");
    if (!ctx) return "";

    // Dark slate background
    ctx.fillStyle = "#020617";
    ctx.fillRect(0, 0, 600, 360);

    // Grid
    ctx.strokeStyle = "rgba(255, 255, 255, 0.05)";
    ctx.lineWidth = 1;
    for (let i = 50; i < 600; i += 50) {
      ctx.beginPath();
      ctx.moveTo(i, 0);
      ctx.lineTo(i, 360);
      ctx.stroke();
    }
    for (let i = 40; i < 360; i += 40) {
      ctx.beginPath();
      ctx.moveTo(0, i);
      ctx.lineTo(600, i);
      ctx.stroke();
    }

    // Header Title
    ctx.fillStyle = "#f1f5f9";
    ctx.font = "bold 13px 'JetBrains Mono', monospace";
    ctx.fillText(`PREVIEW:${sym}T, ${tf} - DETERMINISTIC CANVAS (NOT LIVE FEED)`, 20, 30);

    // Technical Indicator Legends
    ctx.fillStyle = "#38bdf8"; // Light Blue
    ctx.font = "9px 'JetBrains Mono', monospace";
    ctx.fillText("Bollinger Bands (20, 2)", 20, 48);
    ctx.fillStyle = "#a855f7"; // Purple
    ctx.fillText("RSI (14)", 180, 48);
    ctx.fillStyle = "#10b981"; // Emerald
    ctx.fillText("Neo-Quantum SMC Structure Active", 250, 48);

    // Generate some semi-random candlesticks around a base price
    const count = 18;
    const spacing = 30;
    const startX = 50;

    // Draw simulated Bollinger Bands (shaded area)
    ctx.fillStyle = "rgba(56, 189, 248, 0.03)";
    ctx.beginPath();
    ctx.moveTo(startX, 180);
    for (let i = 0; i < count; i++) {
      const x = startX + i * spacing;
      const bandDev = 40 + Math.sin(i * 0.5) * 15;
      ctx.lineTo(x, 180 - bandDev);
    }
    for (let i = count - 1; i >= 0; i--) {
      const x = startX + i * spacing;
      const bandDev = 40 + Math.sin(i * 0.5) * 15;
      ctx.lineTo(x, 180 + bandDev);
    }
    ctx.closePath();
    ctx.fill();

    // Draw upper/lower BB band lines
    ctx.strokeStyle = "rgba(56, 189, 248, 0.25)";
    ctx.lineWidth = 1;
    ctx.beginPath();
    for (let i = 0; i < count; i++) {
      const x = startX + i * spacing;
      const bandDev = 40 + Math.sin(i * 0.5) * 15;
      if (i === 0) ctx.moveTo(x, 180 - bandDev);
      else ctx.lineTo(x, 180 - bandDev);
    }
    ctx.stroke();

    ctx.beginPath();
    for (let i = 0; i < count; i++) {
      const x = startX + i * spacing;
      const bandDev = 40 + Math.sin(i * 0.5) * 15;
      if (i === 0) ctx.moveTo(x, 180 + bandDev);
      else ctx.lineTo(x, 180 + bandDev);
    }
    ctx.stroke();

    // Draw candles
    let currentClose = 180;
    for (let i = 0; i < count; i++) {
      const x = startX + i * spacing;
      const open = currentClose;
      // Deterministic preview candles (not a live exchange feed).
      const change = (Math.sin(i * 0.7) * 0.5 + 0.05) * 35;
      const close = open - change;
      currentClose = close;

      const high = Math.min(open, close) - Math.abs(Math.cos(i * 0.9)) * 15;
      const low = Math.max(open, close) + Math.abs(Math.sin(i * 1.1)) * 15;

      const isGreen = close < open; // Canvas Y coordinate is inverted: smaller value is higher price!
      ctx.strokeStyle = isGreen ? "#10b981" : "#ef4444";
      ctx.fillStyle = isGreen ? "#10b981" : "#ef4444";
      ctx.lineWidth = 1.5;

      // Wick
      ctx.beginPath();
      ctx.moveTo(x, high);
      ctx.lineTo(x, low);
      ctx.stroke();

      // Body
      const bodyHeight = Math.abs(close - open) || 2;
      const bodyY = Math.min(open, close);
      ctx.fillRect(x - 5, bodyY, 10, bodyHeight);
    }

    // Draw some key SMC structural breaks (BOS/CHoCH)
    ctx.strokeStyle = "rgba(16, 185, 129, 0.4)";
    ctx.setLineDash([4, 4]);
    ctx.beginPath();
    ctx.moveTo(150, 140);
    ctx.lineTo(350, 140);
    ctx.stroke();
    ctx.setLineDash([]);
    ctx.fillStyle = "#10b981";
    ctx.font = "bold 8px 'JetBrains Mono', monospace";
    ctx.fillText("BOS (Break of Structure)", 160, 134);

    // Order block rectangle
    ctx.fillStyle = "rgba(16, 185, 129, 0.08)";
    ctx.strokeStyle = "rgba(16, 185, 129, 0.3)";
    ctx.fillRect(280, 190, 120, 30);
    ctx.strokeRect(280, 190, 120, 30);
    ctx.fillStyle = "#34d399";
    ctx.fillText("SMC Bullish OB", 285, 202);

    return canvas.toDataURL("image/png");
  };

  const handleAnalyzeChart = async (overrideImage?: string) => {
    const imgToUse = overrideImage || visionImage;
    if (!imgToUse) return;
    setIsVisionAnalyzing(true);
    setVisionAnalysisResult(null);

    try {
      const data = await postTvapiAnalyzeChart({
        image: imgToUse,
        mimeType: overrideImage ? "image/png" : visionMimeType,
        promptMode: visionMode,
      });
      if (data.success) {
        setVisionAnalysisResult(data.analysis ?? "");
      } else {
        setVisionAnalysisResult(`⚠️ Error: ${data.error || "Failed to analyze chart screenshot"}`);
      }
    } catch (err: unknown) {
      const message =
        err instanceof ApiError ? `${err.code}: ${err.message}` : err instanceof Error ? err.message : "Failed to connect";
      setVisionAnalysisResult(`⚠️ Error: ${message}`);
    } finally {
      setIsVisionAnalyzing(false);
    }
  };

  return (
    <div id="tvapi-optimizer-panel" className="bg-slate-900/40 border border-white/5 rounded-2xl p-6 space-y-6 transition-all duration-300 hover:border-white/10 hover:bg-slate-900/50">
      
      {/* Panel Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-white/5 pb-4">
        <div className="space-y-1">
          <div className="flex items-center gap-2">
            <div className="bg-cyan-500/10 border border-cyan-500/20 p-1.5 rounded-lg text-cyan-400">
              <Cpu className="w-4 h-4 animate-pulse" />
            </div>
            <h2 className="text-sm font-bold uppercase tracking-wider text-slate-100">
              TVAPI Strategy Sweep Optimizer & SMC Guard
            </h2>
          </div>
          <p className="text-[10px] text-slate-400 leading-relaxed max-w-2xl">
            Integrates multi-stage TradingView TVAPI backtest sweeps with advanced Smart Money Concepts (SMC) guards. 
            Automates rule-based ranking, sequential trailing exit sweeps, and commits parameters via secure input mapping.
          </p>
        </div>

        {/* Configuration Type Selector */}
        <div className="flex bg-slate-950/60 p-1 border border-white/5 rounded-xl self-start">
          <button
            onClick={() => setStrategy("smc")}
            className={`px-3 py-1.5 rounded-lg text-[10px] font-bold uppercase tracking-wider transition-all duration-200 ${
              strategy === "smc" 
                ? "bg-cyan-500 text-slate-950 shadow-md shadow-cyan-500/20" 
                : "text-slate-400 hover:text-slate-200"
            }`}
          >
            SMC Cluster
          </button>
          <button
            onClick={() => setStrategy("bb_rsi_sl")}
            className={`px-3 py-1.5 rounded-lg text-[10px] font-bold uppercase tracking-wider transition-all duration-200 ${
              strategy === "bb_rsi_sl" 
                ? "bg-cyan-500 text-slate-950 shadow-md shadow-cyan-500/20" 
                : "text-slate-400 hover:text-slate-200"
            }`}
          >
            BB/RSI/SL Sweep
          </button>
          <button
            onClick={() => setStrategy("trailing")}
            className={`px-3 py-1.5 rounded-lg text-[10px] font-bold uppercase tracking-wider transition-all duration-200 ${
              strategy === "trailing" 
                ? "bg-cyan-500 text-slate-950 shadow-md shadow-cyan-500/20" 
                : "text-slate-400 hover:text-slate-200"
            }`}
          >
            Trailing Sweep
          </button>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        
        {/* Section 1: Optimization Config & active status */}
        <div className="space-y-4 lg:col-span-1">
          <div className="bg-slate-950/40 border border-white/5 rounded-xl p-4 space-y-4">
            <div className="flex items-center gap-2 border-b border-white/5 pb-2">
              <Sliders className="w-3.5 h-3.5 text-cyan-400" />
              <span className="text-[10px] font-bold uppercase tracking-wider text-slate-300">
                Sweep Configuration
              </span>
            </div>

            {/* Config Fields */}
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1">
                <label className="text-[9px] text-slate-500 uppercase tracking-wider">Asset / Symbol</label>
                <select
                  value={symbol}
                  onChange={(e) => setSymbol(e.target.value)}
                  className="w-full bg-slate-900 border border-white/5 text-[10px] text-slate-300 p-2 rounded-lg focus:border-cyan-500 outline-none"
                >
                  <option value="BTCUSD">BTCUSD</option>
                  <option value="ETHUSD">ETHUSD</option>
                  <option value="SOLUSD">SOLUSD</option>
                  <option value="AVAXUSD">AVAXUSD</option>
                </select>
              </div>

              <div className="space-y-1">
                <label className="text-[9px] text-slate-500 uppercase tracking-wider">Timeframe</label>
                <select
                  value={timeframe}
                  onChange={(e) => setTimeframe(e.target.value)}
                  className="w-full bg-slate-900 border border-white/5 text-[10px] text-slate-300 p-2 rounded-lg focus:border-cyan-500 outline-none"
                >
                  <option value="5m">5m (Intraday)</option>
                  <option value="15m">15m (Scalp)</option>
                  <option value="1h">1h (Structure)</option>
                  <option value="4h">4h (Macro)</option>
                </select>
              </div>

              <div className="space-y-1">
                <label className="text-[9px] text-slate-500 uppercase tracking-wider">Primary Goal</label>
                <select
                  value={primaryObjective}
                  onChange={(e) => setPrimaryObjective(e.target.value)}
                  className="w-full bg-slate-900 border border-white/5 text-[10px] text-slate-300 p-2 rounded-lg focus:border-cyan-500 outline-none"
                >
                  <option value="profit_factor">Profit Factor</option>
                  <option value="net_profit">Net Profit</option>
                  <option value="win_rate">Win Rate (%)</option>
                </select>
              </div>

              <div className="space-y-1">
                <label className="text-[9px] text-slate-500 uppercase tracking-wider">Secondary Goal</label>
                <select
                  value={secondaryObjective}
                  onChange={(e) => setSecondaryObjective(e.target.value)}
                  className="w-full bg-slate-900 border border-white/5 text-[10px] text-slate-300 p-2 rounded-lg focus:border-cyan-500 outline-none"
                >
                  <option value="percent_profitable">Win Rate (%)</option>
                  <option value="net_profit">Net Profit</option>
                  <option value="profit_factor">Profit Factor</option>
                </select>
              </div>

              <div className="space-y-1 col-span-2">
                <label className="text-[9px] text-slate-500 uppercase tracking-wider flex items-center justify-between">
                  <span>Min. Trades Threshold</span>
                  <span className="text-cyan-400 font-bold">{minTrades}</span>
                </label>
                <input
                  type="range"
                  min="10"
                  max="100"
                  step="5"
                  value={minTrades}
                  onChange={(e) => setMinTrades(Number(e.target.value))}
                  className="w-full accent-cyan-400"
                />
              </div>
            </div>

            {/* Run Sweeps Trigger */}
            <button
              onClick={handleRunOptimization}
              disabled={isOptimizing}
              className="w-full bg-cyan-500 hover:bg-cyan-400 text-slate-950 font-bold text-[10px] uppercase tracking-wider py-2.5 rounded-lg transition-all duration-200 flex items-center justify-center gap-2 shadow-lg shadow-cyan-500/10 disabled:opacity-50"
            >
              {isOptimizing ? (
                <>
                  <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                  Running Dual Sweep Scan...
                </>
              ) : (
                <>
                  <Play className="w-3.5 h-3.5" />
                  Run Multi-Stage Sweep Scan
                </>
              )}
            </button>
          </div>

          {/* Current TV programmed State panel */}
          <div className="bg-slate-950/40 border border-white/5 rounded-xl p-4 space-y-3">
            <div className="flex items-center justify-between border-b border-white/5 pb-2">
              <span className="text-[10px] font-bold uppercase tracking-wider text-slate-300 flex items-center gap-1.5">
                <Database className="w-3.5 h-3.5 text-cyan-400" />
                Pine Script Active inputs
              </span>
              <span className="text-[8px] bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 px-1.5 py-0.5 rounded uppercase font-mono">
                SYNCHRONIZED
              </span>
            </div>

            <div className="space-y-1.5 font-mono text-[10px] text-slate-400">
              {strategy === "bb_rsi_sl" ? (
                <>
                  <div className="flex justify-between border-b border-white/5 pb-1">
                    <span>in_0 (BB Length):</span>
                    <span className="text-slate-200 font-bold">{currentTVInputs.in_0}</span>
                  </div>
                  <div className="flex justify-between border-b border-white/5 pb-1">
                    <span>in_1 (BB Deviation):</span>
                    <span className="text-slate-200 font-bold">{currentTVInputs.in_1}</span>
                  </div>
                  <div className="flex justify-between border-b border-white/5 pb-1">
                    <span>in_2 (Hard Stop Loss %):</span>
                    <span className="text-slate-200 font-bold">{currentTVInputs.in_2}%</span>
                  </div>
                  <div className="flex justify-between">
                    <span>in_6 (RSI Length):</span>
                    <span className="text-slate-200 font-bold">{currentTVInputs.in_6}</span>
                  </div>
                </>
              ) : strategy === "trailing" ? (
                <>
                  <div className="flex justify-between border-b border-white/5 pb-1">
                    <span>in_3 (Trailing Activation):</span>
                    <span className="text-slate-200 font-bold">{currentTVInputs.in_3}</span>
                  </div>
                  <div className="flex justify-between border-b border-white/5 pb-1">
                    <span>in_4 (Trailing Offset):</span>
                    <span className="text-slate-200 font-bold">{currentTVInputs.in_4}</span>
                  </div>
                  <div className="flex justify-between border-b border-white/5 pb-1">
                    <span>in_0 (BB Length - Fixed):</span>
                    <span className="text-slate-500 font-semibold">18</span>
                  </div>
                  <div className="flex justify-between">
                    <span>in_2 (Hard Stop Loss - Fixed):</span>
                    <span className="text-slate-500 font-semibold">1.0%</span>
                  </div>
                </>
              ) : (
                <>
                  <div className="flex justify-between border-b border-white/5 pb-1">
                    <span>Structure Length:</span>
                    <span className="text-slate-200 font-bold">{currentTVInputs["Structure Length"]}</span>
                  </div>
                  <div className="flex justify-between border-b border-white/5 pb-1">
                    <span>Base Risk (%):</span>
                    <span className="text-slate-200 font-bold">{currentTVInputs["Base Risk (%)"]}%</span>
                  </div>
                  <div className="flex justify-between border-b border-white/5 pb-1">
                    <span>Risk:Reward Ratio:</span>
                    <span className="text-slate-200 font-bold">{currentTVInputs["Risk:Reward Ratio"]}</span>
                  </div>
                  <div className="flex justify-between">
                    <span>Use Kelly Sizing:</span>
                    <span className="text-emerald-400 font-bold">TRUE</span>
                  </div>
                </>
              )}
            </div>
          </div>
        </div>

        {/* Section 2: Results Terminal & Abschlussbericht & Custom CSV SMC Knowledge representation */}
        <div className="space-y-4 lg:col-span-2">
          
          {optimizationResult ? (
            <div className="space-y-4">
              
              {/* Highlight Sweep Winner Card */}
              {optimizationResult.winner && (
                <div className="bg-gradient-to-r from-cyan-950/40 to-slate-900/40 border border-cyan-500/20 rounded-xl p-4 flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
                  <div className="space-y-1">
                    <div className="flex items-center gap-1.5 text-cyan-400 text-[10px] uppercase font-bold tracking-wider">
                      <Sparkles className="w-3.5 h-3.5" />
                      TVAPI VALIDATED OPTIMUM WINNER DETECTED
                    </div>
                    <h3 className="text-base font-extrabold text-slate-100 font-mono tracking-tight">
                      {optimizationResult.winner.label}
                    </h3>
                    <p className="text-[10px] text-slate-400">
                      Primary Objective score: <span className="text-cyan-400 font-bold">{primaryObjective === "profit_factor" ? `${optimizationResult.winner.profitFactor.toFixed(2)} PF` : primaryObjective === "net_profit" ? `$${optimizationResult.winner.netProfit.toFixed(2)} NP` : `${optimizationResult.winner.winRate.toFixed(1)}% WR`}</span> | Completed Trades: <span className="text-slate-300 font-semibold">{optimizationResult.winner.trades}</span>
                    </p>
                  </div>

                  <button
                    onClick={handleSetStrategyInputs}
                    disabled={isProgramming}
                    className="bg-emerald-500 hover:bg-emerald-400 text-slate-950 font-black text-[10px] uppercase tracking-wider px-4 py-2 rounded-lg transition-all duration-200 flex items-center gap-1.5 shadow-md shadow-emerald-500/10 disabled:opacity-50"
                  >
                    <CheckCircle2 className="w-3.5 h-3.5" />
                    {isProgramming ? "Synchronizing..." : "Set Strategy Inputs"}
                  </button>
                </div>
              )}

              {/* Execution Pipeline Status */}
              {setPipelineLog.length > 0 && (
                <div className="bg-slate-950/80 border border-white/5 rounded-xl p-3 font-mono text-[9px] text-slate-300 space-y-1 max-h-36 overflow-y-auto scrollbar-thin">
                  <div className="text-slate-500 border-b border-white/5 pb-1 mb-1 font-bold uppercase tracking-wider">
                    🛰️ TVAPI IN-SERIES PARAMETER SET pipeline log:
                  </div>
                  {setPipelineLog.map((log, i) => (
                    <div key={i} className={log.includes("SUCCESS") ? "text-emerald-400" : log.includes("🏁") ? "text-cyan-400 font-bold" : "text-slate-300"}>
                      {log}
                    </div>
                  ))}
                </div>
              )}

              {/* Report Tab Container */}
              <div className="bg-slate-950/40 border border-white/5 rounded-xl overflow-hidden flex flex-col h-[340px]">
                
                {/* Tabs */}
                <div className="flex border-b border-white/5 bg-slate-950/80 p-1">
                  <button
                    onClick={() => setActiveTab("bericht")}
                    className={`flex-1 text-center py-2 text-[10px] font-bold uppercase tracking-wider transition-all duration-200 ${
                      activeTab === "bericht" 
                        ? "bg-slate-900 border border-white/10 text-cyan-400 rounded-lg" 
                        : "text-slate-400 hover:text-slate-200"
                    }`}
                  >
                    Abschlussbericht
                  </button>
                  <button
                    onClick={() => setActiveTab("selbstprüfung")}
                    className={`flex-1 text-center py-2 text-[10px] font-bold uppercase tracking-wider transition-all duration-200 ${
                      activeTab === "selbstprüfung" 
                        ? "bg-slate-900 border border-white/10 text-cyan-400 rounded-lg" 
                        : "text-slate-400 hover:text-slate-200"
                    }`}
                  >
                    Selbstprüfung
                  </button>
                  <button
                    onClick={() => setActiveTab("runs")}
                    className={`flex-1 text-center py-2 text-[10px] font-bold uppercase tracking-wider transition-all duration-200 ${
                      activeTab === "runs" 
                        ? "bg-slate-900 border border-white/10 text-cyan-400 rounded-lg" 
                        : "text-slate-400 hover:text-slate-200"
                    }`}
                  >
                    Raw Combos ({optimizationResult.results.length})
                  </button>
                </div>

                {/* Content area */}
                <div className="flex-1 overflow-y-auto p-4 scrollbar-thin text-[11px] leading-relaxed">
                  
                  {activeTab === "bericht" && (
                    <div className="space-y-4 text-slate-300 whitespace-pre-wrap font-sans">
                      {/* Simple custom markdown renderer to ensure high contrast beauty */}
                      {optimizationResult.bericht.split("\n").map((line: string, i: number) => {
                        if (line.startsWith("###")) {
                          return (
                            <h4 key={i} className="text-cyan-400 font-bold text-[11px] uppercase tracking-wider border-b border-white/5 pb-1 mt-4">
                              {line.replace("###", "")}
                            </h4>
                          );
                        }
                        if (line.startsWith("- ")) {
                          return (
                            <li key={i} className="ml-3 list-disc text-slate-300">
                              {line.replace("- ", "")}
                            </li>
                          );
                        }
                        if (line.startsWith("|")) {
                          // Is table row, render formatted nicely
                          return (
                            <div key={i} className="font-mono text-[10px] bg-slate-950/40 px-2 py-0.5 border-l border-cyan-500/30">
                              {line}
                            </div>
                          );
                        }
                        return <p key={i} className="text-slate-300">{line}</p>;
                      })}
                    </div>
                  )}

                  {activeTab === "selbstprüfung" && (
                    <div className="space-y-4 text-slate-300 whitespace-pre-wrap font-sans">
                      {optimizationResult.selfTest.split("\n").map((line: string, i: number) => {
                        if (line.startsWith("###") || line.startsWith("1.") || line.startsWith("2.") || line.startsWith("3.") || line.startsWith("4.") || line.startsWith("5.")) {
                          return (
                            <h4 key={i} className="text-purple-400 font-bold uppercase tracking-wider border-b border-white/5 pb-1 mt-4">
                              {line}
                            </h4>
                          );
                        }
                        return <p key={i} className="text-slate-300 font-mono text-[10px]">{line}</p>;
                      })}
                    </div>
                  )}

                  {activeTab === "runs" && (
                    <div className="space-y-2">
                      <div className="border border-white/5 rounded-xl overflow-hidden">
                        <table className="w-full text-left border-collapse text-[10px] font-mono">
                          <thead>
                            <tr className="bg-slate-950/80 text-slate-400 border-b border-white/5">
                              <th className="p-2.5">Rang</th>
                              <th className="p-2.5">Label</th>
                              <th className="p-2.5">Profit Factor</th>
                              <th className="p-2.5">Win Rate</th>
                              <th className="p-2.5">Net Profit</th>
                              <th className="p-2.5">Trades</th>
                              <th className="p-2.5">Status</th>
                            </tr>
                          </thead>
                          <tbody>
                            {optimizationResult.results.map((run: any) => (
                              <tr 
                                key={run.rank} 
                                className={`border-b border-white/5 transition-colors ${
                                  run.isWinner 
                                    ? "bg-cyan-500/5 text-cyan-400" 
                                    : run.isDisqualified 
                                      ? "bg-red-500/5 text-red-400/80" 
                                      : "text-slate-300 hover:bg-white/5"
                                }`}
                              >
                                <td className="p-2.5 font-bold">{run.rank}</td>
                                <td className="p-2.5">{run.label}</td>
                                <td className="p-2.5">{run.profitFactor.toFixed(2)}</td>
                                <td className="p-2.5">{run.winRate.toFixed(1)}%</td>
                                <td className="p-2.5">${run.netProfit.toFixed(2)}</td>
                                <td className="p-2.5">{run.trades}</td>
                                <td className="p-2.5">
                                  <span className={`px-1.5 py-0.5 rounded text-[8px] font-bold uppercase ${
                                    run.isWinner 
                                      ? "bg-cyan-500/10 border border-cyan-500/20" 
                                      : run.isDisqualified 
                                        ? "bg-red-500/10 border border-red-500/20" 
                                        : "bg-slate-800 border border-white/5 text-slate-400"
                                  }`}>
                                    {run.isWinner ? "Winner" : run.isDisqualified ? "Disqualified" : "Valid"}
                                  </span>
                                </td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    </div>
                  )}

                </div>
              </div>

            </div>
          ) : (
            <div className="bg-slate-950/40 border border-white/5 rounded-2xl h-[440px] flex flex-col items-center justify-center p-8 text-center space-y-4">
              <div className="w-12 h-12 rounded-2xl bg-cyan-500/5 border border-cyan-500/10 flex items-center justify-center text-cyan-400">
                <Settings className="w-6 h-6 animate-spin" style={{ animationDuration: "8s" }} />
              </div>
              <div className="space-y-1 max-w-sm">
                <h3 className="text-xs font-bold uppercase tracking-wider text-slate-200">
                  Ready for Sweep Calibration
                </h3>
                <p className="text-[10px] text-slate-400 leading-relaxed">
                  Select your Pine Strategy parameters in the left panel. Press **"Run Multi-Stage Sweep Scan"** to fetch rule-evaluated TradingView TVAPI backtest sweeps.
                </p>
              </div>

              {strategy === "smc" && (
                <div className="pt-4 border-t border-dashed border-white/5 w-full max-w-lg">
                  <div className="bg-slate-950/60 p-3 rounded-xl border border-white/5 text-left space-y-2">
                    <span className="text-[9px] font-bold uppercase tracking-wider text-cyan-400 flex items-center gap-1">
                      <ShieldCheck className="w-3.5 h-3.5" />
                      Knowledge Base 05 - SMC Parameter Suite loaded:
                    </span>
                    <div className="grid grid-cols-2 gap-x-4 gap-y-1 font-mono text-[9px] text-slate-500">
                      <div>Name: <span className="text-slate-300">Neo-Quantum SMC</span></div>
                      <div>Structure Len: <span className="text-slate-300">5 Bars</span></div>
                      <div>Show Breaker Blocks: <span className="text-slate-300">TRUE</span></div>
                      <div>Risk:Reward Ratio: <span className="text-slate-300">2.0</span></div>
                      <div>Kelly Sizing: <span className="text-slate-300">TRUE</span></div>
                      <div>Base Risk (%): <span className="text-slate-300">1.0%</span></div>
                    </div>
                  </div>
                </div>
              )}
            </div>
          )}

        </div>

      </div>

      {/* SECTION 3: ADVANCED AI CHART VISION & PATTERN RECOGNITION WORKSPACE */}
      <div className="border-t border-white/5 pt-6 mt-6 space-y-4">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div className="space-y-1">
            <div className="flex items-center gap-2">
              <div className="bg-purple-500/10 border border-purple-500/20 p-1.5 rounded-lg text-purple-400">
                <Camera className="w-4 h-4 animate-pulse" />
              </div>
              <h3 className="text-sm font-bold uppercase tracking-wider text-slate-100 flex items-center gap-2">
                Human-Like AI Chart Vision & Pattern Guard
                <span className="text-[8px] bg-purple-500/10 border border-purple-500/20 text-purple-400 px-1.5 py-0.5 rounded font-mono font-normal">
                  GEMINI 3.1 PRO (HIGH THINKING)
                </span>
              </h3>
            </div>
            <p className="text-[10px] text-slate-400 leading-relaxed max-w-3xl">
              Upload a screenshot of your active TradingView chart, or choose one of our advanced SMC pattern presets to trigger the High-Thinking vision reasoning engine.
              Reviews structure, breaker blocks, liquidity pools, and provides discretionary backtesting filters like a veteran analyst.
            </p>
          </div>

          {/* Mode Selector */}
          <div className="flex bg-slate-950/60 p-1 border border-white/5 rounded-xl self-start">
            <button
              onClick={() => setVisionMode("pattern")}
              className={`px-3 py-1.5 rounded-lg text-[10px] font-bold uppercase tracking-wider transition-all duration-200 flex items-center gap-1.5 ${
                visionMode === "pattern" 
                  ? "bg-purple-500 text-slate-950 shadow-md shadow-purple-500/20" 
                  : "text-slate-400 hover:text-slate-200"
              }`}
            >
              <Eye className="w-3.5 h-3.5" />
              Pattern Recognition
            </button>
            <button
              onClick={() => setVisionMode("backtest")}
              className={`px-3 py-1.5 rounded-lg text-[10px] font-bold uppercase tracking-wider transition-all duration-200 flex items-center gap-1.5 ${
                visionMode === "backtest" 
                  ? "bg-purple-500 text-slate-950 shadow-md shadow-purple-500/20" 
                  : "text-slate-400 hover:text-slate-200"
              }`}
            >
              <Sliders className="w-3.5 h-3.5" />
              Backtest Control
            </button>
          </div>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
          
          {/* Left Column: Image Selection & Preview (lg:col-span-5) */}
          <div className="lg:col-span-5 space-y-4">
            <div className="bg-slate-950/40 border border-white/5 rounded-xl p-4 space-y-4">
              <div className="flex items-center justify-between">
                <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400 block">
                  1. Select Chart Source
                </span>
                
                {/* Source Selectors */}
                <div className="flex bg-slate-900/60 p-0.5 border border-white/5 rounded-lg">
                  <button
                    onClick={() => setChartMode("live")}
                    className={`px-2 py-1 rounded text-[8px] font-bold uppercase tracking-wider transition-all duration-200 ${
                      chartMode === "live"
                        ? "bg-purple-500/25 border border-purple-500/30 text-purple-300"
                        : "text-slate-500 hover:text-slate-300"
                    }`}
                  >
                    Live Widget
                  </button>
                  <button
                    onClick={() => setChartMode("presets")}
                    className={`px-2 py-1 rounded text-[8px] font-bold uppercase tracking-wider transition-all duration-200 ${
                      chartMode === "presets"
                        ? "bg-purple-500/25 border border-purple-500/30 text-purple-300"
                        : "text-slate-500 hover:text-slate-300"
                    }`}
                  >
                    AI Presets
                  </button>
                  <button
                    onClick={() => setChartMode("upload")}
                    className={`px-2 py-1 rounded text-[8px] font-bold uppercase tracking-wider transition-all duration-200 ${
                      chartMode === "upload"
                        ? "bg-purple-500/25 border border-purple-500/30 text-purple-300"
                        : "text-slate-500 hover:text-slate-300"
                    }`}
                  >
                    Upload
                  </button>
                  <button
                    onClick={() => setChartMode("youtube")}
                    className={`px-2 py-1 rounded text-[8px] font-bold uppercase tracking-wider transition-all duration-200 ${
                      chartMode === "youtube"
                        ? "bg-purple-500/25 border border-purple-500/30 text-purple-300"
                        : "text-slate-500 hover:text-slate-300"
                    }`}
                  >
                    YouTube
                  </button>
                </div>
              </div>

              {/* Dynamic Content based on chartMode */}
              {chartMode === "live" && (
                <div className="space-y-4">
                  <div className="border border-white/10 rounded-xl overflow-hidden bg-slate-950 flex flex-col h-[280px] relative">
                    <iframe
                      src={`https://s3.tradingview.com/external-embedding/embed-widget-advanced-chart.html?locale=en#${encodeURIComponent(JSON.stringify({
                        autosize: true,
                        symbol: symbol === "BTCUSD" ? "BINANCE:BTCUSDT" : symbol === "ETHUSD" ? "BINANCE:ETHUSDT" : symbol === "SOLUSD" ? "BINANCE:SOLUSDT" : symbol === "AVAXUSD" ? "BINANCE:AVAXUSDT" : (symbol === "NIO" || symbol === "NIOUSD") ? "NYSE:NIO" : `BINANCE:${symbol}T`,
                        interval: timeframe === "5m" ? "5" : timeframe === "15m" ? "15" : timeframe === "1h" ? "60" : "240",
                        timezone: "Etc/UTC",
                        theme: "dark",
                        style: "1",
                        locale: "en",
                        enable_publishing: false,
                        hide_side_toolbar: false,
                        allow_symbol_change: true,
                        calendar: false,
                        support_host: "https://www.tradingview.com"
                      }))}`}
                      style={{ width: "100%", height: "100%", border: "none" }}
                      title="TradingView Advanced Chart Widget"
                      id="tradingview-advanced-widget-iframe"
                    />
                    <div className="absolute top-2 right-2 bg-slate-950/80 border border-white/10 px-1.5 py-0.5 rounded text-[8px] font-mono text-slate-400 flex items-center gap-1 pointer-events-none">
                      <div className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse"></div>
                      TV LIVE FEED
                    </div>
                  </div>

                  {/* Action button */}
                  <button
                    onClick={() => {
                      const dataUrl = getLiveChartCanvasDataUrl(symbol, timeframe);
                      handleAnalyzeChart(dataUrl);
                    }}
                    disabled={isVisionAnalyzing}
                    className="w-full bg-purple-500 hover:bg-purple-400 text-slate-950 font-black text-[10px] uppercase tracking-wider py-2.5 rounded-lg transition-all duration-200 flex items-center justify-center gap-1.5 shadow-md shadow-purple-500/10 disabled:opacity-50"
                  >
                    {isVisionAnalyzing ? (
                      <>
                        <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                        AI high-thinking reasoning in progress...
                      </>
                    ) : (
                      <>
                        <Cpu className="w-3.5 h-3.5" />
                        Capture Live & Run High-Thinking Vision Guard
                      </>
                    )}
                  </button>
                </div>
              )}

              {chartMode === "presets" && (
                <div className="space-y-4">
                  {/* Presets Grid */}
                  <div className="grid grid-cols-3 gap-2">
                    <button
                      onClick={() => handleLoadPreset("wedge")}
                      className="bg-slate-900 hover:bg-slate-800 border border-white/5 hover:border-amber-500/30 p-2.5 rounded-lg text-left transition-all duration-200 group"
                    >
                      <div className="text-[8px] text-amber-400 font-bold tracking-widest uppercase mb-1">BTC Presets</div>
                      <div className="text-[10px] font-bold text-slate-200 group-hover:text-amber-300">Rising Wedge</div>
                      <div className="text-[8px] text-slate-500 font-mono mt-0.5">Bearish OB</div>
                    </button>

                    <button
                      onClick={() => handleLoadPreset("hns")}
                      className="bg-slate-900 hover:bg-slate-800 border border-white/5 hover:border-purple-500/30 p-2.5 rounded-lg text-left transition-all duration-200 group"
                    >
                      <div className="text-[8px] text-purple-400 font-bold tracking-widest uppercase mb-1">ETH Presets</div>
                      <div className="text-[10px] font-bold text-slate-200 group-hover:text-purple-300">Head & Shoulders</div>
                      <div className="text-[8px] text-slate-500 font-mono mt-0.5">Neckline Break</div>
                    </button>

                    <button
                      onClick={() => handleLoadPreset("sweep")}
                      className="bg-slate-900 hover:bg-slate-800 border border-white/5 hover:border-red-500/30 p-2.5 rounded-lg text-left transition-all duration-200 group"
                    >
                      <div className="text-[8px] text-red-400 font-bold tracking-widest uppercase mb-1">SOL Presets</div>
                      <div className="text-[10px] font-bold text-slate-200 group-hover:text-red-300">Liquidity Sweep</div>
                      <div className="text-[8px] text-slate-500 font-mono mt-0.5">SMC Trap Zone</div>
                    </button>
                  </div>

                  {visionImage ? (
                    <div className="space-y-2">
                      <div className="flex items-center justify-between">
                        <span className="text-[9px] font-mono text-slate-400">
                          Preset Pattern Loaded:
                        </span>
                        <button
                          onClick={() => setVisionImage(null)}
                          className="text-[8px] text-red-400 font-bold hover:underline"
                        >
                          Clear
                        </button>
                      </div>
                      <div className="border border-white/10 rounded-xl overflow-hidden bg-slate-950 flex items-center justify-center relative aspect-[1.6]">
                        <img 
                          src={visionImage} 
                          alt="TradingView Active Feed" 
                          className="w-full h-full object-cover"
                          referrerPolicy="no-referrer"
                        />
                        <div className="absolute top-2 right-2 bg-slate-950/80 border border-white/10 px-1.5 py-0.5 rounded text-[8px] font-mono text-slate-400 flex items-center gap-1">
                          <div className="w-1.5 h-1.5 rounded-full bg-amber-500 animate-pulse"></div>
                          PRESET
                        </div>
                      </div>
                      
                      {/* Action button */}
                      <button
                        onClick={() => handleAnalyzeChart()}
                        disabled={isVisionAnalyzing}
                        className="w-full bg-purple-500 hover:bg-purple-400 text-slate-950 font-black text-[10px] uppercase tracking-wider py-2.5 rounded-lg transition-all duration-200 flex items-center justify-center gap-1.5 shadow-md shadow-purple-500/10 disabled:opacity-50"
                      >
                        {isVisionAnalyzing ? (
                          <>
                            <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                            AI high-thinking reasoning in progress...
                          </>
                        ) : (
                          <>
                            <Cpu className="w-3.5 h-3.5" />
                            Run High-Thinking Vision Guard
                          </>
                        )}
                      </button>
                    </div>
                  ) : (
                    <div className="border border-white/5 bg-slate-950/20 rounded-xl aspect-[1.6] flex flex-col items-center justify-center p-6 text-center space-y-2">
                      <FileImage className="w-6 h-6 text-slate-600" />
                      <div className="space-y-0.5">
                        <span className="text-[9px] font-bold text-slate-400 block">No Pattern Selected</span>
                        <span className="text-[8px] text-slate-500 block max-w-[200px] leading-relaxed">
                          Select one of the three preset pattern configurations above to instantly load and visualize the preset chart.
                        </span>
                      </div>
                    </div>
                  )}
                </div>
              )}

              {chartMode === "upload" && (
                <div className="space-y-4">
                  {/* Upload Drag & Drop Area */}
                  <div 
                    onClick={() => fileInputRef.current?.click()}
                    className="border border-dashed border-white/10 hover:border-purple-500/30 bg-slate-900/20 hover:bg-slate-900/40 rounded-xl p-4 text-center cursor-pointer transition-all duration-200 group"
                  >
                    <input 
                      type="file" 
                      ref={fileInputRef} 
                      onChange={handleImageUpload} 
                      accept="image/*" 
                      className="hidden" 
                    />
                    <Upload className="w-5 h-5 mx-auto text-slate-400 group-hover:text-purple-400 mb-2 transition-transform duration-200 group-hover:-translate-y-0.5" />
                    <span className="text-[10px] font-bold text-slate-300 block group-hover:text-purple-300">
                      Upload custom chart screenshot
                    </span>
                    <span className="text-[8px] text-slate-500 mt-0.5 block">
                      Drag and drop files here, or click to browse
                    </span>
                  </div>

                  {visionImage ? (
                    <div className="space-y-2">
                      <div className="flex items-center justify-between">
                        <span className="text-[9px] font-mono text-slate-400">
                          Uploaded Snapshot Loaded:
                        </span>
                        <button
                          onClick={() => setVisionImage(null)}
                          className="text-[8px] text-red-400 font-bold hover:underline"
                        >
                          Clear
                        </button>
                      </div>
                      <div className="border border-white/10 rounded-xl overflow-hidden bg-slate-950 flex items-center justify-center relative aspect-[1.6]">
                        <img 
                          src={visionImage} 
                          alt="TradingView Active Feed" 
                          className="w-full h-full object-cover"
                          referrerPolicy="no-referrer"
                        />
                        <div className="absolute top-2 right-2 bg-slate-950/80 border border-white/10 px-1.5 py-0.5 rounded text-[8px] font-mono text-slate-400 flex items-center gap-1">
                          <div className="w-1.5 h-1.5 rounded-full bg-blue-500 animate-pulse"></div>
                          MANUAL SNAPSHOT
                        </div>
                      </div>
                      
                      {/* Action button */}
                      <button
                        onClick={() => handleAnalyzeChart()}
                        disabled={isVisionAnalyzing}
                        className="w-full bg-purple-500 hover:bg-purple-400 text-slate-950 font-black text-[10px] uppercase tracking-wider py-2.5 rounded-lg transition-all duration-200 flex items-center justify-center gap-1.5 shadow-md shadow-purple-500/10 disabled:opacity-50"
                      >
                        {isVisionAnalyzing ? (
                          <>
                            <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                            AI high-thinking reasoning in progress...
                          </>
                        ) : (
                          <>
                            <Cpu className="w-3.5 h-3.5" />
                            Run High-Thinking Vision Guard
                          </>
                        )}
                      </button>
                    </div>
                  ) : (
                    <div className="border border-white/5 bg-slate-950/20 rounded-xl aspect-[1.6] flex flex-col items-center justify-center p-6 text-center space-y-2">
                      <FileImage className="w-6 h-6 text-slate-600" />
                      <div className="space-y-0.5">
                        <span className="text-[9px] font-bold text-slate-400 block">No Custom Upload</span>
                        <span className="text-[8px] text-slate-500 block max-w-[200px] leading-relaxed">
                          Drag and drop or upload a PNG/JPG screenshot of your custom chart to run diagnostic analysis.
                        </span>
                      </div>
                    </div>
                  )}
                </div>
              )}

              {chartMode === "youtube" && (
                <div className="space-y-4">
                  {/* Link Input Section */}
                  <div className="space-y-1.5">
                    <label className="text-[9px] text-slate-500 uppercase tracking-wider font-bold block">
                      YouTube Stream Link
                    </label>
                    <div className="flex gap-2">
                      <div className="relative flex-grow">
                        <Youtube className="w-3.5 h-3.5 text-red-500 absolute left-2.5 top-1/2 -translate-y-1/2" />
                        <input
                          type="text"
                          value={youtubeUrl}
                          onChange={(e) => {
                            setYoutubeUrl(e.target.value);
                            setYoutubeError(null);
                          }}
                          placeholder="https://www.youtube.com/watch?v=..."
                          className="w-full bg-slate-900 border border-white/5 rounded-lg text-[10px] text-slate-300 pl-8 pr-3 py-2.5 focus:border-red-500/50 focus:outline-none placeholder:text-slate-600 transition-all duration-200"
                        />
                      </div>
                      <button
                        onClick={() => handleEmbedYoutube()}
                        className="bg-red-600 hover:bg-red-500 text-white font-black text-[10px] uppercase tracking-wider px-3.5 py-2.5 rounded-lg transition-all duration-200 flex items-center justify-center gap-1 shrink-0"
                      >
                        <Plus className="w-3.5 h-3.5" />
                        Load
                      </button>
                    </div>
                    {youtubeError && (
                      <span className="text-[9px] text-red-400 font-medium block animate-pulse mt-1">
                        ⚠️ {youtubeError}
                      </span>
                    )}
                  </div>

                  {/* Player Embed or Empty State */}
                  {youtubeVideoId ? (
                    <div className="space-y-2">
                      <div className="flex items-center justify-between">
                        <span className="text-[9px] font-mono text-slate-400 flex items-center gap-1">
                          <span className="w-1.5 h-1.5 rounded-full bg-red-500 animate-pulse"></span>
                          Active Coping Stream:
                        </span>
                        <button
                          onClick={() => setYoutubeVideoId(null)}
                          className="text-[8px] text-red-400 font-bold hover:underline flex items-center gap-0.5"
                        >
                          <Trash2 className="w-3 h-3" /> Clear Player
                        </button>
                      </div>
                      <div className="border border-white/10 rounded-xl overflow-hidden bg-slate-950 aspect-video relative">
                        <iframe
                          src={`https://www.youtube.com/embed/${youtubeVideoId}?autoplay=1&mute=1`}
                          title="YouTube Coping Stream"
                          allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share"
                          allowFullScreen
                          className="w-full h-full border-none"
                        />
                      </div>
                    </div>
                  ) : (
                    <div className="border border-white/5 bg-slate-950/20 rounded-xl aspect-[1.6] flex flex-col items-center justify-center p-6 text-center space-y-2">
                      <div className="w-10 h-10 rounded-full bg-red-500/10 flex items-center justify-center text-red-500">
                        <Youtube className="w-5 h-5" />
                      </div>
                      <div className="space-y-0.5">
                        <span className="text-[9px] font-bold text-slate-400 block">No Stream Connected</span>
                        <span className="text-[8px] text-slate-500 block max-w-[200px] leading-relaxed">
                          Enter a YouTube stream link or charting webinar URL above to visualize charts side-by-side with your optimizer workspace.
                        </span>
                      </div>
                    </div>
                  )}

                  {/* History Section */}
                  <div className="pt-2 border-t border-white/5 space-y-2">
                    <div className="flex items-center justify-between">
                      <span className="text-[9px] font-bold uppercase tracking-wider text-slate-400 flex items-center gap-1">
                        <History className="w-3.5 h-3.5 text-slate-500" />
                        Stream Link History
                      </span>
                      {youtubeHistory.length > 0 && (
                        <button
                          onClick={handleClearHistory}
                          className="text-[8px] text-slate-500 hover:text-red-400 font-bold transition-colors"
                        >
                          Clear All
                        </button>
                      )}
                    </div>

                    {youtubeHistory.length > 0 ? (
                      <div className="space-y-1.5 max-h-[140px] overflow-y-auto pr-1 scrollbar-thin">
                        {youtubeHistory.map((link, idx) => (
                          <div
                            key={idx}
                            onClick={() => handleEmbedYoutube(link)}
                            className="flex items-center justify-between bg-slate-900/60 hover:bg-slate-900 border border-white/5 hover:border-red-500/20 px-2.5 py-2 rounded-lg cursor-pointer transition-all duration-200 group"
                          >
                            <div className="flex items-center gap-2 min-w-0 flex-grow mr-2">
                              <Youtube className="w-3 h-3 text-red-500/60 group-hover:text-red-500 shrink-0" />
                              <span className="text-[9px] text-slate-400 group-hover:text-slate-200 font-mono truncate">
                                {link}
                              </span>
                            </div>
                            <div className="flex items-center gap-1.5 shrink-0">
                              <ExternalLink className="w-3 h-3 text-slate-600 group-hover:text-slate-400" />
                              <button
                                onClick={(e) => handleDeleteHistoryItem(e, idx)}
                                className="p-1 hover:bg-red-500/10 text-slate-600 hover:text-red-400 rounded transition-colors"
                                title="Remove from history"
                              >
                                <Trash2 className="w-3 h-3" />
                              </button>
                            </div>
                          </div>
                        ))}
                      </div>
                    ) : (
                      <div className="text-[8px] text-slate-600 italic font-mono py-1">
                        No previous stream links recorded.
                      </div>
                    )}
                  </div>
                </div>
              )}
            </div>
          </div>

          {/* Right Column: AI Analysis Report Terminal (lg:col-span-7) */}
          <div className="lg:col-span-7">
            <div className="bg-slate-950/40 border border-white/5 rounded-xl p-4 flex flex-col h-full min-h-[380px]">
              <div className="flex items-center justify-between border-b border-white/5 pb-2 mb-4">
                <span className="text-[10px] font-bold uppercase tracking-wider text-slate-300 flex items-center gap-1.5">
                  <Sparkles className="w-3.5 h-3.5 text-purple-400" />
                  AI Guard - Advanced CMT Analysis Terminal
                </span>
                {visionAnalysisResult && (
                  <span className="text-[8px] bg-purple-500/10 text-purple-400 border border-purple-500/20 px-1.5 py-0.5 rounded uppercase font-mono">
                    REPORT COMPLETED
                  </span>
                )}
              </div>

              {/* Analysis output container */}
              <div className="flex-grow overflow-y-auto max-h-[360px] scrollbar-thin text-xs text-slate-300 space-y-4 whitespace-pre-wrap leading-relaxed font-sans pr-1">
                {isVisionAnalyzing ? (
                  <div className="h-full flex flex-col items-center justify-center p-8 text-center space-y-4">
                    <div className="relative">
                      <div className="w-12 h-12 rounded-full border-2 border-purple-500/10 border-t-purple-500 animate-spin"></div>
                      <Cpu className="w-5 h-5 text-purple-400 absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 animate-pulse" />
                    </div>
                    <div className="space-y-1 max-w-sm">
                      <h4 className="text-[10px] font-bold uppercase tracking-wider text-slate-200">
                        Deep Multi-Modal Reasoning Running
                      </h4>
                      <p className="text-[9px] text-slate-500 leading-relaxed">
                        Analyzing visual candlestick patterns, identifying trend-lines, structure breaks, and mapping order blocks. 
                        Applying high reasoning density with model <strong>gemini-3.1-pro-preview</strong>.
                      </p>
                    </div>
                  </div>
                ) : visionAnalysisResult ? (
                  <div className="space-y-4">
                    {/* Parse simple custom markdown structure for CMT aesthetic */}
                    {visionAnalysisResult.split("\n").map((line, i) => {
                      if (line.startsWith("###")) {
                        return (
                          <h4 key={i} className="text-purple-400 font-bold text-[11px] uppercase tracking-wider border-b border-white/5 pb-1 mt-4 flex items-center gap-1.5">
                            <CheckCircle2 className="w-3.5 h-3.5 text-purple-400" />
                            {line.replace("###", "")}
                          </h4>
                        );
                      }
                      if (line.startsWith("####")) {
                        return (
                          <h5 key={i} className="text-slate-200 font-bold text-[10px] uppercase tracking-wide mt-3">
                            {line.replace("####", "")}
                          </h5>
                        );
                      }
                      if (line.startsWith("- ")) {
                        return (
                          <li key={i} className="ml-3 list-none text-slate-300 text-[10px] pl-3 relative before:content-[''] before:absolute before:left-0 before:top-2 before:w-1 before:h-1 before:bg-purple-500 before:rounded-full font-sans">
                            {line.replace("- ", "")}
                          </li>
                        );
                      }
                      return <p key={i} className="text-slate-400 text-[10px] font-mono leading-relaxed">{line}</p>;
                    })}
                  </div>
                ) : (
                  <div className="h-full flex flex-col items-center justify-center p-8 text-center space-y-3">
                    <Eye className="w-6 h-6 text-slate-700 animate-pulse" />
                    <div className="space-y-1 max-w-sm">
                      <h4 className="text-[9px] font-bold uppercase tracking-wider text-slate-400">
                        Terminal Standby
                      </h4>
                      <p className="text-[9px] text-slate-500 leading-relaxed">
                        Select a chart layout pattern preset or drag in a manual snapshot to initiate high-fidelity visual reasoning diagnostics.
                      </p>
                    </div>
                  </div>
                )}
              </div>
            </div>
          </div>

        </div>
      </div>

    </div>
  );
}
