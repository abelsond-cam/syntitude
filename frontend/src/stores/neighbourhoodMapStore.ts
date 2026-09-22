/**
 * What the neighbourhood map is showing: which representation.
 *
 * ⭐ **It survives a walk, and that is the point of it being here.** Which arrangement is drawn and
 * which popover is open are properties of *this locus* and reset on every step
 * (`trackDisplayStore`); which space the reader is looking at is a property of *the reader*, and
 * resetting it on every step would undo their choice forty times in a forty-step walk.
 *
 * ⚠ It fetches nothing. The six-point geometry rides in the locus response, so switching is zero
 * round trips — like every other control on this page.
 *
 * (There was a second setting, the zoom: this locus's own fit, or the whole-catalogue UMAP. The
 * catalogue picture was removed on 2026-09-22 — David: *"It isn't helpful."* — and the zoom with it.)
 */

import { defineStore } from "pinia";
import { ref } from "vue";

import type { Representation } from "@/api/types";

export const useNeighbourhoodMapStore = defineStore("neighbourhoodMap", () => {
  /**
   * ⚠ Bacformer first, matching the published page's own tab order — the two representations pick
   * **different loci** (their separations agree at only ρ ≈ 0.47), so the default is a real choice
   * about which question the map opens on: context, not sequence.
   */
  const representation = ref<Representation>("bacformer");

  function selectRepresentation(next: Representation): void {
    representation.value = next;
  }

  return { representation, selectRepresentation };
});
