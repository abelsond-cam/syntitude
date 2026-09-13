/**
 * @vitest-environment jsdom
 */
import { mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";

import type {
  CatalogueScatterSprite,
  LocusDetailResponse,
  MapProjection,
  NeighbourDisplayRow,
  Representation,
} from "@/api/types";
import type { MapZoom } from "@/stores/neighbourhoodMapStore";

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
    // ⚠ The two representations get DIFFERENT positions on purpose: reading the wrong one draws a
    // locus where another belongs, and the picture still looks like a picture.
    map_position: { bacformer: [ordinal * 10, ordinal], esm: [-ordinal, ordinal * 10] },
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
    /** ⚠ `null` is *no medoid, not on the catalogue picture* — never a position of 0,0. */
    focalMapPosition?: readonly [number, number] | null;
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
          map_position:
            overrides.focalMapPosition === undefined ? [0, 0] : overrides.focalMapPosition,
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

function scatterSprite(overrides: Partial<CatalogueScatterSprite> = {}): CatalogueScatterSprite {
  return {
    pixel_size: 1200,
    viewport_centre: [0, 0],
    viewport_span: 1000,
    dust_radius_pixels: 2.2,
    alpha_per_locus: 0.55,
    plotted_locus_count: 17_531,
    unplotted_locus_count: 0,
    content_digest: "deadbeef",
    ...overrides,
  };
}

function projection(overrides: Partial<MapProjection> = {}): MapProjection {
  return {
    representation: "bacformer",
    method: "umap-learn(cosine)",
    scatter_sprite: scatterSprite(),
    ...overrides,
  } as unknown as MapProjection;
}

function mountMap(
  overrides: Parameters<typeof detail>[0] = {},
  representation: Representation = "bacformer",
  available: readonly Representation[] = ["bacformer", "esm"],
  extra: { zoom?: MapZoom; projection?: MapProjection | null } = {},
) {
  return mount(NeighbourhoodMapCard, {
    props: {
      detail: detail(overrides),
      representation,
      availableRepresentations: available,
      zoom: extra.zoom ?? "near",
      speciesKey: "ecoli",
      projection: extra.projection === undefined ? projection() : extra.projection,
    },
  });
}

/** The catalogue view, which is the same card with the other zoom selected. */
function mountGlobal(
  overrides: Parameters<typeof detail>[0] = {},
  representation: Representation = "bacformer",
  projectionOverride?: MapProjection | null,
) {
  return mountMap(overrides, representation, ["bacformer", "esm"], {
    zoom: "global",
    ...(projectionOverride === undefined ? {} : { projection: projectionOverride }),
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

// ── the whole-catalogue zoom ───────────────────────────────────────────────────────────────────
describe("⭐ whole catalogue — a picture from the server, with the six drawn onto it", () => {
  it("draws the sprite as one image filling the same square the dots are projected into", () => {
    const image = mountGlobal().find("image");
    expect(image.exists()).toBe(true);
    expect(image.attributes("width")).toBe("600");
    expect(image.attributes("href")).toContain("/species/ecoli/map/bacformer/scatter.png");
  });

  it("⚠ addresses the sprite by its CONTENT digest, so a re-render can never be served stale", () => {
    // The ETag is the content hash rather than the pangenome id, because an image is cached hard by
    // caches we do not control. The URL carries it, which makes the cache entry permanent.
    expect(mountGlobal().find("image").attributes("href")).toContain("v=deadbeef");
  });

  it("⛔ projects each dot with the viewport the SERVER published", () => {
    // Neighbour 10 sits at (100, 10) in bacformer space; the fixture's sprite is centred on (0,0)
    // with a span of 1000 over a 600-unit square, so x = 100/1000*600 + 300 and y flips.
    const dots = mountGlobal().findAll(".map-dot");
    const positions = dots.map((dot) => [dot.attributes("cx"), dot.attributes("cy")]);
    expect(positions).toContainEqual([String(300 + 60), String(300 - 6)]);
  });

  it("⛔⛔ MOVES every dot when the served viewport moves — it is read, never re-derived", () => {
    // The failure mode this exists for: a client that takes the extent, or a constant, and produces
    // a picture where the focal dot sits beside its own speck. Nothing on the page contradicts it.
    const shifted = mountGlobal({}, "bacformer", projection({
      scatter_sprite: scatterSprite({ viewport_centre: [500, 0] }),
    }));
    const focal = shifted.findAll(".map-dot").at(-1)!;
    expect(Number(focal.attributes("cx"))).toBeLessThan(300);
  });

  it("⛔ draws NO rings, because on a UMAP a distance is not a distance", () => {
    expect(mountGlobal().findAll(".map-ring")).toHaveLength(0);
    expect(mountGlobal().findAll(".map-dot").length).toBeGreaterThan(0);
  });

  it("⛔ reads THIS representation's positions, not the other's", () => {
    // The fixture gives the two representations mirrored positions, so a card reading the wrong one
    // draws a picture that is entirely plausible and entirely wrong.
    const bacformer = mountGlobal().findAll(".map-dot").map((d) => d.attributes("cx"));
    const esm = mountGlobal({}, "esm").findAll(".map-dot").map((d) => d.attributes("cx"));
    expect(bacformer).not.toEqual(esm);
  });

  it("⚠ tints via an INLINE filter, so the default is right with no stylesheet at all", () => {
    // The sprite is a coverage mask — flat black, varying alpha — because the server does not know
    // the viewer's theme. `--map-sprite-invert: 1` under a dark theme lightens the dust.
    expect(mountGlobal().find("image").attributes("style")).toContain(
      "invert(var(--map-sprite-invert, 0))",
    );
  });
});

describe("⭐ the two zooms agree about which locus is which colour", () => {
  it("keeps a locus's hue when the other picture drops a DIFFERENT locus", () => {
    // ⛔ The fixture is the whole test: gene12 has a measured cosine but no medoid, so it is on the
    // fit and not on the catalogue picture. A colour taken from the DRAWN subset would then shift
    // every locus after it by one hue in the catalogue view — and the legend beside it would agree,
    // so both pictures would be internally consistent and the reader would be told two things.
    const rows = [10, 11, 12, 13, 14].map((ordinal) =>
      neighbour(ordinal, ordinal === 12 ? { map_position: { bacformer: null, esm: null } } : {}),
    );
    const hueByName = (card: ReturnType<typeof mountMap>) =>
      Object.fromEntries(
        card.findAll(".map-key .map-row").map((row) => [
          row.find(".nm").text(),
          row.find("i").attributes("style"),
        ]),
      );
    const near = hueByName(mountMap({ rows }));
    const global = hueByName(mountGlobal({ rows }));

    const shared = Object.keys(global);
    expect(shared).toHaveLength(5);
    expect(shared).not.toContain("gene12");
    for (const name of shared) expect(global[name]).toBe(near[name]);
  });
});

describe("⛔ the legend names what is ON the picture", () => {
  it("drops a locus with no medoid from the catalogue view AND from its legend", () => {
    const rows = [10, 11, 12, 13, 14].map((ordinal) =>
      neighbour(ordinal, ordinal === 12 ? { map_position: { bacformer: null, esm: null } } : {}),
    );
    const global = mountGlobal({ rows });
    expect(global.findAll(".map-dot")).toHaveLength(5);
    expect(global.findAll(".map-key .map-row")).toHaveLength(5);
    expect(global.find(".map-key").text()).not.toContain("gene12");
    // ⚠ and it is still on the "these loci" fit, which asks a different question of it
    expect(mountMap({ rows }).findAll(".map-key .map-row")).toHaveLength(6);
  });

  it("says so when the reader's OWN locus has no medoid", () => {
    // On a picture whose whole job is "where am I", a missing focal dot is the one thing a reader
    // cannot infer from what is drawn.
    const global = mountGlobal({ focalMapPosition: null });
    expect(global.text()).toContain("no Bacformer medoid, so it is not on this picture");
  });
});

describe("⛔ a missing sprite is a SENTENCE, never an empty frame", () => {
  it("says the projection was never rendered and offers no picture", () => {
    const global = mountGlobal({}, "bacformer", projection({ scatter_sprite: null }));
    expect(global.find("image").exists()).toBe(false);
    expect(global.find(".map-figure-global").exists()).toBe(false);
    expect(global.text()).toContain("No whole-catalogue picture for Bacformer");
  });

  it("disables the zoom rather than offering a button that does nothing", () => {
    const card = mountMap({}, "bacformer", ["bacformer", "esm"], {
      projection: projection({ scatter_sprite: null }),
    });
    const global = card.findAll(".map-zoom").find((button) => button.text() === "whole catalogue")!;
    expect(global.attributes("disabled")).toBeDefined();
    expect(global.attributes("title")).toContain("no whole-catalogue picture was rendered");
  });
});

describe("the zoom strip", () => {
  it("emits the zoom it was clicked with, ABSOLUTELY and never as a toggle", () => {
    // Same rule as the walk direction: a toggle called twice from two places lands back where it
    // started while every call site believes it moved.
    const card = mountMap();
    const buttons = card.findAll(".map-zoom");
    buttons[1]!.trigger("click");
    buttons[1]!.trigger("click");
    expect(card.emitted("selectZoom")).toEqual([["global"], ["global"]]);
  });

  it("marks the zoom that is showing", () => {
    expect(mountMap().findAll(".map-zoom.on").map((b) => b.text())).toEqual(["these loci"]);
    expect(mountGlobal().findAll(".map-zoom.on").map((b) => b.text())).toEqual(["whole catalogue"]);
  });
});

describe("⭐ the catalogue caption quotes what it DREW", () => {
  it("names the projection and the count on the picture", () => {
    const note = mountGlobal().findAll(".muted").at(-1)!.text();
    expect(note).toContain("One umap-learn(cosine) over every locus's Bacformer medoid");
    expect(note).toContain("all 17,531 loci");
    expect(note).toContain("a gap on this picture is not a distance");
  });

  it("⛔ names the loci that are NOT on it rather than quoting the catalogue size", () => {
    const note = mountGlobal({}, "bacformer", projection({
      scatter_sprite: scatterSprite({ plotted_locus_count: 12_104, unplotted_locus_count: 5_427 }),
    })).findAll(".muted").at(-1)!.text();
    expect(note).toContain("12,104 loci — the 5,427 with no medoid are not on this picture");
  });
});

describe("⛔ a sprite that does not arrive must not render as a catalogue of six loci", () => {
  it("says the picture is still loading, and stops saying it once it is", async () => {
    const card = mountGlobal();
    expect(card.text()).toContain("Loading the catalogue picture…");
    await card.find("image").trigger("load");
    expect(card.text()).not.toContain("Loading the catalogue picture…");
  });

  it("⚠ draws the dots WHILE pending — a browser that never fires `load` must still get a map", () => {
    // Withholding them until `load` is the more literal reading of the rule, and its failure mode is
    // worse: no dots at all, permanently, on a browser whose `<image>` load event we do not control.
    expect(mountGlobal().findAll(".map-dot").length).toBeGreaterThan(0);
  });

  it("⛔ replaces the whole figure with a sentence when the image ERRORS", async () => {
    const card = mountGlobal();
    await card.find("image").trigger("error");
    expect(card.find(".map-figure-global").exists()).toBe(false);
    expect(card.findAll(".map-dot")).toHaveLength(0);
    expect(card.text()).toContain("The catalogue picture did not load");
    // ⚠ and the caption goes with it — left up, it describes a picture that is not there
    expect(card.text()).not.toContain("over every locus's Bacformer medoid");
  });

  it("⛔ says something DIFFERENT from 'never rendered' — a reader can act on only one of them", async () => {
    // One is a fact about the catalogue and permanent; the other is a fact about this request and a
    // reload may fix it. Rendering the same sentence for both throws that away.
    const failed = mountGlobal();
    await failed.find("image").trigger("error");
    const absent = mountGlobal({}, "bacformer", projection({ scatter_sprite: null }));
    expect(failed.text()).not.toContain("No whole-catalogue picture");
    expect(absent.text()).not.toContain("did not load");
  });

  it("goes back to pending when the reader switches to the other representation's sprite", async () => {
    // ⚠ Each representation is its own image at its own URL. Leaving the state at `ready` would show
    // the new sprite's dots over the old sprite's dust for as long as the fetch took.
    const card = mountGlobal();
    await card.find("image").trigger("load");
    await card.setProps({ representation: "esm", projection: projection({
      representation: "esm",
      scatter_sprite: scatterSprite({ content_digest: "cafe" }),
    }) });
    expect(card.text()).toContain("Loading the catalogue picture…");
  });
});
