import React from "react";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const mockStatus = {
  agent: "chronos",
  paper_only: true,
  live_trading: false,
  phase: 1,
  encoder: "stub_linear_v1",
  latent_dim: 20,
  vocab: { coarse: 1024, fine: 1024, full_bits: 20 },
  features: ["open", "high", "low", "close", "volume", "amount"],
  matplotlib_available: true,
  indicators_available: true,
  vectorbt_available: true,
  deps: {
    numpy: true,
    pandas: true,
    matplotlib: true,
    torch: true,
    vectorbt: true,
    pinets_cli: true,
    research_ready: true,
  },
};

const mockTokenize = vi.fn(async () => ({
  paper_only: true,
  encoder: "stub_linear_v1",
  lookback: 4,
  feature_order: ["open", "high", "low", "close", "volume", "amount"],
  mean: [1, 1, 1, 1, 1, 1],
  std: [1, 1, 1, 1, 1, 1],
  x_norm: [
    [0, 0, 0, 0, 0, 0],
    [0, 0, 0, 0, 0, 0],
    [0, 0, 0, 0, 0, 0],
    [0, 0, 0, 0, 0, 0],
  ],
  s1_ids: [10, 20, 30, 40],
  s2_ids: [11, 21, 31, 41],
  vocab: { coarse: 1024, fine: 1024, full_bits: 20 },
  entropy_mean: 0.42,
  live_trading: false,
}));

vi.mock("../../api/chronos", () => ({
  fetchChronosStatus: vi.fn(async () => mockStatus),
  normalizeChronos: vi.fn(async () => ({
    paper_only: true,
    lookback: 4,
    feature_order: ["open", "high", "low", "close", "volume", "amount"],
    mean: [1, 1, 1, 1, 1, 1],
    std: [1, 1, 1, 1, 1, 1],
    x_norm: [],
  })),
  tokenizeChronos: (...args: unknown[]) => mockTokenize(...args),
  fetchChronosCharts: vi.fn(async () => ({
    charts: {
      ohlc: "data:image/png;base64,aaa",
      zscore: "data:image/png;base64,bbb",
      tokens: "data:image/png;base64,ccc",
      token_hist: "data:image/png;base64,ddd",
    },
    lookback: 4,
    paper_only: true,
    renderer: "matplotlib",
  })),
  predictChronos: vi.fn(async () => ({
    paper_only: true,
    live_trading: false,
    encoder: "stub_momentum_v1",
    lookback: 4,
    pred_len: 8,
    sample_count: 8,
    T: 1,
    top_p: 0.9,
    columns: ["open", "high", "low", "close", "volume", "amount"],
    pred: Array.from({ length: 8 }, () => ({
      open: 100,
      high: 101,
      low: 99,
      close: 100.5,
      volume: 10,
      amount: 1000,
    })),
    history: [],
    charts: {
      prediction: "data:image/png;base64,pred",
      prediction_wo_vol: "data:image/png;base64,predwo",
      monte_carlo: "data:image/png;base64,mc",
    },
  })),
  bsqDecode: vi.fn(async () => ({ z: Array(20).fill(0.1), scale: 0.22, paper_only: true })),
  bsqEncode: vi.fn(),
  fetchChronosIndicators: vi.fn(async () => ({
    paper_only: true,
    indicators: { rsi: 55.2, ema_distance_pct: 0.12, atr_pct: 1.8 },
    engine: "numpy_pandas",
  })),
  fetchChronosBacktest: vi.fn(async () => ({
    paper_only: true,
    strategy: "ema_cross_8_21",
    total_return_pct: 2.5,
    sharpe: 0.8,
    max_drawdown_pct: -1.2,
    trades: 4,
  })),
}));

vi.mock("../../api/ohlcv", () => ({
  fetchOhlcvCandles: vi.fn(async () => ({
    candles: [
      { time: "t1", open: 100, high: 101, low: 99, close: 100.5, volume: 10 },
      { time: "t2", open: 100.5, high: 102, low: 100, close: 101, volume: 12 },
      { time: "t3", open: 101, high: 103, low: 100.5, close: 102, volume: 8 },
      { time: "t4", open: 102, high: 104, low: 101, close: 103, volume: 15 },
    ],
    asOf: "now",
    source: "mock",
  })),
}));

import ChronosPage from "./ChronosPage";

describe("ChronosPage", () => {
  afterEach(() => cleanup());
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders PAPER ONLY badge", async () => {
    render(<ChronosPage activeSymbol="BTC" language="en" />);
    await waitFor(() => {
      expect(screen.getByTestId("chronos-paper-only").textContent).toContain("PAPER ONLY");
    });
    expect(screen.getByRole("tabpanel")).toBeTruthy();
  });

  it("can tokenize and show s1_ids length", async () => {
    render(<ChronosPage activeSymbol="BTC" language="en" />);
    await waitFor(() => {
      expect(screen.getByTestId("chronos-paper-only")).toBeTruthy();
    });

    fireEvent.click(screen.getByRole("button", { name: /Load lookback/i }));
    await waitFor(() => {
      expect(screen.getByText(/Loaded: 4 bars/i)).toBeTruthy();
    });

    fireEvent.click(screen.getByRole("button", { name: /Pipeline/i }));
    fireEvent.click(screen.getByRole("button", { name: /Tokenize/i }));
    await waitFor(() => {
      expect(mockTokenize).toHaveBeenCalled();
      expect(screen.getByTestId("chronos-charts")).toBeTruthy();
      expect(screen.getByAltText(/OHLC lookback/i)).toBeTruthy();
    });
    fireEvent.click(screen.getByRole("button", { name: /Advanced/i }));
    await waitFor(() => {
      expect(screen.getByTestId("chronos-s1-len").textContent).toBe("4");
    });
  });

  it("can predict and show Kronos-style charts", async () => {
    const { predictChronos } = await import("../../api/chronos");
    render(<ChronosPage activeSymbol="BTC" language="en" />);
    await waitFor(() => {
      expect(screen.getByTestId("chronos-paper-only")).toBeTruthy();
    });
    fireEvent.click(screen.getByRole("button", { name: /Load lookback/i }));
    await waitFor(() => {
      expect(screen.getByText(/Loaded: 4 bars/i)).toBeTruthy();
    });
    fireEvent.click(screen.getByRole("button", { name: /Forecast/i }));
    fireEvent.click(screen.getByTestId("chronos-predict"));
    await waitFor(() => {
      expect(predictChronos).toHaveBeenCalled();
      expect(screen.getByTestId("chronos-prediction-charts")).toBeTruthy();
      expect(screen.getByTestId("chronos-pred-len").textContent).toContain("pred rows: 8");
    });
  });
});
