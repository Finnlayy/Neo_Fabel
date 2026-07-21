import {describe, expect, it} from "vitest";
import {scoreToDashOffset} from "./CircularGauge";

describe("CircularGauge", () => {
  it("maps 0/50/100 scores to full/half/empty dash offsets", () => {
    const full = 2 * Math.PI * 32;
    expect(scoreToDashOffset(0)).toBeCloseTo(full);
    expect(scoreToDashOffset(50)).toBeCloseTo(full / 2);
    expect(scoreToDashOffset(100)).toBeCloseTo(0);
  });

  it("maps 87.5 to a ~87.5% filled ring", () => {
    const full = 2 * Math.PI * 32;
    expect(scoreToDashOffset(87.5)).toBeCloseTo(full * 0.125);
  });
});
