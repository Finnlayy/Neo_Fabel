import React, { useCallback, useEffect, useState } from "react";
import { RefreshCw, Globe, AlertTriangle } from "lucide-react";
import { ApiError, apiRequest } from "../api/client";

interface IntegratedConnectorsProps {
  tradingExchange: string;
  setTradingExchange: (exchange: string) => void;
}

type MonitorPayload = {
  request_id?: string;
  [key: string]: unknown;
};

export default function IntegratedConnectors({ tradingExchange, setTradingExchange }: IntegratedConnectorsProps) {
  const [monitor, setMonitor] = useState<MonitorPayload | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [lastRefreshed, setLastRefreshed] = useState("");

  const fetchMonitor = useCallback(async () => {
    setIsLoading(true);
    try {
      const body = await apiRequest<MonitorPayload>("/api/v1/trading/monitor");
      setMonitor(body);
      setError(null);
      setLastRefreshed(new Date().toLocaleTimeString());
    } catch (err) {
      setMonitor(null);
      setError(err instanceof ApiError ? `${err.code}: ${err.message}` : "Monitor unavailable");
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    void fetchMonitor();
    const timer = window.setInterval(() => void fetchMonitor(), 30000);
    return () => window.clearInterval(timer);
  }, [fetchMonitor]);

  return (
    <div id="integrated-connectors-card" className="bg-slate-900/40 border border-white/5 hover:border-white/10 rounded-xl p-5 font-mono text-xs space-y-4 transition-all duration-300">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between border-b border-white/10 pb-3 gap-2">
        <div className="flex items-center gap-2">
          <Globe className="w-4 h-4 text-cyan-400" />
          <h3 className="text-white font-bold uppercase tracking-wider text-[11px]">
            TRADING MONITOR DECK
          </h3>
        </div>
        <div className="flex items-center gap-2.5">
          {lastRefreshed && (
            <span className="text-[9px] text-slate-500 uppercase">Synced: {lastRefreshed}</span>
          )}
          <button
            type="button"
            onClick={() => void fetchMonitor()}
            disabled={isLoading}
            className="flex items-center gap-1.5 text-[9px] bg-white/5 hover:bg-white/10 text-white px-2 py-1 rounded border border-white/10 cursor-pointer transition-all uppercase"
          >
            <RefreshCw className={`w-3 h-3 text-cyan-400 ${isLoading ? "animate-spin" : ""}`} />
            Refresh
          </button>
        </div>
      </div>

      <div className="flex gap-2 items-center">
        <label className="text-[9px] text-slate-500 uppercase">Exchange preference</label>
        <select
          value={tradingExchange}
          onChange={(event) => setTradingExchange(event.target.value)}
          className="bg-slate-950 border border-white/10 rounded px-2 py-1 text-slate-200"
        >
          <option value="simulated">Kraken paper</option>
          <option value="kraken">Kraken CLI</option>
        </select>
      </div>

      {error && (
        <div className="flex items-start gap-2 text-amber-300 border border-amber-500/20 bg-amber-950/20 rounded p-3">
          <AlertTriangle className="w-4 h-4 shrink-0" />
          <span>{error}</span>
        </div>
      )}

      <div className="bg-slate-950/60 border border-white/5 rounded p-3 space-y-2">
        <p className="text-[9px] text-slate-500 uppercase">GET /api/v1/trading/monitor</p>
        {monitor ? (
          <pre className="text-[10px] text-slate-300 whitespace-pre-wrap break-all max-h-64 overflow-auto">
            {JSON.stringify(monitor, null, 2)}
          </pre>
        ) : (
          <p className="text-slate-500 text-[11px]">
            No monitor payload yet. Sign in with Firebase and ensure the API is reachable.
          </p>
        )}
      </div>

      <p className="text-[9px] text-slate-600">
        News / Alpha Vantage indicator panels were removed until dedicated intel backends exist. Balances
        come only from the trading monitor response above.
      </p>
    </div>
  );
}
