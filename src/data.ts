import { TickerData, Trade, TelegramSignal, SubAgentState, OrderBookEntry } from "./types";

export const INITIAL_TICKERS: TickerData[] = [
  { symbol: "BTC", name: "Bitcoin", price: 92450.5, change: 4.7, history: [91100, 91350, 91800, 92100, 91900, 92250, 92450.5] },
  { symbol: "ETH", name: "Ethereum", price: 3412.2, change: 3.7, history: [3310, 3325, 3350, 3370, 3360, 3390, 3412.2] },
  { symbol: "SOL", name: "Solana", price: 184.6, change: 6.1, history: [172, 175, 174, 178, 181, 183, 184.6] },
  { symbol: "MATIC", name: "Polygon", price: 0.58, change: 1.2, history: [0.56, 0.57, 0.57, 0.58, 0.58, 0.57, 0.58] },
  { symbol: "AVAX", name: "Avalanche", price: 28.4, change: -1.7, history: [29.1, 29.0, 28.8, 28.5, 28.9, 28.6, 28.4] },
  { symbol: "DOT", name: "Polkadot", price: 4.85, change: -0.3, history: [4.90, 4.88, 4.87, 4.85, 4.86, 4.84, 4.85] },
  { symbol: "XRP", name: "Ripple", price: 0.62, change: 2.2, history: [0.59, 0.60, 0.61, 0.61, 0.62, 0.61, 0.62] },
  { symbol: "ADA", name: "Cardano", price: 0.38, change: -1.1, history: [0.39, 0.39, 0.38, 0.38, 0.39, 0.38, 0.38] },
  { symbol: "NIO", name: "NIO Inc. (EV)", price: 4.25, change: 2.1, history: [4.10, 4.15, 4.20, 4.18, 4.22, 4.21, 4.25] }
];

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
    lastAction: "Processed 12,450 trade events across 8 high-volume pairs."
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

export const INITIAL_TRADES: Trade[] = [
  { id: "T-01", time: "07:45:12", asset: "BTC", type: "BUY", price: 92150.0, amount: 0.15, pnl: 45.0, status: "COMPLETED" },
  { id: "T-02", time: "07:48:33", asset: "ETH", type: "BUY", price: 3385.5, amount: 1.2, pnl: 32.0, status: "COMPLETED" },
  { id: "T-03", time: "07:51:04", asset: "SOL", type: "BUY", price: 178.2, amount: 15.0, pnl: 96.0, status: "COMPLETED" },
  { id: "T-04", time: "07:54:19", asset: "BTC", type: "SELL", price: 92400.0, amount: 0.15, pnl: 37.5, status: "COMPLETED" },
  { id: "T-05", time: "07:56:55", asset: "AVAX", type: "SELL", price: 28.9, amount: 40.0, pnl: -20.0, status: "COMPLETED" },
  { id: "T-06", time: "07:58:21", asset: "SOL", type: "BUY", price: 181.4, amount: 20.0, pnl: 64.0, status: "COMPLETED" },
  { id: "T-07", time: "08:00:45", asset: "ETH", type: "SELL", price: 3410.0, amount: 0.8, pnl: 19.6, status: "COMPLETED" },
  { id: "T-08", time: "08:01:12", asset: "MATIC", type: "BUY", price: 0.575, amount: 1000, pnl: 5.0, status: "COMPLETED" }
];

export const INITIAL_TELEGRAM_SIGNALS: TelegramSignal[] = [
  {
    id: "TS-1",
    timestamp: "07:58:12",
    channel: "LIVE TRADE EBP TELEGRAM",
    message: "🚨 BREAKOUT DETECTED: SOL/USD showing heavy order book pressure near $183.5 resistance. Entering scaled long strategy.",
    sentiment: "BULLISH",
    actionable: true
  },
  {
    id: "TS-2",
    timestamp: "08:00:04",
    channel: "ALPHA FEED SIGNALS",
    message: "📊 ETH consolidated successfully above 100-EMA on 1h chart. Dynamic support holds firmly. Targets: $3,450 / $3,490.",
    sentiment: "BULLISH",
    actionable: false
  },
  {
    id: "TS-3",
    timestamp: "08:02:19",
    channel: "WHALE ALERTS TELEGRAM",
    message: "🐳 Massive buy wall cleared on BTC perpetual order book at $92,200. Adaptive agent scaling exposure index.",
    sentiment: "BULLISH",
    actionable: true
  },
  {
    id: "TS-4",
    timestamp: "08:03:01",
    channel: "RISK MONITOR DECK",
    message: "⚠️ AVAX funding rate spiking, slight bearish divergence on volume indices. Recommending margin safety scaling.",
    sentiment: "BEARISH",
    actionable: false
  }
];

export const generateOrderBook = (midPrice: number): OrderBookEntry[] => {
  const bids: OrderBookEntry[] = [];
  const asks: OrderBookEntry[] = [];
  
  // Create 5 bids below midPrice
  let bidAccum = 0;
  for (let i = 1; i <= 6; i++) {
    const price = Number((midPrice * (1 - i * 0.0005)).toFixed(2));
    const amount = Number((Math.random() * 2 + 0.1).toFixed(3));
    bidAccum += amount;
    bids.push({ price, amount, total: Number(bidAccum.toFixed(3)), type: "BID" });
  }

  // Create 5 asks above midPrice
  let askAccum = 0;
  for (let i = 1; i <= 6; i++) {
    const price = Number((midPrice * (1 + i * 0.0005)).toFixed(2));
    const amount = Number((Math.random() * 2 + 0.1).toFixed(3));
    askAccum += amount;
    asks.push({ price, amount, total: Number(askAccum.toFixed(3)), type: "ASK" });
  }

  return [...asks.reverse(), ...bids];
};
