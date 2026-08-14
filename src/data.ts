import { SubAgentState } from "./types";

/** Static agent roster (status copy only — not a market data feed). */
export const INITIAL_SUB_AGENTS: SubAgentState[] = [
  {
    id: "orchestrator",
    name: "MASTER ORCHESTRATOR AGENT",
    status: "ACTIVE",
    efficiency: 99.4,
    directive: "Coordinate multi-agent telemetry, verify execution safety, and allocate real-time resources based on composite neural signals.",
    lastAction: "Awaiting live market + allocation sync."
  },
  {
    id: "market_data",
    name: "Market Data Agent",
    status: "ACTIVE",
    efficiency: 98.9,
    directive: "Ingest multi-exchange ticks, compute real-time VWAP, and stream order book depth profiles.",
    lastAction: "Waiting for CCXT/WebSocket market stream."
  },
  {
    id: "adaptive",
    name: "Adaptive Agent",
    status: "ACTIVE",
    efficiency: 97.5,
    directive: "Continually optimize parameter thresholds, scale leverage ratios dynamically, and balance risk profiles.",
    lastAction: "Awaiting live tape for sizing recalibration."
  },
  {
    id: "rna_smart",
    name: "RNA Smartelligent Agent",
    status: "ACTIVE",
    efficiency: 99.1,
    directive: "Blindfolded candlestick pattern recognition — geometry only; no symbol, timeframe, or absolute prices.",
    lastAction: "Blind pattern scan idle — awaiting relative candle geometry."
  },
  {
    id: "risk_gov",
    name: "Risk Governor Agent",
    status: "ACTIVE",
    efficiency: 100.0,
    directive: "Enforce hard max drawdowns, audit slippage deviations, verify counterparty margin parameters.",
    lastAction: "Awaiting execution mode + compliance sync."
  },
  {
    id: "kraken_broker",
    name: "Kraken Broker Execution",
    status: "ACTIVE",
    efficiency: 98.2,
    directive:
      "Route paper/live orders through the Kraken broker path, enforce autonomy gates, and report fill/reject telemetry.",
    lastAction: "Awaiting execution mode + paper ledger sync."
  },
  {
    id: "predictive",
    name: "Predictive Modeling Agent",
    status: "STANDBY",
    efficiency: 96.2,
    directive: "Generate short-term price vectors, estimate volatility corridors, and project liquidations cascades.",
    lastAction: "Awaiting live movers for vector refresh."
  },
  {
    id: "chronos",
    name: "Chronos K-Line Agent",
    status: "STANDBY",
    efficiency: 97.0,
    directive:
      "Context-free OHLCVA language modeling via causal Z-score + Binary Spherical Quantization (coarse/fine). Paper signals only — never auto-executes.",
    lastAction: "Phase-1 substrate ready — awaiting lookback tokenize."
  },
  {
    id: "analytic",
    name: "Analytical Analysis Agent",
    status: "ACTIVE",
    efficiency: 98.7,
    directive: "Perform multi-asset portfolio optimization, compile performance histories, and evaluate yield curves.",
    lastAction: "Awaiting paper ledger rows for analysis."
  }
];
