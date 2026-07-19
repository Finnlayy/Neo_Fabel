import {describe, expect, it} from "vitest";
import {mapPaperStatusToTrades} from "./paper";

describe("mapPaperStatusToTrades", () => {
  it("returns empty for unknown shapes", () => {
    expect(mapPaperStatusToTrades(null)).toEqual([]);
    expect(mapPaperStatusToTrades({})).toEqual([]);
  });

  it("maps a simple orders array", () => {
    const trades = mapPaperStatusToTrades({
      orders: [
        {
          id: "o1",
          pair: "BTCUSD",
          side: "buy",
          price: 100,
          volume: 0.01,
          pnl: 12,
          status: "closed",
          time: "10:00:00",
        },
      ],
    });
    expect(trades).toHaveLength(1);
    expect(trades[0].asset).toBe("BTC");
    expect(trades[0].type).toBe("BUY");
    expect(trades[0].status).toBe("COMPLETED");
    expect(trades[0].pnl).toBe(12);
  });
});
