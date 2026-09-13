/**
 * @vitest-environment jsdom
 */
import { mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";

import type { LocusDetailResponse, NeighbourDisplayRow, Representation } from "@/api/types";

import NeighbourhoodMapCard from "./NeighbourhoodMapCard.vue";

/** A 6×6 cosine matrix whose off-diagonal is a constant, so the six sit on a regular simplex. */
function cosineMatrix(
  pairs: Readonly<Record<string, number>> = {},
  size = 6,
): (number | null)[][] {
  const matrix: (number | null)[][] = Array.from({ length: size }, (_u, a) =>
    Array.from({ length: size }, (_v, b) => (a === b ? 1 : 0.8)),
  );
  for (const [key, value] of Object.entries(pairs)) {
    const [a, b] = key.split(",").map(Number) as [number, number];
    matrix[a]![b] = value;
    matrix[b]![a] = value;
  }
  return matrix;
}

function neighbour(ordinal: number, overrides: Partial<NeighbourDisplayRow> = {}): NeighbourDisplayRow {
  return {
    label: `n${ordinal}`,
    catalogue_ordinal: ordinal,
    best_product: `product ${ordinal}`,
    within_medoid_distance: { esm: 0.05, bacformer: 0.05 },
    display_name: `gene${ordinal}`,
    display_name_source: "bakta_symbol",
    genome_count: 50,
    median_gene_length_nt: 900,
    prevalence_band: "shell",
    ...overrides,
  };
}

function detail(
  overrides: {
    nearest?: readonly number[] | null;
    matrix?: (number | null)[][] | null;
    esmNearest?: readonly number[] | null;
    rows?: readonly NeighbourDisplayRow[];
    withinDistance?: number | null;
  } = {},
): LocusDetailResponse {
  const nearest = overrides.nearest === undefined ? [10, 11, 12, 13, 14] : overrides.nearest;
  const matrix = overrides.matrix === undefined ? cosineMatrix() : overrides.matrix;
  return {
    locus: {
      label: "focal",
      display_name: "traC",
      best_product: "conjugal transfer protein TraC",
      gene_count: 100,
      genome_count: 97,
      geometry: {
        bacformer: {
          within_medoid_distance: overrides.withinDistance === undefined ? 0.02 : overrides.withinDistance,
          nearest_medoid_distance: 0.3,
          separation_percentile: 0.6,
          map_position: [0.1, 0.2],
          nearest_locus_ordinals: nearest,
          cosine_matrix: matrix,
        },
        esm: {
          within_medoid_distance: 0.02,
          nearest_medoid_distance: 0.3,
          separation_percentile: 0.6,
          map_position: [0.3, 0.4],
          nearest_locus_ordinals:
            overrides.esmNearest === undefined ? [20, 21, 22, 23, 24] : overrides.esmNearest,
          cosine_matrix: matrix,
        },
      },
    },
    neighbour_display_rows:
      overrides.rows ??
      [10, 11, 12, 13, 14, 20, 21, 22, 23, 24].map((ordinal) => neighbour(ordinal)),
  } as unknown as LocusDetailResponse;
}

function mountMap(
  overrides: Parameters<typeof detail>[0] = {},
  representation: Representation = "bacformer",
  available: readonly Representation[] = ["bacformer", "esm"],
) {
  return mount(NeighbourhoodMapCard, {
    props: { detail: detail(overrides), representation, availableRepresentations: available },
  });
}

describe("⭐ a FIT of these six, not a crop of a big one", () => {
  it("draws one dot and one ring per drawn locus", () => {
    const map = mountMap();
    expect(map.findAll(".map-dot")).toHaveLength(6);
    expect(map.findAll(".map-ring")).toHaveLength(6);
  });

  it("says what fraction of their variance the plane keeps", () => {
    // Six points at a constant pairwise distance are a regular 5-simplex: genuinely 5-dimensional,
    // so a plane cannot keep all of it and the note must not imply it does.
    const note = mountMap().findAll(".muted").at(-1)!.text();
    expect(note).toContain("A fit of these 6 alone, not a crop");
    expect(note).toMatch(/keeping \d+(\.\d)?% of their variance/);
    expect(note).not.toContain("keeping 100% of their variance");
  });

  it("⭐ keeps ALL of it for a configuration that is genuinely planar", () => {
    // Three loci are always planar, so the fit is exact and the card may say so.
    const note = mountMap({ nearest: [10, 11] }).findAll(".muted").at(-1)!.text();
    expect(note).toContain("A fit of these 3 alone");
    expect(note).toContain("keeping 100% of their variance");
  });

  it("names the representation whose medoids were fitted", () => {
    expect(mountMap().findAll(".muted").at(-1)!.text()).toContain("L2-normalised Bacformer medoids");
    expect(mountMap({}, "esm").findAll(".muted").at(-1)!.text()).toContain("L2-normalised ESM medoids");
  });
});

describe("⭐ the ring is the locus's own spread, at TRUE scale", () => {
  it("scales every ring by the same factor as the positions", () => {
    // Equal spreads must draw equal rings; a ring rescaled independently would break the one
    // comparison the map exists for. The default fixture gives the focal locus a TIGHTER spread
    // than its neighbours, so this one levels them deliberately.
    const radii = mountMap({ withinDistance: 0.05 })
      .findAll(".map-ring")
      .map((ring) => Number(ring.attributes("r")));
    expect(new Set(radii.map((r) => r.toFixed(6))).size).toBe(1);
    expect(radii[0]).toBeGreaterThan(0);
  });

  it("⭐ draws the focal locus's own tighter spread as a smaller ring than its neighbours'", () => {
    // The default fixture: focal at distance 0.02, neighbours at 0.05. Most loci are far tighter
    // than their nearest rival, and that is the finding the true-scale rule exists to show.
    const radii = mountMap().findAll(".map-ring").map((ring) => Number(ring.attributes("r")));
    // Rings are drawn in reverse order, so the focal locus is LAST.
    expect(radii.at(-1)).toBeLessThan(radii[0] as number);
  });

  it("⚠ draws a BIGGER ring for a locus whose members are further from its centre", () => {
    const loose = mountMap({
      rows: [10, 11, 12, 13, 14].map((ordinal) =>
        neighbour(ordinal, {
          within_medoid_distance: { esm: 0.05, bacformer: ordinal === 10 ? 0.3 : 0.05 },
        }),
      ),
    });
    const rings = loose.findAll(".map-ring").map((ring) => Number(ring.attributes("r")));
    // Rings are drawn in reverse order, so the loose neighbour is the LAST of the six.
    expect(Math.max(...rings)).toBeGreaterThan(Math.min(...rings) * 2);
  });

  it("⛔ gives a locus with no measured spread a ring of ZERO, not a default one", () => {
    const unmeasured = mountMap({
      rows: [10, 11, 12, 13, 14].map((ordinal) =>
        neighbour(ordinal, { within_medoid_distance: { esm: null, bacformer: null } }),
      ),
      withinDistance: null,
    });
    const radii = unmeasured.findAll(".map-ring").map((ring) => Number(ring.attributes("r")));
    expect(radii.every((radius) => radius === 0)).toBe(true);
  });
});

describe("⛔ slots are not ranks", () => {
  it("drops a `-1` neighbour AND its slot, reading the rest at their own slots", () => {
    // -1 is "outside the catalogue". Closing the gap by rank would read slot 3's cosine for the
    // locus that is actually in slot 4 — one locus's distances drawn on another.
    const map = mountMap({
      nearest: [10, -1, 12, 13, 14],
      matrix: cosineMatrix({ "0,1": 0.99, "0,3": 0.5 }),
    });
    const cosines = map.findAll(".map-row .cos").map((node) => node.text());
    // Focal is "—"; then slot 1 (0.99), slot 3 (0.5), slot 4 and slot 5 at the 0.8 default.
    expect(cosines).toEqual(["—", "0.990", "0.500", "0.800", "0.800"]);
  });

  it("drops a neighbour the response could not resolve, without shifting the others", () => {
    const map = mountMap({
      rows: [10, 12, 13, 14].map((ordinal) => neighbour(ordinal)),
      matrix: cosineMatrix({ "0,1": 0.99, "0,3": 0.5 }),
    });
    expect(map.findAll(".map-row")).toHaveLength(5);
    expect(map.findAll(".map-row .cos").map((n) => n.text())).toEqual([
      "—",
      "0.990",
      "0.500",
      "0.800",
      "0.800",
    ]);
  });
});

describe("the legend", () => {
  it("names each locus and its product, because the number is not what tells you", () => {
    const rows = mountMap().findAll(".map-row");
    expect(rows[0]!.find(".nm").text()).toBe("traC");
    expect(rows[0]!.find(".desc").text()).toBe("conjugal transfer protein TraC");
    expect(rows[1]!.find(".desc").text()).toBe("product 10");
  });

  it("⛔ marks the focal row and refuses to walk to the locus already being read", () => {
    const map = mountMap();
    const focal = map.findAll(".map-row")[0]!;
    expect(focal.classes()).toContain("is-focal");
    expect(focal.attributes("disabled")).toBeDefined();
    expect(focal.find(".cos").text()).toBe("—");
  });

  it("walks to a neighbour by LABEL when its row is clicked", () => {
    const map = mountMap();
    map.findAll(".map-row")[1]!.trigger("click");
    expect(map.emitted("walk")).toEqual([["n10"]]);
  });
});

describe("⚠ the two representations are different sets of loci", () => {
  it("changes the legend as well as the picture when the tab changes", () => {
    // Their separations agree at only rho ~0.47, so the tab is not a restyling.
    const context = mountMap({}, "bacformer").findAll(".map-row .nm").map((n) => n.text());
    const sequence = mountMap({}, "esm").findAll(".map-row .nm").map((n) => n.text());
    expect(context).not.toEqual(sequence);
    expect(context.slice(1)).toEqual(["gene10", "gene11", "gene12", "gene13", "gene14"]);
    expect(sequence.slice(1)).toEqual(["gene20", "gene21", "gene22", "gene23", "gene24"]);
  });

  it("emits the representation the reader picked", () => {
    const map = mountMap();
    map.findAll(".map-tab")[1]!.trigger("click");
    expect(map.emitted("selectRepresentation")).toEqual([["esm"]]);
  });

  it("offers no tabs where the catalogue has only one representation", () => {
    expect(mountMap({}, "bacformer", ["bacformer"]).find(".map-tabs").exists()).toBe(false);
  });
});

describe("⛔ too few points is a SENTENCE, not an empty frame", () => {
  it("says so rather than drawing a blank square", () => {
    // An empty box reads as "these loci are all at the same place", which is a different claim.
    const alone = mountMap({ nearest: [] });
    expect(alone.find("svg").exists()).toBe(false);
    expect(alone.find(".muted").text()).toContain("fewer than two measured neighbours");
  });

  it("says so where the cosine matrix was never measured at all", () => {
    const noMatrix = mountMap({ matrix: null });
    expect(noMatrix.find("svg").exists()).toBe(false);
    expect(noMatrix.findAll(".map-row")).toHaveLength(0);
  });

  it("⛔ refuses the fit where an INTERIOR pair is unmeasured, rather than guessing it", () => {
    const gap = mountMap({ matrix: cosineMatrix({ "1,2": null as unknown as number }) });
    expect(gap.find("svg").exists()).toBe(false);
  });
});
