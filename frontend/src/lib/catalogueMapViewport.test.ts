import { describe, expect, it } from "vitest";

import type { CatalogueScatterSprite } from "@/api/types";
import { projectOntoSprite, spriteCoverageSentence } from "./catalogueMapViewport";

function sprite(overrides: Partial<CatalogueScatterSprite> = {}): CatalogueScatterSprite {
  return {
    pixel_size: 1200,
    viewport_centre: [100, 50],
    viewport_span: 1000,
    dust_radius_pixels: 2.2,
    alpha_per_locus: 0.55,
    plotted_locus_count: 17_531,
    unplotted_locus_count: 0,
    content_digest: "a".repeat(64),
    ...overrides,
  };
}

describe("⛔ the projection uses the SERVED viewport and computes none of its own", () => {
  it("puts the viewport centre at the centre of the drawn square", () => {
    expect(projectOntoSprite([100, 50], sprite(), 600)).toEqual([300, 300]);
  });

  it("⛔ FLIPS y — the map's grows upward and a raster's grows downward", () => {
    // A version that forgets this is a valid projection of nothing: mirrored, plausible, and wrong
    // for every locus at once, so no dot ever looks out of place.
    const [, highY] = projectOntoSprite([100, 300], sprite(), 600);
    const [, lowY] = projectOntoSprite([100, -200], sprite(), 600);
    expect(highY).toBeLessThan(lowY);
    expect(highY).toBe(300 - (250 / 1000) * 600);
  });

  it("does NOT flip x", () => {
    const [right] = projectOntoSprite([600, 50], sprite(), 600);
    const [left] = projectOntoSprite([-400, 50], sprite(), 600);
    expect(right).toBeGreaterThan(left);
  });

  it("⭐ moves every point when the SERVED viewport moves — it is read, not assumed", () => {
    // The failure this guards is a client that hard-codes a transform that happens to agree with
    // today's sprite. Shift the published centre and the dots must shift with it.
    const shifted = projectOntoSprite([100, 50], sprite({ viewport_centre: [600, 50] }), 600);
    expect(shifted[0]).toBe(300 - (500 / 1000) * 600);
  });

  it("scales with the drawn size, so the same sprite fits any square", () => {
    expect(projectOntoSprite([600, 50], sprite(), 600)[0]).toBe(600);
    expect(projectOntoSprite([600, 50], sprite(), 1200)[0]).toBe(1200);
  });
});

describe("⭐ the caption's denominator is what was DRAWN, not the catalogue size", () => {
  it("says all of them when every locus has a medoid", () => {
    expect(spriteCoverageSentence(sprite())).toBe("all 17,531 loci");
  });

  it("⛔ names the loci that are NOT on the picture rather than counting them in", () => {
    // The published caption read "among all 17,531" — the catalogue size. A locus with no medoid
    // never reached the map, so quoting the catalogue size overstates what the picture shows.
    expect(
      spriteCoverageSentence(sprite({ plotted_locus_count: 12_104, unplotted_locus_count: 5_427 })),
    ).toBe("12,104 loci — the 5,427 with no medoid are not on this picture");
  });
});
