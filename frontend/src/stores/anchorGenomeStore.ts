/**
 * The anchor: one named genome, drawn instead of the commonest arrangement.
 *
 * ⭐ **Session state, deliberately not in the URL.** The hash already carries a trailing `r` for
 * walk direction, and putting the anchor there too would make every anchor change a history entry
 * (`app.js:195-200`). Switching species is a full navigation to a different catalogue, so the
 * anchor drops with it — which is right, because the two BioSample sets are disjoint.
 *
 * ⭐ **One assignment, not a walk over mounted boxes.** `app.js:3950`'s `setAnchor` walks `ANCHORS`
 * writing through every box that is mounted, because *"the boxes are two views of one state, not
 * two states that are kept in step"*. Here that sentence is the implementation: there is one ref,
 * both boxes read it, and there is nothing to keep in step.
 *
 * ⚠ `null` is "no anchor", and the page must be able to hold it with the control absent altogether:
 * a catalogue with no membership offers no anchor box rather than one that could only ever answer
 * "not found".
 */

import { defineStore } from "pinia";
import { computed, ref } from "vue";

export const useAnchorGenomeStore = defineStore("anchorGenome", () => {
  /** The anchored genome's `sample_id`, or `null` for none. */
  const sampleId = ref<string | null>(null);
  /** Whether this catalogue can offer an anchor at all — false removes the control. */
  const isAvailable = ref(false);

  const isAnchored = computed(() => sampleId.value !== null);

  /** Absolute, like every other setter here: say what it becomes. */
  function setAnchor(nextSampleId: string | null): void {
    // ⚠ `""` from a cleared input is "no anchor", not a genome named the empty string. Normalising
    // here is what keeps the cache key stable — see `locusCacheKey`.
    sampleId.value = nextSampleId ? nextSampleId : null;
  }

  function clearAnchor(): void {
    sampleId.value = null;
  }

  /** Called when a catalogue loads: does it carry the membership an anchor needs? */
  function setAvailability(available: boolean): void {
    isAvailable.value = available;
    if (!available) sampleId.value = null;
  }

  return { sampleId, isAvailable, isAnchored, setAnchor, clearAnchor, setAvailability };
});
