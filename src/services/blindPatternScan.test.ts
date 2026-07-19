import {describe, expect, it} from "vitest";
import {closesToBlindCandles, ohlcToBlindCandles, scanBlindPatterns} from "./blindPatternScan";

describe("blindPatternScan", () => {
  it("detects bullish engulfing without using absolute prices in summary", () => {
    const candles = ohlcToBlindCandles([
      {open: 110, high: 111, low: 100, close: 101},
      {open: 100, high: 120, low: 99, close: 118},
    ]);
    const result = scanBlindPatterns(candles);
    expect(result.hits.some((h) => h.name === "Bullish Engulfing")).toBe(true);
    expect(result.summary.toLowerCase()).not.toMatch(/btc|usd|\$|15m|sol/);
    expect(result.summary).toMatch(/no symbol\/TF\/price context/i);
  });

  it("builds relative candles from closes only", () => {
    const candles = closesToBlindCandles([100, 99, 98, 105]);
    expect(candles.length).toBe(3);
    const result = scanBlindPatterns(candles);
    expect(result.candleCount).toBe(3);
  });

  it("detects hammer geometry", () => {
    const candles = ohlcToBlindCandles([{open: 10, high: 10.2, low: 8, close: 10.1}]);
    const result = scanBlindPatterns(candles);
    expect(result.hits.some((h) => h.name === "Hammer" || h.name === "Hanging Man")).toBe(true);
  });
});
