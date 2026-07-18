import {apiRequest} from "./client";
import type {Trade} from "../types";

export type PaperStatusResponse = {
  mode: string;
  data: unknown;
  request_id?: string;
};

export async function fetchPaperStatus(): Promise<PaperStatusResponse> {
  return apiRequest<PaperStatusResponse>("/api/v1/paper/status");
}

/** Best-effort map of opaque Kraken paper status JSON into Trade rows. */
export function mapPaperStatusToTrades(data: unknown): Trade[] {
  if (!data || typeof data !== "object") return [];
  const root = data as Record<string, unknown>;
  const candidates: unknown[] = [];
  for (const key of ["orders", "open_orders", "closed_orders", "fills", "trades", "history"]) {
    const value = root[key];
    if (Array.isArray(value)) candidates.push(...value);
  }
  if (Array.isArray(root.result)) candidates.push(...root.result);
  if (root.result && typeof root.result === "object") {
    const nested = root.result as Record<string, unknown>;
    for (const value of Object.values(nested)) {
      if (Array.isArray(value)) candidates.push(...value);
      else if (value && typeof value === "object") candidates.push(value);
    }
  }

  const trades: Trade[] = [];
  candidates.forEach((item, index) => {
    if (!item || typeof item !== "object") return;
    const row = item as Record<string, unknown>;
    const pair = String(row.pair ?? row.symbol ?? row.descr ?? "UNKNOWN");
    const asset = pair.replace(/USD$|\/USD$/i, "").replace(/[^A-Z0-9]/gi, "") || "UNK";
    const sideRaw = String(row.side ?? row.type ?? row.ordertype ?? "buy").toLowerCase();
    const type: "BUY" | "SELL" = sideRaw.includes("sell") ? "SELL" : "BUY";
    const price = Number(row.price ?? row.avg_price ?? row.limit_price ?? 0) || 0;
    const amount = Number(row.vol ?? row.volume ?? row.amount ?? row.qty ?? 0) || 0;
    const pnl = Number(row.pnl ?? row.realized_pnl ?? row.net ?? 0) || 0;
    const statusRaw = String(row.status ?? row.state ?? "PENDING").toUpperCase();
    const status: Trade["status"] =
      statusRaw.includes("CLOSE") || statusRaw.includes("FILL") || statusRaw === "CLOSED"
        ? "COMPLETED"
        : statusRaw.includes("CANCEL") || statusRaw.includes("HALT")
          ? "HALTED"
          : "PENDING";
    const id = String(row.txid ?? row.id ?? row.order_id ?? `PAPER-${index}`);
    const time = String(row.time ?? row.opentm ?? row.closetm ?? new Date().toLocaleTimeString());
    trades.push({id, time, asset, type, price, amount, pnl, status});
  });
  return trades;
}
