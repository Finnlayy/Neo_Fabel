// Datei: src/components/OrchestratorAdvisoryPanel.tsx
// Zweck: Manuelle, rein beratende Orchestrator-Analyse im Hauptdashboard.
// Erstellt: 2026-07-23 | Version: 1.0
// Abhaengig: api/orchestrator, api/client, types

import {useEffect, useMemo, useState} from "react";
import {AlertCircle, BrainCircuit, ChevronDown, ChevronUp, RefreshCw, ShieldCheck} from "lucide-react";
import {ApiError} from "../api/client";
import {
  MarketRegime,
  fetchOrchestratorHistory,
  getOrchestratorDecision,
  type OrchestratorDecision,
  type ResolvedTelegramSignal,
  type SourceCoverage,
} from "../api/orchestrator";
import type {TelegramSignal, TickerData, Trade} from "../types";

interface OrchestratorAdvisoryPanelProps {
  tickers: TickerData[];
  signals: TelegramSignal[];
  rnaPattern: {bias: string; confidence: number} | null;
  activeSymbol: string;
  trades: Trade[];
  language: "en" | "de";
}

const EMPTY_COVERAGE: SourceCoverage = {
  marketData: false,
  telegramSignals: false,
  neuralStates: false,
  rnaPatterns: false,
  recentTrades: false,
};

function escapeRegex(value: string): string {
  return value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

export function resolveSignalSymbols(
  signals: TelegramSignal[],
  tickers: TickerData[],
): ResolvedTelegramSignal[] {
  const symbols = [...new Set(tickers.map((ticker) => ticker.symbol.toUpperCase()))]
    .sort((left, right) => right.length - left.length);
  return signals.slice(-20).map((signal) => {
    const message = signal.message.toUpperCase();
    const symbol = symbols.find((candidate) => {
      const aliases = [candidate, candidate.replace(/(?:USDT|USD|EUR)$/u, "")].filter(
        (alias) => alias.length >= 2,
      );
      return aliases.some((alias) =>
        new RegExp(`(^|[^A-Z0-9])${escapeRegex(alias)}([^A-Z0-9]|$)`, "u").test(message),
      );
    });
    return symbol ? {...signal, symbol} : signal;
  });
}

function historyDecision(
  outputData: Record<string, unknown> | null,
  metadata: {requestId: string; provider: string; model: string; timestamp: string},
): OrchestratorDecision | null {
  if (!outputData || typeof outputData.regime !== "string" || typeof outputData.regimeConfidence !== "number") {
    return null;
  }
  if (!Object.values(MarketRegime).includes(outputData.regime as MarketRegime)) return null;
  const sourceCoverage =
    outputData.sourceCoverage && typeof outputData.sourceCoverage === "object"
      ? (outputData.sourceCoverage as SourceCoverage)
      : EMPTY_COVERAGE;
  return {
    ...(outputData as unknown as Pick<
      OrchestratorDecision,
      "regime" | "regimeConfidence" | "regimeReasoning" | "riskLevel" | "signalScores" | "strategyWeights"
    >),
    mode: "advisory",
    executionAllowed: false,
    requestId: metadata.requestId,
    provider: metadata.provider,
    model: metadata.model,
    sourceCoverage,
    auditPersisted: true,
    timestamp: metadata.timestamp,
  };
}

export default function OrchestratorAdvisoryPanel({
  tickers,
  signals,
  rnaPattern,
  activeSymbol,
  trades,
  language,
}: OrchestratorAdvisoryPanelProps) {
  const [decision, setDecision] = useState<OrchestratorDecision | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [expanded, setExpanded] = useState(false);

  const resolvedSignals = useMemo(() => resolveSignalSymbols(signals, tickers), [signals, tickers]);
  const stale = decision
    ? Date.now() - new Date(decision.timestamp).getTime() > 15 * 60 * 1_000
    : false;

  useEffect(() => {
    let cancelled = false;
    void fetchOrchestratorHistory(1, "full_decision")
      .then((history) => {
        const latest = history.decisions[0];
        if (!cancelled && latest) {
          setDecision(
            historyDecision(latest.outputData, {
              requestId: latest.requestId,
              provider: latest.provider,
              model: latest.model,
              timestamp: latest.timestamp,
            }),
          );
        }
      })
      .catch(() => {
        // History is optional; manual analysis remains available without the audit database.
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const runAnalysis = async (): Promise<void> => {
    if (tickers.length === 0) {
      setError(language === "de" ? "Keine Marktdaten verfügbar." : "No market data available.");
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const result = await getOrchestratorDecision({
        tickers: tickers.slice(0, 25).map(({symbol, price, change, history}) => ({
          symbol,
          price,
          change,
          history: history.slice(-120),
        })),
        signals: resolvedSignals,
        neuralStates: {},
        rnaPatterns: rnaPattern
          ? {
              [activeSymbol]: {
                bias:
                  rnaPattern.bias === "bullish" || rnaPattern.bias === "bearish"
                    ? rnaPattern.bias
                    : "neutral",
                confidence: rnaPattern.confidence,
              },
            }
          : {},
        recentTrades: trades.slice(-50).map(({asset, positionCost, price}) => ({
          asset,
          positionCost,
          price,
        })),
      });
      setDecision(result);
      setExpanded(true);
    } catch (caught: unknown) {
      const message =
        caught instanceof ApiError
          ? `${caught.code}: ${caught.message}`
          : caught instanceof Error
            ? caught.message
            : "Unknown error";
      setError(message);
    } finally {
      setLoading(false);
    }
  };

  const coverageCount = decision
    ? Object.values(decision.sourceCoverage).filter(Boolean).length
    : 0;

  return (
    <section
      aria-label={language === "de" ? "Orchestrator-Beratung" : "Orchestrator advisory"}
      className="bg-slate-900/40 border border-emerald-500/20 rounded-xl p-5 glow-emerald min-h-56 font-mono text-xs"
    >
      <div className="flex items-center justify-between border-b border-white/10 pb-2">
        <span className="text-emerald-400 font-bold uppercase tracking-wider text-[11px] flex items-center gap-2">
          <BrainCircuit className="w-4 h-4" />
          {language === "de" ? "HAUPT-ORCHESTRATOR" : "MASTER ORCHESTRATOR"}
        </span>
        <span className="text-[9px] text-amber-300 border border-amber-500/30 px-1.5 py-0.5 rounded">
          ADVISORY ONLY
        </span>
      </div>

      <div className="mt-3 flex items-start justify-between gap-3">
        <div>
          <div className="text-slate-500 text-[9px] uppercase">
            {language === "de" ? "Marktregime" : "Market regime"}
          </div>
          <div className="text-white font-bold text-sm">
            {decision?.regime ?? (language === "de" ? "Noch nicht analysiert" : "Not analyzed")}
          </div>
          {decision && (
            <div className="text-[10px] text-emerald-400">
              {(decision.regimeConfidence * 100).toFixed(0)}% · {decision.riskLevel}
              {stale ? ` · ${language === "de" ? "VERALTET" : "STALE"}` : ""}
            </div>
          )}
        </div>
        <button
          type="button"
          onClick={() => void runAnalysis()}
          disabled={loading || tickers.length === 0}
          className="px-2.5 py-1.5 rounded border border-emerald-500/30 bg-emerald-500/10 text-emerald-300 disabled:opacity-40 flex items-center gap-1"
        >
          <RefreshCw className={`w-3 h-3 ${loading ? "animate-spin" : ""}`} />
          {loading
            ? language === "de"
              ? "Analysiere"
              : "Analyzing"
            : language === "de"
              ? "Analyse starten"
              : "Run analysis"}
        </button>
      </div>

      {error && (
        <div role="alert" className="mt-2 text-[10px] text-rose-300 flex items-start gap-1">
          <AlertCircle className="w-3 h-3 mt-0.5 shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {decision && (
        <>
          <div className="mt-3 flex items-center justify-between text-[9px] text-slate-500">
            <span>
              {coverageCount}/5 {language === "de" ? "Quellen" : "sources"} · {decision.provider}
            </span>
            <button
              type="button"
              onClick={() => setExpanded((value) => !value)}
              className="text-slate-300 flex items-center gap-1"
            >
              {expanded ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
              {language === "de" ? "Details" : "Details"}
            </button>
          </div>
          {expanded && (
            <div className="mt-2 max-h-36 overflow-y-auto space-y-2 pr-1">
              <p className="text-[10px] leading-relaxed text-slate-300">{decision.regimeReasoning}</p>
              {decision.signalScores.slice(0, 3).map((score) => (
                <div key={score.symbol} className="border-t border-white/5 pt-1 text-[9px]">
                  <div className="flex justify-between text-white">
                    <span>{score.symbol} · {score.recommendation}</span>
                    <span>{(score.quality * 100).toFixed(0)}%</span>
                  </div>
                  <div className="text-slate-500">{score.reasoning}</div>
                </div>
              ))}
              <div className="grid grid-cols-2 gap-x-3 text-[9px] text-slate-400 border-t border-white/5 pt-1">
                {Object.entries(decision.strategyWeights).map(([name, value]) => (
                  <div key={name} className="flex justify-between">
                    <span>{name}</span>
                    <span>{(Number(value) * 100).toFixed(0)}%</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </>
      )}

      <div className="mt-3 pt-2 border-t border-white/10 text-[9px] text-amber-300 flex items-center gap-1">
        <ShieldCheck className="w-3 h-3" />
        {language === "de"
          ? "Nur Beratung – keine Paper- oder Live-Orderausführung."
          : "Advisory only – no paper or live order execution."}
      </div>
    </section>
  );
}
