import {describe, expect, it, vi, beforeEach, afterEach} from "vitest";
import * as client from "./client";
import {probeVectorBackend} from "./vector";

describe("probeVectorBackend", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("labels Qdrant live only when ready", async () => {
    vi.spyOn(client, "apiRequest").mockResolvedValue({
      status: "ok",
      enabled: true,
      ready: true,
      collection: "neo_fabel_vectors",
    });

    const result = await probeVectorBackend();
    expect(result.mode).toBe("qdrant");
    expect(result.label).toBe("QDRANT LIVE");
  });

  it("uses honest RAM fallback when Qdrant is down", async () => {
    vi.spyOn(client, "apiRequest").mockResolvedValue({
      status: "unavailable",
      enabled: true,
      ready: false,
      error: "timeout",
    });

    const result = await probeVectorBackend();
    expect(result.mode).toBe("memory");
    expect(result.label).toBe("RAM FALLBACK (QDRANT DOWN)");
    expect(result.label).not.toMatch(/LIVE/i);
  });

  it("falls back when health request fails", async () => {
    vi.spyOn(client, "apiRequest").mockRejectedValue(new Error("network"));

    const result = await probeVectorBackend();
    expect(result.mode).toBe("memory");
    expect(result.label).toContain("RAM FALLBACK");
  });
});
