import { describe, expect, it } from "vitest";

import {
  cohesion,
  copiesPerGenome,
  percentileLabel,
  separation,
  separationVerdict,
  signedFixed,
  similarityFromDistance,
} from "./locusStatistics";

/** The two baselines are nowhere near each other, which is the whole reason they are per rep. */
const ESM_NULL = 0.645;
const BACFORMER_NULL = 0.065;

describe("⛔ the payload stores DISTANCE, and every read converts", () => {
  it("turns a distance into a similarity", () => {
    expect(similarityFromDistance(0.02)).toBeCloseTo(0.98, 10);
  });

  it("⚠ keeps a measured zero as a similarity of 1, and passes null through as null", () => {
    // 85 % of ESM loci arrive at an indistinguishable 1.000 if similarity is stored directly, which
    // is why the distance is what is stored — a measured 0 distance is a real perfect similarity.
    expect(similarityFromDistance(0)).toBe(1);
    expect(similarityFromDistance(null)).toBeNull();
  });
});

describe("⛔ cohesion is distance from RANDOM towards perfect, not a catalogue percentile", () => {
  it("reads the same raw similarity very differently in the two representations", () => {
    // The published page's own point: ESM's random pairs sit at ~0.645 and Bacformer's at ~0.065,
    // so 0.82 is unremarkable in one and excellent in the other.
    expect(cohesion(0.82, ESM_NULL)).toBeCloseTo(0.4930, 3);
    expect(cohesion(0.82, BACFORMER_NULL)).toBeCloseTo(0.8074, 3);
  });

  it("⭐ puts `traC` at 84 % of the way from random to perfect, where its percentile says p12", () => {
    // The measured example the rule exists for: ranking cohesion against peers says the opposite of
    // the truth, because almost every locus in these catalogues is cohesive.
    expect(cohesion(0.85, BACFORMER_NULL)).toBeCloseTo(0.84, 2);
  });

  it("clamps rather than reporting a locus as worse than random or better than perfect", () => {
    expect(cohesion(0.01, ESM_NULL)).toBe(0);
    expect(cohesion(1.2, ESM_NULL)).toBe(1);
  });

  it("⛔ returns null rather than inventing a baseline it does not have", () => {
    expect(cohesion(0.9, null)).toBeNull();
    expect(cohesion(null, ESM_NULL)).toBeNull();
    // A degenerate baseline would divide by zero and render as Infinity — a number, on a page.
    expect(cohesion(0.9, 1)).toBeNull();
  });
});

describe("separation, and the three bands", () => {
  it("is the gap between a locus's own members and its nearest rival", () => {
    expect(separation(0.94, 0.61)).toBeCloseTo(0.33, 10);
    expect(separation(0.94, null)).toBeNull();
  });

  it("calls a NEGATIVE gap poor — the nearest rival is closer than its own members", () => {
    const verdict = separationVerdict(0.6, 0.7, 0.01);
    expect(verdict?.verdictClass).toBe("bad");
    expect(verdict?.label).toBe("Poor cluster separation");
  });

  it("⚠ calls the bottom 5 % unclear, and everything above it clean", () => {
    // Cut at p5 because the zero crossing already sits near p2.5, so `Poor` catches the bottom ~2 %
    // alone and `Unclear` adds a thin sliver.
    expect(separationVerdict(0.94, 0.61, 0.04)?.label).toBe("Unclear cluster separation");
    expect(separationVerdict(0.94, 0.61, 0.05)?.label).toBe("Clean cluster separation");
    expect(separationVerdict(0.94, 0.61, 0.9)?.verdictClass).toBe("win");
  });

  it("⛔ returns null for NOT MEASURABLE, which the card must say in words", () => {
    // A singleton is its own medoid and has no separation at all. That is an absence, not a bad
    // score, and rendering it as 0.000 would put a made-up number on the page.
    expect(separationVerdict(null, null, null)).toBeNull();
    expect(separationVerdict(0.94, 0.61, null)).toBeNull();
    expect(separationVerdict(0.94, null, 0.5)).toBeNull();
  });

  it("⚠ a measured percentile of ZERO is a rank, not an absence", () => {
    const verdict = separationVerdict(0.94, 0.61, 0);
    expect(verdict).not.toBeNull();
    expect(verdict?.verdictClass).toBe("warn");
  });
});

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
