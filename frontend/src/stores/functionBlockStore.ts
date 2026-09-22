/**
 * The Function tab's data — **fetched on tab open, not on every walk.**
 *
 * ⭐ That rule is the whole reason this is a second request rather than part of the locus response.
 * The hot path is a walk: forty steps, four hundred blocks drawn, and on most of them nobody opens
 * this tab. COG, GO, EC and KEGG lists are dead weight on every one of those steps, so they are not
 * in the response that pays for them.
 *
 * ⚠ **But a reader who leaves the tab open and walks must see the NEW locus's function**, not the
 * old one's and not a blank panel. So "open" is state here: the drawn locus changing clears the
 * block and, if the tab is still open, asks again. The pairing is exact because the clear is keyed
 * on the **drawn** locus — while a response is in flight the page is still showing the previous
 * locus, and the previous function block is the right one for it.
 *
 * ⚠ **No in-memory cache, deliberately.** Every response here is immutable for a build and carries
 * a year-long `Cache-Control`, so walking back to a locus re-reads the browser's own HTTP cache and
 * costs nothing. A second cache in front of that one would be a second thing that can go stale.
 */

import { defineStore, storeToRefs } from "pinia";
import { ref, watch } from "vue";

import { fetchLocusFunction } from "@/api/client";
import { LANES } from "@/api/request";
import type { Failure } from "@/api/result";
import type { FunctionResponse } from "@/api/types";

import { useLocusNavigationStore } from "./locusNavigationStore";

export type FunctionLoadStatus = "idle" | "pending" | "ready" | "failed";

export const useFunctionBlockStore = defineStore("functionBlock", () => {
  const navigation = useLocusNavigationStore();
  const { drawable, speciesKey } = storeToRefs(navigation);

  const block = ref<FunctionResponse | null>(null);
  const status = ref<FunctionLoadStatus>("idle");
  const lastFailure = ref<Failure | null>(null);
  /** Whether the reader has this tab open. Survives a walk; that is the point of it. */
  const isOpen = ref(false);

  /**
   * ⛔ Keyed on the DRAWN locus, not the route — the same rule as every other per-locus store here.
   * The route changes the instant the reader clicks, so a route watcher would blank the panel under
   * a locus that is still on screen. And flipping the walk direction is the same locus seen the
   * other way round: it must not throw the block away or re-request it.
   */
  watch(
    () => drawable.value?.locus.label ?? null,
    (label, previousLabel) => {
      if (label === previousLabel) return;
      discard();
      if (isOpen.value) void load();
    },
  );

  function discard(): void {
    // ⚠ Cancel first: a request in flight belongs to the locus that is going away, and the lane is
    // what makes its response arrive as `superseded` rather than as another locus's function.
    LANES.function.cancel();
    block.value = null;
    status.value = "idle";
    lastFailure.value = null;
  }

  /**
   * ⛔ **Absolute, never a toggle** — the same rule as the walk direction. A
   * toggle called from two places (a tab click and a keyboard shortcut) lands back where it started
   * while both call sites believe it moved.
   */
  function setOpen(open: boolean): void {
    isOpen.value = open;
    if (open && status.value === "idle") void load();
  }

  /**
   * Fetch this locus's function block.
   *
   * ⛔ `superseded` means change NOTHING — not an error, not an empty panel. ⛔ And a failure
   * renders AS a failure: *"a panel that fails silently is one a reader will read as 'this locus has
   * no function annotation', which is a different claim and a false one"* (`app.js:4604`). An empty
   * COG list and an unanswered request must never look alike.
   */
  async function load(): Promise<void> {
    const species = speciesKey.value;
    const label = drawable.value?.locus.label ?? null;
    if (species === null || label === null || status.value === "pending") return;

    status.value = "pending";
    lastFailure.value = null;
    const outcome = await LANES.function.run((signal) =>
      fetchLocusFunction(species, label, signal),
    );
    if (outcome.superseded) return;
    // ⚠ A backstop against microtask ordering, not a tested path — the lane's cancel in `discard`
    // is what actually carries this. Kept because correctness should not depend on whether Vue's
    // watcher flush or this continuation runs first.
    if ((drawable.value?.locus.label ?? null) !== label) return;

    if (!outcome.result.ok) {
      lastFailure.value = outcome.result;
      status.value = "failed";
      return;
    }
    block.value = outcome.result.value;
    status.value = "ready";
  }

  return { block, status, lastFailure, isOpen, setOpen, load, discard };
});
