import {describe, expect, it} from "vitest";
import {mapPaperStatusToTrades} from "./paper";

describe("mapPaperStatusToTrades v2", () => {
  it("reads fills from spot and futures partitions", () => {
    const trades = mapPaperStatusToTrades({
      version: 2,
      spot: {
        fills: [
          {
            txid: "s1",
            pair: "BTCUSD",
            side: "buy",
            volume: "0.01",
            price: "50000",
            realized_pnl: "0",
            status: "closed",
            time: "2026-07-20T10:00:00Z",
          },
        ],
      },
      futures: {
        fills: [
          {
            txid: "f1",
            pair: "PF_XBTUSD",
            side: "sell",
            volume: "0.02",
            price: "51000",
            realized_pnl: "5",
            status: "closed",
            time: "2026-07-20T11:00:00Z",
          },
        ],
      },
      orders: [],
    });
    expect(trades).toHaveLength(2);
    expect(trades.some((t) => t.asset === "BTC")).toBe(true);
    expect(trades.some((t) => t.type === "SELL")).toBe(true);
  });
});

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
