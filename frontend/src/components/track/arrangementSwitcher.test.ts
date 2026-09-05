/**
 * @vitest-environment jsdom
 */
import { mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";

import type { Arrangement, Locus } from "@/api/types";
import { SIGNED_OFFSETS, type NeighbourSlot } from "@/lib/slotSpaces";
import { FORWARD } from "@/lib/walkDirection";

import ArrangementSwitcher from "./ArrangementSwitcher.vue";

const NEIGHBOURS: readonly string[] = ["10", "11", "12", "13", "14", "15", "16", "17", "18", "19"];

function slotsFrom(loci: readonly (string | null)[]): NeighbourSlot[] {
  return loci.map((locus, index) => ({
    signed_offset: SIGNED_OFFSETS[index] as number,
    locus,
    absence_reason: locus === null ? ("contig_end" as const) : null,
    same_strand: locus === null ? null : true,
  }));
}

function arrangement(rank: number, genes: number, overrides: Partial<Arrangement> = {}): Arrangement {
  return {
    rank,
    gene_count: genes,
    genome_count: genes,
    is_recorded_reverse_complement: false,
    slots: slotsFrom(NEIGHBOURS),
    ...overrides,
  };
}

function locus(geneCount = 100, genomeCount = 97): Locus {
  return {
    label: "77",
    display_name: "rfaL",
    gene_count: geneCount,
    genome_count: genomeCount,
  } as unknown as Locus;
}

function mountSwitcher(props: Partial<InstanceType<typeof ArrangementSwitcher>["$props"]> = {}) {
  return mount(ArrangementSwitcher, {
    props: {
      locus: locus(),
      arrangements: [arrangement(0, 60), arrangement(1, 30)],
      total: 4,
      selectedIndex: 0,
      anchorRanks: [],
      anchorGenomeName: null,
      membershipIsComplete: true,
      walkDirection: FORWARD,
      ...props,
    },
  });
}

describe("⭐ this is the control that PICKS an arrangement", () => {
  it("offers one button per row the track holds slots for", () => {
    const buttons = mountSwitcher().findAll(".arr-opt");
    expect(buttons).toHaveLength(2);
    expect(buttons.map((b) => b.find(".arr-rank").text())).toEqual(["#1", "#2"]);
  });

  it("emits the INDEX, which is what the track selects by", () => {
    // Not the rank: an anchored row spliced in past the cap makes the two diverge, and the store
    // indexes into `arrangements.listed`.
    const switcher = mountSwitcher({ arrangements: [arrangement(0, 60), arrangement(36, 1)] });
    switcher.findAll(".arr-opt")[1]!.trigger("click");
    expect(switcher.emitted("select")).toEqual([[1]]);
  });

  it("renders nothing at all when there is no arrangement to offer", () => {
    const empty = mountSwitcher({ arrangements: [] });
    expect(empty.find(".arr-row").exists()).toBe(false);
    expect(empty.find(".arr-notes").exists()).toBe(false);
  });

  it("⛔ puts the row and the notes at the ROOT, with nothing wrapping them", () => {
    // `app.css:720` places `.arr-notes` at `grid-row: 3` of the page grid. A wrapping <div> would
    // make them a grid of one and silently drop that placement — and the option row must stay its
    // own grid row so the anchor control beside it can sit centred on the buttons.
    const switcher = mountSwitcher();
    const row = switcher.find(".arr-row").element;
    const notes = switcher.find(".arr-notes").element;
    expect(notes.parentElement).toBe(row.parentElement);
    // …and that shared parent belongs to the harness, not to this component: an empty class name
    // is the mount host. Any class here would be a wrapper this component rendered.
    expect(row.parentElement?.className).toBe("");
  });
});

describe("⛔ two marks, not one", () => {
  it("separates `this is drawn` from `this is yours`", () => {
    // A manual pick overriding the anchor is exactly when a reader has to see both.
    const switcher = mountSwitcher({ selectedIndex: 1, anchorRanks: [0], anchorGenomeName: "SAMEA1" });
    const drawn = switcher.findAll(".arr-opt").filter((b) => b.classes("on"));
    const anchored = switcher.findAll(".arr-opt").filter((b) => b.classes("anchored"));
    expect(drawn[0]!.find(".arr-rank").text()).toBe("#2");
    expect(anchored[0]!.find(".arr-rank").text()).toBe("#1");
    expect(switcher.findAll(".arr-anch-mark")).toHaveLength(1);
  });

  it("marks the drawn button for assistive technology too", () => {
    const switcher = mountSwitcher({ selectedIndex: 1 });
    expect(switcher.findAll(".arr-opt").map((b) => b.attributes("aria-pressed"))).toEqual([
      "false",
      "true",
    ]);
  });
});

describe("⚠ the sentence counts EVERY arrangement; the row draws a few", () => {
  it("names the total, not the number of buttons", () => {
    const head = mountSwitcher({ total: 84 }).find(".arr-head").text();
    expect(head).toContain("sits in 84 neighbourhoods across 97 genomes");
  });

  it("⛔ takes coverage over what is DRAWN, so the line qualifies the buttons", () => {
    // Summing every arrangement would print "100% of its genes" at every locus — true, and useless.
    expect(mountSwitcher({ total: 84 }).find(".arr-head").text()).toContain(
      "The 2 here account for 90% of its genes",
    );
  });

  it("agrees with itself in the singular", () => {
    const switcher = mountSwitcher({ arrangements: [arrangement(0, 60)], total: 84 });
    expect(switcher.find(".arr-head").text()).toContain("The 1 here accounts for 60% of its genes");
  });
});

describe("the single-arrangement locus", () => {
  it("says so in words and offers no buttons to press", () => {
    const switcher = mountSwitcher({ arrangements: [arrangement(0, 97)], total: 1 });
    expect(switcher.findAll(".arr-opt")).toHaveLength(0);
    expect(switcher.find(".arr-only").text()).toBe(
      "All 97 genomes put the same genes around this locus — one arrangement.",
    );
  });

  it("⚠ still carries the anchor line — it is the shape an uncarried locus usually has", () => {
    const switcher = mountSwitcher({
      arrangements: [arrangement(0, 97)],
      total: 1,
      anchorGenomeName: "SAMEA1",
      anchorRanks: [],
      membershipIsComplete: true,
    });
    expect(switcher.find(".arr-anchored").text()).toContain("has no gene at this locus");
  });
});

describe("⛔ the anchor line says one of two DIFFERENT things, and only one is ever true", () => {
  it("names the genome plainly when it carries an arrangement here", () => {
    const line = mountSwitcher({ anchorGenomeName: "SAMEA1", anchorRanks: [0] }).find(".arr-anchored");
    expect(line.text()).toBe("Anchored to SAMEA1");
    expect(line.classes()).not.toContain("muted");
  });

  it("says `no gene at this locus` ONLY where every genome present reaches an arrangement", () => {
    const line = mountSwitcher({
      anchorGenomeName: "SAMEA1",
      anchorRanks: [],
      membershipIsComplete: true,
    }).find(".arr-anchored");
    expect(line.text()).toContain("has no gene at this locus");
    expect(line.classes()).toContain("muted");
  });

  it("⛔ says `no recorded neighbourhood` where it does not — at 6.26 % of ecoli loci", () => {
    // `coords` is an inner join in the export, so a gene with no coordinates never reaches a
    // window: its genome is counted present and sits in no arrangement. Saying "has no gene here"
    // there is simply false.
    const line = mountSwitcher({
      anchorGenomeName: "SAMEA1",
      anchorRanks: [],
      membershipIsComplete: false,
    }).find(".arr-anchored");
    expect(line.text()).toContain("has no recorded neighbourhood at this locus");
    expect(line.text()).not.toContain("has no gene at this locus");
  });

  it("prints no anchor line at all when nothing is anchored", () => {
    expect(mountSwitcher().find(".arr-anchored").exists()).toBe(false);
  });
});

describe("↺ an inverted row", () => {
  it("is badged and explained, and the badge names the focal gene", () => {
    const switcher = mountSwitcher({
      arrangements: [
        arrangement(0, 60),
        arrangement(1, 30, {
          is_recorded_reverse_complement: true,
          slots: slotsFrom([...NEIGHBOURS].reverse()),
        }),
      ],
    });
    const badge = switcher.find(".arr-inv");
    expect(badge.exists()).toBe(true);
    expect(badge.attributes("title")).toContain("rfaL inverted relative to it");
    expect(switcher.findAll(".arr-opt")[1]!.classes()).toContain("flip");
    expect(switcher.findAll(".arr-diff")[1]!.text()).toBe("inverted · same neighbours");
  });

  it("says so in the button's own tooltip, where the counts are", () => {
    const switcher = mountSwitcher({
      arrangements: [arrangement(0, 60), arrangement(1, 30, { is_recorded_reverse_complement: true })],
    });
    expect(switcher.findAll(".arr-opt")[1]!.attributes("title")).toBe(
      "30 of 100 member genes, in 30 genomes — displayed reverse-complemented",
    );
  });
});
