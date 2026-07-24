export type MainTab = "dashboard" | "terminal" | "strategy" | "swarm" | "signals" | "academy" | "full";

export interface TickerData {
  symbol: string;
  name: string;
  price: number;
  change: number; // percentage change, e.g. +4.7
  history: number[]; // simple array of recent prices for sparklines
}

export interface Trade {
  id: string;
  time: string;
  asset: string;
  type: "BUY" | "SELL";
  price: number;
  amount: number;
  pnl: number;
  status: "COMPLETED" | "PENDING" | "HALTED";
}

export interface TelegramSignal {
  id: string;
  timestamp: string;
  channel: string;
  message: string;
  sentiment: "BULLISH" | "BEARISH" | "NEUTRAL";
  actionable: boolean;
}

export interface SubAgentState {
  id: string;
  name: string;
  status: "ACTIVE" | "IDLE" | "OPTIMIZING" | "STANDBY" | "ALERT";
  efficiency: number; // e.g. 98.2%
  directive: string;
  lastAction: string;
}

export interface OrderBookEntry {
  price: number;
  amount: number;
  total: number;
  type: "BID" | "ASK";
}

export interface GenerativePlan {
  planTitle: string;
  summary: string;
  subAgentDirectives: {
    marketData: string;
    adaptiveAgent: string;
    rnaSmartelligent: string;
    riskGovernor: string;
  };
  resourceAllocation: { name: string; value: number }[];
  suggestedRules: string[];
}

export interface AgentStatusPacket {
  id: string;
  status: string;
  message?: string;
  data?: any;
}
