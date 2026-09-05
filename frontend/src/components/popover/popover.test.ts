/**
 * @vitest-environment jsdom
 */
import { mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";

import type { NeighbourDisplayRow, OffsetMarginal } from "@/api/types";
import { type DisplayMirror, displayMirrorApplied } from "@/lib/slotSpaces";
import { FORWARD, REVERSED } from "@/lib/walkDirection";

import OffsetPopover from "./OffsetPopover.vue";

const UPRIGHT = displayMirrorApplied(false, FORWARD);
const MIRRORED = displayMirrorApplied(true, FORWARD);

const NEIGHBOURS = new Map<string, NeighbourDisplayRow>([
  ["77", { label: "77", display_name: "rfaL", display_name_source: "O-antigen ligase", genome_count: 90, median_gene_length_nt: 1230, prevalence_band: "core" }],
  ["78", { label: "78", display_name: "waaL", display_name_source: "ligase", genome_count: 20, median_gene_length_nt: 900, prevalence_band: "shell" }],
]);

function marginal(overrides: Partial<OffsetMarginal> = {}): OffsetMarginal {
  return {
    signed_offset: -1,
    observed_member_count: 100,
    observed_not_listed: 7,
    members_without_an_observation: 12,
    occupants: [
      // 70 of 70 same-strand -> recorded majority TRUE
      { rank: 0, locus: "77", gene_count: 70, same_strand_gene_count: 70 },
      // 2 of 20 same-strand -> recorded majority FALSE
      { rank: 1, locus: "78", gene_count: 20, same_strand_gene_count: 2 },
    ],
    ...overrides,
  };
}

function mountPopover(props: Partial<InstanceType<typeof OffsetPopover>["$props"]> = {}) {
  return mount(OffsetPopover, {
    props: {
      marginal: marginal(),
      labelledOffset: -1,
      recordedOffset: -1,
      displayMirror: UPRIGHT as DisplayMirror,
      drawnLocus: "77",
      focalGeneCount: 112,
      neighboursByLabel: NEIGHBOURS,
      topNeighbourCount: 5,
      ...props,
    },
  });
}

describe("⛔ the heading names the column the reader CLICKED", () => {
  it("says upstream for a negative offset and downstream for a positive one", () => {
    expect(mountPopover().find("h2").text()).toBe("A-1 · upstream");
    expect(mountPopover({ labelledOffset: 3, recordedOffset: 3 }).find("h2").text()).toBe(
      "A+3 · downstream",
    );
  });

  it("⛔ adds `recorded at` ONLY when the counts came from a different offset", () => {
    // A row drawn mirrored: the block is labelled A-1 but its counts are from A+1. Without this
    // note the panel and the block look like different data.
    const mirrored = mountPopover({ labelledOffset: -1, recordedOffset: 1 });
    expect(mirrored.find(".pop-meta").text()).toContain("↺ recorded at A+1");
    expect(mountPopover().find(".pop-meta").text()).not.toContain("recorded at");
  });

  it("⚠ compares the two OFFSETS, not the flip — so a cancelling pair prints no note", () => {
    // An arrangement flip under a reversed walk draws the row the right way up. Reading the flip
    // alone would wrongly claim the counts came from elsewhere.
    const cancelled = mountPopover({
      labelledOffset: -1,
      recordedOffset: -1,
      displayMirror: displayMirrorApplied(true, REVERSED),
    });
    expect(cancelled.find(".pop-meta").text()).not.toContain("recorded at");
  });

  it("reports the honest denominator — members with a gene here, not the locus size", () => {
    expect(mountPopover().find(".pop-meta").text()).toContain("100 of 112 member genes");
  });
});

describe("⭐ clicking a row is a WALK carrying the orientation AS DRAWN", () => {
  it("walks forward from a co-oriented occupant on an upright row", () => {
    const wrapper = mountPopover();
    wrapper.findAll(".alt")[0]!.trigger("click");
    expect(wrapper.emitted("walk")).toEqual([["77", FORWARD]]);
  });

  it("walks reversed from an opposed occupant", () => {
    const wrapper = mountPopover();
    wrapper.findAll(".alt")[1]!.trigger("click");
    expect(wrapper.emitted("walk")).toEqual([["78", REVERSED]]);
  });

  it("⛔ INVERTS both on a mirrored row — the published page's own bug", () => {
    // The marginal list used the raw recorded bit and pointed the wrong way under a reversed walk.
    const wrapper = mountPopover({ displayMirror: MIRRORED });
    wrapper.findAll(".alt")[0]!.trigger("click");
    wrapper.findAll(".alt")[1]!.trigger("click");
    expect(wrapper.emitted("walk")).toEqual([
      ["77", REVERSED],
      ["78", FORWARD],
    ]);
  });

  it("draws the arrow to agree with the direction it will walk", () => {
    const upright = mountPopover();
    expect(upright.findAll(".alt .strand").map((n) => n.text())).toEqual(["→", "←"]);
    const mirrored = mountPopover({ displayMirror: MIRRORED });
    expect(mirrored.findAll(".alt .strand").map((n) => n.text())).toEqual(["←", "→"]);
  });
});

describe("the rows", () => {
  it("⚠ show the locus id beside the name, because names are not unique", () => {
    // 1,364 display names in these catalogues are carried by more than one locus, so two blocks
    // reading the same name may or may not be the same node.
    expect(mountPopover().findAll(".alt .lid").map((n) => n.text())).toEqual(["·77", "·78"]);
  });

  it("marks the occupant that is actually drawn on the track", () => {
    const wrapper = mountPopover();
    const marked = wrapper.findAll(".alt").filter((n) => n.classes("on-track"));
    expect(marked).toHaveLength(1);
    expect(marked[0]!.find(".lid").text()).toBe("·77");
  });

  it("shows each occupant's count and its share of the OBSERVED members", () => {
    expect(mountPopover().findAll(".alt-n").map((n) => n.text())).toEqual(["70 · 70%", "20 · 20%"]);
  });
});

describe("⛔ the two remainders are two, and never merged", () => {
  it("names the display cut and the missing data separately", () => {
    const text = mountPopover().find(".pop-tail").text();
    expect(text).toContain("+7 outside the top 5");
    expect(text).toContain("12 genes: contig ends first");
  });

  it("omits each independently when it is zero", () => {
    const noCut = mountPopover({ marginal: marginal({ observed_not_listed: 0 }) });
    expect(noCut.find(".pop-tail").text()).toBe("12 genes: contig ends first");

    const noMissing = mountPopover({ focalGeneCount: 100 });
    expect(noMissing.find(".pop-tail").text()).toBe("+7 outside the top 5");
  });

  it("prints no tail at all when both are zero", () => {
    const clean = mountPopover({
      marginal: marginal({ observed_not_listed: 0 }),
      focalGeneCount: 100,
    });
    expect(clean.find(".pop-tail").exists()).toBe(false);
  });
});
