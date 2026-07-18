import { describe, expect, it } from "vitest";
import { pineJsonTemplate } from "./api";

describe("pineJsonTemplate", () => {
  it("includes schema_version and never invents a live target", () => {
    const raw = pineJsonTemplate("tvsec_test");
    const body = JSON.parse(raw) as Record<string, unknown>;
    expect(body.schema_version).toBe(1);
    expect(body.credential).toBe("tvsec_test");
    expect(body.pair).toBe("BTCUSD");
    expect(JSON.stringify(body)).not.toContain("kraken_live");
  });
});
