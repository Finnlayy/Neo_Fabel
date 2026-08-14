/** Lean chat wire protocol — UI may keep a long transcript; only this window hits /api/chat. */

export const WIRE_MAX_MESSAGES = 12;
export const WIRE_MAX_CONTENT_CHARS = 4000;
/** Last N paper trades sent to analyze-trades (server also caps). */
export const ANALYZE_TRADES_MAX = 25;

export type WireChatMessage = {
  role: "user" | "assistant";
  content: string;
  /** Welcome / reset fluff — UI-only; never sent on the wire. */
  ephemeral?: boolean;
};

export function toWireMessages(
  history: Array<{ role: "user" | "assistant"; content: string; ephemeral?: boolean }>
): WireChatMessage[] {
  const substantive = history.filter((m) => !m.ephemeral && m.content.trim());
  const windowed = substantive.slice(-WIRE_MAX_MESSAGES);
  return windowed.map((m) => ({
    role: m.role,
    content:
      m.content.length > WIRE_MAX_CONTENT_CHARS
        ? `${m.content.slice(0, WIRE_MAX_CONTENT_CHARS - 32)}\n…[truncated for token budget]`
        : m.content,
  }));
}

export function tradesForAnalyzeWire<T>(trades: T[]): T[] {
  return trades.slice(-ANALYZE_TRADES_MAX);
}
