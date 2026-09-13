/**
 * @vitest-environment jsdom
 *
 * **The API/front-end boundary, checked against real bytes.**
 *
 * ⭐ Everything in `src/api/types.ts` is hand-transcribed from `serialisers/locus_serialiser.py`,
 * and a transcription error there is invisible: TypeScript happily believes a field exists that the
 * server never sends, and the component renders `undefined` as an empty string. So the fixture here
 * is **three real responses from the Flask test client**, and the real track component is mounted
 * against them.
 *
 * The three loci are chosen for what they exercise, not at random:
 * - `ordinary` — every arrangement fits, both members-remainders are zero.
 * - `over_cap` — **84 arrangements, 8 listed, 86 members past the cap and 7 with no window.**
 *   Before the remainder split this locus told a reader that 93 member genes had no coordinates.
 * - `no_window` — 64 members genuinely have no recorded neighbourhood, and 4 sit past the cap.
 *
 * ⚠ Regenerate with `backend/scripts/dump_api_locus_fixture.py` whenever the serialiser changes. A
 * fixture that silently goes stale is worse than none, so the shape checks below are exhaustive
 * over the keys the client reads rather than a spot check.
 *
 * ⛔ **This suite has already earned itself.** Mounting the real component against real bytes found
 * that `_neighbour_display_rows` looked catalogue ordinals up in the *locus id* set — two key
 * spaces over the same small integers, merged one screen below the comment warning about exactly
 * that. It mostly worked, because an arrangement occupant is usually also a marginal mode; the
 * ones that are not rendered as blank, unwalkable blocks. On these three loci, 37 of 190 slots.
 */
import { mount } from "@vue/test-utils";
import { existsSync, readFileSync } from "node:fs";
import { resolve } from "node:path";

import { createPinia, setActivePinia } from "pinia";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { LocusDetailResponse } from "@/api/types";
import { SLOT_COUNT } from "@/lib/slotSpaces";
import { useLocusNavigationStore } from "@/stores/locusNavigationStore";

import ArrangementPopover from "@/components/popover/ArrangementPopover.vue";
import NeighbourhoodMapCard from "@/components/map/NeighbourhoodMapCard.vue";
import EmbeddingGeometryCard from "@/components/locusCard/EmbeddingGeometryCard.vue";
import LocusHeadline from "@/components/locusCard/LocusHeadline.vue";
import SequenceDiversityCard from "@/components/locusCard/SequenceDiversityCard.vue";
import { PREVALENCE_BANDS } from "@/lib/prevalence";
import ArrangementSwitcher from "@/components/track/ArrangementSwitcher.vue";
import GeneTrack from "@/components/track/GeneTrack.vue";

vi.mock("@/api/client", () => ({
  fetchLocus: vi.fn(async () => ({ ok: false, kind: "network", detail: "not used" })),
}));

// ⚠ Resolved from the project root, NOT from `import.meta.url`. This suite runs under jsdom,
// where `import.meta.url` is an http URL rather than a file one, so `fileURLToPath` yields an
// absolute path rooted at `/` and the read fails with a bare ENOENT that reads as a missing
// fixture. Vitest runs with the project root as cwd.
const FIXTURE = resolve(process.cwd(), "tests/fixtures/api_locus_responses.json");

interface Recorded {
  readonly recorded_from: string;
  readonly loci: Readonly<Record<string, { readonly label: string; readonly response: LocusDetailResponse }>>;
}

const recorded: Recorded = JSON.parse(readFileSync(FIXTURE, "utf8")) as Recorded;
const CASES = ["ordinary", "over_cap", "no_window"] as const;

beforeEach(() => setActivePinia(createPinia()));

function detailFor(name: (typeof CASES)[number]): LocusDetailResponse {
  const entry = recorded.loci[name];
  if (entry === undefined) throw new Error(`fixture has no '${name}' locus`);
  return entry.response;
}

describe("the fixture itself", () => {
  it("⛔ exists and says where it came from, rather than being skipped", () => {
    expect(existsSync(FIXTURE)).toBe(true);
    expect(recorded.recorded_from).toBe("the API test client");
    expect(Object.keys(recorded.loci).sort()).toEqual([...CASES].sort());
  });

  it("⭐ actually exercises the case it exists for", () => {
    // Without this the suite would keep passing after a regenerate that happened to pick three
    // ordinary loci, and the discriminating cases would be gone with nothing to say so.
    const overCap = detailFor("over_cap").arrangements;
    expect(overCap.total).toBeGreaterThan(overCap.listed.length);
    expect(overCap.members_in_arrangements_not_listed).toBeGreaterThan(0);
    const noWindow = detailFor("no_window").arrangements;
    expect(noWindow.members_without_a_neighbourhood).toBeGreaterThan(0);
  });
});

describe.each(CASES)("%s — the real response satisfies the contract the client reads", (name) => {
  const detail = detailFor(name);

  it("carries every top-level block the client destructures", () => {
    expect(Object.keys(detail).sort()).toEqual(
      [
        "anchor",
        "annotations",
        "arrangements",
        "intergenic_gaps",
        "locus",
        "neighbour_display_rows",
        "offsets",
        "pfam_reference",
        "resolved_neighbour_count",
        "uniref50_families",
      ].sort(),
    );
  });

  it("⛔ has exactly ten offsets, in recorded order", () => {
    expect(detail.offsets).toHaveLength(SLOT_COUNT);
    expect(detail.offsets.map((offset) => offset.signed_offset)).toEqual([
      -5, -4, -3, -2, -1, 1, 2, 3, 4, 5,
    ]);
  });

  it("⛔ every arrangement has exactly ten slots, each null-plus-a-reason or resolved", () => {
    for (const arrangement of detail.arrangements.listed) {
      expect(arrangement.slots).toHaveLength(SLOT_COUNT);
      for (const slot of arrangement.slots) {
        // Never a bare -1: the packed form is where "−1 means five different things" lives.
        expect(typeof slot.signed_offset).toBe("number");
        if (slot.locus === null) {
          expect(slot.absence_reason).not.toBeNull();
          expect(slot.same_strand).toBeNull();
        } else {
          expect(slot.absence_reason).toBeNull();
          expect(typeof slot.same_strand).toBe("boolean");
        }
      }
    }
  });

  it("⛔ names all five remainders, even where they are zero", () => {
    const arrangements = detail.arrangements;
    for (const field of [
      "arrangements_not_listed",
      "members_in_arrangements_not_listed",
      "members_without_a_neighbourhood",
    ] as const) {
      expect(typeof arrangements[field]).toBe("number");
    }
    for (const offset of detail.offsets) {
      expect(typeof offset.observed_not_listed).toBe("number");
      expect(typeof offset.members_without_an_observation).toBe("number");
    }
  });

  it("⚠ the remainders ADD UP, so none of them is quietly absorbing another", () => {
    const arrangements = detail.arrangements;
    const listed = arrangements.listed.reduce((total, one) => total + one.gene_count, 0);
    expect(
      listed +
        arrangements.members_in_arrangements_not_listed +
        arrangements.members_without_a_neighbourhood,
    ).toBe(detail.locus.gene_count);
    expect(arrangements.listed.length + arrangements.arrangements_not_listed).toBe(
      arrangements.total,
    );
  });

  it("resolves every arrangement slot's locus into neighbour_display_rows", () => {
    // ⭐ The fan-out, answered in this one response. A slot naming a locus with no display row
    // would render as a blank block that is nonetheless clickable.
    const known = new Set(detail.neighbour_display_rows.map((row) => row.label));
    const missing = new Set<string>();
    for (const arrangement of detail.arrangements.listed) {
      for (const slot of arrangement.slots) {
        if (slot.locus !== null && !known.has(slot.locus)) missing.add(slot.locus);
      }
    }
    expect([...missing]).toEqual([]);
  });

  it("⭐ mounts the real track component without warnings", () => {
    const warn = vi.spyOn(console, "warn").mockImplementation(() => undefined);
    const error = vi.spyOn(console, "error").mockImplementation(() => undefined);

    const navigation = useLocusNavigationStore();
    navigation.setSpecies("ecoli");
    navigation.route = { label: detail.locus.label, direction: "forward" };
    navigation.view = { status: "ready", value: detail };

    const wrapper = mount(GeneTrack, {
      props: { detail, collectionGenomeCount: 123 },
    });

    const geneSlots = wrapper
      .findAll(".slot")
      .filter((node) => !node.classes("gap") && !node.classes("joint"));
    expect(geneSlots).toHaveLength(SLOT_COUNT + 1);
    expect(wrapper.findAll(".slot.focal")).toHaveLength(1);
    // Every gene slot carries an inline width — the one thing a stylesheet-free harness can see.
    for (const node of geneSlots) {
      expect(node.attributes("style") ?? "").toMatch(/width:\s*\d+px/);
    }
    // ⚠ Vue reports a missing required prop or a bad type as a console warning, not a throw, so a
    // shape mismatch between the hand-written types and the real response would otherwise render
    // `undefined` silently and pass every assertion above.
    expect(error).not.toHaveBeenCalled();
    expect(warn).not.toHaveBeenCalled();
    warn.mockRestore();
    error.mockRestore();
  });
});

describe("⭐ the remainder split, on the locus that proves it matters", () => {
  it("does NOT tell a reader that members past the cap have no coordinates", () => {
    const arrangements = detailFor("over_cap").arrangements;
    const listed = arrangements.listed.reduce((total, one) => total + one.gene_count, 0);
    // What the old subtraction would have reported as "no coordinates for the gene, so no window".
    const wouldHaveClaimed = detailFor("over_cap").locus.gene_count - listed;
    expect(arrangements.members_without_a_neighbourhood).toBeLessThan(wouldHaveClaimed);
    expect(
      wouldHaveClaimed - arrangements.members_without_a_neighbourhood,
    ).toBe(arrangements.members_in_arrangements_not_listed);
  });
});

describe("⭐ the A0 card, mounted on the same real bytes", () => {
  function mountCard(kind: (typeof CASES)[number]) {
    const detail = detailFor(kind);
    return mount(ArrangementPopover, {
      props: {
        locus: detail.locus,
        arrangements: detail.arrangements.listed,
        total: detail.arrangements.total,
        selectedRank: detail.arrangements.listed[0]?.rank ?? null,
        anchorRanks: detail.anchor.arrangement_ranks,
        membersWithoutANeighbourhood: detail.arrangements.members_without_a_neighbourhood,
        walkDirection: "forward" as const,
        arrangementsNotShown: detail.arrangements.arrangements_not_listed,
        loadStatus: "idle" as const,
      },
    });
  }

  it("⛔ derives the display cut to exactly what the SERVER named it", () => {
    // The card cannot use `members_in_arrangements_not_listed` directly — that number is computed
    // against the capped list and stops being true the moment a page arrives — so it derives the
    // same quantity from `gene_count − members_without_a_neighbourhood − Σ listed`. This asserts
    // the two agree on real bytes, which is the only thing that proves the identity holds.
    for (const kind of CASES) {
      const detail = detailFor(kind);
      const card = mountCard(kind);
      const tail = card.find(".pop-tail");
      const expected = detail.arrangements.members_in_arrangements_not_listed;
      if (expected > 0) {
        expect(tail.text()).toContain(`${expected} member genes sit in arrangements not listed here`);
      } else {
        // ⚠ Read the whole card, not the tail: with both remainders zero there IS no tail element,
        // and `.text()` on an absent wrapper throws rather than returning "" — which would have
        // made this branch pass without looking at anything.
        expect(card.text()).not.toContain("sit in arrangements not listed here");
      }
    }
  });

  it("⛔ still names the members with no window as their own, separate sentence", () => {
    const detail = detailFor("no_window");
    expect(detail.arrangements.members_without_a_neighbourhood).toBeGreaterThan(0);
    expect(mountCard("no_window").find(".pop-tail").text()).toContain(
      `${detail.arrangements.members_without_a_neighbourhood} member genes have no recorded neighbourhood`,
    );
  });

  it("⚠ does not claim completeness at a locus where 76 arrangements are missing", () => {
    const detail = detailFor("over_cap");
    expect(detail.arrangements.total).toBeGreaterThan(detail.arrangements.listed.length);
    const lede = mountCard("over_cap").find(".pop-lede").text();
    expect(lede).not.toContain("every one of them");
    expect(lede).toContain(`${detail.arrangements.listed.length} of them listed below`);
    expect(lede).toContain(`sits in ${detail.arrangements.total}`);
  });

  it("says every one IS listed where every one is, and prints no tail at all", () => {
    const detail = detailFor("ordinary");
    expect(detail.arrangements.arrangements_not_listed).toBe(0);
    expect(detail.arrangements.members_in_arrangements_not_listed).toBe(0);
    expect(detail.arrangements.members_without_a_neighbourhood).toBe(0);
    const card = mountCard("ordinary");
    expect(card.find(".pop-lede").text()).toContain("every one of them listed below");
    expect(card.find(".pop-tail").exists()).toBe(false);
    expect(card.find(".arr-more").exists()).toBe(false);
  });

  it("⛔ lists one row per arrangement the response carried, and none of them selectable", () => {
    for (const kind of CASES) {
      const card = mountCard(kind);
      expect(card.findAll(".alt")).toHaveLength(detailFor(kind).arrangements.listed.length);
      expect(card.findAll("button.alt")).toHaveLength(0);
    }
  });
});

describe("⭐ the switcher, on the same real bytes", () => {
  function mountSwitcher(kind: (typeof CASES)[number], anchor: string | null = null) {
    const detail = detailFor(kind);
    return mount(ArrangementSwitcher, {
      props: {
        locus: detail.locus,
        arrangements: detail.arrangements.listed,
        total: detail.arrangements.total,
        selectedIndex: 0,
        anchorRanks: detail.anchor.arrangement_ranks,
        anchorGenomeName: anchor,
        membershipIsComplete: detail.arrangements.membership_is_complete,
        walkDirection: "forward" as const,
      },
    });
  }

  it("⛔ the server sends `membership_is_complete`, and the three loci disagree about it", () => {
    // A field every response carried the same value for would be untested by this fixture, so
    // assert the cases actually differ — otherwise the branch below is never taken either way.
    const flags = CASES.map((kind) => detailFor(kind).arrangements.membership_is_complete);
    expect(flags.every((flag) => typeof flag === "boolean")).toBe(true);
    expect(new Set(flags).size).toBe(2);
  });

  it("⛔ picks the anchor sentence from THAT field, not from the gene remainders", () => {
    for (const kind of CASES) {
      const detail = detailFor(kind);
      const text = mountSwitcher(kind, "SAMEA_TEST").find(".arr-anchored").text();
      // Every fixture locus has an empty anchor rank list, so this is the muted branch throughout.
      expect(detail.anchor.arrangement_ranks).toHaveLength(0);
      if (detail.arrangements.membership_is_complete) {
        expect(text).toContain("has no gene at this locus");
      } else {
        expect(text).toContain("has no recorded neighbourhood at this locus");
      }
    }
  });

  it("⚠ `no_window` is the locus that proves the gene remainder cannot answer it", () => {
    // 64 members have no window here — and `over_cap` has 7, an order of magnitude fewer, yet both
    // are incomplete. A rule keyed on the gene count would have to pick a threshold; there isn't one.
    const noWindow = detailFor("no_window").arrangements;
    const overCap = detailFor("over_cap").arrangements;
    expect(noWindow.members_without_a_neighbourhood).toBeGreaterThan(
      overCap.members_without_a_neighbourhood,
    );
    expect(noWindow.membership_is_complete).toBe(false);
    expect(overCap.membership_is_complete).toBe(false);
  });

  it("counts the total in the sentence and the drawn rows in the coverage", () => {
    const detail = detailFor("over_cap");
    const head = mountSwitcher("over_cap").find(".arr-head").text();
    expect(head).toContain(`sits in ${detail.arrangements.total} neighbourhoods`);
    expect(head).toContain(`The ${detail.arrangements.listed.length} here account for`);
    expect(head).not.toContain("100% of its genes");
  });

  it("offers exactly the rows the track holds slots for, and no more", () => {
    for (const kind of CASES) {
      const detail = detailFor(kind);
      const buttons = mountSwitcher(kind).findAll(".arr-opt");
      // The single-arrangement branch draws none; every other locus draws one per listed row.
      const expected = detail.arrangements.total <= 1 ? 0 : detail.arrangements.listed.length;
      expect(buttons).toHaveLength(expected);
    }
  });
});

describe("⭐ the locus card, on real bytes", () => {
  /** The catalogue-level block the card needs; the fixture is per locus, so this stands in. */
  const PROJECTIONS = [
    {
      representation: "bacformer" as const,
      method: "cmds",
      requested_metric: "cosine",
      extent: [0, 0, 1, 1] as [number, number, number, number],
      cosine_scale_factor: 10_000,
      null_mean_cosine: 0.065,
      null_bin_lower_edge: -0.1,
      null_bin_width: 0.1,
      null_bin_counts: [1, 4, 30, 12, 3, 1, 0, 0, 0, 0, 0, 0],
      separation_measurable_locus_count: 12_104,
    },
    {
      representation: "esm" as const,
      method: "cmds",
      requested_metric: "cosine",
      extent: [0, 0, 1, 1] as [number, number, number, number],
      cosine_scale_factor: 10_000,
      null_mean_cosine: 0.645,
      null_bin_lower_edge: -0.1,
      null_bin_width: 0.1,
      null_bin_counts: [1, 4, 30, 12, 3, 1, 0, 0, 0, 0, 0, 0],
      separation_measurable_locus_count: 12_104,
    },
  ];

  it("⛔ every prevalence band on the wire is in the union the client switches on", () => {
    // `rare` was absent from `PrevalenceBand` while 30 % of loci carried it. TypeScript cannot see
    // that — the value arrives as a string — so this is the assertion that can.
    const seen = new Set<string>();
    for (const kind of CASES) {
      const detail = detailFor(kind);
      seen.add(detail.locus.prevalence_band);
      for (const row of detail.neighbour_display_rows) seen.add(row.prevalence_band);
    }
    expect(seen.size).toBeGreaterThan(1);
    for (const band of seen) {
      expect(PREVALENCE_BANDS).toContain(band);
    }
  });

  it("mounts the headline against every fixture locus without a warning", () => {
    for (const kind of CASES) {
      const detail = detailFor(kind);
      const head = mount(LocusHeadline, {
        props: {
          locus: detail.locus,
          collectionGenomeCount: 100,
          mapProjections: PROJECTIONS,
          separationMeasurableLocusCount: 12_104,
        },
      });
      expect(head.find(".locus-name").text()).toBe(detail.locus.display_name);
      expect(head.findAll(".tile")).toHaveLength(6);
      // ⛔ No tile may render `undefined` or `NaN`: both are what a missing field looks like once
      // it has been through `toFixed` or a percentage.
      for (const tile of head.findAll(".tile .v")) {
        expect(tile.text()).not.toContain("undefined");
        expect(tile.text()).not.toContain("NaN");
      }
    }
  });

  it("⭐ resolves every Pfam accession the card chips — no bare accessions survive", () => {
    // The reference is built from the accessions the response itself mentions, so a bare chip means
    // the join failed. This is the assertion that the version-stripping actually works on real data.
    let chipped = 0;
    for (const kind of CASES) {
      const detail = detailFor(kind);
      const card = mount(SequenceDiversityCard, {
        props: {
          locus: detail.locus,
          families: detail.uniref50_families,
          symbols: detail.annotations["gene_symbol"] ?? [],
          pfamReference: detail.pfam_reference,
          listedArchitectureCount: (detail.annotations["pfam_architecture"] ?? []).length,
        },
      });
      for (const chip of card.findAll(".chip.pfam")) {
        chipped += 1;
        expect(chip.text()).not.toMatch(/^PF\d{5}$/);
        expect(chip.attributes("href")).toMatch(/^https:\/\/www\.ebi\.ac\.uk\/interpro\/entry\//);
      }
    }
    expect(chipped).toBeGreaterThan(0);
  });

  it("⛔ takes every family share over the LOCUS SIZE, so they need not sum to 100 %", () => {
    const detail = detailFor("over_cap");
    const card = mount(SequenceDiversityCard, {
      props: {
        locus: detail.locus,
        families: detail.uniref50_families,
        symbols: detail.annotations["gene_symbol"] ?? [],
        pfamReference: detail.pfam_reference,
        listedArchitectureCount: (detail.annotations["pfam_architecture"] ?? []).length,
      },
    });
    const listed = detail.uniref50_families.reduce((total, one) => total + one.gene_count, 0);
    expect(listed).toBeLessThanOrEqual(detail.locus.gene_count);
    const rows = card.findAll("tbody tr");
    expect(rows).toHaveLength(detail.uniref50_families.length);
  });

  it("mounts the geometry card and never prints a distance where a similarity belongs", () => {
    for (const kind of CASES) {
      const detail = detailFor(kind);
      const card = mount(EmbeddingGeometryCard, {
        props: {
          geometry: detail.locus.geometry,
          mapProjections: PROJECTIONS,
          geneCount: detail.locus.gene_count,
          separationMeasurableLocusCount: 12_104,
        },
      });
      if (!card.find(".card").exists()) continue;
      // ⛔ Every rail is a SIMILARITY, and the column stores a DISTANCE. Asserted as the exact
      // identity rather than as a plausible range: on this fixture a real `nearest other` sits at
      // 0.404, so any threshold that would catch an unconverted distance also rejects real data.
      const expected = (["bacformer", "esm"] as const).flatMap((representation) => {
        const geometry = detail.locus.geometry[representation];
        return [geometry.within_medoid_distance, geometry.nearest_medoid_distance]
          .filter((distance): distance is number => distance !== null)
          .map((distance) => (1 - distance).toFixed(3));
      });
      expect(card.findAll(".pair:not(.sep) .val").map((node) => node.text())).toEqual(expected);
    }
  });

  it("⚠ renders a MEASURED ZERO distance as a similarity of 1.000, not as a missing rail", () => {
    // ESM's median member→medoid distance is ~1e-5, which the payload's precision stores as 0.0.
    // A card testing truthiness rather than `!== null` would drop that rail entirely.
    const detail = detailFor("ordinary");
    expect(detail.locus.geometry.esm.within_medoid_distance).toBe(0);
    const card = mount(EmbeddingGeometryCard, {
      props: {
        geometry: detail.locus.geometry,
        mapProjections: PROJECTIONS,
        geneCount: detail.locus.gene_count,
        separationMeasurableLocusCount: 12_104,
      },
    });
    expect(card.findAll(".pair:not(.sep) .val").map((node) => node.text())).toContain("1.000");
  });
});

describe("⭐ the neighbourhood map, on real bytes", () => {
  it("⛔ resolves every map neighbour — the set the fan-out nearly missed entirely", () => {
    // `nearest_locus_ordinals` is a THIRD address space alongside arrangement slot ordinals and
    // marginal occupant locus ids, and it was not collected at all: the legend would have had a
    // swatch and a cosine with no name beside it.
    let checked = 0;
    for (const kind of CASES) {
      const detail = detailFor(kind);
      const byOrdinal = new Set(detail.neighbour_display_rows.map((row) => row.catalogue_ordinal));
      for (const representation of ["bacformer", "esm"] as const) {
        const nearest = detail.locus.geometry[representation].nearest_locus_ordinals ?? [];
        for (const ordinal of nearest) {
          // ⛔ `-1` is "outside the catalogue" and is never resolved — it drops its SLOT, not its rank.
          if (ordinal < 0) continue;
          checked += 1;
          expect(byOrdinal.has(ordinal)).toBe(true);
        }
      }
    }
    expect(checked).toBeGreaterThan(0);
  });

  it("⚠ the two representations really do name different loci on real data", () => {
    // The reason the tab changes the legend and not just the picture. If they agreed here, every
    // test above about switching representations would be proving nothing.
    let differing = 0;
    for (const kind of CASES) {
      const geometry = detailFor(kind).locus.geometry;
      const context = new Set(geometry.bacformer.nearest_locus_ordinals ?? []);
      const sequence = new Set(geometry.esm.nearest_locus_ordinals ?? []);
      if ([...context].some((ordinal) => !sequence.has(ordinal))) differing += 1;
    }
    expect(differing).toBeGreaterThan(0);
  });

  it("fits a real cosine matrix and never draws a NaN coordinate", () => {
    let drawn = 0;
    for (const kind of CASES) {
      for (const representation of ["bacformer", "esm"] as const) {
        const map = mount(NeighbourhoodMapCard, {
          props: {
            detail: detailFor(kind),
            representation,
            availableRepresentations: ["bacformer", "esm"] as const,
          },
        });
        const dots = map.findAll(".map-dot");
        if (dots.length === 0) continue;
        drawn += 1;
        for (const dot of dots) {
          // ⛔ A NaN coordinate is what an unclamped `Math.sqrt` of a negative distance produces,
          // and SVG silently drops the element rather than complaining.
          expect(Number.isFinite(Number(dot.attributes("cx")))).toBe(true);
          expect(Number.isFinite(Number(dot.attributes("cy")))).toBe(true);
          expect(Number.isFinite(Number(dot.attributes("r")))).toBe(true);
        }
        for (const ring of map.findAll(".map-ring")) {
          expect(Number(ring.attributes("r"))).toBeGreaterThanOrEqual(0);
        }
      }
    }
    expect(drawn).toBeGreaterThan(0);
  });

  it("⚠ keeps LESS than all the variance on real data — six loci are not planar", () => {
    // If every real fit kept 100 %, the `kept` number would be decoration rather than a caveat.
    const notes = CASES.map((kind) =>
      mount(NeighbourhoodMapCard, {
        props: {
          detail: detailFor(kind),
          representation: "bacformer" as const,
          availableRepresentations: ["bacformer", "esm"] as const,
        },
      })
        .findAll(".muted")
        .at(-1)
        ?.text() ?? "",
    );
    expect(notes.some((note) => /keeping (?!100%)\d/.test(note))).toBe(true);
  });
});
