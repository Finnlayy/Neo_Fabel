import {describe, expect, it, vi, beforeEach} from "vitest";
import {fetchLoopsStatus, parseLiveSymbols, startPaperLoop, startLiveLoop} from "./loops";

vi.mock("./client", () => ({
  apiRequest: vi.fn(),
}));

import {apiRequest} from "./client";

describe("loops api client", () => {
  beforeEach(() => {
    vi.mocked(apiRequest).mockReset();
  });

  it("fetches loop status", async () => {
    vi.mocked(apiRequest).mockResolvedValueOnce({
      paper: {running: false, mode: "paper"},
      live: {running: false, can_start: false, deadman_armed: false, autonomy: 2, live_enabled: false},
    });
    const status = await fetchLoopsStatus();
    expect(apiRequest).toHaveBeenCalledWith("/api/v1/loops/status");
    expect(status.paper.running).toBe(false);
  });

  it("posts paper start", async () => {
    vi.mocked(apiRequest).mockResolvedValueOnce({started: true});
    await startPaperLoop();
    expect(apiRequest).toHaveBeenCalledWith("/api/v1/loops/paper/start", {method: "POST"});
  });

  it("posts live start with session caps and symbols", async () => {
    vi.mocked(apiRequest).mockResolvedValueOnce({started: true});
    await startLiveLoop({
      max_margin_eur: 10,
      max_session_size: {value: 10, unit: "eur"},
      max_concurrent_trades: 2,
      starting_capital_eur: 10,
      max_drawdown_usd: 2,
      daily_loss_limit: {value: 5, unit: "pct"},
      min_confidence_pct: 60,
      allow_pre_post_market: false,
      human_verification: true,
      symbols: ["XRPUSD", "METAUSD", "ADAUSD"],
      position_sizing_mode: "dynamic_kelly",
    });
    expect(apiRequest).toHaveBeenCalledWith("/api/v1/loops/live/start", {
      method: "POST",
      body: JSON.stringify({
        max_concurrent_trades: 2,
        position_sizing_mode: "dynamic_kelly",
        starting_capital_eur: 10,
        max_drawdown_usd: 2,
        min_confidence_pct: 60,
        allow_pre_post_market: false,
        human_verification: true,
        max_session_size: {value: 10, unit: "eur"},
        daily_loss_limit: {value: 5, unit: "pct"},
        symbols: ["XRPUSD", "METAUSD", "ADAUSD"],
      }),
    });
  });

  it("posts live start with manual sizing", async () => {
    vi.mocked(apiRequest).mockResolvedValueOnce({started: true});
    await startLiveLoop({
      max_margin_eur: 10,
      max_concurrent_trades: 2,
      starting_capital_eur: 10,
      max_drawdown_usd: 2,
      position_sizing_mode: "fixed_usd",
      fixed_notional_usd: 5,
    });
    expect(apiRequest).toHaveBeenCalledWith("/api/v1/loops/live/start", {
      method: "POST",
      body: JSON.stringify({
        max_concurrent_trades: 2,
        position_sizing_mode: "fixed_usd",
        starting_capital_eur: 10,
        max_drawdown_usd: 2,
        min_confidence_pct: 0,
        allow_pre_post_market: true,
        human_verification: false,
        max_margin_eur: 10,
        max_session_size: {value: 10, unit: "eur"},
        fixed_notional_usd: 5,
      }),
    });
  });

  it("parses symbol lists", () => {
    expect(parseLiveSymbols("xrpusd, meta-usd ; ADAUSD")).toEqual([
      "XRPUSD",
      "METAUSD",
      "ADAUSD",
    ]);
  });
});
