/**
 * @vitest-environment jsdom
 */
import { mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";

import type {
  AnnotationEntry,
  Locus,
  LocusGeometry,
  MapProjection,
  PfamFamilyReference,
  Representation,
  UnirefFamily,
} from "@/api/types";

import EmbeddingGeometryCard from "./EmbeddingGeometryCard.vue";
import LocusHeadline from "./LocusHeadline.vue";
import SequenceDiversityCard from "./SequenceDiversityCard.vue";

/** The two baselines, an order of magnitude apart — which is the whole reason they are per rep. */
const ESM_NULL = 0.645;
const BACFORMER_NULL = 0.065;

function geometry(overrides: Partial<LocusGeometry> = {}): LocusGeometry {
  return {
    within_medoid_distance: 0.06,
    nearest_medoid_distance: 0.39,
    separation_percentile: 0.62,
    map_position: null,
    nearest_locus_ordinals: null,
    cosine_matrix: null,
    ...overrides,
  };
}

function projection(representation: Representation, mean: number): MapProjection {
  return {
    representation,
    method: "cmds",
    requested_metric: "cosine",
    extent: [0, 0, 1, 1],
    cosine_scale_factor: 10_000,
    null_mean_cosine: mean,
    scatter_sprite: null,
    null_bin_lower_edge: -0.1,
    null_bin_width: 0.1,
    null_bin_counts: [1, 4, 30, 12, 3, 1, 0, 0, 0, 0, 0, 0],
    separation_measurable_locus_count: 12_104,
  };
}

const PROJECTIONS = [projection("bacformer", BACFORMER_NULL), projection("esm", ESM_NULL)];

function locus(overrides: Partial<Locus> = {}): Locus {
  return {
    label: "4222",
    catalogue_ordinal: 10,
    display_name: "traC",
    display_name_source: "bakta_symbol",
    display_name_source_accession: null,
    best_product: "conjugal transfer protein TraC",
    bakta_gene_symbol: "traC",
    gene_count: 100,
    genome_count: 97,
    named_gene_count: 80,
    prevalence_band: "shell",
    median_gene_length_nt: 2400,
    gene_length_interquartile_range_nt: 120,
    uniref50: {
      family_count: 3,
      major_family_count: 2,
      labelled_gene_count: 95,
      impurity: 0.12,
      coverage: 0.95,
    },
    pfam: { annotated_gene_count: 90, architecture_count: 2, concordance_class: "nested" },
    evidence: {
      syntenic_a5: 0.91,
      collapse_tier: "mmseq@0.98",
      collapse_bucket: null,
      resolved_threshold: 0.98,
      resolved_threshold_is_capped_at_50_members: false,
    },
    geometry: { esm: geometry(), bacformer: geometry() },
    interest_score: 0.5,
    ...overrides,
  } as Locus;
}

// ── the headline ───────────────────────────────────────────────────────────────────────────────
function mountHeadline(overrides: Partial<Locus> = {}, collectionGenomeCount = 100) {
  return mount(LocusHeadline, {
    props: {
      locus: locus(overrides),
      collectionGenomeCount,
      mapProjections: PROJECTIONS,
      separationMeasurableLocusCount: 12_104,
    },
  });
}

function tileValues(wrapper: ReturnType<typeof mountHeadline>): string[] {
  return wrapper.findAll(".tile .v").map((node) => node.text());
}

describe("⭐ the headline — what it is, then how good it is", () => {
  it("names the locus, its band and its id", () => {
    const head = mountHeadline();
    expect(head.find(".locus-name").text()).toBe("traC");
    expect(head.find(".band").text()).toBe("shell");
    expect(head.find(".locus-id").text()).toBe("locus 4222");
  });

  it("⚠ shades the band from its POSITION, so the ramp stays monotonic", () => {
    expect(mountHeadline({ prevalence_band: "core" }).find(".band").attributes("style")).toContain(
      "--b: 1.00",
    );
    expect(mountHeadline({ prevalence_band: "rare" }).find(".band").attributes("style")).toContain(
      "--b: 0.00",
    );
  });

  it("⛔ renders `rare`, the band that was missing from the contract for 30 % of loci", () => {
    expect(mountHeadline({ prevalence_band: "rare" }).find(".band").text()).toBe("rare");
  });

  it("reads `soft_core` without its underscore", () => {
    expect(mountHeadline({ prevalence_band: "soft_core" }).find(".band").text()).toBe("soft core");
  });

  it("shows six tiles: three saying WHAT, three saying HOW GOOD", () => {
    expect(tileValues(mountHeadline())).toEqual([
      "97%", // 97 of 100 genomes
      "1.03", // 100 genes / 97 genomes
      "0.91", // synteny A5
      "94%", // Bacformer cohesion: (0.94 − 0.065) / (1 − 0.065)
      "83%", // ESM cohesion:       (0.94 − 0.645) / (1 − 0.645)
      "p62", // the separation midrank
    ]);
  });

  it("⛔ prints `—` where a number was never measured, never 0", () => {
    const head = mountHeadline({
      evidence: { ...locus().evidence, syntenic_a5: null },
      geometry: {
        esm: geometry({ within_medoid_distance: null, separation_percentile: null }),
        bacformer: geometry({
          within_medoid_distance: null,
          nearest_medoid_distance: null,
          separation_percentile: null,
        }),
      },
    });
    expect(tileValues(head)).toEqual(["97%", "1.03", "—", "—", "—", "—"]);
  });

  it("⭐ reads the SAME similarity very differently in the two representations", () => {
    // A within-similarity of 0.70 is two thirds of the way from random to perfect against
    // Bacformer's 0.065 baseline, and barely off the floor against ESM's 0.645. A single cohesion
    // scale would have to be wrong in one of them, which is why the baseline is per representation.
    const head = mountHeadline({
      geometry: {
        esm: geometry({ within_medoid_distance: 0.3 }),
        bacformer: geometry({ within_medoid_distance: 0.3 }),
      },
    });
    const values = tileValues(head);
    expect(values[3]).toBe("68%"); // (0.70 − 0.065) / (1 − 0.065)
    expect(values[4]).toBe("15%"); // (0.70 − 0.645) / (1 − 0.645)
  });

  it("⛔ carries the separation VERDICT as a class and names its denominator", () => {
    const head = mountHeadline();
    const tile = head.findAll(".tile")[5]!;
    expect(tile.classes()).toContain("sep-win");
    expect(tile.attributes("title")).toContain("Clean cluster separation");
    expect(tile.attributes("title")).toContain("+0.330");
    expect(tile.attributes("title")).toContain("ranked against 12,104 loci");
  });

  it("flags a NEGATIVE separation, where the nearest rival is closer than its own members", () => {
    const head = mountHeadline({
      geometry: {
        esm: geometry(),
        bacformer: geometry({ nearest_medoid_distance: 0.02, separation_percentile: 0.01 }),
      },
    });
    expect(head.findAll(".tile")[5]!.classes()).toContain("sep-bad");
  });
});

describe("⚠ the inferred-name caveat sits BESIDE the name, not in the typography", () => {
  it("says nothing where the name is a real Bakta symbol", () => {
    expect(mountHeadline().find(".inferred-note").exists()).toBe(false);
  });

  it("names the Bakta product where it came from one", () => {
    expect(mountHeadline({ display_name_source: "product" }).find(".inferred-note").text()).toBe(
      "inferred from the Bakta product — not a Bakta gene name",
    );
  });

  it("names the Pfam accession where it came from one", () => {
    const head = mountHeadline({
      display_name_source: "pfam_architecture",
      display_name_source_accession: "PF00126",
    });
    expect(head.find(".inferred-note").text()).toBe(
      "inferred from PF00126 — not a Bakta gene name",
    );
  });

  it("⛔ says NOTHING where the name is the locus id — there is no name to caveat", () => {
    // 16,551 of 33,201 loci. A line reading "inferred from label" would invent a claim about a name
    // nothing inferred.
    const head = mountHeadline({ display_name_source: "label", display_name: "4222" });
    expect(head.find(".inferred-note").exists()).toBe(false);
  });
});

// ── sequence diversity ─────────────────────────────────────────────────────────────────────────
function family(overrides: Partial<UnirefFamily> = {}): UnirefFamily {
  return {
    rank: 0,
    uniref50_accession: "UniRef50_P76362",
    gene_count: 60,
    modal_product: "LysR family transcriptional regulator",
    modal_architecture: "PF00126,PF03466",
    pfam_annotated_gene_count: 60,
    modal_symbol: "lysR",
    distinct_symbol_count: 1,
    ...overrides,
  };
}

const PFAM_REFERENCE: Record<string, PfamFamilyReference> = {
  PF00126: {
    short_name: "HTH_1",
    description: "Bacterial regulatory helix-turn-helix protein",
    interpro_accession: "IPR000847",
    interpro_name: "HTH transcriptional regulator LysR",
    clan_accession: "CL0123",
    clan_name: "HTH",
  },
  PF03466: {
    short_name: "LysR_substrate",
    description: "LysR substrate binding domain",
    interpro_accession: "",
    clan_accession: "",
    clan_name: "",
    interpro_name: "",
  },
};

function symbol(term: string, count: number): AnnotationEntry {
  return { rank: 0, term, name: null, gene_count: count };
}

function mountDiversity(
  overrides: {
    locus?: Partial<Locus>;
    families?: readonly UnirefFamily[];
    symbols?: readonly AnnotationEntry[];
    listedArchitectureCount?: number;
  } = {},
) {
  return mount(SequenceDiversityCard, {
    props: {
      locus: locus(overrides.locus ?? {}),
      families: overrides.families ?? [family(), family({ rank: 1, uniref50_accession: "UniRef50_Q664A4", gene_count: 30 })],
      symbols: overrides.symbols ?? [symbol("lysR", 80)],
      pfamReference: PFAM_REFERENCE,
      listedArchitectureCount: overrides.listedArchitectureCount ?? 2,
    },
  });
}

describe("⭐ families and names are ONE table", () => {
  it("claims with the MAJOR-family count, not every straggler", () => {
    // The table lists every family; claiming with that number would overstate the split at every
    // locus with a long tail.
    expect(mountDiversity().find(".lede").text()).toContain("UniRef50 files these genes under 2 families");
  });

  it("says so plainly where the locus and the sequence family agree", () => {
    const card = mountDiversity({
      locus: { uniref50: { ...locus().uniref50, family_count: 1, major_family_count: 1 } },
      families: [family()],
    });
    expect(card.find(".lede").text()).toBe(
      "One UniRef50 family — this locus and the sequence family agree.",
    );
  });

  it("⛔ takes every share over the LOCUS SIZE, not the sum of the listed families", () => {
    // 60 + 30 of 100 member genes. Summing the rows would print 67 % / 33 % and claim the table is
    // the whole locus.
    expect(mountDiversity().findAll("td.n:not(.share)").map((n) => n.text())).toEqual(["60%", "30%"]);
  });

  it("links each accession to UniProt and chips its architecture by NAME", () => {
    const card = mountDiversity();
    expect(card.find("a.acc-link").attributes("href")).toBe(
      "https://www.uniprot.org/uniref/UniRef50_P76362",
    );
    expect(card.findAll(".chip.pfam").map((n) => n.text())).toEqual([
      "HTH_1",
      "LysR_substrate",
      "HTH_1",
      "LysR_substrate",
    ]);
  });

  it("⭐ links a chip to INTERPRO where there is one, and to Pfam where there is not", () => {
    const chips = mountDiversity().findAll(".chip.pfam");
    expect(chips[0]!.attributes("href")).toBe(
      "https://www.ebi.ac.uk/interpro/entry/InterPro/IPR000847/",
    );
    expect(chips[1]!.attributes("href")).toBe("https://www.ebi.ac.uk/interpro/entry/pfam/PF03466/");
  });

  it("⚠ shows an UNRESOLVED accession as itself rather than dropping the chip", () => {
    // A dropped chip would say the locus has no such domain, which is a different, false claim.
    const card = mountDiversity({ families: [family({ modal_architecture: "PF99999" })] });
    expect(card.find(".chip.pfam").text()).toBe("PF99999");
  });

  it("⚠ marks a family split across gene names with a COUNT, never a list", () => {
    const card = mountDiversity({
      families: [family({ distinct_symbol_count: 3 })],
    });
    const marker = card.find(".fam-sym .alt-n");
    expect(marker.text()).toBe("+2");
    expect(marker.attributes("title")).toContain("3 different gene names among this family's 60 genes");
  });

  it("⛔ shows NO `+N` marker where the count was never measured", () => {
    // `null` is not measured and `1` is measured agreement — two different facts, and neither is a
    // disagreement. A `> 1` test on a null reads as false by accident rather than by decision.
    expect(mountDiversity({ families: [family({ distinct_symbol_count: null })] })
      .find(".fam-sym .alt-n").exists()).toBe(false);
    expect(mountDiversity({ families: [family({ distinct_symbol_count: 1 })] })
      .find(".fam-sym .alt-n").exists()).toBe(false);
  });

  it("⚠ a family with a measured coverage but NO architecture still earns the Pfam column", () => {
    // Its cell reads "no domain" plus its coverage, which is a statement. Dropping the column would
    // turn "0 of 60 annotated" into silence.
    const card = mountDiversity({
      families: [family({ modal_architecture: null, pfam_annotated_gene_count: 0 })],
    });
    expect(card.findAll("th").map((n) => n.text())).toContain("Pfam");
    expect(card.find(".fam-pf .none").text()).toBe("no domain");
    expect(card.find(".fam-cov").text()).toBe("0/60 annotated");
  });

  it("omits the optional columns it has not earned", () => {
    const card = mountDiversity({
      families: [
        family({ modal_symbol: null, modal_architecture: null, pfam_annotated_gene_count: null }),
      ],
    });
    expect(card.findAll("th").map((n) => n.text())).toEqual([
      "UniRef50",
      "modal Bakta product",
      "genes",
      "share",
    ]);
  });
});

describe("the naming line", () => {
  it("names how many genes the locus is naming", () => {
    expect(mountDiversity().findAll(".lede")[1]!.text()).toContain(
      "20 of 100 genes here carry no gene name. This locus names them traC",
    );
  });

  it("says when there is no symbol at all", () => {
    expect(mountDiversity({ locus: { named_gene_count: 0 } }).findAll(".lede")[1]!.text()).toBe(
      "None of these 100 genes carries a gene name — a coherent locus with no symbol at all.",
    );
  });

  it("says when every gene already has one", () => {
    expect(mountDiversity({ locus: { named_gene_count: 100 } }).findAll(".lede")[1]!.text()).toBe(
      "Every one of these 100 genes already carries a gene name.",
    );
  });

  it("counts the names to reconcile only when there is more than one", () => {
    expect(mountDiversity({ symbols: [symbol("a", 5), symbol("b", 3)] }).text()).toContain(
      "2 different gene names are in use across this one locus, the names to reconcile",
    );
    expect(mountDiversity().text()).not.toContain("names to reconcile");
  });
});

describe("⛔ the two verdicts, both READ and neither re-derived", () => {
  it("chips the collapse tier and the Pfam class side by side", () => {
    const chips = mountDiversity().findAll(".chip-row .chip");
    expect(chips.map((n) => n.text())).toEqual([
      "holds together at 98% identity",
      "partial annotation",
    ]);
  });

  it("⚠ calls `nested` partial annotation and says so under the chip", () => {
    expect(mountDiversity().find(".verdict-note").text()).toContain(
      "Absent evidence, not conflicting evidence",
    );
  });

  it("⛔ shows NO Pfam chip where no gene carries a domain — a verdict needs coverage", () => {
    const card = mountDiversity({
      locus: { pfam: { annotated_gene_count: 0, architecture_count: 0, concordance_class: "single" } },
    });
    expect(card.findAll(".chip-row .chip").map((n) => n.text())).toEqual([
      "holds together at 98% identity",
    ]);
    expect(card.find(".verdict-note").exists()).toBe(false);
  });
});

describe("⛔ Pfam coverage is stated AS COVERAGE", () => {
  it("says the unannotated remainder is absent evidence, not a competing architecture", () => {
    expect(mountDiversity().findAll(".muted").at(-1)!.text()).toBe(
      "90 of 100 genes carry a Pfam-A domain; the other 10 carry none at all — absent annotation, " +
        "not a competing architecture · 2 architectures across the locus.",
    );
  });

  it("says Pfam can neither support nor contradict where it has no coverage", () => {
    const card = mountDiversity({
      locus: { pfam: { annotated_gene_count: 0, architecture_count: 0, concordance_class: null } },
    });
    expect(card.findAll(".muted").at(-1)!.text()).toBe(
      "None of these 100 genes carries a Pfam-A domain — Pfam has no coverage here, so it can " +
        "neither support nor contradict this locus.",
    );
  });

  it("⚠ names how many architectures are LISTED when the locus has more", () => {
    const card = mountDiversity({
      locus: { pfam: { annotated_gene_count: 100, architecture_count: 9, concordance_class: "nested" } },
      listedArchitectureCount: 5,
    });
    expect(card.findAll(".muted").at(-1)!.text()).toBe(
      "All 100 genes carry a Pfam-A domain · 9 architectures across the locus (5 listed).",
    );
  });

  it("⛔ shows a family's own coverage only when it is SHORT, and a measured zero counts", () => {
    // `v-if` on the number would hide a family where NO gene is annotated — the loudest case.
    const none = mountDiversity({
      families: [family({ pfam_annotated_gene_count: 0, modal_architecture: null })],
    });
    expect(none.find(".fam-cov").text()).toBe("0/60 annotated");
    expect(mountDiversity().find(".fam-cov").exists()).toBe(false);
  });
});

// ── embedding geometry ─────────────────────────────────────────────────────────────────────────
function mountGeometry(
  overrides: {
    geometry?: Partial<Record<Representation, LocusGeometry>>;
    geneCount?: number;
    mapProjections?: readonly MapProjection[];
  } = {},
) {
  return mount(EmbeddingGeometryCard, {
    props: {
      geometry: {
        bacformer: overrides.geometry?.bacformer ?? geometry(),
        esm: overrides.geometry?.esm ?? geometry(),
      },
      mapProjections: overrides.mapProjections ?? PROJECTIONS,
      geneCount: overrides.geneCount ?? 100,
      separationMeasurableLocusCount: 12_104,
    },
  });
}

describe("⛔ embedding geometry is consistency, never corroboration", () => {
  it("says so, in the card's own footer", () => {
    expect(mountGeometry().find(".muted").text()).toContain(
      "reported as consistency and diagnosis — never as corroboration",
    );
  });

  it("⚠ leads with Bacformer, the context axis the track is built on", () => {
    expect(mountGeometry().findAll(".sub-head").map((n) => n.text())).toEqual(["Bacformer", "ESM"]);
  });

  it("converts the stored DISTANCE back to a similarity for both rails", () => {
    const values = mountGeometry().findAll(".pair:not(.sep) .val").map((n) => n.text());
    expect(values).toEqual(["0.940", "0.610", "0.940", "0.610"]);
  });

  it("names the denominator of the percentile, both halves of the sentence", () => {
    expect(mountGeometry().findAll(".sep-pct")[0]!.text()).toBe("p62 of 12,104 loci");
  });

  it("⛔ says NOT MEASURABLE in words, never 0.000, and gives the reason where it has one", () => {
    const single = mountGeometry({
      geometry: {
        bacformer: geometry({ nearest_medoid_distance: null, separation_percentile: null }),
        esm: geometry({ nearest_medoid_distance: null, separation_percentile: null }),
      },
      geneCount: 1,
    });
    expect(single.findAll(".sep-pct")[0]!.text()).toBe("not measurable — single gene");
    expect(single.findAll(".pair.sep .val")[0]!.text()).toBe("—");
  });

  it("drops the reason where the locus is not a singleton", () => {
    const many = mountGeometry({
      geometry: {
        bacformer: geometry({ separation_percentile: null }),
        esm: geometry({ separation_percentile: null }),
      },
      geneCount: 40,
    });
    expect(many.findAll(".sep-pct")[0]!.text()).toBe("not measurable");
  });

  it("renders no card at all where neither representation has geometry", () => {
    const empty = mountGeometry({
      geometry: {
        bacformer: geometry({ within_medoid_distance: null, nearest_medoid_distance: null }),
        esm: geometry({ within_medoid_distance: null, nearest_medoid_distance: null }),
      },
    });
    expect(empty.find(".card").exists()).toBe(false);
  });
});

describe("⭐ the null strip is what makes a raw similarity readable", () => {
  it("draws the density and both ticks, positioned on one linear 0..1 axis", () => {
    const strip = mountGeometry().findAll(".nullstrip")[0]!;
    expect(strip.findAll(".nd i").length).toBeGreaterThan(0);
    // ⚠ jsdom normalises `94.0%` to `94%`, so a whole-number case cannot show whether the decimal
    // survives. The sub-percent case below is what actually pins it.
    expect(strip.find(".nt.intra").attributes("style")).toContain("left: 94%");
    expect(strip.find(".nt.inter").attributes("style")).toContain("left: 61%");
  });

  it("⚠ places a tick to sub-percent precision — two loci 0.5 % apart must not coincide", () => {
    const strip = mountGeometry({
      geometry: {
        bacformer: geometry({ within_medoid_distance: 0.065, nearest_medoid_distance: 0.388 }),
        esm: geometry(),
      },
    }).findAll(".nullstrip")[0]!;
    expect(strip.find(".nt.intra").attributes("style")).toContain("left: 93.5%");
    expect(strip.find(".nt.inter").attributes("style")).toContain("left: 61.2%");
  });

  it("⛔ draws only the 0..1 half — a medoid pair below zero is vanishingly rare", () => {
    // 12 bins from -0.1 at 0.1 wide: the first is below zero and is not drawn.
    expect(mountGeometry().findAll(".nullstrip")[0]!.findAll(".nd i")).toHaveLength(11);
  });

  it("scales the tallest bar to full height", () => {
    const bars = mountGeometry().findAll(".nullstrip")[0]!.findAll(".nd i");
    expect(bars.map((bar) => bar.attributes("style"))).toContain("height: 100%;");
  });

  it("names the random-pair mean, which differs by an order of magnitude between reps", () => {
    const feet = mountGeometry().findAll(".nsfoot span:first-child");
    expect(feet.map((n) => n.text())).toEqual(["random pairs 0.065", "random pairs 0.645"]);
  });

  it("⛔ draws no strip where the baseline was never measured", () => {
    const noBaseline = mountGeometry({ mapProjections: [] });
    expect(noBaseline.find(".nullstrip").exists()).toBe(false);
    // …and the rails and the separation row are still there: an absent baseline is not an absent
    // measurement.
    expect(noBaseline.findAll(".pair:not(.sep)").length).toBe(4);
  });
});
