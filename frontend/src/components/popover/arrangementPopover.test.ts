/**
 * @vitest-environment jsdom
 */
import { mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";

import type { Arrangement, Locus } from "@/api/types";
import { SIGNED_OFFSETS, type NeighbourSlot } from "@/lib/slotSpaces";
import { FORWARD } from "@/lib/walkDirection";

import ArrangementPopover from "./ArrangementPopover.vue";

const NEIGHBOURS = ["10", "11", "12", "13", "14", "15", "16", "17", "18", "19"] as const;

function slotsFrom(loci: readonly (string | null)[]): NeighbourSlot[] {
  return loci.map((locus, index) => ({
    signed_offset: SIGNED_OFFSETS[index] as number,
    locus,
    absence_reason: locus === null ? ("contig_end" as const) : null,
    same_strand: locus === null ? null : true,
  }));
}

function arrangement(rank: number, geneCount: number, overrides: Partial<Arrangement> = {}): Arrangement {
  return {
    rank,
    gene_count: geneCount,
    genome_count: geneCount,
    is_recorded_reverse_complement: false,
    slots: slotsFrom(NEIGHBOURS),
    ...overrides,
  };
}

/** Only the fields this card reads; the rest of `Locus` is irrelevant to it. */
function locus(geneCount: number): Locus {
  return { label: "77", display_name: "rfaL", gene_count: geneCount } as unknown as Locus;
}

function mountCard(props: Partial<InstanceType<typeof ArrangementPopover>["$props"]> = {}) {
  return mount(ArrangementPopover, {
    props: {
      locus: locus(100),
      arrangements: [arrangement(0, 70), arrangement(1, 20)],
      total: 2,
      selectedRank: 0,
      anchorRanks: [],
      membersWithoutANeighbourhood: 10,
      walkDirection: FORWARD,
      arrangementsNotShown: 0,
      loadStatus: "idle" as const,
      ...props,
    },
  });
}

describe("⭐ A0 is about the SPLIT, not about what else is here", () => {
  it("heads the card with the locus and counts its neighbourhoods", () => {
    const card = mountCard();
    expect(card.find("h2").text()).toBe("A0 · this locus");
    expect(card.find(".pop-meta").text()).toBe("100 member genes · 2 neighbourhoods");
  });

  it("says `1 neighbourhood` in the singular, and that there is nothing to choose", () => {
    const card = mountCard({ arrangements: [arrangement(0, 90)], total: 1 });
    expect(card.find(".pop-meta").text()).toBe("100 member genes · 1 neighbourhood");
    expect(card.find(".pop-lede").text()).toContain("there is nothing to choose between");
  });

  it("points at the switcher, because the rows here do not select", () => {
    expect(mountCard().find(".pop-lede").text()).toContain(
      "pick one in the neighbourhood browser under the track to draw it",
    );
  });
});

describe("⛔ the rows are static — this card lists, it does not select", () => {
  it("renders no button for a row", () => {
    const card = mountCard();
    expect(card.findAll(".alt")).toHaveLength(2);
    expect(card.findAll(".alt button")).toHaveLength(0);
    expect(card.findAll("button.alt")).toHaveLength(0);
  });

  it("marks the one drawn on the track, and only that one", () => {
    const card = mountCard({ selectedRank: 1 });
    const marked = card.findAll(".alt").filter((row) => row.classes("alt-on"));
    expect(marked).toHaveLength(1);
    expect(marked[0]!.text()).toContain("#2 — drawn above");
  });

  it("draws nothing as `drawn above` when no arrangement is drawn", () => {
    const card = mountCard({ selectedRank: null });
    expect(card.text()).not.toContain("drawn above");
  });
});

describe("the one line under each row", () => {
  it("calls rank 1 the commonest arrangement rather than leaving the line empty", () => {
    expect(mountCard().findAll(".alt-desc")[0]!.text()).toBe("commonest arrangement");
  });

  it("describes the others against rank 1, in the displayed frame", () => {
    const changed = [...NEIGHBOURS] as (string | null)[];
    changed[4] = "94";
    const card = mountCard({
      arrangements: [arrangement(0, 70), arrangement(1, 20, { slots: slotsFrom(changed) })],
    });
    expect(card.findAll(".alt-desc")[1]!.text()).toBe("differs at A-1");
  });

  it("shows each arrangement's gene count and its share of the member genes", () => {
    expect(mountCard().findAll(".alt-n").map((n) => n.text())).toEqual(["70 · 70%", "20 · 20%"]);
  });

  it("⚠ keeps a decimal below 10 %, so a listed row never reports zero", () => {
    const card = mountCard({
      locus: locus(500),
      arrangements: [arrangement(0, 400), arrangement(1, 2)],
      membersWithoutANeighbourhood: 98,
    });
    expect(card.findAll(".alt-n")[1]!.text()).toBe("2 · 0.4%");
  });
});

describe("⛔ the two remainders are two, and never merged", () => {
  it("names the missing data on its own when the list is complete", () => {
    expect(mountCard().find(".pop-tail").text()).toBe(
      "10 member genes have no recorded neighbourhood — no coordinates for the gene, so no window",
    );
  });

  it("⛔ derives the display cut from the response's own identity, not by one subtraction", () => {
    // 100 members: 70 + 20 listed here, 10 with no window at all — so 0 in unlisted arrangements.
    // Add an unlisted arrangement's worth of members and only THAT number may move.
    const card = mountCard({
      locus: locus(140),
      total: 5,
      arrangementsNotShown: 3,
      membersWithoutANeighbourhood: 10,
    });
    expect(card.find(".pop-tail").text()).toContain(
      "40 member genes sit in arrangements not listed here",
    );
    expect(card.find(".pop-tail").text()).toContain("10 member genes have no recorded neighbourhood");
  });

  it("prints no tail when both are zero", () => {
    const card = mountCard({ locus: locus(90), membersWithoutANeighbourhood: 0 });
    expect(card.find(".pop-tail").exists()).toBe(false);
  });
});

describe("⛔ a list that ended, a list still loading and a list that FAILED are three things", () => {
  it("offers the rest, counted, while any remain", () => {
    const card = mountCard({ total: 84, arrangementsNotShown: 82 });
    expect(card.find(".arr-more").text()).toBe("Show more — 82 not listed");
    card.find(".arr-more").trigger("click");
    expect(card.emitted("loadMore")).toHaveLength(1);
  });

  it("offers nothing more once the list is complete", () => {
    expect(mountCard().find(".arr-more").exists()).toBe(false);
  });

  it("says it is loading, and cannot be asked twice", () => {
    const card = mountCard({ total: 84, arrangementsNotShown: 82, loadStatus: "pending" });
    expect(card.find(".arr-more").text()).toBe("Loading…");
    expect(card.find(".arr-more").attributes("disabled")).toBeDefined();
  });

  it("⛔ shows the server's own sentence on a failure, never an ended list", () => {
    const card = mountCard({
      total: 84,
      arrangementsNotShown: 82,
      loadStatus: "failed",
      loadFailureDetail: "the request did not reach the server",
    });
    expect(card.find(".arr-more").exists()).toBe(false);
    const error = card.find(".pop-error");
    expect(error.attributes("role")).toBe("alert");
    expect(error.text()).toContain("the request did not reach the server");
    error.find(".pop-retry").trigger("click");
    expect(card.emitted("loadMore")).toHaveLength(1);
  });
});

describe("⚠ what the card claims about its own completeness", () => {
  it("says every one is listed only when every one IS", () => {
    expect(mountCard().find(".pop-lede").text()).toContain("every one of them listed below");
  });

  it("names how many it is showing when it is not showing them all", () => {
    const card = mountCard({ total: 84, arrangementsNotShown: 82 });
    expect(card.find(".pop-lede").text()).toContain("2 of them listed below");
    expect(card.find(".pop-lede").text()).not.toContain("every one of them");
  });
});

describe("⚓ the anchored genome's own arrangement", () => {
  it("is marked wherever it appears, which is the only place a rank past the cut is visible", () => {
    const card = mountCard({
      arrangements: [arrangement(0, 70), arrangement(36, 1)],
      total: 84,
      arrangementsNotShown: 82,
      anchorRanks: [36],
      selectedRank: 36,
    });
    const anchored = card.findAll(".alt").filter((row) => row.classes("anchored"));
    expect(anchored).toHaveLength(1);
    expect(anchored[0]!.text()).toContain("#37");
  });
});

describe("↺ an inverted row is badged", () => {
  it("badges the arrangement's own recorded flip", () => {
    const card = mountCard({
      arrangements: [
        arrangement(0, 70),
        arrangement(1, 20, {
          is_recorded_reverse_complement: true,
          slots: slotsFrom([...NEIGHBOURS].reverse()),
        }),
      ],
    });
    expect(card.findAll(".arr-inv")).toHaveLength(1);
    expect(card.findAll(".alt-desc")[1]!.text()).toBe("inverted · same neighbours");
  });
});
