import {apiRequest} from "./client";

export type ReadyStatus = {
  status: string;
  database?: string;
  execution?: string;
  autonomy_level?: number;
  live_trading_enabled?: boolean;
};

export async function fetchReadyStatus(): Promise<ReadyStatus> {
  return apiRequest<ReadyStatus>("/health/ready");
}
