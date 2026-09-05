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
