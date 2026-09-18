import { describe, expect, it } from "vitest";

import { VARIANCE_TINT_CEILING, varianceTint } from "./intergenicGaps";

describe("⛔ the IGR tint's display curve — `app.js::gapVar`, carried across", () => {
  it("keeps a measured ZERO exactly zero: white means identical in every genome", () => {
    expect(varianceTint(0)).toBe(0);
  });

  it("saturates at the ceiling and stays there", () => {
    expect(varianceTint(VARIANCE_TINT_CEILING)).toBe(1);
    expect(varianceTint(4)).toBe(1);
  });

  it("⭐ is a SQUARE ROOT, so the typical varying region is visible at all", () => {
    // The median varying score is 0.014. Linear, that is 2.8 % opacity — indistinguishable from
    // white; through the curve it is ~17 %, which is the whole point of the curve.
    expect(varianceTint(0.125)).toBeCloseTo(0.5, 12);
    expect(varianceTint(0.014)).toBeCloseTo(Math.sqrt(0.028), 12);
    expect(varianceTint(0.014)).toBeGreaterThan(0.15);
  });

  it("treats a negative or NaN score as no tint rather than a colour", () => {
    expect(varianceTint(-1)).toBe(0);
    expect(varianceTint(Number.NaN)).toBe(0);
  });
});
