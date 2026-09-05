/**
 * The full arrangement list behind the A0 card — the one place where the accounting for *"which
 * neighbourhood does each member gene sit in"* closes.
 *
 * ⛔ **This is the only store that fetches on a reader's behalf outside navigation**, and that is
 * deliberate rather than incidental: `trackDisplayStore` states that every action it offers is zero
 * round trips, and putting a fetch there would falsify its own header. The argument for the lane is
 * in `api/request.ts` beside `LANES`.
 *
 * ⚠ **The published page had every arrangement resident**, so its card could say *"every one of
 * them listed below"*. At 100 genomes that sentence was true. `arr.tot` rises to 10.3 arrangements
 * per locus at 80,000 genomes and a hypervariable accessory locus runs to thousands, so the card
 * now lists what it has, names the total, and offers the rest — and its wording says so. Claiming
 * completeness the list does not have is the failure this whole rebuild is against.
 */

import { defineStore, storeToRefs } from "pinia";
import { computed, ref, watch } from "vue";

import { fetchArrangementPage } from "@/api/client";
import { LANES } from "@/api/request";
import type { Failure } from "@/api/result";
import type { Arrangement } from "@/api/types";

import { useLocusNavigationStore } from "./locusNavigationStore";

/** Whether more of the list is on its way, and what happened last time we asked. */
export type ArrangementLoadStatus = "idle" | "pending" | "ready" | "failed";

/**
 * ⛔ Merge two rank-ordered sets, keeping one row per rank.
 *
 * The fetched pages are a contiguous prefix by rank; `arrangements.listed` is the top few **plus
 * whichever the anchored genome carries**, which may be rank 60 out of 200. Replacing the list with
 * the prefix would make the reader's own arrangement vanish from the card the moment they asked to
 * see more of it — the exact complaint the display cap's rule exists to answer.
 */
export function mergeArrangementsByRank(
  ...sets: readonly (readonly Arrangement[])[]
): readonly Arrangement[] {
  const byRank = new Map<number, Arrangement>();
  for (const set of sets) for (const arrangement of set) byRank.set(arrangement.rank, arrangement);
  return [...byRank.values()].sort((left, right) => left.rank - right.rank);
}

export const useArrangementBrowserStore = defineStore("arrangementBrowser", () => {
  const navigation = useLocusNavigationStore();
  const { drawable, speciesKey } = storeToRefs(navigation);

  /** The contiguous prefix fetched so far, in rank order. Empty until the reader asks. */
  const fetched = ref<readonly Arrangement[]>([]);
  const status = ref<ArrangementLoadStatus>("idle");
  const lastFailure = ref<Failure | null>(null);

  /**
   * ⛔ Reset on the DRAWN locus, not on the route — the same rule as `trackDisplayStore`, and for
   * the same reason: the route changes the instant the reader clicks, so a route watcher would
   * clear the list while the previous locus is still on screen. Flipping the walk direction is the
   * same locus seen the other way round and must not throw the list away either.
   */
  watch(
    () => drawable.value?.locus.label ?? null,
    (label, previousLabel) => {
      if (label === previousLabel) return;
      reset();
    },
  );

  function reset(): void {
    // ⚠ Cancel first. A page still in flight belongs to the locus that is going away, and the lane
    // is what makes its response arrive as `superseded` rather than as rows appended to the wrong
    // list.
    LANES.arrangements.cancel();
    fetched.value = [];
    status.value = "idle";
    lastFailure.value = null;
  }

  /**
   * What the card lists: everything fetched, plus the capped set the locus response already
   * carried, one row per rank.
   */
  const rows = computed<readonly Arrangement[]>(() =>
    mergeArrangementsByRank(drawable.value?.arrangements.listed ?? [], fetched.value),
  );

  /** ⛔ Never moved by any cap, and read from the response rather than counted off the list. */
  const total = computed(() => drawable.value?.arrangements.total ?? 0);

  /**
   * How many arrangements this locus has that the card is **not** showing.
   *
   * ⚠ Computed against what is on screen, so it stays true as pages arrive — and it is a count of
   * *arrangements*. The count of member *genes* inside them is a different remainder and is the
   * card's own business; conflating the two is the bug of `c1cb12b`.
   */
  const arrangementsNotShown = computed(() => Math.max(0, total.value - rows.value.length));

  const hasMore = computed(() => arrangementsNotShown.value > 0);

  /**
   * Fetch the next page.
   *
   * ⛔ **`superseded` means change NOTHING** — not an error, not an empty list. A reader who walks
   * on abandons a page they never see, and the lane's cancel in {@link reset} is what makes that
   * response arrive here as a supersession rather than as rows appended to the wrong locus. That
   * cancel is the guard that actually carries it: measured by mutation, removing the label re-check
   * below fails no test, because the reset watcher has always run by the time a page resolves.
   *
   * ⚠ The label re-check is kept anyway, and named for what it is — a backstop against microtask
   * ordering, not a tested path. Whether Vue's watcher flush or this promise's continuation runs
   * first is a function of how many hops the fetch chain has, and correctness should not be. It is
   * cheap; it is simply not the reason the behaviour holds.
   *
   * The failure branch renders as a failure, never as "this locus has no more arrangements".
   */
  async function loadMore(): Promise<void> {
    const species = speciesKey.value;
    const label = drawable.value?.locus.label ?? null;
    if (species === null || label === null || !hasMore.value || status.value === "pending") return;

    status.value = "pending";
    lastFailure.value = null;
    // ⚠ The offset is the FETCHED prefix length, never `rows.length` — an anchored row spliced in
    // past the cut would otherwise skip a page's worth of arrangements that were never fetched.
    const offset = fetched.value.length;
    const outcome = await LANES.arrangements.run((signal) =>
      fetchArrangementPage(species, label, offset, signal),
    );
    if (outcome.superseded) return;
    if ((drawable.value?.locus.label ?? null) !== label) return;

    if (!outcome.result.ok) {
      lastFailure.value = outcome.result;
      status.value = "failed";
      return;
    }
    // ⚠ Trust the offset we asked for over the length we hold: a duplicated page would otherwise
    // append rows already present and inflate the list past `total`.
    fetched.value =
      outcome.result.value.offset === fetched.value.length
        ? [...fetched.value, ...outcome.result.value.arrangements]
        : fetched.value;
    status.value = "ready";
  }

  return {
    fetched,
    status,
    lastFailure,
    rows,
    total,
    arrangementsNotShown,
    hasMore,
    loadMore,
    reset,
  };
});
