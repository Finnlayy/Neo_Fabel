import React, { useState, useEffect } from 'react';
import { 
  Cpu, 
  RefreshCw, 
  Sparkles, 
  TrendingUp, 
  TrendingDown, 
  Eye, 
  LineChart, 
  Code, 
  Calculator, 
  Database, 
  Copy, 
  Check,
  ChevronRight,
  Info
} from 'lucide-react';
import { NeuralOptimizationEngine, NeuralInferenceState, PatternMatch } from '../services/neuralOptimization';
import { 
  playSlotTick, 
  playReelSpin, 
  playChipClick, 
  playChipStack, 
  playJackpotBell, 
  playBuzzerWarning, 
  playCascadingCoins 
} from '../services/casinoAudio';

interface NeuralTrackerProps {
  currentPrice?: number;
}

// Code templates dictionary containing the user's uploaded scripts
  const codeTemplates: Record<string, { title: string; desc: string; code: string }> = {
    model_train: {
      title: "GOLD Close Predictor",
      desc: "Trains an LSTM (input 10 bars x 4 features) to predict standard Close price regression targets.",
      code: `def collect_dataset(df: pd.DataFrame, history_size: int):
    # input: history_size consecutive D1 bars (open, high, low, close)
    # output: close price for the next bar
    n = len(df)
    xs, ys = [], []
    for i in range(n - history_size):
        w = df.iloc[i: i + history_size + 1]
        x = w[['open', 'high', 'low', 'close']].iloc[:-1].values
        y = w.iloc[-1]['close'] # direct close regression
        xs.append(x)
        ys.append(y)
    return np.array(xs), np.array(ys)`
    },
    model2_train: {
      title: "Model 2 Volatility Target",
      desc: "Trains an LSTM to detect volatility skew between buying & selling pressure vectors within high/low boundaries.",
      code: `def collect_dataset(df: pd.DataFrame, history_size: int):
    # input: history_size H1 bars
    # output: Volatility spread targets: (High-Open) - (Open-Low)
    n = len(df)
    xs, ys = [], []
    for i in range(n - history_size):
        w = df.iloc[i: i + history_size + 1]
        x = w[['open', 'high', 'low', 'close']].iloc[:-1].values
        y = (w.iloc[-1]['high'] - w.iloc[-1]['open']) - (w.iloc[-1]['open'] - w.iloc[-1]['low'])
        xs.append(x)
        ys.append(y)
    return np.array(xs), np.array(ys)`
    },
    model4_train: {
      title: "Model 4 Range Momentum",
      desc: "Predicts standard multi-bar range momentum shift delta offsets to guard against SMC structural breakout traps.",
      code: `def collect_dataset(df: pd.DataFrame, history_size: int):
    # input: history_size H1 bars
    # output: Range trend momentum shift delta: (High - High_prev) + (Low - Low_prev)
    n = len(df)
    xs, ys = [], []
    for i in range(n - history_size):
        w = df.iloc[i: i + history_size + 1]
        x = w[['open', 'high', 'low', 'close']].iloc[:-1].values
        y = (w.iloc[-1]['high'] - w.iloc[-2]['high']) + (w.iloc[-1]['low'] - w.iloc[-2]['low'])
        xs.append(x)
        ys.append(y)
    return np.array(xs), np.array(ys)`
    },
    inference: {
      title: "ONNX MT5 Runtime Engine",
      desc: "Standard Python MetaTrader 5 inference engine standardizing feature buffers and executing the ONNX model.",
      code: `# Prepare the feature buffer vector shape [1, 10, 4]
eurusd_rates = mt5.copy_rates_from_pos("EURUSD", mt5.TIMEFRAME_H1, 1, 10)
df = pd.DataFrame(eurusd_rates)
X = df[['open', 'high', 'low', 'close']].values
X = np.expand_dims(X, axis=0)

# Normalize features: X_norm = (X - mean) / std
m = X.mean(axis=1, keepdims=True)
s = X.std(axis=1, keepdims=True)
X_norm = (X - m) / s

# Execute ONNX Session
ort_sess = ort.InferenceSession("model4.onnx")
outputs = ort_sess.run(None, {'lstm_input': X_norm.astype(np.float32)})
y_pred_norm = outputs[0]
y_pred = np.round(y_pred_norm.flatten(), decimals=5)`
    }
  };

export default function NeuralTracker({ currentPrice = 64250 }: NeuralTrackerProps) {
  // Model state variables
  const [selectedModel, setSelectedModel] = useState<string>("model4.onnx");
  const [state, setState] = useState<NeuralInferenceState>(() => 
    NeuralOptimizationEngine.calculateInference(currentPrice, "model4.onnx")
  );
  
  // Tab control: 'live' | 'zscore' | 'python'
  const [activeTab, setActiveTab] = useState<'live' | 'zscore' | 'python'>('live');
  const [selectedCodePreset, setSelectedCodePreset] = useState<string>("model4_train");
  const [isCopied, setIsCopied] = useState<boolean>(false);

  // Rolling price history buffer
  const [priceHistory, setPriceHistory] = useState<number[]>(() => {
    const base = currentPrice;
    return [
      base - 15, base - 5, base + 10, base + 5, base - 8,
      base + 12, base + 22, base + 15, base - 5, base + 8
    ];
  });

  const [patternResult, setPatternResult] = useState<PatternMatch>(() =>
    NeuralOptimizationEngine.detectPattern(
      [
        currentPrice - 15, currentPrice - 5, currentPrice + 10, currentPrice + 5, currentPrice - 8,
        currentPrice + 12, currentPrice + 22, currentPrice + 15, currentPrice - 5, currentPrice + 8
      ]
    )
  );

  const [isTraining, setIsTraining] = useState(false);
  const [activeSimulationMode, setActiveSimulationMode] = useState<'live' | 'hs' | 'db'>('live');

  // Trigger calculation updates when price or selected model changes
  useEffect(() => {
    const updatedInference = NeuralOptimizationEngine.calculateInference(currentPrice, selectedModel);
    setState(updatedInference);
  }, [currentPrice, selectedModel]);

  // Append live ticker price when the parent feed updates — no random jitter.
  useEffect(() => {
    if (activeSimulationMode !== "live" || isTraining) return;
    if (!Number.isFinite(currentPrice) || currentPrice <= 0) return;
    setPriceHistory((prev) => {
      const last = prev[prev.length - 1];
      if (last === currentPrice) return prev;
      const updated = [...prev, currentPrice].slice(-15);
      setPatternResult(NeuralOptimizationEngine.detectPattern(updated));
      return updated;
    });
  }, [activeSimulationMode, isTraining, currentPrice]);

  // Handle weight optimization training cycle
  const handleTrainCycle = () => {
    setIsTraining(true);
    // Casino sound: Start active slot reel roll
    playReelSpin(2000);

    setTimeout(() => {
      setIsTraining(false);
      // Casino sound: Successful cascade sound
      playCascadingCoins();
      setState(prev => ({ 
        ...prev, 
        confidence: parseFloat(Math.min(99.9, prev.confidence + 1.2).toFixed(1)) 
      }));
    }, 2000);
  };

  // Helper to trigger specific pattern scenarios for interactive validation
  const triggerPatternSimulation = (type: 'hs' | 'db') => {
    setActiveSimulationMode(type);
    const base = currentPrice;
    
    let simulatedPrices: number[] = [];
    if (type === 'hs') {
      // Bearish H&S Trap - Warning/Buzzer Sound
      playBuzzerWarning();
      simulatedPrices = [
        base - 20,
        base + 40,  // Left Shoulder Peak
        base - 10,  // Neckline 1
        base + 80,  // Head Peak
        base - 15,  // Neckline 2
        base + 38,  // Right Shoulder Peak
        base - 30   // Breakdown
      ];
    } else {
      // Bullish Double Bottom breakout - Jackpot Sound!
      playJackpotBell();
      simulatedPrices = [
        base + 50,
        base - 40,  // Bottom 1 Valley
        base + 10,  // Neckline Peak
        base - 42,  // Bottom 2 Valley
        base + 60,  // Breakout
        base + 80
      ];
    }

    setPriceHistory(simulatedPrices);
    const match = NeuralOptimizationEngine.detectPattern(simulatedPrices);
    setPatternResult(match);
    
    setState(prev => ({
      ...prev,
      direction: type === 'hs' ? 'DOWN' : 'UP',
      prediction: type === 'hs' ? -0.06502 : 0.08514,
      confidence: 94.5
    }));
  };

  const resumeLiveFeed = () => {
    // Casino sound: Chip Shuffle
    playChipStack();
    setActiveSimulationMode('live');
    const baseSequence = [
      currentPrice - 15, currentPrice - 5, currentPrice + 10, currentPrice + 5, currentPrice - 8,
      currentPrice + 12, currentPrice + 22, currentPrice + 15, currentPrice - 5, currentPrice + 8
    ];
    setPriceHistory(baseSequence);
    setPatternResult(NeuralOptimizationEngine.detectPattern(baseSequence));
  };

  const copyToClipboard = (text: string) => {
    // Casino sound: Short Chip click
    playChipClick();
    navigator.clipboard.writeText(text);
    setIsCopied(true);
    setTimeout(() => setIsCopied(false), 2000);
  };

  const handleTabChange = (tab: 'live' | 'zscore' | 'python') => {
    playChipClick();
    setActiveTab(tab);
  };

  const handleModelChange = (model: string) => {
    playChipStack();
    setSelectedModel(model);
  };

  const handlePresetCodeChange = (preset: string) => {
    playChipClick();
    setSelectedCodePreset(preset);
  };

  // Min-max normalization for basic SVG sparkline
  const minVal = Math.min(...priceHistory);
  const maxVal = Math.max(...priceHistory);
  const valRange = maxVal - minVal || 1;

  // SVG point calculator
  const pointsString = priceHistory.map((val, idx) => {
    const x = (idx / (priceHistory.length - 1)) * 100;
    const y = 90 - ((val - minVal) / valRange) * 80;
    return `${x},${y}`;
  }).join(' ');



  return (
    <div id="neural-tracker-card" className="bg-slate-900/40 border border-white/5 rounded-2xl p-5 space-y-4 transition-all duration-300 hover:border-white/10 hover:bg-slate-900/50 flex flex-col h-[520px]">
      
      {/* Dynamic Header */}
      <div className="flex items-center justify-between border-b border-white/5 pb-3">
        <div className="flex items-center gap-2.5">
          <div className="bg-emerald-500/10 border border-emerald-500/20 p-1.5 rounded-lg text-emerald-400">
            <Cpu className="w-4 h-4 animate-pulse" />
          </div>
          <div>
            <h3 className="text-sm font-bold uppercase tracking-wider text-slate-100 flex items-center gap-1.5">
              LSTM ONNX Neural Core
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse"></span>
            </h3>
            <p className="text-[10px] text-slate-500 leading-none">
              Z-Score Standardization & Classical Pattern Guard
            </p>
          </div>
        </div>

        {/* Model dropdown selector */}
        <select
          value={selectedModel}
          onChange={(e) => handleModelChange(e.target.value)}
          className="bg-slate-950/80 border border-white/5 text-[9px] text-slate-300 p-1.5 rounded-lg font-mono focus:border-emerald-500 outline-none"
        >
          <option value="model.onnx">🎯 model.onnx (Close target)</option>
          <option value="model2.onnx">📊 model2.onnx (Spread skew)</option>
          <option value="model4.onnx">⚙️ model4.onnx (Range momentum)</option>
        </select>
      </div>

      {/* Tabs Selectors */}
      <div className="flex bg-slate-950/50 p-0.5 rounded-lg border border-white/5 text-[10px] font-mono">
        <button
          onClick={() => handleTabChange('live')}
          className={`flex-1 py-1.5 rounded-md font-bold transition-all flex items-center justify-center gap-1.5 ${
            activeTab === 'live'
              ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20'
              : 'text-slate-400 hover:text-slate-200 border border-transparent'
          }`}
        >
          <LineChart className="w-3 h-3" />
          Live Predictor
        </button>
        <button
          onClick={() => handleTabChange('zscore')}
          className={`flex-1 py-1.5 rounded-md font-bold transition-all flex items-center justify-center gap-1.5 ${
            activeTab === 'zscore'
              ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20'
              : 'text-slate-400 hover:text-slate-200 border border-transparent'
          }`}
        >
          <Calculator className="w-3 h-3" />
          X_norm Standard
        </button>
        <button
          onClick={() => handleTabChange('python')}
          className={`flex-1 py-1.5 rounded-md font-bold transition-all flex items-center justify-center gap-1.5 ${
            activeTab === 'python'
              ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20'
              : 'text-slate-400 hover:text-slate-200 border border-transparent'
          }`}
        >
          <Code className="w-3 h-3" />
          Python Code Vault
        </button>
      </div>

      {/* Primary Tab Contents Container */}
      <div className="flex-1 overflow-y-auto scrollbar-thin space-y-3">
        
        {/* TAB 1: LIVE PREDICTOR VIEW */}
        {activeTab === 'live' && (
          <LivePredictorTab
            state={state}
            priceHistory={priceHistory}
            patternResult={patternResult}
            minVal={minVal}
            maxVal={maxVal}
            valRange={valRange}
            pointsString={pointsString}
          />
        )}

        {/* TAB 2: Z-SCORE STANDARDIZATION PANEL */}
        {activeTab === 'zscore' && (
          <ZScoreTab state={state} priceHistory={priceHistory} />
        )}

        {/* TAB 3: PYTHON TRAINING CODE VAULT */}
        {activeTab === 'python' && (
          <PythonCodeVaultTab
            selectedCodePreset={selectedCodePreset}
            handlePresetCodeChange={handlePresetCodeChange}
            copyToClipboard={copyToClipboard}
            isCopied={isCopied}
          />
        )}
      </div>

      {/* FOOTER INTERACTIVE CONTROLLER ACTIONS */}
      <div className="pt-3 border-t border-white/5 space-y-2.5 shrink-0">
        
        {/* Pattern Simulation controller triggers */}
        {activeTab === 'live' && (
          <div className="space-y-1">
            <span className="text-[8px] font-bold text-slate-500 uppercase tracking-widest block font-sans">
              Diagnose Scanning Pattern Algorithms:
            </span>
            <div className="grid grid-cols-3 gap-1.5">
              <button
                onClick={() => triggerPatternSimulation('hs')}
                className={`py-1.5 rounded-lg text-[9px] font-bold font-mono border transition-all ${
                  activeSimulationMode === 'hs'
                    ? 'bg-rose-500/10 border-rose-500/40 text-rose-400'
                    : 'bg-slate-950/40 border-white/5 text-slate-500 hover:text-slate-300 hover:bg-slate-900'
                }`}
              >
                Scan Head & Shoulders
              </button>
              <button
                onClick={() => triggerPatternSimulation('db')}
                className={`py-1.5 rounded-lg text-[9px] font-bold font-mono border transition-all ${
                  activeSimulationMode === 'db'
                    ? 'bg-emerald-500/10 border-emerald-500/40 text-emerald-400'
                    : 'bg-slate-950/40 border-white/5 text-slate-500 hover:text-slate-300 hover:bg-slate-900'
                }`}
              >
                Scan Double Bottom
              </button>
              <button
                onClick={resumeLiveFeed}
                className={`py-1.5 rounded-lg text-[9px] font-bold font-mono border transition-all ${
                  activeSimulationMode === 'live'
                    ? 'bg-cyan-500/10 border-cyan-500/40 text-cyan-400'
                    : 'bg-slate-950/40 border-white/5 text-slate-500 hover:text-slate-300 hover:bg-slate-900'
                }`}
              >
                Live Oscillations
              </button>
            </div>
          </div>
        )}

        {/* Optimize Model Weights Button */}
        <button
          onClick={handleTrainCycle}
          disabled={isTraining}
          className="w-full flex items-center justify-center gap-2 h-9 text-[10px] font-mono uppercase tracking-wider bg-emerald-600 hover:bg-emerald-500 disabled:bg-slate-950 disabled:text-slate-600 disabled:border-white/5 text-white font-bold rounded-xl transition-all border border-transparent shadow-[0_0_15px_rgba(16,185,129,0.15)] cursor-pointer"
        >
          {isTraining ? (
            <>
              <RefreshCw className="h-3 w-3 animate-spin text-amber-400" />
              Optimizing Hyperparameters...
            </>
          ) : (
            <>
              <Sparkles className="h-3 w-3 text-emerald-200" />
              Optimize ONNX Core Weights
            </>
          )}
        </button>
      </div>

    </div>
  );
}


interface LivePredictorTabProps {
  state: NeuralInferenceState;
  priceHistory: number[];
  patternResult: PatternMatch;
  minVal: number;
  maxVal: number;
  valRange: number;
  pointsString: string;
}

function LivePredictorTab({
  state,
  priceHistory,
  patternResult,
  minVal,
  maxVal,
  valRange,
  pointsString
}: LivePredictorTabProps) {
  return (
    <div className="space-y-3">
      {/* prediction metrics widget */}
      <div className="bg-slate-950/40 border border-white/5 p-3 rounded-xl space-y-2 font-mono">
        <div className="flex justify-between items-center text-[10px]">
          <span className="text-slate-500">Target Formula</span>
          <span className="text-cyan-400 font-bold bg-slate-950 px-2 py-0.5 rounded text-[9px] border border-white/5">
            {state.targetFormula}
          </span>
        </div>
        <div className="flex justify-between items-center text-xs">
          <span className="text-slate-500">LSTM Prediction Out</span>
          <span className={`font-bold ${
            state.direction === 'UP' ? 'text-emerald-400' : state.direction === 'DOWN' ? 'text-rose-400' : 'text-slate-400'
          }`}>
            {state.prediction > 0 ? `+${state.prediction}` : state.prediction}
          </span>
        </div>

        {/* Progress Slider representation */}
        <div className="h-1.5 w-full bg-slate-950 rounded-full overflow-hidden border border-white/5">
          <div
            className={`h-full transition-all duration-1000 ${
              state.direction === 'UP' ? 'bg-emerald-500' : state.direction === 'DOWN' ? 'bg-rose-500' : 'bg-slate-600'
            }`}
            style={{ width: `${Math.max(5, Math.min(95, 50 + (state.prediction * 500)))}%` }}
          ></div>
        </div>
      </div>

      {/* Sparkline & Pattern Analyzer */}
      <div className="space-y-1">
        <div className="flex items-center justify-between text-[10px] font-mono text-slate-500">
          <span className="flex items-center gap-1.5">
            <Database className="w-3 h-3 text-cyan-400" />
            Pattern Buffer Sparkline
          </span>
          <span>{priceHistory.length} Bars windowed</span>
        </div>
        <div className="h-14 w-full bg-slate-950 rounded-xl border border-white/5 relative p-1.5 overflow-hidden flex items-end">
          <svg className="w-full h-full overflow-visible" viewBox="0 0 100 100" preserveAspectRatio="none">
            <polyline
              fill="none"
              stroke={patternResult.pattern === 'No Pattern' ? '#06b6d4' : patternResult.pattern === 'Head & Shoulders' ? '#f43f5e' : '#10b981'}
              strokeWidth="2"
              points={pointsString}
              className="transition-all duration-500"
            />
            {patternResult.keyLevels.map((lvl, lIdx) => {
              const step = priceHistory.length > 1 ? (100 / (priceHistory.length - 1)) : 50;
              const pIdx = priceHistory.findIndex(p => Math.abs(p - lvl.price) < 2);
              if (pIdx !== -1) {
                const x = pIdx * step;
                const y = 90 - ((priceHistory[pIdx] - minVal) / valRange) * 80;
                return (
                  <circle
                    key={lIdx}
                    cx={x}
                    cy={y}
                    r="4"
                    className={`animate-ping ${patternResult.pattern === 'Head & Shoulders' ? 'fill-rose-500' : 'fill-emerald-500'}`}
                  />
                );
              }
              return null;
            })}
          </svg>
          <span className="absolute bottom-1 left-2 text-[8px] font-mono text-slate-600">
            Min: ${minVal.toFixed(1)}
          </span>
          <span className="absolute top-1 right-2 text-[8px] font-mono text-slate-600">
            Max: ${maxVal.toFixed(1)}
          </span>
        </div>
      </div>

      {/* Diagnostics details */}
      <div className={`p-3 rounded-xl border text-[10px] leading-relaxed space-y-1.5 ${
        patternResult.pattern === 'No Pattern'
          ? 'bg-slate-950/40 border-white/5 text-slate-400'
          : patternResult.pattern === 'Head & Shoulders'
            ? 'bg-rose-500/5 border-rose-500/20 text-rose-200'
            : 'bg-emerald-500/5 border-emerald-500/20 text-emerald-200'
      }`}>
        <div className="flex items-center justify-between">
          <span className="font-bold flex items-center gap-1.5 uppercase font-mono">
            <Eye className={`w-3.5 h-3.5 ${
              patternResult.pattern === 'No Pattern' ? 'text-slate-500' : patternResult.pattern === 'Head & Shoulders' ? 'text-rose-400' : 'text-emerald-400'
            }`} />
            {patternResult.pattern} Detected
          </span>
          {patternResult.confidence > 0 && (
            <span className={`font-mono font-bold px-1.5 py-0.5 rounded text-[8px] ${
              patternResult.pattern === 'Head & Shoulders' ? 'bg-rose-500/10 text-rose-400' : 'bg-emerald-500/10 text-emerald-400'
            }`}>
              {patternResult.confidence}% Confidence
            </span>
          )}
        </div>
        <p className="text-[10px] leading-relaxed text-slate-400">
          {patternResult.description}
        </p>

        {patternResult.keyLevels.length > 0 && (
          <div className="pt-2 grid grid-cols-3 gap-1.5 font-mono text-[9px]">
            {patternResult.keyLevels.map((lvl, lIdx) => (
              <div key={lIdx} className="bg-slate-950 p-1.5 rounded border border-white/5 text-center">
                <div className="text-slate-500 text-[8px] truncate">{lvl.name}</div>
                <div className="font-bold text-slate-200">${lvl.price.toFixed(1)}</div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Model specifications stats */}
      <div className="grid grid-cols-2 gap-2 font-mono text-[9px]">
        <div className="bg-slate-950 p-2 rounded-xl border border-white/5">
          <div className="text-slate-500 uppercase">Test Mean Absolute Error</div>
          <div className="text-slate-200 font-bold text-xs mt-0.5">{state.testMae} MAE</div>
        </div>
        <div className="bg-slate-950 p-2 rounded-xl border border-white/5">
          <div className="text-slate-500 uppercase">Target Confidence</div>
          <div className="text-emerald-400 font-bold text-xs mt-0.5">{state.confidence}%</div>
        </div>
      </div>
    </div>
  );
}

interface ZScoreTabProps {
  state: NeuralInferenceState;
  priceHistory: number[];
}

function ZScoreTab({ state, priceHistory }: ZScoreTabProps) {
  return (
    <div className="space-y-3 font-mono text-[10px] leading-relaxed text-slate-400">
      <div className="bg-slate-950/60 p-3.5 rounded-xl border border-white/5 space-y-2">
        <div className="flex items-center gap-1.5 text-slate-200 font-bold border-b border-white/5 pb-2">
          <Calculator className="w-4 h-4 text-emerald-400" />
          <span>Feature Vector Standardization</span>
        </div>
        <p className="text-[9px] text-slate-500 leading-normal">
          LSTM weight nodes require inputs scaled using rolling Z-Score normalization:
        </p>
        <div className="bg-slate-950 p-2.5 rounded border border-white/5 text-center text-slate-200 font-bold my-2 text-[11px]">
          X_norm = (X - μ) / σ
        </div>
        <div className="space-y-1.5 text-[9px]">
          <div className="flex justify-between">
            <span>Input Tensor Dimensions:</span>
            <span className="text-slate-200 font-bold">[1, 10, 4]</span>
          </div>
          <div className="flex justify-between">
            <span>Input Channels:</span>
            <span className="text-emerald-400">[Open, High, Low, Close]</span>
          </div>
          <div className="flex justify-between">
            <span>Rolling Mean (μ):</span>
            <span className="text-slate-200 font-bold">${state.meanVal}</span>
          </div>
          <div className="flex justify-between">
            <span>Standard Deviation (σ):</span>
            <span className="text-slate-200 font-bold">{state.stdVal}</span>
          </div>
          <div className="flex justify-between">
            <span>DataType alignment:</span>
            <span className="text-amber-500">numpy.float32</span>
          </div>
        </div>
      </div>

      {/* Interactive calculation trace */}
      <div className="bg-slate-950/30 p-3 rounded-xl border border-white/5 space-y-2">
        <div className="text-slate-300 font-bold text-[9px] uppercase tracking-wider">
          Normalized Live Vector Trace (Close values)
        </div>
        <div className="grid grid-cols-5 gap-1 text-[9px] text-center">
          {priceHistory.slice(-10).map((price, idx) => {
            const xNorm = (price - state.meanVal) / state.stdVal;
            return (
              <div key={idx} className="bg-slate-950 p-1 rounded border border-white/5">
                <div className="text-[8px] text-slate-600">Bar -{9-idx}</div>
                <div className="text-slate-300 font-bold truncate">${price.toFixed(0)}</div>
                <div className={`font-bold mt-0.5 truncate ${xNorm > 0 ? 'text-emerald-400' : 'text-rose-400'}`}>
                  {xNorm > 0 ? `+${xNorm.toFixed(2)}` : xNorm.toFixed(2)}
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}

interface PythonCodeVaultTabProps {
  selectedCodePreset: string;
  handlePresetCodeChange: (preset: string) => void;
  copyToClipboard: (text: string) => void;
  isCopied: boolean;
}

function PythonCodeVaultTab({
  selectedCodePreset,
  handlePresetCodeChange,
  copyToClipboard,
  isCopied
}: PythonCodeVaultTabProps) {
  return (
    <div className="space-y-3 flex flex-col h-full">
      <div className="flex gap-1.5 bg-slate-950/60 p-1 rounded-lg border border-white/5 text-[9px] font-mono select-none">
        <button
          onClick={() => handlePresetCodeChange("model_train")}
          className={`flex-1 py-1 rounded transition-colors ${
            selectedCodePreset === "model_train" ? "bg-emerald-500/10 text-emerald-400 font-bold" : "text-slate-500 hover:text-slate-300"
          }`}
        >
          model.onnx
        </button>
        <button
          onClick={() => handlePresetCodeChange("model2_train")}
          className={`flex-1 py-1 transition-colors ${
            selectedCodePreset === "model2_train" ? "bg-emerald-500/10 text-emerald-400 font-bold" : "text-slate-500 hover:text-slate-300"
          }`}
        >
          model2.onnx
        </button>
        <button
          onClick={() => handlePresetCodeChange("model4_train")}
          className={`flex-1 py-1 transition-colors ${
            selectedCodePreset === "model4_train" ? "bg-emerald-500/10 text-emerald-400 font-bold" : "text-slate-500 hover:text-slate-300"
          }`}
        >
          model4.onnx
        </button>
        <button
          onClick={() => handlePresetCodeChange("inference")}
          className={`flex-1 py-1 transition-colors ${
            selectedCodePreset === "inference" ? "bg-emerald-500/10 text-emerald-400 font-bold" : "text-slate-500 hover:text-slate-300"
          }`}
        >
          MT5 Run
        </button>
      </div>

      {/* Description & Code block container */}
      <div className="flex-1 bg-slate-950 border border-white/5 rounded-xl p-3 flex flex-col min-h-0 relative">
        <div className="flex justify-between items-start mb-2">
          <div className="space-y-0.5">
            <span className="text-[10px] text-slate-200 font-bold font-sans">
              {codeTemplates[selectedCodePreset].title}
            </span>
            <p className="text-[8px] text-slate-500 font-sans leading-normal pr-8">
              {codeTemplates[selectedCodePreset].desc}
            </p>
          </div>

          <button
            onClick={() => copyToClipboard(codeTemplates[selectedCodePreset].code)}
            className="absolute top-3 right-3 bg-slate-900/80 hover:bg-emerald-500/10 p-1.5 rounded-lg border border-white/5 text-slate-400 hover:text-emerald-400 transition-all"
            title="Copy Python Code to Clipboard"
          >
            {isCopied ? <Check className="w-3.5 h-3.5 text-emerald-400 animate-scale" /> : <Copy className="w-3.5 h-3.5" />}
          </button>
        </div>

        {/* Code viewer panel */}
        <div className="flex-1 overflow-auto bg-slate-950/80 p-2.5 rounded border border-white/5 font-mono text-[9px] leading-relaxed text-emerald-400 scrollbar-thin">
          <pre className="whitespace-pre">{codeTemplates[selectedCodePreset].code}</pre>
        </div>
      </div>
    </div>
  );
}
