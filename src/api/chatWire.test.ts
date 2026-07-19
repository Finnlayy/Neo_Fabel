import {describe, expect, it} from "vitest";
import {ANALYZE_TRADES_MAX, toWireMessages, tradesForAnalyzeWire, WIRE_MAX_MESSAGES} from "./chatWire";

describe("chatWire", () => {
  it("excludes ephemeral welcome and windows to max messages", () => {
    const history = [
      {role: "assistant" as const, content: "welcome", ephemeral: true},
      ...Array.from({length: 20}, (_, i) => ({
        role: (i % 2 === 0 ? "user" : "assistant") as "user" | "assistant",
        content: `m${i}`,
      })),
    ];
    const wire = toWireMessages(history);
    expect(wire.every((m) => m.content !== "welcome")).toBe(true);
    expect(wire).toHaveLength(WIRE_MAX_MESSAGES);
    expect(wire[0]?.content).toBe("m8");
  });

  it("caps content length", () => {
    const wire = toWireMessages([{role: "user", content: "z".repeat(5000)}]);
    expect(wire[0]?.content.length).toBeLessThanOrEqual(4000);
    expect(wire[0]?.content).toContain("truncated for token budget");
  });

  it("samples last trades for analyze-trades", () => {
    const trades = Array.from({length: 40}, (_, i) => ({id: i}));
    const sample = tradesForAnalyzeWire(trades);
    expect(sample).toHaveLength(ANALYZE_TRADES_MAX);
    expect(sample[0]?.id).toBe(15);
    expect(sample.at(-1)?.id).toBe(39);
  });
});
