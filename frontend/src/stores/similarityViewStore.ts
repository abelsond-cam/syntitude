/**
 * Which of the similarity card's three views the reader is looking at.
 *
 * ⭐ **It survives a walk, and that is the point of it being here.** Which arrangement is drawn and
 * which popover is open are properties of *this locus* and reset on every step
 * (`trackDisplayStore`); which question the reader is asking of the embedding is a property of *the
 * reader*, and resetting it on every step would undo their choice forty times in a forty-step walk.
 *
 * ⛔ **Never in the URL.** A locus address is what a reader shares and what the trail replays; a
 * per-reader display preference riding in it would make two links to the same locus compare unequal
 * and would pin one reader's choice onto everyone they send it to.
 *
 * ⚠ It fetches nothing. Both representations and all three views ride in the locus response, so
 * switching is zero round trips — like every other control on this page.
 *
 * (It replaces `neighbourhoodMapStore`, which held which representation the map drew. The two
 * representations are no longer a choice: they are STACKED inside whichever view is showing,
 * because they disagree about which loci are weak — of the 1,059 ecoli loci Bacformer flags, ESM
 * rescues 817 — and a tab would hide exactly that disagreement behind a click.)
 */

import { defineStore } from "pinia";
import { ref } from "vue";

import type { SimilarityViewId } from "@/lib/similarityViews";

export const useSimilarityViewStore = defineStore("similarityView", () => {
  /**
   * ⚠ The median pair, matching the card's own default: it is the reading over whole sets, and the
   * other two are secondary questions about the same locus.
   */
  const view = ref<SimilarityViewId>("median");

  function selectView(next: SimilarityViewId): void {
    view.value = next;
  }

  return { view, selectView };
});
