import {apiRequest} from "../api/client";

export type RnaPatternBias = "bullish" | "bearish" | "neutral";

export async function pushRnaContext(body: {
  bias: RnaPatternBias;
  confidence: number;
  symbol?: string;
  positionCost?: number;
  executionPrice?: number;
}): Promise<void> {
  await apiRequest("/api/v1/signals/rna-context", {
    method: "PUT",
    body: JSON.stringify({
      bias: body.bias,
      confidence: String(body.confidence),
      symbol: body.symbol,
      positionCost: body.positionCost ? String(body.positionCost) : undefined,
      executionPrice: body.executionPrice ? String(body.executionPrice) : undefined,
    }),
  });
}
