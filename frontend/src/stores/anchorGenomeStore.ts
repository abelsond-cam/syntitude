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

/**
 * ⛔ **Which RELATION this genome has to the catalogue, and it is not decoration.** A `catalogue`
 * genome is one of the modelled hundred: its genes are in the model, and it is COUNTED in the
 * arrangements it occupies. A `projected` genome was never clustered: its genes were placed on the
 * loci of their nearest modelled genes afterwards, and it MATCHES an arrangement without being
 * counted in one. The two are fetched by different query parameters, cached under different keys,
 * and described by different sentences — and a page that lost the distinction would tell a reader
 * their genome is part of a model it is not part of.
 */
export type AnchorKind = "catalogue" | "projected";

export const useAnchorGenomeStore = defineStore("anchorGenome", () => {
  /** The anchored genome's `sample_id`, or `null` for none. */
  const sampleId = ref<string | null>(null);
  /** ⚠ Meaningless while `sampleId` is null, and never read then. */
  const kind = ref<AnchorKind>("catalogue");
  /** Whether this catalogue can offer an anchor at all — false removes the control. */
  const isAvailable = ref(false);

  const isAnchored = computed(() => sampleId.value !== null);
  const isProjected = computed(() => sampleId.value !== null && kind.value === "projected");

  /** Absolute, like every other setter here: say what it becomes.
   *
   * ⛔ **Setting either kind releases the other**, because there is one anchor. That is the whole
   * reason both live in this store rather than one each: two independent refs would let a reader
   * anchor a modelled genome and one of their own at the same time, and the track can only draw one.
   */
  function setAnchor(nextSampleId: string | null, nextKind: AnchorKind = "catalogue"): void {
    // ⚠ `""` from a cleared input is "no anchor", not a genome named the empty string. Normalising
    // here is what keeps the cache key stable — see `locusCacheKey`.
    sampleId.value = nextSampleId ? nextSampleId : null;
    kind.value = nextSampleId ? nextKind : "catalogue";
  }

  /** The projected half of the same one anchor. */
  function setProjectedAnchor(nextSampleId: string | null): void {
    setAnchor(nextSampleId, "projected");
  }

  function clearAnchor(): void {
    sampleId.value = null;
    kind.value = "catalogue";
  }

  /** Called when a catalogue loads: does it carry the membership an anchor needs?
   *
   * ⚠ Only a CATALOGUE anchor depends on that membership. A projected genome is anchored through
   * its own table, so an unavailable catalogue anchor must not silently drop one.
   */
  function setAvailability(available: boolean): void {
    isAvailable.value = available;
    if (!available && kind.value === "catalogue") sampleId.value = null;
  }

  return {
    sampleId,
    kind,
    isAvailable,
    isAnchored,
    isProjected,
    setAnchor,
    setProjectedAnchor,
    clearAnchor,
    setAvailability,
  };
});
