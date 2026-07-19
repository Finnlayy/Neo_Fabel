import React from "react";
import {cleanup, render, screen, waitFor} from "@testing-library/react";
import {afterEach, beforeEach, describe, expect, it, vi} from "vitest";

vi.mock("../../api/onnx", () => ({
  fetchOnnxStatus: vi.fn(async () => ({
    configured: false,
    runtime_available: false,
    netron_available: false,
    models_dir: "",
    model_count: 0,
  })),
  fetchOnnxModels: vi.fn(async () => ({models: []})),
  netronEmbedUrl: (id: string) => `/static/netron/index.html?url=%2Fstatic%2Fonnx%2F${id}.onnx`,
  inferOnnx: vi.fn(),
  startOnnxTrain: vi.fn(),
}));

vi.mock("../../components/NeuralTracker", () => ({
  default: ({currentPrice}: {currentPrice: number}) => (
    <div data-testid="neural-tracker">price:{currentPrice}</div>
  ),
}));

import OnnxPage from "./OnnxPage";

describe("OnnxPage", () => {
  afterEach(() => cleanup());
  beforeEach(() => vi.clearAllMocks());

  it("renders LSTM core panel with price", async () => {
    render(
      <OnnxPage currentPrice={50123.45} activeSymbol="BTC" marketLive language="en" />,
    );
    await waitFor(() => {
      expect(screen.getByTestId("neural-tracker").textContent).toContain("50123.45");
    });
    expect(screen.getByText(/BTC\/USD/)).toBeTruthy();
    expect(screen.getByRole("button", {name: /LSTM core/i})).toBeTruthy();
    expect(screen.getByRole("button", {name: /Model graph/i})).toBeTruthy();
  });
});
