/**
 * What the track is showing right now: which arrangement is drawn, and which position's popover is
 * open. **Both reset on a new locus**, and neither fetches anything.
 *
 * ⭐ Every action here is zero round trips. Switching arrangement, flipping the frame, opening and
 * closing a popover are all answered out of the locus response already in hand — which is the whole
 * reason that response carries all ten offset slots, the drawn arrangements, the gaps and the map
 * geometry together.
 */

import { defineStore, storeToRefs } from "pinia";
import { computed, ref, watch } from "vue";

import type { Arrangement, LocusDetailResponse } from "@/api/types";
import {
  type DisplayMirror,
  type DisplaySlot,
  type NeighbourSlot,
  type ObservedSlot,
  SIGNED_OFFSETS,
  displayMirrorApplied,
  displaySlots,
  labelSlotFor,
  marginalDisplayMirror,
  observedSlotFor,
  signedOffsetForLabelSlot,
  slotsInDisplayOrder,
  strandRelationAsShown,
} from "@/lib/slotSpaces";
import { type WalkDirection, walkDirectionAfterStep } from "@/lib/walkDirection";

import { useAnchorGenomeStore } from "./anchorGenomeStore";
import { useLocusDetailCacheStore } from "./locusDetailCacheStore";
import { useLocusNavigationStore } from "./locusNavigationStore";

export const useTrackDisplayStore = defineStore("trackDisplay", () => {
  const navigation = useLocusNavigationStore();
  const cache = useLocusDetailCacheStore();
  const { sampleId: anchorSampleId } = storeToRefs(useAnchorGenomeStore());
  const { drawable, walkDirection } = storeToRefs(navigation);

  /**
   * Which of `arrangements.listed` is drawn — an INDEX into that array, not a rank. The two differ
   * the moment an anchored arrangement past the cap is spliced in.
   */
  const selectedArrangementIndex = ref(0);

  /**
   * The position whose popover is open, in the OBSERVED space, or `null` for none.
   *
   * ⚠ A new locus opens with none. The old page's panel lived in a fixed column and could sensibly
   * default to A−1; a popover that opened by itself on every step would sit over the track the
   * reader is trying to read.
   */
  const openPopoverSlot = ref<ObservedSlot | null>(null);

  /**
   * Whether the FOCAL bar's popover is open. Separate state from {@link openPopoverSlot}, because
   * they hold different things: the offset popover names a position in the ±5 window, and the focal
   * one lists the locus's own arrangements. Encoding "focal" as a slot value would need an eleventh
   * member of a ten-element space, which is exactly the kind of overloading this codebase keeps
   * paying for.
   */
  const isFocalPopoverOpen = ref(false);

  /**
   * ⭐ A newly DRAWN locus takes its own default arrangement, and closes the popover. Anchored that
   * means whichever arrangement THIS genome carries here, so the anchor is a default per locus and
   * a manual pick still wins until the reader walks on.
   *
   * ⛔ Keyed on the label of what is **drawable**, not on the route. The route changes the instant
   * the reader clicks, before any response has arrived — so watching it computed the default from
   * the PREVIOUS locus's arrangements and then never corrected itself, silently drawing rank 1 at
   * every anchored locus. Keying on the drawn locus also gives the right behaviour while
   * `refreshing`: the previous track stays up with its own arrangement until the new one lands.
   *
   * ⚠ And it must not be the route for a second reason: flipping the walk direction is the same
   * locus seen the other way round, and must not reset the reader's arrangement choice or shut
   * their popover.
   */
  watch(
    () => drawable.value?.locus.label ?? null,
    (label, previousLabel) => {
      if (label === previousLabel) return;
      selectedArrangementIndex.value = defaultArrangementIndex(drawable.value);
      openPopoverSlot.value = null;
      isFocalPopoverOpen.value = false;
    },
  );

  /**
   * The anchored genome's arrangement if it carries one, else rank 1.
   *
   * ⛔ Takes the FIRST of the anchor's ranks. A genome at rho > 1 sits in two arrangements at one
   * locus and the track can only draw one of them — the same rule as the published page's bisect,
   * which returns the lowest rank for exactly this reason.
   */
  function defaultArrangementIndex(detail: LocusDetailResponse | null): number {
    if (detail === null) return 0;
    const ranks = detail.anchor.arrangement_ranks;
    if (ranks.length === 0) return 0;
    const wanted = Math.min(...ranks);
    const index = detail.arrangements.listed.findIndex(
      (arrangement) => arrangement.rank === wanted,
    );
    return index >= 0 ? index : 0;
  }

  /** The arrangement actually drawn, or `null` where the locus has no recorded neighbourhood. */
  const drawnArrangement = computed<Arrangement | null>(() => {
    const listed = drawable.value?.arrangements.listed ?? [];
    return listed[selectedArrangementIndex.value] ?? listed[0] ?? null;
  });

  /**
   * ⭐ The mirroring applied to draw the current row — the arrangement's own recorded
   * reverse-complement composed with the reader's walk direction, and the two CANCEL.
   *
   * With no arrangement drawn only the walk contributes, which is the marginal fallback.
   */
  const displayMirror = computed<DisplayMirror>(() => {
    const arrangement = drawnArrangement.value;
    return arrangement === null
      ? marginalDisplayMirror(walkDirection.value)
      : displayMirrorApplied(arrangement.is_recorded_reverse_complement, walkDirection.value);
  });

  /** The ten slots in the order the reader sees them, strand bits already mirrored. */
  const slotsShown = computed<readonly NeighbourSlot[] | null>(() => {
    const arrangement = drawnArrangement.value;
    return arrangement === null
      ? null
      : slotsInDisplayOrder(arrangement.slots, displayMirror.value);
  });

  /**
   * ⭐ The ten slots the track actually draws, **in display order, whichever view is available.**
   *
   * With an arrangement drawn these are its own slots, mirrored. Without one — a locus whose members
   * have no recorded neighbourhood at all — the track falls back to the MARGINAL mode at each
   * position, which is raw and needs mirroring here.
   *
   * ⛔ The fallback is a synthesis and is marked as one: `signed_offset` is the recorded offset of
   * the position it came from, and a position with nothing observed stays absent rather than being
   * filled with the previous locus. A component must never have to ask which view it is looking at
   * to know what a slot means.
   */
  const slotsForDisplay = computed<readonly NeighbourSlot[]>(() => {
    const fromArrangement = slotsShown.value;
    if (fromArrangement !== null) return fromArrangement;
    const detail = drawable.value;
    return displaySlots().map((display) => {
      const observed = observedSlotFor(display, displayMirror.value);
      const marginal = detail?.offsets[observed];
      const top = marginal?.occupants[0];
      const signedOffset = marginal?.signed_offset ?? SIGNED_OFFSETS[observed] ?? 0;
      if (marginal === undefined || top === undefined || marginal.observed_member_count === 0) {
        return {
          signed_offset: signedOffset,
          locus: null,
          absence_reason: "contig_end" as const,
          same_strand: null,
        };
      }
      const recorded = top.same_strand_gene_count * 2 >= top.gene_count;
      return {
        signed_offset: signedOffset,
        locus: top.locus,
        absence_reason: top.locus === null ? ("outside_catalogue" as const) : null,
        same_strand: top.locus === null ? null : strandRelationAsShown(recorded, displayMirror.value),
      };
    });
  });

  /**
   * The two offsets an open offset-popover needs: the one its heading names, and the one its counts
   * were recorded at.
   *
   * ⛔ `openPopoverSlot` is an OBSERVED slot, because the marginal lives in observed space. The
   * heading must name the column the reader **clicked**, which on a mirrored row is a different
   * offset — otherwise the panel reads "A−1" beside a block labelled "A+1" and the two look like
   * different data. `observedSlotFor` is an involution, so it maps back to the display column.
   */
  const openPopoverHeading = computed(() => {
    const observed = openPopoverSlot.value;
    if (observed === null) return null;
    const display = observedSlotFor(
      observed as unknown as DisplaySlot,
      displayMirror.value,
    ) as unknown as DisplaySlot;
    return {
      labelledOffset: signedOffsetForLabelSlot(labelSlotFor(display, walkDirection.value)),
      recordedOffset: SIGNED_OFFSETS[observed] ?? 0,
    };
  });

  /** The marginal for the position whose popover is open. */
  const openPopoverMarginal = computed(() => {
    const observed = openPopoverSlot.value;
    if (observed === null) return null;
    return drawable.value?.offsets[observed] ?? null;
  });

  /** The locus drawn in the block above the open popover, so its row can be marked. */
  const openPopoverDrawnLocus = computed(() => {
    const observed = openPopoverSlot.value;
    if (observed === null) return null;
    const display = observedSlotFor(
      observed as unknown as DisplaySlot,
      displayMirror.value,
    ) as unknown as DisplaySlot;
    return slotsForDisplay.value[display]?.locus ?? null;
  });

  /** Whether the anchored genome carries the arrangement currently drawn. */
  const drawnArrangementIsAnchored = computed(() => {
    const arrangement = drawnArrangement.value;
    const detail = drawable.value;
    if (arrangement === null || detail === null || !detail.anchor.is_anchored) return false;
    return detail.anchor.arrangement_ranks.includes(arrangement.rank);
  });

  /** Absolute. Ignores an index the response does not carry rather than clamping into a neighbour. */
  function selectArrangement(index: number): void {
    const listed = drawable.value?.arrangements.listed ?? [];
    if (index < 0 || index >= listed.length) return;
    selectedArrangementIndex.value = index;
    // ⚠ The popover names a position on the row that is going away, so it closes with it.
    openPopoverSlot.value = null;
  }

  /** Open the popover for a display column, or close it if that column is already open. */
  function togglePopoverAt(display: DisplaySlot): void {
    const observed = observedSlotFor(display, displayMirror.value);
    openPopoverSlot.value = openPopoverSlot.value === observed ? null : observed;
    if (openPopoverSlot.value !== null) isFocalPopoverOpen.value = false;
  }

  function closePopover(): void {
    openPopoverSlot.value = null;
    isFocalPopoverOpen.value = false;
  }

  /**
   * Walk to the locus in a display column.
   *
   * ⛔ The direction is computed from the strand relation **as shown** — already mirrored by
   * `slotsInDisplayOrder` — and handed to `walkDirectionAfterStep`, which is absolute. Passing the
   * recorded relation instead, or composing with the current direction, is the two-mirrorings bug.
   *
   * Returns the direction it walked in, or `null` if that column has no occupant to walk to.
   */
  async function walkTo(display: DisplaySlot): Promise<WalkDirection | null> {
    const shown = slotsForDisplay.value;
    const slot = shown[display];
    if (slot === undefined || slot.locus === null || slot.same_strand === null) return null;
    const direction = walkDirectionAfterStep(slot.same_strand);
    await navigation.navigateTo(slot.locus, direction);
    return direction;
  }

  /**
   * The strand relation a reader sees at a display column, for drawing the arrow.
   *
   * ⚠ Anything that draws an arrow must come through here or through `slotsShown`. The published
   * page's marginal list and its no-arrangement fallback both used the raw recorded value and
   * pointed the wrong way under a reversed walk.
   */
  function shownStrandAt(display: DisplaySlot): boolean | null {
    const shown = slotsShown.value;
    if (shown !== null) return shown[display]?.same_strand ?? null;
    // The marginal fallback: no arrangement, so the recorded mode is raw and needs mirroring here.
    const observed = observedSlotFor(display, displayMirror.value);
    const marginal = drawable.value?.offsets[observed];
    const top = marginal?.occupants[0];
    if (top === undefined || marginal === undefined || marginal.observed_member_count === 0) {
      return null;
    }
    const recorded = top.same_strand_gene_count * 2 >= top.gene_count;
    return strandRelationAsShown(recorded, displayMirror.value);
  }

  /**
   * Warm the cache for a locus the reader is hovering. Runs on no lane and reports nothing — a
   * prefetch the reader did not ask for must leave no trace when it fails.
   */
  function prefetchNeighbour(speciesKey: string, locusLabel: string): void {
    void cache.prefetch(speciesKey, locusLabel, anchorSampleId.value);
  }

  function toggleFocalPopover(): void {
    isFocalPopoverOpen.value = !isFocalPopoverOpen.value;
    // ⚠ The two popovers are mutually exclusive on screen, so opening one closes the other rather
    // than leaving a stale panel pointing at a position the reader has stopped asking about.
    if (isFocalPopoverOpen.value) openPopoverSlot.value = null;
  }

  return {
    selectedArrangementIndex,
    openPopoverSlot,
    openPopoverHeading,
    openPopoverMarginal,
    openPopoverDrawnLocus,
    isFocalPopoverOpen,
    slotsForDisplay,
    prefetchNeighbour,
    toggleFocalPopover,
    drawnArrangement,
    drawnArrangementIsAnchored,
    displayMirror,
    slotsShown,
    selectArrangement,
    togglePopoverAt,
    closePopover,
    walkTo,
    shownStrandAt,
    defaultArrangementIndex,
  };
});
