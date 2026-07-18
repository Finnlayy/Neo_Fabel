import React, { useState, useMemo } from "react";
import { 
  InMemoryVectorIndex, 
  VectorDocument, 
  DistanceMetric 
} from "../services/vectorIndex";
import { 
  Database, 
  Search, 
  Cpu, 
  Plus, 
  HelpCircle, 
  ChevronRight, 
  Flame, 
  ShieldAlert, 
  TrendingUp, 
  Target, 
  Compass, 
  Zap, 
  Layers, 
  RefreshCw, 
  Maximize2 
} from "lucide-react";
import { motion } from "motion/react";

// Instantiating a single persistent instance of our index
const vectorEngine = new InMemoryVectorIndex(8);

const DIMENSION_LABELS = [
  { name: "Profit Factor", color: "bg-emerald-500", desc: "Estimated return ratio" },
  { name: "Win Rate", color: "bg-cyan-500", desc: "Percentage of profitable closures" },
  { name: "Volatility", color: "bg-purple-500", desc: "Price variance susceptibility" },
  { name: "Max Drawdown", color: "bg-rose-500", desc: "Peak-to-trough capital risk" },
  { name: "Cap Leverage", color: "bg-amber-500", desc: "Leverage & margin weight" },
  { name: "Market Sentiment", color: "bg-blue-500", desc: "Social/sentiment score bias" },
  { name: "Time Decay", color: "bg-teal-500", desc: "Holding time decay factor" },
  { name: "Neural Risk", color: "bg-fuchsia-500", desc: "Fable 5 machine compliance threat" }
];

export default function NeuralVectorAnalyzer() {
  const [docs, setDocs] = useState<VectorDocument[]>(() => vectorEngine.listAll());
  
  // Query state
  const [queryMode, setQueryMode] = useState<"sliders" | "text">("sliders");
  const [textQuery, setTextQuery] = useState("");
  
  // Slider query vector
  const [sliderVector, setSliderVector] = useState<number[]>([0.7, 0.6, 0.5, 0.2, 0.4, 0.6, 0.3, 0.3]);
  const [metric, setMetric] = useState<DistanceMetric>("cosine");
  const [topK, setTopK] = useState<number>(3);
  
  // Results
  const [queryResults, setQueryResults] = useState<{ document: VectorDocument; score: number }[]>([]);
  const [hasQueried, setHasQueried] = useState(false);
  const [isQuerying, setIsQuerying] = useState(false);

  // New Vector form
  const [newTitle, setNewTitle] = useState("");
  const [newCategory, setNewCategory] = useState<"strategy" | "pattern" | "trade_cluster" | "market_alert">("strategy");
  const [newVector, setNewVector] = useState<number[]>([0.5, 0.5, 0.5, 0.2, 0.3, 0.5, 0.3, 0.2]);
  const [newDesc, setNewDesc] = useState("");

  const handleSliderValueChange = (index: number, val: number) => {
    const updated = [...sliderVector];
    updated[index] = val;
    setSliderVector(updated);
  };

  const handleNewSliderChange = (index: number, val: number) => {
    const updated = [...newVector];
    updated[index] = val;
    setNewVector(updated);
  };

  // Run vector similarity calculation
  const handleExecuteQuery = () => {
    setIsQuerying(true);
    setHasQueried(true);
    
    setTimeout(() => {
      let targetVector = [...sliderVector];
      if (queryMode === "text" && textQuery.trim()) {
        targetVector = vectorEngine.embedText(textQuery, [metric]);
        // Update sliders visually to show embedded text vector profile!
        setSliderVector(targetVector);
      }
      
      const results = vectorEngine.query(targetVector, topK, metric);
      setQueryResults(results);
      setIsQuerying(false);
    }, 280);
  };

  // Add custom vector to in-memory state
  const handleAddVectorDoc = (e: React.FormEvent) => {
    e.preventDefault();
    if (!newTitle.trim()) return;

    const added = vectorEngine.add({
      title: newTitle,
      category: newCategory,
      vector: newVector,
      metadata: {
        description: newDesc || "Custom structured vector strategy node",
        profitFactor: Number((newVector[0] * 3).toFixed(1)),
        winRate: Math.round(newVector[1] * 100),
        volatility: Math.round(newVector[2] * 100),
        drawdown: Math.round(newVector[3] * 100)
      }
    });

    setDocs(vectorEngine.listAll());
    // Reset form
    setNewTitle("");
    setNewDesc("");
    setNewVector([0.5, 0.5, 0.5, 0.2, 0.3, 0.5, 0.3, 0.2]);
  };

  const handleDeleteDoc = (id: string) => {
    vectorEngine.delete(id);
    setDocs(vectorEngine.listAll());
    // Filter results if deleted
    setQueryResults(prev => prev.filter(r => r.document.id !== id));
  };

  return (
    <div id="neural-vector-analyzer" className="grid grid-cols-1 xl:grid-cols-12 gap-6">
      
      {/* LEFT BLOCK: Config & Queries (8 Cols) */}
      <div className="xl:col-span-8 space-y-6">
        
        {/* Main Vector Console Box */}
        <div className="bg-slate-900/40 border border-white/5 rounded-2xl p-5 relative overflow-hidden transition-all hover:border-white/10">
          <div className="absolute top-0 right-0 w-64 h-64 bg-cyan-500/5 rounded-full blur-3xl pointer-events-none"></div>
          
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-white/5 pb-4 mb-5">
            <div className="flex items-center gap-3">
              <div className="bg-gradient-to-tr from-cyan-500/20 to-purple-500/20 border border-cyan-500/30 p-2 rounded-xl text-cyan-400 shadow-[0_0_15px_rgba(6,182,212,0.15)]">
                <Database className="w-5 h-5 animate-pulse" />
              </div>
              <div>
                <h3 className="text-sm font-black uppercase tracking-wider text-slate-100 flex items-center gap-2">
                  FABLE 5 NEURAL VECTOR CORE
                  <span className="bg-cyan-500/10 text-cyan-400 text-[8px] font-mono px-2 py-0.5 rounded border border-cyan-500/30 animate-pulse">
                    IN-MEMORY QDRANT LAYER
                  </span>
                </h3>
                <p className="text-[10px] text-slate-500 font-mono mt-0.5 leading-none">
                  Mathematical Cosine Similarity & Multi-Dimensional Vector Indexing
                </p>
              </div>
            </div>

            {/* Quick Switch Metric */}
            <div className="flex items-center gap-2 bg-slate-950/60 p-1 rounded-lg border border-white/5 font-mono text-[9px]">
              <span className="text-slate-500 px-2">METRIC:</span>
              {(["cosine", "euclidean", "dot_product"] as DistanceMetric[]).map((m) => (
                <button
                  key={m}
                  onClick={() => setMetric(m)}
                  className={`px-2 py-1 rounded transition-colors capitalize ${
                    metric === m 
                      ? "bg-cyan-500 text-slate-950 font-extrabold" 
                      : "text-slate-400 hover:text-slate-200"
                  }`}
                >
                  {m.replace("_", " ")}
                </button>
              ))}
            </div>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Vector Query Engine Selector */}
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <span className="text-[11px] font-bold text-slate-300 uppercase tracking-wider flex items-center gap-1.5 font-mono">
                  <Compass className="w-4 h-4 text-cyan-400" />
                  Configure Query Coordinates
                </span>
                
                {/* Mode Selector */}
                <div className="flex bg-slate-950/80 p-0.5 rounded border border-white/5 font-mono text-[8px]">
                  <button
                    onClick={() => setQueryMode("sliders")}
                    className={`px-2 py-0.5 rounded ${queryMode === "sliders" ? "bg-white/10 text-white" : "text-slate-500"}`}
                  >
                    Sliders
                  </button>
                  <button
                    onClick={() => setQueryMode("text")}
                    className={`px-2 py-0.5 rounded ${queryMode === "text" ? "bg-white/10 text-white" : "text-slate-500"}`}
                  >
                    Semantic Text
                  </button>
                </div>
              </div>

              {queryMode === "sliders" ? (
                /* Sliders input for precise manual weights */
                <div className="space-y-3 bg-slate-950/30 border border-white/5 p-4 rounded-xl">
                  {DIMENSION_LABELS.map((dim, idx) => (
                    <div key={idx} className="space-y-1.5 font-mono">
                      <div className="flex items-center justify-between text-[10px]">
                        <span className="text-slate-400 flex items-center gap-1">
                          <span className={`w-1.5 h-1.5 rounded-full ${dim.color}`}></span>
                          {dim.name}
                        </span>
                        <span className="text-cyan-400 font-bold">{(sliderVector[idx] * 100).toFixed(0)}%</span>
                      </div>
                      <div className="flex items-center gap-2">
                        <input
                          type="range"
                          min="0"
                          max="1"
                          step="0.05"
                          value={sliderVector[idx]}
                          onChange={(e) => handleSliderValueChange(idx, parseFloat(e.target.value))}
                          className="w-full accent-cyan-500 cursor-pointer h-1 bg-slate-800 rounded-lg"
                        />
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                /* Semantic prompt embedder query */
                <div className="space-y-3 bg-slate-950/30 border border-white/5 p-4 rounded-xl">
                  <p className="text-[10px] text-slate-400 leading-relaxed font-mono">
                    Type a description of your target risk strategy profile. Our neural text engine will determine vectors based on weight profiles.
                  </p>
                  <div className="relative">
                    <textarea
                      value={textQuery}
                      onChange={(e) => setTextQuery(e.target.value)}
                      placeholder="e.g., highly volatile momentum trade on EV assets with strict compliance drawdown defense..."
                      className="w-full bg-slate-950 border border-white/10 rounded-xl p-3 text-[11px] text-slate-300 placeholder-slate-600 focus:border-cyan-500 outline-none h-28 font-mono resize-none"
                    />
                    <Search className="absolute right-3 bottom-3 text-slate-600 w-4 h-4 pointer-events-none" />
                  </div>
                  
                  <div className="flex flex-wrap gap-1.5">
                    <button 
                      type="button"
                      onClick={() => setTextQuery("Aggressive scalper with massive winrate but extreme leverage drawdowns")}
                      className="bg-white/5 hover:bg-white/10 text-[8px] text-slate-400 hover:text-slate-200 border border-white/5 px-2 py-1 rounded font-mono"
                    >
                      🔥 Aggressive Scalp
                    </button>
                    <button 
                      type="button"
                      onClick={() => setTextQuery("Conservative yield algorithm focused on high compliance and near-zero volatility")}
                      className="bg-white/5 hover:bg-white/10 text-[8px] text-slate-400 hover:text-slate-200 border border-white/5 px-2 py-1 rounded font-mono"
                    >
                      🛡️ Conservative Defenses
                    </button>
                  </div>
                </div>
              )}

              {/* Sweep Trigger */}
              <div className="flex gap-3">
                <button
                  onClick={handleExecuteQuery}
                  disabled={isQuerying}
                  className="w-full bg-cyan-500 hover:bg-cyan-400 disabled:bg-slate-950 disabled:text-slate-600 disabled:border-white/5 border border-transparent text-slate-950 py-2.5 rounded-xl text-xs font-black uppercase tracking-wider flex items-center justify-center gap-2 transition-all shadow-[0_0_15px_rgba(6,182,212,0.15)] cursor-pointer"
                >
                  {isQuerying ? (
                    <>
                      <RefreshCw className="w-4 h-4 animate-spin text-slate-950" />
                      Scanning Vector Grid...
                    </>
                  ) : (
                    <>
                      <Zap className="w-4 h-4" />
                      Orchestrate Vector Sweep
                    </>
                  )}
                </button>
              </div>
            </div>

            {/* Live Search Results */}
            <div className="space-y-4">
              <span className="text-[11px] font-bold text-slate-300 uppercase tracking-wider flex items-center gap-1.5 font-mono">
                <Target className="w-4 h-4 text-purple-400" />
                Query Vector Matches ({queryResults.length})
              </span>

              <div className="bg-slate-950/40 border border-white/5 rounded-xl p-4 h-[352px] flex flex-col justify-between overflow-y-auto">
                {!hasQueried ? (
                  <div className="flex-1 flex flex-col items-center justify-center text-center p-6 space-y-3">
                    <Cpu className="w-8 h-8 text-slate-600 animate-pulse" />
                    <div className="space-y-1">
                      <p className="text-xs text-slate-400 font-bold font-mono">Vector core is idle.</p>
                      <p className="text-[9px] text-slate-500 font-mono">
                        Run a sweep using sliders or semantic text to query similar indices.
                      </p>
                    </div>
                  </div>
                ) : (
                  <div className="space-y-3 flex-1 overflow-y-auto scrollbar-thin">
                    {queryResults.map((res, index) => {
                      const matchPct = metric === "euclidean" 
                        ? (res.score * 100).toFixed(1) + "% Score"
                        : (res.score * 100).toFixed(1) + "% Cosine";

                      return (
                        <div 
                          key={res.document.id}
                          className="bg-slate-950 border border-white/5 hover:border-cyan-500/20 p-3 rounded-lg flex items-start justify-between transition-all group"
                        >
                          <div className="space-y-1.5 max-w-[70%]">
                            <div className="flex items-center gap-2">
                              <span className="text-[8px] bg-cyan-500/10 text-cyan-400 border border-cyan-500/20 px-1 py-0.5 rounded font-mono font-black">
                                {res.document.id}
                              </span>
                              <span className="text-[10px] font-bold text-white tracking-tight group-hover:text-cyan-400 transition-colors truncate">
                                {res.document.title}
                              </span>
                            </div>
                            <p className="text-[9px] text-slate-400 leading-normal line-clamp-2 font-mono">
                              {res.document.metadata.description}
                            </p>
                            
                            {/* Similarity Bar */}
                            <div className="w-full bg-slate-900 h-1 rounded-full overflow-hidden">
                              <div 
                                className="bg-gradient-to-r from-cyan-500 to-purple-500 h-full transition-all duration-500"
                                style={{ width: `${Math.min(100, Math.max(0, res.score * 100))}%` }}
                              />
                            </div>
                          </div>

                          <div className="text-right flex flex-col items-end gap-1 shrink-0">
                            <span className="text-[11px] font-black font-mono text-cyan-400">
                              {matchPct}
                            </span>
                            <span className="text-[8px] text-slate-500 font-mono uppercase">
                              Rank #{index + 1}
                            </span>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                )}

                {hasQueried && (
                  <div className="border-t border-white/5 pt-2 mt-3 text-[9px] text-slate-500 font-mono text-center leading-none">
                    Calculations complete. Match score based on 8 dimensions.
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* RIGHT BLOCK: Index Registry & Add (4 Cols) */}
      <div className="xl:col-span-4 space-y-6">
        
        {/* Vector Document Register */}
        <div className="bg-slate-900/40 border border-white/5 rounded-2xl p-5 relative overflow-hidden transition-all hover:border-white/10 flex flex-col justify-between h-[308px]">
          <div>
            <h4 className="text-xs font-black uppercase tracking-wider text-slate-200 border-b border-white/10 pb-2 mb-3 flex items-center justify-between">
              <span className="flex items-center gap-1.5 font-mono">
                <Layers className="w-4 h-4 text-emerald-400" />
                Indexed Strategies ({docs.length})
              </span>
              <span className="text-[8px] text-slate-500 font-mono uppercase">RAM STORAGE</span>
            </h4>

            {/* List with scroll */}
            <div className="space-y-2 h-[210px] overflow-y-auto scrollbar-thin pr-1">
              {docs.map((doc) => (
                <div 
                  key={doc.id}
                  className="bg-slate-950/80 border border-white/5 p-2 rounded-lg flex items-center justify-between hover:border-white/15 transition-all group"
                >
                  <div className="space-y-1">
                    <div className="flex items-center gap-1.5">
                      <span className="text-[8px] font-bold text-slate-400 font-mono bg-slate-900 px-1 py-0.5 rounded">
                        {doc.id}
                      </span>
                      <span className="text-[10px] font-bold text-white group-hover:text-emerald-400 transition-colors">
                        {doc.title}
                      </span>
                    </div>

                    {/* Miniature 8-stripe matrix representing the Vector weights! */}
                    <div className="flex gap-0.5 pt-1">
                      {doc.vector.map((val, idx) => (
                        <div 
                          key={idx}
                          className="w-2 h-1.5 rounded-sm transition-opacity"
                          style={{
                            backgroundColor: 
                              idx === 0 ? "#10b981" : 
                              idx === 1 ? "#06b6d4" : 
                              idx === 2 ? "#a855f7" : 
                              idx === 3 ? "#f43f5e" : 
                              idx === 4 ? "#f59e0b" : 
                              idx === 5 ? "#3b82f6" : 
                              idx === 6 ? "#14b8a6" : "#d946ef",
                            opacity: 0.15 + val * 0.85
                          }}
                          title={`${DIMENSION_LABELS[idx].name}: ${Math.round(val * 100)}%`}
                        />
                      ))}
                    </div>
                  </div>

                  {/* Delete Button */}
                  <button
                    onClick={() => handleDeleteDoc(doc.id)}
                    className="text-slate-500 hover:text-red-400 transition-colors p-1"
                    title="Remove Vector Node"
                  >
                    <Plus className="w-3.5 h-3.5 rotate-45" />
                  </button>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Index Custom Node */}
        <div className="bg-slate-900/40 border border-white/5 rounded-2xl p-5 relative overflow-hidden transition-all hover:border-white/10">
          <h4 className="text-xs font-black uppercase tracking-wider text-slate-200 border-b border-white/10 pb-2 mb-4 flex items-center gap-1.5 font-mono">
            <Plus className="w-4 h-4 text-cyan-400" />
            Index Custom Vector
          </h4>

          <form onSubmit={handleAddVectorDoc} className="space-y-4">
            <div className="space-y-1 font-mono">
              <label className="text-[9px] text-slate-500 uppercase tracking-widest block font-bold">Node Title</label>
              <input
                type="text"
                required
                value={newTitle}
                onChange={(e) => setNewTitle(e.target.value)}
                placeholder="e.g., NIO High-Beta Pullback Scalper"
                className="w-full bg-slate-950 border border-white/10 rounded-lg p-2 text-[10px] text-slate-200 placeholder-slate-600 focus:border-cyan-500 outline-none"
              />
            </div>

            <div className="grid grid-cols-2 gap-3 font-mono">
              <div className="space-y-1">
                <label className="text-[9px] text-slate-500 uppercase tracking-widest block font-bold">Category</label>
                <select
                  value={newCategory}
                  onChange={(e: any) => setNewCategory(e.target.value)}
                  className="w-full bg-slate-950 border border-white/10 rounded-lg p-2 text-[10px] text-slate-300 outline-none focus:border-cyan-500"
                >
                  <option value="strategy">Strategy</option>
                  <option value="pattern">Pattern</option>
                  <option value="trade_cluster">Trade Cluster</option>
                  <option value="market_alert">Alert Vector</option>
                </select>
              </div>

              <div className="space-y-1">
                <label className="text-[9px] text-slate-500 uppercase tracking-widest block font-bold">Base Volatility</label>
                <div className="relative">
                  <input
                    type="range"
                    min="0"
                    max="1"
                    step="0.05"
                    value={newVector[2]} // Volatility dimension index
                    onChange={(e) => handleNewSliderChange(2, parseFloat(e.target.value))}
                    className="w-full accent-purple-500 mt-3 cursor-pointer"
                  />
                </div>
              </div>
            </div>

            <div className="space-y-2">
              <span className="text-[9px] text-slate-500 uppercase tracking-widest block font-bold font-mono">Adjust Vector Coordinates</span>
              
              <div className="grid grid-cols-2 gap-2 bg-slate-950/40 p-2.5 rounded-lg border border-white/5 font-mono text-[9px]">
                {DIMENSION_LABELS.slice(0, 4).map((dim, idx) => (
                  <div key={idx} className="space-y-0.5">
                    <span className="text-[8px] text-slate-400 block truncate">{dim.name}</span>
                    <input
                      type="range"
                      min="0"
                      max="1"
                      step="0.1"
                      value={newVector[idx]}
                      onChange={(e) => handleNewSliderChange(idx, parseFloat(e.target.value))}
                      className="w-full accent-cyan-500"
                    />
                  </div>
                ))}
              </div>
            </div>

            <button
              type="submit"
              className="w-full bg-emerald-500 hover:bg-emerald-400 text-slate-950 py-2 rounded-xl text-[10px] font-black uppercase tracking-wider flex items-center justify-center gap-1 transition-all cursor-pointer shadow-[0_0_15px_rgba(16,182,129,0.15)]"
            >
              <Database className="w-3.5 h-3.5" />
              Store Vector Node
            </button>
          </form>
        </div>

      </div>

    </div>
  );
}
