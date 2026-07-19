import {describe, expect, it} from "vitest";
import {streamTickersToTickerData} from "./marketStream";

describe("streamTickersToTickerData", () => {
  it("maps stream rows into TickerData and drops invalid prices", () => {
    const rows = streamTickersToTickerData([
      {symbol: "BTC", name: "Bitcoin", price: 100, change: 1.2, history: [90, 100]},
      {symbol: "BAD", name: "Bad", price: 0, change: 0},
    ]);
    expect(rows).toHaveLength(1);
    expect(rows[0]).toMatchObject({
      symbol: "BTC",
      name: "Bitcoin",
      price: 100,
      change: 1.2,
      history: [90, 100],
    });
  });

  it("seeds history from price when history missing", () => {
    const rows = streamTickersToTickerData([{symbol: "ETH", name: "Ethereum", price: 50, change: -0.5}]);
    expect(rows[0].history).toEqual([50]);
  });
});
