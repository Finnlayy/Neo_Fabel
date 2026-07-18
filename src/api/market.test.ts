import {describe, expect, it} from "vitest";
import {extractChangePct, extractLastPrice, mergeTickerHistory} from "./market";

describe("market parsers", () => {
  it("extracts last price from nested kraken-shaped payloads", () => {
    expect(extractLastPrice({last: "118500.25"})).toBe(118500.25);
    expect(extractLastPrice({XXBTZUSD: {c: ["95000.1", "95000.1"]}})).toBe(95000.1);
  });

  it("computes change from open when percent missing", () => {
    expect(extractChangePct({open: "100"}, 110)).toBeCloseTo(10);
  });

  it("merges history without dropping prior samples", () => {
    const merged = mergeTickerHistory(
      [{symbol: "BTC", name: "Bitcoin", price: 1, change: 0, history: [1, 2]}],
      [{symbol: "BTC", name: "Bitcoin", price: 3, change: 1, history: [3]}],
    );
    expect(merged[0].history).toEqual([1, 2, 3]);
  });
});
