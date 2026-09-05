import { createPinia, setActivePinia } from "pinia";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { nextTick } from "vue";

import { failure, success } from "@/api/result";
import type { Arrangement, LocusDetailResponse, NeighbourSlot } from "@/api/types";
import { SIGNED_OFFSETS } from "@/lib/slotSpaces";

import { mergeArrangementsByRank, useArrangementBrowserStore } from "./arrangementBrowserStore";
import { useLocusNavigationStore } from "./locusNavigationStore";

const fetchLocus = vi.hoisted(() => vi.fn());
const fetchArrangementPage = vi.hoisted(() => vi.fn());
vi.mock("@/api/client", () => ({ fetchLocus, fetchArrangementPage }));

function slots(): NeighbourSlot[] {
  return SIGNED_OFFSETS.map((signed_offset, position) => ({
    signed_offset,
    locus: String(position),
    absence_reason: null,
    same_strand: true,
  }));
}

function arrangement(rank: number, geneCount = 1): Arrangement {
  return {
    rank,
    gene_count: geneCount,
    genome_count: geneCount,
    is_recorded_reverse_complement: false,
    slots: slots(),
  };
}

function locusDetail(
  label: string,
  listed: readonly Arrangement[],
  total: number,
): LocusDetailResponse {
  return {
    locus: { label, gene_count: 100 } as LocusDetailResponse["locus"],
    annotations: {},
    uniref50_families: [],
    arrangements: {
      listed,
      total,
      arrangements_not_listed: Math.max(0, total - listed.length),
      members_in_arrangements_not_listed: 0,
      members_without_a_neighbourhood: 0,
      membership_is_complete: true,
    },
    anchor: { is_anchored: false, arrangement_ranks: [] },
    offsets: [],
    intergenic_gaps: [],
    neighbour_display_rows: [],
    resolved_neighbour_count: 0,
  };
}

/** Ranks 0..7 plus the anchored one at 36 — exactly the shape the display cap produces. */
const CAPPED = [...Array.from({ length: 8 }, (_u, rank) => arrangement(rank)), arrangement(36)];

async function drawLocus(label: string, listed: readonly Arrangement[], total: number) {
  const navigation = useLocusNavigationStore();
  navigation.setSpecies("ecoli");
  fetchLocus.mockResolvedValueOnce(success(locusDetail(label, listed, total)));
  await navigation.navigateTo(label);
  await nextTick();
  return navigation;
}

beforeEach(() => {
  setActivePinia(createPinia());
  fetchLocus.mockReset();
  fetchArrangementPage.mockReset();
});

describe("⛔ merging the fetched prefix with the capped list", () => {
  it("keeps one row per rank and sorts by rank", () => {
    const merged = mergeArrangementsByRank([arrangement(3), arrangement(0)], [arrangement(1)]);
    expect(merged.map((a) => a.rank)).toEqual([0, 1, 3]);
  });

  it("⛔ does not drop the anchored row the cap spliced in past the fetched prefix", () => {
    // The whole reason the cap has that rule: a reader told in words that their genome sits in #37
    // must not watch that row vanish the moment they ask to see more of the list.
    const prefix = Array.from({ length: 4 }, (_u, rank) => arrangement(rank));
    const merged = mergeArrangementsByRank([arrangement(0), arrangement(36)], prefix);
    expect(merged.map((a) => a.rank)).toEqual([0, 1, 2, 3, 36]);
  });

  it("lets a later set win on a rank both carry, so a fetched row replaces a capped one", () => {
    const merged = mergeArrangementsByRank([arrangement(0, 5)], [arrangement(0, 9)]);
    expect(merged).toHaveLength(1);
    expect(merged[0]!.gene_count).toBe(9);
  });
});

describe("before anything is fetched", () => {
  it("lists what the locus response already carried, and asks for nothing", async () => {
    await drawLocus("1", CAPPED, 84);
    const browser = useArrangementBrowserStore();
    expect(browser.rows.map((a) => a.rank)).toEqual([0, 1, 2, 3, 4, 5, 6, 7, 36]);
    expect(browser.total).toBe(84);
    expect(browser.arrangementsNotShown).toBe(75);
    expect(browser.status).toBe("idle");
    expect(fetchArrangementPage).not.toHaveBeenCalled();
  });

  it("has nothing more to offer when the response already held them all", async () => {
    await drawLocus("1", [arrangement(0), arrangement(1)], 2);
    const browser = useArrangementBrowserStore();
    expect(browser.hasMore).toBe(false);
    await browser.loadMore();
    expect(fetchArrangementPage).not.toHaveBeenCalled();
  });
});

describe("paging", () => {
  it("⛔ asks at the FETCHED prefix length, not at the length of what is on screen", async () => {
    // `rows` is nine long — eight plus the spliced #37 — but only ranks 0..7 have been fetched.
    // Asking at offset 9 would skip rank 8 entirely and it would never be shown.
    await drawLocus("1", CAPPED, 84);
    const browser = useArrangementBrowserStore();
    fetchArrangementPage.mockResolvedValueOnce(
      success({ arrangements: [arrangement(0), arrangement(1)], offset: 0, total: 84 }),
    );
    await browser.loadMore();
    expect(fetchArrangementPage).toHaveBeenCalledWith("ecoli", "1", 0, expect.anything());
  });

  it("appends the next page and asks at the new prefix length", async () => {
    await drawLocus("1", [arrangement(0)], 84);
    const browser = useArrangementBrowserStore();
    fetchArrangementPage.mockResolvedValueOnce(
      success({ arrangements: [arrangement(0), arrangement(1)], offset: 0, total: 84 }),
    );
    await browser.loadMore();
    expect(browser.rows.map((a) => a.rank)).toEqual([0, 1]);
    expect(browser.status).toBe("ready");

    fetchArrangementPage.mockResolvedValueOnce(
      success({ arrangements: [arrangement(2)], offset: 2, total: 84 }),
    );
    await browser.loadMore();
    expect(fetchArrangementPage).toHaveBeenLastCalledWith("ecoli", "1", 2, expect.anything());
    expect(browser.rows.map((a) => a.rank)).toEqual([0, 1, 2]);
    expect(browser.arrangementsNotShown).toBe(81);
  });

  it("⚠ ignores a page that answers a different offset rather than appending it twice", async () => {
    await drawLocus("1", [arrangement(0)], 84);
    const browser = useArrangementBrowserStore();
    fetchArrangementPage.mockResolvedValueOnce(
      success({ arrangements: [arrangement(5)], offset: 40, total: 84 }),
    );
    await browser.loadMore();
    expect(browser.rows.map((a) => a.rank)).toEqual([0]);
  });

  it("cannot be asked twice while a page is in flight", async () => {
    await drawLocus("1", [arrangement(0)], 84);
    const browser = useArrangementBrowserStore();
    let release: (value: unknown) => void = () => {};
    fetchArrangementPage.mockReturnValueOnce(
      new Promise((resolve) => {
        release = resolve;
      }),
    );
    const first = browser.loadMore();
    await browser.loadMore();
    expect(fetchArrangementPage).toHaveBeenCalledTimes(1);
    release(success({ arrangements: [arrangement(1)], offset: 0, total: 84 }));
    await first;
  });
});

describe("⛔ a failure, a supersession and an empty answer are three different things", () => {
  it("reports a failure as a failure and leaves the list exactly as it was", async () => {
    await drawLocus("1", CAPPED, 84);
    const browser = useArrangementBrowserStore();
    fetchArrangementPage.mockResolvedValueOnce(failure("network", "the request did not reach the server"));
    await browser.loadMore();
    expect(browser.status).toBe("failed");
    expect(browser.lastFailure?.detail).toBe("the request did not reach the server");
    expect(browser.rows).toHaveLength(9);
  });

  it("clears the failure when the reader tries again and it works", async () => {
    await drawLocus("1", [arrangement(0)], 84);
    const browser = useArrangementBrowserStore();
    fetchArrangementPage.mockResolvedValueOnce(failure("network", "down"));
    await browser.loadMore();
    fetchArrangementPage.mockResolvedValueOnce(
      success({ arrangements: [arrangement(0), arrangement(1)], offset: 0, total: 84 }),
    );
    await browser.loadMore();
    expect(browser.status).toBe("ready");
    expect(browser.lastFailure).toBeNull();
  });

  it("⛔ changes NOTHING when a page is superseded — not an error, not an empty list", async () => {
    await drawLocus("1", [arrangement(0)], 84);
    const browser = useArrangementBrowserStore();
    let release: (value: unknown) => void = () => {};
    fetchArrangementPage.mockReturnValueOnce(
      new Promise((resolve) => {
        release = resolve;
      }),
    );
    const stale = browser.loadMore();
    browser.reset();
    release(success({ arrangements: [arrangement(0), arrangement(1)], offset: 0, total: 84 }));
    await stale;
    expect(browser.status).toBe("idle");
    expect(browser.lastFailure).toBeNull();
    expect(browser.fetched).toHaveLength(0);
  });
});

describe("⛔ the list belongs to the DRAWN locus", () => {
  it("throws the fetched pages away when the reader walks on", async () => {
    await drawLocus("1", [arrangement(0)], 84);
    const browser = useArrangementBrowserStore();
    fetchArrangementPage.mockResolvedValueOnce(
      success({ arrangements: [arrangement(0), arrangement(1)], offset: 0, total: 84 }),
    );
    await browser.loadMore();
    expect(browser.fetched).toHaveLength(2);

    const navigation = useLocusNavigationStore();
    fetchLocus.mockResolvedValueOnce(success(locusDetail("2", [arrangement(0)], 3)));
    await navigation.navigateTo("2");
    await nextTick();
    expect(browser.fetched).toHaveLength(0);
    expect(browser.total).toBe(3);
  });

  it("⛔ does not land a page on the locus that replaced the one it was asked for", async () => {
    // ⚠ Pins the BEHAVIOUR, and deliberately not the mechanism: measured by mutation, it is the
    // lane cancel in `reset` that catches this, and removing the store's label re-check fails
    // nothing. Saying which guard fired would make this test wrong the day the ordering changes —
    // the outcome is what must hold.
    await drawLocus("1", [arrangement(0)], 84);
    const browser = useArrangementBrowserStore();
    let release: (value: unknown) => void = () => {};
    fetchArrangementPage.mockReturnValueOnce(
      new Promise((resolve) => {
        release = resolve;
      }),
    );
    const stale = browser.loadMore();

    const navigation = useLocusNavigationStore();
    fetchLocus.mockResolvedValueOnce(success(locusDetail("2", [arrangement(0)], 3)));
    await navigation.navigateTo("2");
    release(success({ arrangements: [arrangement(0), arrangement(1)], offset: 0, total: 84 }));
    await stale;
    // ⛔ And as a supersession, not a failure: the reader is shown the new locus, not an error
    // about a page they abandoned.
    expect(browser.status).toBe("idle");
    expect(browser.lastFailure).toBeNull();
    expect(browser.fetched).toHaveLength(0);
    expect(browser.rows.map((a) => a.rank)).toEqual([0]);
  });
});
