import { createPinia, setActivePinia } from "pinia";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { nextTick } from "vue";

import { failure, success } from "@/api/result";
import type { Arrangement, LocusDetailResponse, NeighbourSlot } from "@/api/types";
import { SIGNED_OFFSETS, asDisplaySlot } from "@/lib/slotSpaces";
import { FORWARD, REVERSED } from "@/lib/walkDirection";

import { useAnchorGenomeStore } from "./anchorGenomeStore";
import { locusCacheKey, useLocusDetailCacheStore } from "./locusDetailCacheStore";
import { DIM_AFTER_MS, useLocusNavigationStore } from "./locusNavigationStore";
import { useTrackDisplayStore } from "./trackDisplayStore";

const fetchLocus = vi.hoisted(() => vi.fn());
vi.mock("@/api/client", () => ({ fetchLocus }));

/** Ten slots, every one identifiable, alternating strand so a reversal alone would not pass. */
function slots(occupants: readonly (string | null)[]): NeighbourSlot[] {
  return SIGNED_OFFSETS.map((signed_offset, position) => ({
    signed_offset,
    locus: occupants[position] ?? null,
    absence_reason: occupants[position] ? null : ("contig_end" as const),
    same_strand: occupants[position] ? position % 2 === 0 : null,
  }));
}

function arrangement(overrides: Partial<Arrangement> = {}): Arrangement {
  return {
    rank: 0,
    gene_count: 10,
    genome_count: 10,
    is_recorded_reverse_complement: false,
    slots: slots(["A", "B", "C", "D", "E", "F", "G", "H", "I", "J"]),
    ...overrides,
  };
}

function locusDetail(overrides: Partial<LocusDetailResponse> = {}): LocusDetailResponse {
  return {
    locus: { label: "1" } as LocusDetailResponse["locus"],
    annotations: {},
    uniref50_families: [],
    arrangements: {
      listed: [arrangement()],
      total: 1,
      arrangements_not_listed: 0,
      members_without_a_neighbourhood: 0,
    },
    anchor: { is_anchored: false, arrangement_ranks: [] },
    offsets: [],
    intergenic_gaps: [],
    neighbour_display_rows: [],
    resolved_neighbour_count: 0,
    ...overrides,
  };
}

beforeEach(() => {
  setActivePinia(createPinia());
  fetchLocus.mockReset();
});
afterEach(() => {
  vi.useRealTimers();
});

describe("the cache key", () => {
  it("⛔ INCLUDES the anchor, because the response shape depends on it", () => {
    // Given an anchor the API adds the arrangement that genome carries even past the display cap,
    // so keying on the label alone would serve a reader who just set one the response from before
    // they set it — with their genome's arrangement missing, which is the exact failure the anchor
    // exists to prevent.
    expect(locusCacheKey("ecoli", "42", null)).not.toBe(locusCacheKey("ecoli", "42", "SAMEA1"));
  });

  it("treats an empty string and null as the same absence", () => {
    // A control that clears itself to "" would otherwise silently double the cache.
    expect(locusCacheKey("ecoli", "42", "")).toBe(locusCacheKey("ecoli", "42", null));
  });

  it("separates species", () => {
    expect(locusCacheKey("ecoli", "42", null)).not.toBe(locusCacheKey("kp", "42", null));
  });
});

describe("the cache", () => {
  it("⭐ has no invalidation API at all — nothing can go stale within a build", () => {
    // Read-only means a response is immutable for a build, so there is nothing to expire,
    // revalidate or bust. `clear` exists only for switching species, where every key changes
    // anyway. ⚠ Asserted as the ABSENCE of those names rather than as an exact surface, because
    // Pinia adds its own `_hmrPayload`/`_hotUpdate` in dev and pinning the whole list would make
    // this test fail for a reason nobody cares about — and a test that fails for the wrong reason
    // gets deleted rather than fixed.
    const cache = useLocusDetailCacheStore();
    const invalidation = Object.keys(cache).filter((name) =>
      /invalidat|expire|stale|revalidat|refresh|bust|ttl|evict/i.test(name),
    );
    expect(invalidation).toEqual([]);
    for (const required of ["get", "has", "put", "prefetch", "clear", "size"]) {
      expect(cache).toHaveProperty(required);
    }
  });

  it("evicts least-recently-USED, not least-recently-written", async () => {
    const cache = useLocusDetailCacheStore();
    const { CACHE_LIMIT } = await import("./locusDetailCacheStore");
    for (let index = 0; index < CACHE_LIMIT; index++) cache.put(`k${index}`, locusDetail());
    // Touch the oldest, then overflow by one: the oldest must survive and the SECOND oldest go.
    cache.get("k0");
    cache.put("overflow", locusDetail());
    expect(cache.has("k0")).toBe(true);
    expect(cache.has("k1")).toBe(false);
    expect(cache.size).toBe(CACHE_LIMIT);
  });

  it("⚠ a prefetch that fails leaves NO trace — the reader did not ask for it", async () => {
    const cache = useLocusDetailCacheStore();
    fetchLocus.mockResolvedValue(failure("network", "down"));
    await cache.prefetch("ecoli", "42", null);
    expect(cache.has(locusCacheKey("ecoli", "42", null))).toBe(false);
    // And the click that follows makes the request again and reports properly.
    expect(fetchLocus).toHaveBeenCalledTimes(1);
  });

  it("hovering twice does not fetch twice", async () => {
    const cache = useLocusDetailCacheStore();
    let release: (value: unknown) => void = () => {};
    fetchLocus.mockImplementation(async () => {
      await new Promise((resolve) => {
        release = resolve;
      });
      return success(locusDetail());
    });
    const first = cache.prefetch("ecoli", "42", null);
    const second = cache.prefetch("ecoli", "42", null);
    release(null);
    await Promise.all([first, second]);
    expect(fetchLocus).toHaveBeenCalledTimes(1);
  });
});

describe("⛔ the three loading states are never conflated", () => {
  it("with nothing on screen it is `pending`, so the track can draw its own shape", async () => {
    const navigation = useLocusNavigationStore();
    navigation.setSpecies("ecoli");
    let release: (value: unknown) => void = () => {};
    fetchLocus.mockImplementation(async () => {
      await new Promise((resolve) => {
        release = resolve;
      });
      return success(locusDetail());
    });
    const walking = navigation.navigateTo("1");
    expect(navigation.view.status).toBe("pending");
    release(null);
    await walking;
    expect(navigation.view.status).toBe("ready");
  });

  it("with a locus already drawn it is `refreshing`, and the PREVIOUS one stays on screen", async () => {
    const navigation = useLocusNavigationStore();
    navigation.setSpecies("ecoli");
    const first = locusDetail({ locus: { label: "1" } as LocusDetailResponse["locus"] });
    fetchLocus.mockResolvedValueOnce(success(first));
    await navigation.navigateTo("1");

    let release: (value: unknown) => void = () => {};
    fetchLocus.mockImplementation(async () => {
      await new Promise((resolve) => {
        release = resolve;
      });
      return success(locusDetail({ locus: { label: "2" } as LocusDetailResponse["locus"] }));
    });
    const walking = navigation.navigateTo("2");
    expect(navigation.view.status).toBe("refreshing");
    // ⭐ The reader keeps reading locus 1 while 2 loads.
    expect(navigation.drawable?.locus.label).toBe("1");
    release(null);
    await walking;
    expect(navigation.drawable?.locus.label).toBe("2");
  });

  it("⚠ and does not DIM for 150 ms, so a fast response never flashes", async () => {
    vi.useFakeTimers();
    const navigation = useLocusNavigationStore();
    navigation.setSpecies("ecoli");
    fetchLocus.mockResolvedValueOnce(success(locusDetail()));
    await navigation.navigateTo("1");

    let release: (value: unknown) => void = () => {};
    fetchLocus.mockImplementation(async () => {
      await new Promise((resolve) => {
        release = resolve;
      });
      return success(locusDetail());
    });
    const walking = navigation.navigateTo("2");
    expect(navigation.view).toMatchObject({ status: "refreshing", isDimmed: false });
    vi.advanceTimersByTime(DIM_AFTER_MS + 1);
    expect(navigation.view).toMatchObject({ status: "refreshing", isDimmed: true });
    release(null);
    await walking;
  });

  it("⭐ a CACHED locus goes straight to ready — no pending, no refreshing, no flash", async () => {
    const navigation = useLocusNavigationStore();
    navigation.setSpecies("ecoli");
    fetchLocus.mockResolvedValueOnce(success(locusDetail()));
    await navigation.navigateTo("1");
    fetchLocus.mockResolvedValueOnce(success(locusDetail()));
    await navigation.navigateTo("2");

    fetchLocus.mockClear();
    const seen: string[] = [];
    const walking = navigation.navigateTo("1");
    seen.push(navigation.view.status);
    await walking;
    seen.push(navigation.view.status);
    expect(seen).toEqual(["ready", "ready"]);
    expect(fetchLocus).not.toHaveBeenCalled();
  });

  it("⛔ a failure keeps the last good track on screen BESIDE the error, not instead of it", async () => {
    const navigation = useLocusNavigationStore();
    navigation.setSpecies("ecoli");
    fetchLocus.mockResolvedValueOnce(success(locusDetail()));
    await navigation.navigateTo("1");
    fetchLocus.mockResolvedValueOnce(failure("server", "boom", 500));
    await navigation.navigateTo("2");
    expect(navigation.view.status).toBe("failed");
    // Clearing to nothing would imply the catalogue is empty, which is a different and false claim.
    expect(navigation.drawable?.locus.label).toBe("1");
  });

  it("and a failure with nothing before it says so rather than showing an empty track", async () => {
    const navigation = useLocusNavigationStore();
    navigation.setSpecies("ecoli");
    fetchLocus.mockResolvedValueOnce(failure("not_found", "no locus '9'", 404));
    await navigation.navigateTo("9");
    expect(navigation.view).toMatchObject({ status: "failed", previous: null });
    expect(navigation.drawable).toBeNull();
  });
});

describe("navigation", () => {
  it("⭐ a superseded response changes NOTHING", async () => {
    const navigation = useLocusNavigationStore();
    navigation.setSpecies("ecoli");
    let releaseFirst: (value: unknown) => void = () => {};
    fetchLocus.mockImplementationOnce(async () => {
      await new Promise((resolve) => {
        releaseFirst = resolve;
      });
      return success(locusDetail({ locus: { label: "stale" } as LocusDetailResponse["locus"] }));
    });
    fetchLocus.mockImplementationOnce(async () =>
      success(locusDetail({ locus: { label: "fresh" } as LocusDetailResponse["locus"] })),
    );
    const first = navigation.navigateTo("1");
    const second = navigation.navigateTo("2");
    releaseFirst(null);
    await Promise.all([first, second]);
    expect(navigation.drawable?.locus.label).toBe("fresh");
    expect(navigation.route?.label).toBe("2");
  });

  it("⛔ setWalkDirection is ABSOLUTE and fetches nothing", async () => {
    const navigation = useLocusNavigationStore();
    navigation.setSpecies("ecoli");
    fetchLocus.mockResolvedValueOnce(success(locusDetail()));
    await navigation.navigateTo("1");
    fetchLocus.mockClear();

    navigation.setWalkDirection(REVERSED);
    expect(navigation.walkDirection).toBe(REVERSED);
    navigation.setWalkDirection(REVERSED);
    expect(navigation.walkDirection).toBe(REVERSED);
    navigation.setWalkDirection(FORWARD);
    expect(navigation.walkDirection).toBe(FORWARD);
    // The API response does not depend on direction, so flipping the frame is zero round trips.
    expect(fetchLocus).not.toHaveBeenCalled();
  });

  it("the store exposes no walk-direction toggle", () => {
    const navigation = useLocusNavigationStore();
    const names = Object.keys(navigation).filter((name) => /walk|flip|toggle/i.test(name));
    expect(names.sort()).toEqual(["setWalkDirection", "walkDirection"]);
  });

  it("the hash reflects the route, direction included", async () => {
    const navigation = useLocusNavigationStore();
    navigation.setSpecies("ecoli");
    fetchLocus.mockResolvedValue(success(locusDetail()));
    await navigation.navigateTo("42", REVERSED);
    expect(navigation.hash).toBe("#42r");
  });

  it("⛔ the trail RETREATS on Back rather than growing", async () => {
    const navigation = useLocusNavigationStore();
    navigation.setSpecies("ecoli");
    fetchLocus.mockResolvedValue(success(locusDetail()));
    await navigation.navigateTo("1");
    await navigation.navigateTo("2");
    await navigation.navigateTo("3");
    expect(navigation.trail).toEqual(["1", "2", "3"]);
    // Back fires hashchange, which lands in the same path a click does.
    await navigation.applyHash("#2", () => true);
    expect(navigation.trail).toEqual(["1", "2"]);
  });

  it("an unknown hash is refused rather than guessed at", async () => {
    const navigation = useLocusNavigationStore();
    navigation.setSpecies("ecoli");
    expect(await navigation.applyHash("#nope", () => false)).toBe(false);
    expect(navigation.route).toBeNull();
  });

  it("switching species drops the anchor, the trail and the cache together", async () => {
    const navigation = useLocusNavigationStore();
    const anchor = useAnchorGenomeStore();
    const cache = useLocusDetailCacheStore();
    navigation.setSpecies("ecoli");
    anchor.setAvailability(true);
    anchor.setAnchor("SAMEA1");
    fetchLocus.mockResolvedValue(success(locusDetail()));
    await navigation.navigateTo("1");
    expect(cache.size).toBe(1);

    navigation.setSpecies("kp");
    // The two BioSample sets are disjoint and the trail names loci that no longer exist.
    expect(anchor.sampleId).toBeNull();
    expect(navigation.trail).toEqual([]);
    expect(navigation.route).toBeNull();
    expect(cache.size).toBe(0);
  });
});

describe("the anchor", () => {
  it("is one ref that both boxes read — not two states kept in step", () => {
    const anchor = useAnchorGenomeStore();
    anchor.setAvailability(true);
    anchor.setAnchor("SAMEA1");
    expect(useAnchorGenomeStore().sampleId).toBe("SAMEA1");
    expect(anchor.isAnchored).toBe(true);
  });

  it("⚠ normalises an empty string to no-anchor, keeping the cache key stable", () => {
    const anchor = useAnchorGenomeStore();
    anchor.setAnchor("");
    expect(anchor.sampleId).toBeNull();
  });

  it("a catalogue that cannot offer an anchor clears the one that was set", () => {
    const anchor = useAnchorGenomeStore();
    anchor.setAvailability(true);
    anchor.setAnchor("SAMEA1");
    anchor.setAvailability(false);
    expect(anchor.sampleId).toBeNull();
    expect(anchor.isAvailable).toBe(false);
  });
});

describe("the track display", () => {
  async function walkTo(label: string, detail: LocusDetailResponse) {
    const navigation = useLocusNavigationStore();
    // ⚠ The response must carry the label it is a response FOR. The store keys its per-locus reset
    // on the DRAWN locus rather than on the route — see `trackDisplayStore` — so a fixture that
    // labelled every response "1" would silently test nothing.
    fetchLocus.mockResolvedValueOnce(
      success({ ...detail, locus: { ...detail.locus, label } }),
    );
    await navigation.navigateTo(label);
    await nextTick();
  }

  it("⭐ defaults to the arrangement the ANCHORED genome carries, even past the cap", async () => {
    const navigation = useLocusNavigationStore();
    navigation.setSpecies("ecoli");
    const track = useTrackDisplayStore();
    const listed = [
      arrangement({ rank: 0 }),
      arrangement({ rank: 1 }),
      arrangement({ rank: 37 }),
    ];
    await walkTo("1", locusDetail({
      arrangements: { listed, total: 60, arrangements_not_listed: 52, members_without_a_neighbourhood: 0 },
      anchor: { is_anchored: true, arrangement_ranks: [37] },
    }));
    expect(track.selectedArrangementIndex).toBe(2);
    expect(track.drawnArrangement?.rank).toBe(37);
    expect(track.drawnArrangementIsAnchored).toBe(true);
  });

  it("⛔ takes the LOWEST rank when rho > 1 puts the genome in two arrangements", async () => {
    const navigation = useLocusNavigationStore();
    navigation.setSpecies("ecoli");
    const track = useTrackDisplayStore();
    const listed = [arrangement({ rank: 0 }), arrangement({ rank: 2 }), arrangement({ rank: 5 })];
    await walkTo("1", locusDetail({
      arrangements: { listed, total: 6, arrangements_not_listed: 3, members_without_a_neighbourhood: 0 },
      anchor: { is_anchored: true, arrangement_ranks: [5, 2] },
    }));
    // The track can only draw one of them, so it draws the first.
    expect(track.drawnArrangement?.rank).toBe(2);
  });

  it("closes the popover on a new locus but NOT on a direction flip", async () => {
    const navigation = useLocusNavigationStore();
    navigation.setSpecies("ecoli");
    const track = useTrackDisplayStore();
    await walkTo("1", locusDetail());
    track.togglePopoverAt(asDisplaySlot(3));
    expect(track.openPopoverSlot).not.toBeNull();

    // ⚠ Flipping the frame is the SAME locus seen the other way round: it must not reset the
    // reader's arrangement choice or shut their popover.
    navigation.setWalkDirection(REVERSED);
    await nextTick();
    expect(track.openPopoverSlot).not.toBeNull();

    await walkTo("2", locusDetail());
    expect(track.openPopoverSlot).toBeNull();
  });

  it("⭐ walks in the direction of the arrow AS SHOWN, not as recorded", async () => {
    const navigation = useLocusNavigationStore();
    navigation.setSpecies("ecoli");
    const track = useTrackDisplayStore();
    // A flipped arrangement under a forward walk: the row is drawn mirrored, so a slot recorded
    // `same_strand: true` shows as against the focal gene and the next frame reverses.
    await walkTo("1", locusDetail({
      arrangements: {
        listed: [arrangement({ is_recorded_reverse_complement: true })],
        total: 1,
        arrangements_not_listed: 0,
        members_without_a_neighbourhood: 0,
      },
    }));
    // Display column 0 holds the slot recorded at 9, whose recorded relation is false → shown true.
    fetchLocus.mockResolvedValueOnce(success(locusDetail()));
    const direction = await track.walkTo(asDisplaySlot(0));
    expect(direction).toBe(FORWARD);
    expect(navigation.route?.label).toBe("J");
  });

  it("refuses to walk from a column with no occupant", async () => {
    const navigation = useLocusNavigationStore();
    navigation.setSpecies("ecoli");
    const track = useTrackDisplayStore();
    await walkTo("1", locusDetail({
      arrangements: {
        listed: [arrangement({ slots: slots(["A", null, "C", "D", "E", "F", "G", "H", "I", "J"]) })],
        total: 1,
        arrangements_not_listed: 0,
        members_without_a_neighbourhood: 0,
      },
    }));
    fetchLocus.mockClear();
    expect(await track.walkTo(asDisplaySlot(1))).toBeNull();
    // A contig end is an absence, and walking into one would assert an observation never made.
    expect(fetchLocus).not.toHaveBeenCalled();
  });

  it("selectArrangement ignores an index the response does not carry", async () => {
    const navigation = useLocusNavigationStore();
    navigation.setSpecies("ecoli");
    const track = useTrackDisplayStore();
    await walkTo("1", locusDetail());
    track.selectArrangement(9);
    // Clamping into a neighbour would draw a different arrangement than the one asked for.
    expect(track.selectedArrangementIndex).toBe(0);
  });
});
