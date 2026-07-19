import type {TickerData} from "../types";

export type MarketStreamTicker = {
  symbol: string;
  name: string;
  price: number;
  change: number;
  history?: number[];
};

export type MarketStreamMessage = {
  type: "hello" | "tickers" | "error" | "pong";
  source?: string;
  exchange?: string;
  as_of?: string;
  message?: string;
  hint?: string;
  tickers?: MarketStreamTicker[];
};

export type MarketStreamHandlers = {
  onTickers: (tickers: TickerData[], asOf: string, source: string) => void;
  onStatus?: (status: "connecting" | "open" | "closed" | "error", detail?: string) => void;
};

function wsUrl(): string {
  const proto = window.location.protocol === "https:" ? "wss:" : "ws:";
  return `${proto}//${window.location.host}/api/v1/market/stream`;
}

export function streamTickersToTickerData(rows: MarketStreamTicker[]): TickerData[] {
  return rows
    .filter((row) => Number.isFinite(row.price) && row.price > 0)
    .map((row) => ({
      symbol: row.symbol,
      name: row.name || row.symbol,
      price: row.price,
      change: Number.isFinite(row.change) ? row.change : 0,
      history: Array.isArray(row.history) && row.history.length > 0 ? row.history : [row.price],
    }));
}

/**
 * Connect to the FastAPI market WebSocket (Vite proxies /api → :8000).
 * Returns a disconnect function. Automatically reconnects with backoff until stopped.
 */
export function connectMarketStream(handlers: MarketStreamHandlers): () => void {
  let stopped = false;
  let socket: WebSocket | null = null;
  let reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  let attempt = 0;
  let pingTimer: ReturnType<typeof setInterval> | null = null;

  const clearTimers = () => {
    if (reconnectTimer !== null) {
      clearTimeout(reconnectTimer);
      reconnectTimer = null;
    }
    if (pingTimer !== null) {
      clearInterval(pingTimer);
      pingTimer = null;
    }
  };

  const scheduleReconnect = () => {
    if (stopped) return;
    const delay = Math.min(15000, 1000 * 2 ** Math.min(attempt, 4));
    attempt += 1;
    reconnectTimer = setTimeout(connect, delay);
  };

  const connect = () => {
    if (stopped) return;
    clearTimers();
    handlers.onStatus?.("connecting");
    const ws = new WebSocket(wsUrl());
    socket = ws;

    ws.onopen = () => {
      attempt = 0;
      handlers.onStatus?.("open");
      pingTimer = setInterval(() => {
        if (ws.readyState === WebSocket.OPEN) {
          ws.send("ping");
        }
      }, 25000);
    };

    ws.onmessage = (event) => {
      let payload: MarketStreamMessage;
      try {
        payload = JSON.parse(String(event.data)) as MarketStreamMessage;
      } catch {
        return;
      }
      if (payload.type === "tickers" && Array.isArray(payload.tickers)) {
        const tickers = streamTickersToTickerData(payload.tickers);
        if (tickers.length > 0) {
          handlers.onTickers(tickers, payload.as_of || new Date().toISOString(), payload.source || "stream");
        }
        return;
      }
      if (payload.type === "error") {
        handlers.onStatus?.("error", payload.message || "stream_error");
      }
    };

    ws.onerror = () => {
      handlers.onStatus?.("error", "websocket_error");
    };

    ws.onclose = () => {
      clearTimers();
      handlers.onStatus?.("closed");
      socket = null;
      scheduleReconnect();
    };
  };

  connect();

  return () => {
    stopped = true;
    clearTimers();
    if (socket) {
      socket.onclose = null;
      socket.close();
      socket = null;
    }
    handlers.onStatus?.("closed");
  };
}
