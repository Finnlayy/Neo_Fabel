import React from "react";
import {cleanup, fireEvent, render, screen, waitFor} from "@testing-library/react";
import {afterEach, beforeEach, describe, expect, it, vi} from "vitest";
import OrchestratorAdvisoryPanel, {resolveSignalSymbols} from "./OrchestratorAdvisoryPanel";
import {MarketRegime} from "../api/orchestrator";

vi.mock("../api/orchestrator", async () => {
  const actual = await vi.importActual<typeof import("../api/orchestrator")>("../api/orchestrator");
  return {
    ...actual,
    fetchOrchestratorHistory: vi.fn().mockResolvedValue({
      mode: "advisory",
      executionAllowed: false,
      decisions: [],
    }),
    getOrchestratorDecision: vi.fn(),
  };
});

import {getOrchestratorDecision} from "../api/orchestrator";

const tickers = [{symbol: "BTC", name: "Bitcoin", price: 50_000, change: 2, history: [49_000, 50_000]}];

describe("OrchestratorAdvisoryPanel", () => {
  afterEach(() => {
    cleanup();
  });

  beforeEach(() => {
    vi.mocked(getOrchestratorDecision).mockReset();
  });

  it("resolves only explicit known symbols and never defaults to BTC", () => {
    const signals = [
      {
        id: "1",
        timestamp: "2026-07-23T12:00:00Z",
        channel: "test",
        message: "BTC breakout",
        sentiment: "BULLISH" as const,
        actionable: true,
      },
      {
        id: "2",
        timestamp: "2026-07-23T12:01:00Z",
        channel: "test",
        message: "Unresolved market note",
        sentiment: "NEUTRAL" as const,
        actionable: false,
      },
    ];
    expect(resolveSignalSymbols(signals, tickers).map((signal) => signal.symbol)).toEqual([
      "BTC",
      undefined,
    ]);
  });

  it("runs a manual advisory and displays its result", async () => {
    vi.mocked(getOrchestratorDecision).mockResolvedValueOnce({
      mode: "advisory",
      executionAllowed: false,
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
      timestamp: new Date().toISOString(),
      regime: MarketRegime.BULL_TRENDING,
      regimeConfidence: 0.82,
      regimeReasoning: "Momentum is broad.",
      riskLevel: "MEDIUM",
      signalScores: [],
      strategyWeights: {sentiment: 0.4, neural: 0.2, rnaPattern: 0.2, technicalPattern: 0.2},
    });

    render(
      <OrchestratorAdvisoryPanel
        tickers={tickers}
        signals={[]}
        rnaPattern={null}
        activeSymbol="BTC"
        trades={[]}
        language="en"
      />,
    );

    fireEvent.click(screen.getByRole("button", {name: /run analysis/i}));
    await waitFor(() => expect(screen.getByText("BULL_TRENDING")).toBeTruthy());
    expect(screen.getByText(/no paper or live order execution/i)).toBeTruthy();
  });

  it("shows provider errors without inventing a neutral decision", async () => {
    vi.mocked(getOrchestratorDecision).mockRejectedValueOnce(new Error("provider unavailable"));
    render(
      <OrchestratorAdvisoryPanel
        tickers={tickers}
        signals={[]}
        rnaPattern={null}
        activeSymbol="BTC"
        trades={[]}
        language="en"
      />,
    );
    fireEvent.click(screen.getByRole("button", {name: /run analysis/i}));
    await waitFor(() => expect(screen.getByRole("alert").textContent).toContain("provider unavailable"));
    expect(screen.getByText("Not analyzed")).toBeTruthy();
  });
});
