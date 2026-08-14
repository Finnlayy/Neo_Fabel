// Datei: src/api/orchestrator.ts
// Zweck: Typisiertes Frontend-Gateway zum rein beratenden Neo-Fabel-Orchestrator.
// Erstellt: 2026-07-23 | Version: 1.0
// Abhaengig: api/client, services/neuralOptimization, types

import {ApiError, apiRequest} from "./client";
import type {NeuralInferenceState} from "../services/neuralOptimization";
import type {TelegramSignal} from "../types";

export enum MarketRegime {
  BULL_TRENDING = "BULL_TRENDING",
  BEAR_TRENDING = "BEAR_TRENDING",
  RANGING = "RANGING",
  HIGH_VOLATILITY = "HIGH_VOLATILITY",
  CRYPTO_BOOM = "CRYPTO_BOOM",
  CRYPTO_BUST = "CRYPTO_BUST",
}

export enum SignalRecommendation {
  STRONG_BUY = "STRONG_BUY",
  BUY = "BUY",
  HOLD = "HOLD",
  AVOID = "AVOID",
}

export interface TickerSnapshot {
  symbol: string;
  price: number;
  change: number;
  history: number[];
}

export interface RnaPatternSnapshot {
  bias: "bullish" | "bearish" | "neutral";
  confidence: number;
}

export type ResolvedTelegramSignal = TelegramSignal & {symbol?: string};

export interface SourceCoverage {
  marketData: boolean;
  telegramSignals: boolean;
  neuralStates: boolean;
  rnaPatterns: boolean;
  recentTrades: boolean;
}

export interface AdvisoryMetadata {
  mode: "advisory";
  executionAllowed: false;
  requestId: string;
  provider: string;
  model: string;
  sourceCoverage: SourceCoverage;
  auditPersisted: boolean;
  timestamp: string;
}

export interface StrategyWeights {
  sentiment: number;
  neural: number;
  rnaPattern: number;
  technicalPattern: number;
}

export interface SignalFactors {
  sentimentScore: number;
  neuralPredictionScore: number;
  patternScore: number;
  rnaScore: number;
  positionSizeRisk: number;
}

export interface MarketRegimeResult extends AdvisoryMetadata {
  regime: MarketRegime;
  confidence: number;
  reasoning: string;
  riskLevel: "LOW" | "MEDIUM" | "HIGH" | "EXTREME";
  strategyWeights: StrategyWeights;
}

export interface SignalQualityResult extends AdvisoryMetadata {
  quality: number;
  recommendation: SignalRecommendation;
  reasoning: string;
  factors: SignalFactors;
}

export interface ScoredSignal {
  symbol: string;
  quality: number;
  recommendation: SignalRecommendation;
  reasoning: string;
  factors: SignalFactors;
}

export interface OrchestratorDecision extends AdvisoryMetadata {
  regime: MarketRegime;
  regimeConfidence: number;
  regimeReasoning: string;
  riskLevel: "LOW" | "MEDIUM" | "HIGH" | "EXTREME";
  signalScores: ScoredSignal[];
  strategyWeights: StrategyWeights;
}

export interface DecisionHistoryItem {
  id: string;
  requestId: string;
  decisionType: "market_regime" | "signal_quality" | "full_decision";
  provider: string;
  model: string;
  status: "success" | "error";
  outputData: Record<string, unknown> | null;
  reasoning: string | null;
  timestamp: string;
}

export interface DecisionHistoryResponse extends AdvisoryMetadata {
  decisions: DecisionHistoryItem[];
}

export interface MarketRegimeRequest {
  tickers: TickerSnapshot[];
  signals: ResolvedTelegramSignal[];
  neuralStates: Record<string, NeuralInferenceState>;
  rnaPatterns?: Record<string, RnaPatternSnapshot>;
}

export interface SignalQualityRequest {
  signal: ResolvedTelegramSignal;
  symbol: string;
  currentPrice: number;
  neuralPrediction?: NeuralInferenceState;
  rnaPattern?: RnaPatternSnapshot;
  positionCost?: number;
  marketRegime: MarketRegime;
}

export interface FullDecisionRequest extends MarketRegimeRequest {
  rnaPatterns: Record<string, RnaPatternSnapshot>;
  recentTrades?: Array<{asset: string; positionCost: number; price: number}>;
}

function assertAdvisory<T extends AdvisoryMetadata>(response: T): T {
  if (response.mode !== "advisory" || response.executionAllowed !== false) {
    throw new ApiError(
      502,
      "invalid_orchestrator_response",
      "Orchestrator response did not enforce advisory-only mode",
    );
  }
  return response;
}

export async function analyzeMarketRegime(body: MarketRegimeRequest): Promise<MarketRegimeResult> {
  const response = await apiRequest<MarketRegimeResult>("/api/v1/orchestrator/market-regime", {
    method: "POST",
    body: JSON.stringify({...body, rnaPatterns: body.rnaPatterns ?? {}}),
  });
  return assertAdvisory(response);
}

export async function scoreSignalQuality(body: SignalQualityRequest): Promise<SignalQualityResult> {
  const response = await apiRequest<SignalQualityResult>("/api/v1/orchestrator/signal-quality", {
    method: "POST",
    body: JSON.stringify(body),
  });
  return assertAdvisory(response);
}

export async function getOrchestratorDecision(body: FullDecisionRequest): Promise<OrchestratorDecision> {
  const response = await apiRequest<OrchestratorDecision>("/api/v1/orchestrator/full-decision", {
    method: "POST",
    body: JSON.stringify({...body, recentTrades: body.recentTrades ?? []}),
  });
  return assertAdvisory(response);
}

export async function fetchOrchestratorHistory(
  limit = 20,
  decisionType?: DecisionHistoryItem["decisionType"],
): Promise<DecisionHistoryResponse> {
  const params = new URLSearchParams({limit: String(limit)});
  if (decisionType) params.set("type", decisionType);
  const response = await apiRequest<DecisionHistoryResponse>(
    `/api/v1/orchestrator/decisions?${params.toString()}`,
  );
  return assertAdvisory(response);
}
