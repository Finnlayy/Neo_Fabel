import { SubAgentState } from "./types";

/** Static agent roster (status copy only — not a market data feed). */
export const INITIAL_SUB_AGENTS: SubAgentState[] = [
  {
    id: "orchestrator",
    name: "MASTER ORCHESTRATOR AGENT",
    status: "ACTIVE",
    efficiency: 99.4,
    directive: "Coordinate multi-agent telemetry, verify execution safety, and allocate real-time resources based on composite neural signals.",
    lastAction: "Synchronized target allocation values with core trading nodes."
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
    status: "OPTIMIZING",
    efficiency: 97.5,
    directive: "Continually optimize parameter thresholds, scale leverage ratios dynamically, and balance risk profiles.",
    lastAction: "Recalibrated position-sizing factor from 1.2x to 1.35x based on volume surge."
  },
  {
    id: "rna_smart",
    name: "RNA Smartelligent Agent",
    status: "ACTIVE",
    efficiency: 99.1,
    directive: "Execute Deep Neural Network model for pattern recognition, real-time fractal detection, and anomaly filtering.",
    lastAction: "Identified high-probability bullish wedge formation on SOL/USD 15m frame."
  },
  {
    id: "risk_gov",
    name: "Risk Governor Agent",
    status: "ACTIVE",
    efficiency: 100.0,
    directive: "Enforce hard max drawdowns, audit slippage deviations, verify counterparty margin parameters.",
    lastAction: "Verified 100% compliance with safe capital deployment limits."
  },
  {
    id: "predictive",
    name: "Predictive Modeling Agent",
    status: "STANDBY",
    efficiency: 96.2,
    directive: "Generate short-term price vectors, estimate volatility corridors, and project liquidations cascades.",
    lastAction: "Refreshed 1-hour interval predictive vectors for top 5 index assets."
  },
  {
    id: "analytic",
    name: "Analytical Analysis Agent",
    status: "ACTIVE",
    efficiency: 98.7,
    directive: "Perform multi-asset portfolio optimization, compile performance histories, and evaluate yield curves.",
    lastAction: "Generated daily execution analysis report; compiled composite profit factor metrics."
  }
];
