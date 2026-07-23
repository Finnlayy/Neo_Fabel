import {beforeEach, describe, expect, it, vi} from "vitest";
import {
  MarketRegime,
  analyzeMarketRegime,
  fetchOrchestratorHistory,
  getOrchestratorDecision,
} from "./orchestrator";

vi.mock("./client", async () => {
  const actual = await vi.importActual<typeof import("./client")>("./client");
  return {...actual, apiRequest: vi.fn()};
});

import {apiRequest} from "./client";

const metadata = {
  mode: "advisory" as const,
  executionAllowed: false as const,
  requestId: "request-1",
  provider: "openrouter",
  model: "test-model",
  sourceCoverage: {
    marketData: true,
    telegramSignals: false,
    neuralStates: false,
    rnaPatterns: false,
    recentTrades: false,
  },
  auditPersisted: true,
  timestamp: "2026-07-23T12:00:00Z",
};

describe("orchestrator api gateway", () => {
  beforeEach(() => {
    vi.mocked(apiRequest).mockReset();
  });

  it("posts a typed market-regime request without adding a fallback result", async () => {
    vi.mocked(apiRequest).mockResolvedValueOnce({
      ...metadata,
      regime: MarketRegime.RANGING,
      confidence: 0.6,
      reasoning: "Mixed market.",
      riskLevel: "MEDIUM",
      strategyWeights: {sentiment: 0.25, neural: 0.25, rnaPattern: 0.25, technicalPattern: 0.25},
    });

    const result = await analyzeMarketRegime({
      tickers: [{symbol: "BTC", price: 50_000, change: 1, history: [49_000, 50_000]}],
      signals: [],
      neuralStates: {},
    });

    expect(result.regime).toBe(MarketRegime.RANGING);
    expect(apiRequest).toHaveBeenCalledWith("/api/v1/orchestrator/market-regime", {
      method: "POST",
      body: JSON.stringify({
        tickers: [{symbol: "BTC", price: 50_000, change: 1, history: [49_000, 50_000]}],
        signals: [],
        neuralStates: {},
        rnaPatterns: {},
      }),
    });
  });

  it("rejects any response that is not explicitly advisory-only", async () => {
    vi.mocked(apiRequest).mockResolvedValueOnce({
      ...metadata,
      mode: "execution",
      executionAllowed: true,
    });

    await expect(
      getOrchestratorDecision({
        tickers: [{symbol: "BTC", price: 50_000, change: 1, history: []}],
        signals: [],
        neuralStates: {},
        rnaPatterns: {},
      }),
    ).rejects.toMatchObject({code: "invalid_orchestrator_response"});
  });

  it("requests bounded decision history with an optional type filter", async () => {
    vi.mocked(apiRequest).mockResolvedValueOnce({...metadata, decisions: []});
    await fetchOrchestratorHistory(10, "full_decision");
    expect(apiRequest).toHaveBeenCalledWith(
      "/api/v1/orchestrator/decisions?limit=10&type=full_decision",
    );
  });
});
