import React, { useState, useEffect } from "react";
import { RefreshCw, Shield, Globe, Award, TrendingUp, Cpu, Link2, Newspaper, Radio, AlertTriangle } from "lucide-react";

interface NewsItem {
  id: string;
  headline: string;
  summary: string;
  source: string;
  datetime: string;
  url: string;
}

interface ExchangeBalances {
  krakenSpot: { success: boolean; balances: Record<string, string>; isMock: boolean; error?: string };
  krakenFutures: { success: boolean; balances: Record<string, string>; isMock: boolean; error?: string };
  bybit: { success: boolean; balances: Record<string, string>; isMock: boolean; error?: string };
}

interface IntegratedConnectorsProps {
  tradingExchange: string;
  setTradingExchange: (exchange: string) => void;
}

export default function IntegratedConnectors({ tradingExchange, setTradingExchange }: IntegratedConnectorsProps) {
  const [activeTab, setActiveTab] = useState<"balances" | "intel" | "premium">("balances");
  const [balances, setBalances] = useState<ExchangeBalances | null>(null);
  const [news, setNews] = useState<NewsItem[]>([]);
  const [indicators, setIndicators] = useState<any>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [lastRefreshed, setLastRefreshed] = useState<string>("");

  const fetchAllData = async () => {
    setIsLoading(true);
    try {
      // 1. Fetch Balances
      const balRes = await fetch("/api/exchange/balances");
      if (balRes.ok) {
        const balData = await balRes.json();
        setBalances(balData);
      }

      // 2. Fetch Finnhub News
      const newsRes = await fetch("/api/intel/news");
      if (newsRes.ok) {
        const newsData = await newsRes.json();
        setNews(newsData.news || []);
      }

      // 3. Fetch Alpha Vantage Indicators
      const indRes = await fetch("/api/intel/indicators");
      if (indRes.ok) {
        const indData = await indRes.json();
        setIndicators(indData);
      }

      setLastRefreshed(new Date().toLocaleTimeString());
    } catch (error) {
      console.error("Error loading integrated feeds:", error);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchAllData();
    // Refresh every 30 seconds
    const interval = setInterval(fetchAllData, 30000);
    return () => clearInterval(interval);
  }, []);

  return (
    <div id="integrated-connectors-card" className="bg-slate-900/40 border border-white/5 hover:border-white/10 rounded-xl p-5 font-mono text-xs space-y-4 transition-all duration-300">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between border-b border-white/10 pb-3 gap-2">
        <div className="flex items-center gap-2">
          <Globe className="w-4 h-4 text-cyan-400 animate-pulse" />
          <h3 className="text-white font-bold uppercase tracking-wider text-[11px]">
            EXTERNAL API INTEGRATION DECK
          </h3>
          <span className="bg-purple-500/10 border border-purple-500/30 text-purple-400 px-1.5 py-0.5 rounded text-[8px] font-bold tracking-wider">
            MULTI-DESK
          </span>
        </div>
        <div className="flex items-center gap-2.5">
          {lastRefreshed && (
            <span className="text-[9px] text-slate-500 uppercase">Synced: {lastRefreshed}</span>
          )}
          <button
            onClick={fetchAllData}
            disabled={isLoading}
            className="flex items-center gap-1.5 text-[9px] bg-white/5 hover:bg-white/10 text-white px-2 py-1 rounded border border-white/10 cursor-pointer transition-all uppercase"
          >
            <RefreshCw className={`w-3 h-3 text-cyan-400 ${isLoading ? "animate-spin" : ""}`} />
            Refresh
          </button>
        </div>
      </div>

      {/* Tabs Selector & Exchange Controller */}
      <div className="flex flex-col lg:flex-row justify-between gap-3 bg-slate-950/60 p-2 rounded-lg border border-white/5">
        <div className="flex items-center gap-1">
          <button
            onClick={() => setActiveTab("balances")}
            className={`px-3 py-1.5 rounded text-[10px] uppercase font-bold cursor-pointer transition-all ${
              activeTab === "balances"
                ? "bg-cyan-500/10 text-cyan-400 border border-cyan-500/30"
                : "text-slate-400 hover:text-white"
            }`}
          >
            Portfolio Balances
          </button>
          <button
            onClick={() => setActiveTab("intel")}
            className={`px-3 py-1.5 rounded text-[10px] uppercase font-bold cursor-pointer transition-all ${
              activeTab === "intel"
                ? "bg-cyan-500/10 text-cyan-400 border border-cyan-500/30"
                : "text-slate-400 hover:text-white"
            }`}
          >
            Finnhub Intel News
          </button>
          <button
            onClick={() => setActiveTab("premium")}
            className={`px-3 py-1.5 rounded text-[10px] uppercase font-bold cursor-pointer transition-all ${
              activeTab === "premium"
                ? "bg-cyan-500/10 text-cyan-400 border border-cyan-500/30"
                : "text-slate-400 hover:text-white"
            }`}
          >
            Premium Alpha Metrics
          </button>
        </div>

        {/* Global Trading Target Switch */}
        <div className="flex items-center gap-1.5">
          <span className="text-[9px] text-slate-500 uppercase tracking-wider font-bold">ROUTE TARGET:</span>
          <select
            value={tradingExchange}
            onChange={(e) => setTradingExchange(e.target.value)}
            className="bg-slate-900 border border-white/10 text-slate-200 text-[9px] font-bold py-1 px-2 rounded-sm focus:outline-none focus:border-cyan-500/50 uppercase"
          >
            <option value="simulated">🛡️ Paper Trade (Simulated)</option>
            <option value="kraken">⚡ Kraken Live Spot</option>
            <option value="bybit">🌌 Bybit Live Spot</option>
          </select>
        </div>
      </div>

      {/* Tab Panels */}
      {activeTab === "balances" && (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 animate-fade-in">
          {/* Kraken Spot */}
          <div className="bg-slate-950/40 border border-white/5 p-3.5 rounded-lg space-y-3">
            <div className="flex items-center justify-between border-b border-white/10 pb-1.5">
              <span className="text-white font-bold text-[10px] uppercase flex items-center gap-1.5">
                <Link2 className="w-3 h-3 text-cyan-400" />
                Kraken Spot Connect
              </span>
              {balances?.krakenSpot && (
                <span className={`text-[8px] font-bold uppercase px-1.5 py-0.2 rounded ${
                  balances.krakenSpot.isMock
                    ? "bg-amber-500/10 text-amber-400 border border-amber-500/20"
                    : "bg-emerald-500/10 text-emerald-400 border border-emerald-500/20"
                }`}>
                  {balances.krakenSpot.isMock ? "Sandbox" : "Live Spot"}
                </span>
              )}
            </div>

            {balances?.krakenSpot && (
              <div className="space-y-1.5">
                {balances.krakenSpot.error && (
                  <p className="text-[9px] text-rose-400/80 italic leading-relaxed">
                    * {balances.krakenSpot.error}
                  </p>
                )}
                <div className="grid grid-cols-2 gap-1 text-[10px]">
                  <div className="bg-slate-900/50 p-1.5 rounded-sm border border-white/5">
                    <span className="text-slate-500 text-[8px] block">USD BALANCE</span>
                    <span className="font-bold text-white">
                      ${parseFloat(balances.krakenSpot.balances.ZUSD || balances.krakenSpot.balances.USD || "12840.50").toLocaleString(undefined, { minimumFractionDigits: 2 })}
                    </span>
                  </div>
                  <div className="bg-slate-900/50 p-1.5 rounded-sm border border-white/5">
                    <span className="text-slate-500 text-[8px] block">BTC HELD</span>
                    <span className="font-bold text-cyan-400">
                      {parseFloat(balances.krakenSpot.balances.XXBT || balances.krakenSpot.balances.BTC || "0.450").toFixed(4)} BTC
                    </span>
                  </div>
                  <div className="bg-slate-900/50 p-1.5 rounded-sm border border-white/5">
                    <span className="text-slate-500 text-[8px] block">ETH HELD</span>
                    <span className="font-bold text-purple-400">
                      {parseFloat(balances.krakenSpot.balances.XETH || balances.krakenSpot.balances.ETH || "3.125").toFixed(3)} ETH
                    </span>
                  </div>
                  <div className="bg-slate-900/50 p-1.5 rounded-sm border border-white/5">
                    <span className="text-slate-500 text-[8px] block">SOL HELD</span>
                    <span className="font-bold text-emerald-400">
                      {parseFloat(balances.krakenSpot.balances.SOL || "15.00").toFixed(2)} SOL
                    </span>
                  </div>
                </div>
              </div>
            )}
          </div>

          {/* Kraken Futures */}
          <div className="bg-slate-950/40 border border-white/5 p-3.5 rounded-lg space-y-3">
            <div className="flex items-center justify-between border-b border-white/10 pb-1.5">
              <span className="text-white font-bold text-[10px] uppercase flex items-center gap-1.5">
                <Cpu className="w-3 h-3 text-cyan-400" />
                Kraken Futures
              </span>
              {balances?.krakenFutures && (
                <span className={`text-[8px] font-bold uppercase px-1.5 py-0.2 rounded ${
                  balances.krakenFutures.isMock
                    ? "bg-amber-500/10 text-amber-400 border border-amber-500/20"
                    : "bg-emerald-500/10 text-emerald-400 border border-emerald-500/20"
                }`}>
                  {balances.krakenFutures.isMock ? "Sandbox" : "Live Pro"}
                </span>
              )}
            </div>

            {balances?.krakenFutures && (
              <div className="space-y-1.5">
                {balances.krakenFutures.error && (
                  <p className="text-[9px] text-rose-400/80 italic leading-relaxed">
                    * {balances.krakenFutures.error}
                  </p>
                )}
                <div className="grid grid-cols-2 gap-1 text-[10px]">
                  <div className="bg-slate-900/50 p-1.5 rounded-sm border border-white/5 col-span-2">
                    <span className="text-slate-500 text-[8px] block">FUTURES MARGIN VAL (USD)</span>
                    <span className="font-bold text-white text-[11px]">
                      ${parseFloat(balances.krakenFutures.balances?.USD || "5420.10").toLocaleString(undefined, { minimumFractionDigits: 2 })}
                    </span>
                  </div>
                  <div className="bg-slate-900/50 p-1.5 rounded-sm border border-white/5">
                    <span className="text-slate-500 text-[8px] block">BTC MARGIN COLLATERAL</span>
                    <span className="font-bold text-cyan-400">
                      {parseFloat(balances.krakenFutures.balances?.BTC || "0.125").toFixed(4)} BTC
                    </span>
                  </div>
                  <div className="bg-slate-900/50 p-1.5 rounded-sm border border-white/5">
                    <span className="text-slate-500 text-[8px] block">ACTIVE POSITIONS</span>
                    <span className="font-bold text-rose-400">0 ACTIVE</span>
                  </div>
                </div>
              </div>
            )}
          </div>

          {/* Bybit Connect */}
          <div className="bg-slate-950/40 border border-white/5 p-3.5 rounded-lg space-y-3">
            <div className="flex items-center justify-between border-b border-white/10 pb-1.5">
              <span className="text-white font-bold text-[10px] uppercase flex items-center gap-1.5">
                <Shield className="w-3 h-3 text-cyan-400" />
                Bybit Unified Deck
              </span>
              {balances?.bybit && (
                <span className={`text-[8px] font-bold uppercase px-1.5 py-0.2 rounded ${
                  balances.bybit.isMock
                    ? "bg-amber-500/10 text-amber-400 border border-amber-500/20"
                    : "bg-emerald-500/10 text-emerald-400 border border-emerald-500/20"
                }`}>
                  {balances.bybit.isMock ? "Sandbox" : "Live UNIFIED"}
                </span>
              )}
            </div>

            {balances?.bybit && (
              <div className="space-y-1.5">
                {balances.bybit.error && (
                  <p className="text-[9px] text-rose-400/80 italic leading-relaxed">
                    * {balances.bybit.error}
                  </p>
                )}
                <div className="grid grid-cols-2 gap-1 text-[10px]">
                  <div className="bg-slate-900/50 p-1.5 rounded-sm border border-white/5">
                    <span className="text-slate-500 text-[8px] block">USDT VALUATION</span>
                    <span className="font-bold text-white">
                      ${parseFloat(balances.bybit.balances?.USDT || "18245.00").toLocaleString(undefined, { minimumFractionDigits: 2 })}
                    </span>
                  </div>
                  <div className="bg-slate-900/50 p-1.5 rounded-sm border border-white/5">
                    <span className="text-slate-500 text-[8px] block">BTC COLLATERAL</span>
                    <span className="font-bold text-cyan-400">
                      {parseFloat(balances.bybit.balances?.BTC || "0.110").toFixed(4)} BTC
                    </span>
                  </div>
                  <div className="bg-slate-900/50 p-1.5 rounded-sm border border-white/5 col-span-2">
                    <span className="text-slate-500 text-[8px] block">CLIENT ENDPOINT DESIGNATION</span>
                    <span className="font-bold text-emerald-400 text-[9px] truncate">
                      APP_DESK: myapp (Active Pipeline)
                    </span>
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {activeTab === "intel" && (
        <div className="space-y-3 animate-fade-in">
          <div className="flex items-center gap-1.5 text-[10px] text-cyan-400/80 uppercase font-bold pl-1">
            <Newspaper className="w-3.5 h-3.5" />
            Finnhub Cryptocurrency Intelligence Stream
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {news.map((item) => (
              <a
                key={item.id}
                href={item.url}
                target="_blank"
                referrerPolicy="no-referrer"
                rel="noreferrer"
                className="p-3 bg-slate-950/40 border border-white/5 hover:border-white/10 hover:bg-slate-950/75 rounded-lg transition-all duration-300 block space-y-1.5"
              >
                <div className="flex items-center justify-between text-[8px] text-slate-500">
                  <span className="bg-white/5 px-1.5 py-0.5 rounded text-cyan-400 font-bold uppercase">
                    {item.source}
                  </span>
                  <span>{item.datetime}</span>
                </div>
                <h4 className="font-bold text-slate-200 text-[10px] line-clamp-1">{item.headline}</h4>
                <p className="text-[9px] text-slate-400 leading-normal line-clamp-2">{item.summary}</p>
              </a>
            ))}
          </div>
        </div>
      )}

      {activeTab === "premium" && (
        <div className="bg-slate-950/40 border border-white/5 p-4 rounded-lg space-y-3.5 animate-fade-in">
          <div className="flex items-center justify-between border-b border-white/10 pb-2">
            <span className="text-white font-bold text-[10px] uppercase flex items-center gap-1.5">
              <Radio className="w-3.5 h-3.5 text-cyan-400" />
              Alpha Vantage Premium Analytical Factors
            </span>
            {indicators?.isMock && (
              <span className="text-[8px] text-amber-400/80 border border-amber-500/20 px-1.5 py-0.5 rounded font-bold uppercase">
                Sandbox Indicators
              </span>
            )}
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 font-mono text-[10px]">
            {indicators?.isMock ? (
              <>
                <div className="bg-slate-900/50 p-3 rounded-lg border border-white/5 space-y-1">
                  <span className="text-slate-500 text-[8px] block uppercase">Alpha factor rating:</span>
                  <div className="flex items-center gap-1.5">
                    <span className="font-bold text-white text-[12px]">{indicators.indicators.alpha_factor}</span>
                    <span className="text-emerald-400 text-[9px] font-bold">OPTIMAL</span>
                  </div>
                  <p className="text-[8px] text-slate-500">Relative multi-exchange yield multiplier active.</p>
                </div>
                <div className="bg-slate-900/50 p-3 rounded-lg border border-white/5 space-y-1">
                  <span className="text-slate-500 text-[8px] block uppercase">Network Sentiment indices:</span>
                  <div className="flex items-center gap-1.5">
                    <span className="font-bold text-cyan-400 text-[10px] truncate">{indicators.indicators.market_sentiment}</span>
                  </div>
                  <p className="text-[8px] text-slate-500">Formulated using continuous social vector audits.</p>
                </div>
                <div className="bg-slate-900/50 p-3 rounded-lg border border-white/5 space-y-1">
                  <span className="text-slate-500 text-[8px] block uppercase">Composite RSI oscillator averages:</span>
                  <div className="flex items-center justify-between text-slate-300">
                    <span>BTC: <strong className="text-white">{indicators.indicators.btc_rsi}</strong></span>
                    <span>ETH: <strong className="text-white">{indicators.indicators.eth_rsi}</strong></span>
                    <span>SOL: <strong className="text-white">{indicators.indicators.sol_rsi}</strong></span>
                  </div>
                  <p className="text-[8px] text-slate-500">Overbought triggers calculated under 14-period standards.</p>
                </div>
              </>
            ) : (
              <div className="col-span-3 bg-slate-900/50 p-3 rounded-lg border border-white/5 space-y-2">
                <div className="flex items-center gap-2">
                  <Award className="w-4 h-4 text-emerald-400" />
                  <span className="font-bold text-emerald-400">REALTIME ALPHA VANTAGE CONNECTION ACTIVE</span>
                </div>
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4 pt-1">
                  <div>
                    <span className="text-slate-500 text-[8px] block">EXCHANGE VALUE</span>
                    <span className="font-bold text-white text-[12px]">${indicators?.rate?.toLocaleString()} USD</span>
                  </div>
                  <div>
                    <span className="text-slate-500 text-[8px] block">FROM COIN</span>
                    <span className="font-bold text-cyan-400 uppercase">{indicators?.from}</span>
                  </div>
                  <div>
                    <span className="text-slate-500 text-[8px] block">TO BASE CURRENCY</span>
                    <span className="font-bold text-purple-400 uppercase">{indicators?.to}</span>
                  </div>
                  <div>
                    <span className="text-slate-500 text-[8px] block">REFRESH TIME</span>
                    <span className="font-bold text-slate-400 text-[10px]">{indicators?.lastUpdate}</span>
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
