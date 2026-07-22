import type { Trade } from "../types";

export function tradesForAnalyzeWire(trades: Trade[]): Trade[] {
  // Return last ~25 trades for analysis (server also caps)
  return trades.slice(-25);
}
