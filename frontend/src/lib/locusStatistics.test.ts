import { describe, expect, it } from "vitest";

import { copiesPerGenome, percentileLabel, signedFixed } from "./locusStatistics";

/**
 * ⛔ Four exports went with the medoid geometry on 2026-09-24, and each departure is a fact rather
 * than a tidy-up. `similarityFromDistance` and its tests are gone because the API serves
 * SIMILARITIES everywhere it once served distances — on the locus card and on the footer's residual
 * rows alike — so there is nothing left to convert and a surviving `1 − d` would print the
 * complement of a real number. `cohesion` is gone because the label and the number have moved
 * together: the within-cluster median over every gene pair is shown directly, in its own units.
 * `separation` and `separationVerdict` banded exactly one of what are now three views, so they live
 * with the view table in `similarityViews.test.ts`, generalised.
 */
describe("how the card writes the numbers", () => {
  it("floors the percentile label at p1, never p0", () => {
    expect(percentileLabel(0)).toBe("p1");
    expect(percentileLabel(0.004)).toBe("p1");
    expect(percentileLabel(0.12)).toBe("p12");
    expect(percentileLabel(1)).toBe("p100");
  });

  it("signs a separation so a negative one cannot be read as small", () => {
    expect(signedFixed(0.412)).toBe("+0.412");
    expect(signedFixed(-0.008)).toBe("-0.008");
    expect(signedFixed(0)).toBe("+0.000");
  });

  it("⛔ refuses to divide by no genomes rather than returning Infinity", () => {
    expect(copiesPerGenome(100, 97)).toBeCloseTo(1.0309, 4);
    expect(copiesPerGenome(3, 0)).toBeNull();
  });
});
