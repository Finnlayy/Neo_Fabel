import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import type { TvapiOptimizeSuccess } from "../api/ai";
import OptimizationDashboard, { numericParameterNames } from "./OptimizationDashboard";

const result: TvapiOptimizeSuccess = {
  success: true,
  source: "candle-backtest/injected-ohlcv",
  candlesUsed: 300,
  tested: 4,
  bericht: "report",
  selfTest: "PASS",
  winner: {
    label: "EMA-CROSS-9/21",
    profitFactor: 1.82,
    winRate: 58.4,
    netProfit: 124.5,
    trades: 37,
    maxDrawdown: 18.2,
    inputs: { emaFast: 9, emaSlow: 21 },
  },
  results: [
    {
      rank: 1,
      label: "EMA-9/21",
      profitFactor: 1.82,
      winRate: 58.4,
      netProfit: 124.5,
      trades: 37,
      maxDrawdown: 18.2,
      inputs: { emaFast: 9, emaSlow: 21 },
      isWinner: true,
      isDisqualified: false,
    },
    {
      rank: 2,
      label: "EMA-12/26",
      profitFactor: 1.41,
      winRate: 52.1,
      netProfit: 74.2,
      trades: 31,
      maxDrawdown: 24.6,
      inputs: { emaFast: 12, emaSlow: 26 },
      isWinner: false,
      isDisqualified: false,
    },
  ],
};

describe("OptimizationDashboard", () => {
  it("renders metrics and provenance from the real optimization response", () => {
    render(
      <OptimizationDashboard
        activeSymbol="BTCUSD"
        strategyName="EMA sweep"
        result={result}
      />,
    );

    expect(screen.getByText("EMA-CROSS-9/21")).toBeTruthy();
    expect(screen.getByText("1.82")).toBeTruthy();
    expect(screen.getByText("58.4%")).toBeTruthy();
    expect(screen.getByText(/candle-backtest\/injected-ohlcv/i)).toBeTruthy();
    expect(screen.getByText(/2 valid of 2 returned runs/i)).toBeTruthy();
    expect(screen.getByTestId("ranked-performance-chart")).toBeTruthy();
    expect(screen.getByTestId("parameter-grid-chart")).toBeTruthy();
    expect(screen.getByTestId("run-robustness-chart")).toBeTruthy();
  });

  it("derives only varying numeric parameters", () => {
    expect(numericParameterNames(result.results)).toEqual(["emaFast", "emaSlow"]);
    expect(
      numericParameterNames([
        {
          ...result.results[0],
          inputs: { fixed: 2, label: "A" },
        },
        {
          ...result.results[1],
          inputs: { fixed: 2, label: "B" },
        },
      ]),
    ).toEqual([]);
  });

  it("does not fabricate a parameter grid when inputs are missing", () => {
    const withoutInputs: TvapiOptimizeSuccess = {
      ...result,
      results: result.results.map(({ inputs: _inputs, ...run }) => run),
    };

    render(
      <OptimizationDashboard
        activeSymbol="ETHUSD"
        strategyName="Legacy response"
        result={withoutInputs}
      />,
    );

    expect(screen.getByText(/parameter grid unavailable/i)).toBeTruthy();
    expect(screen.getByText(/no synthetic grid is generated/i)).toBeTruthy();
  });
});
