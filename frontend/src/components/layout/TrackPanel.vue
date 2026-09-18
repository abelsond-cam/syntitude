<script setup lang="ts">
/**
 * The structural locus browser: the breadcrumb, the track, its two popovers, and the arrangement
 * switcher anchored under the focal gene.
 *
 * ⛔ **Three loading states, drawn three ways** (`locusNavigationStore`): `pending` has nothing to
 * show and draws a placeholder in the track's own place, so the page does not jump; `refreshing`
 * keeps the previous track up and dims it only after 150 ms; `failed` says so in words BESIDE the
 * last good track, never by clearing it — an empty track and an unanswered request must never look
 * alike.
 *
 * ⚠ **A popover that outlives what it points at is worse than no popover** (`app.js::placePop`). It
 * is measured from the live position of the bar that opened it, on open, on every track scroll and on
 * resize — the track scrolls sideways under a panel that does not — and it closes on Escape and on
 * any click outside it.
 */
import { storeToRefs } from "pinia";
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from "vue";

import type { NeighbourDisplayRow } from "@/api/types";
import AnchorGenomeBox from "@/components/anchor/AnchorGenomeBox.vue";
import LocusTrail from "@/components/navigation/LocusTrail.vue";
import ArrangementPopover from "@/components/popover/ArrangementPopover.vue";
import OffsetPopover from "@/components/popover/OffsetPopover.vue";
import ArrangementSwitcher from "@/components/track/ArrangementSwitcher.vue";
import BandKey from "@/components/track/BandKey.vue";
import GeneTrack from "@/components/track/GeneTrack.vue";
import { placePopover } from "@/lib/popoverPlacement";
import type { WalkDirection } from "@/lib/walkDirection";
import { useAnchorGenomeStore } from "@/stores/anchorGenomeStore";
import { useArrangementBrowserStore } from "@/stores/arrangementBrowserStore";
import { useLocusNavigationStore } from "@/stores/locusNavigationStore";
import { useTrackDisplayStore } from "@/stores/trackDisplayStore";

const props = defineProps<{
  speciesKey: string | null;
  collectionGenomeCount: number;
}>();

const navigation = useLocusNavigationStore();
const track = useTrackDisplayStore();
const browser = useArrangementBrowserStore();
const { sampleId: anchorSampleId } = storeToRefs(useAnchorGenomeStore());
const { view, drawable, trail, displayNames, walkDirection } = storeToRefs(navigation);
const {
  selectedArrangementIndex,
  drawnArrangement,
  displayMirror,
  openPopoverSlot,
  openPopoverHeading,
  openPopoverMarginal,
  openPopoverDrawnLocus,
  isFocalPopoverOpen,
} = storeToRefs(track);

const isDimmed = computed(() => view.value.status === "refreshing" && view.value.isDimmed);
const failure = computed(() => (view.value.status === "failed" ? view.value.failure : null));

const neighboursByLabel = computed(() => {
  const index = new Map<string, NeighbourDisplayRow>();
  for (const row of drawable.value?.neighbour_display_rows ?? []) index.set(row.label, row);
  return index;
});

// ── the popover: placed from the live bar, dismissed from outside ─────────────────────────────
const popover = ref<HTMLDivElement | null>(null);
const frame = ref<HTMLDivElement | null>(null);
const popoverStyle = ref<Record<string, string>>({});
const isPopoverOpen = computed(() => openPopoverSlot.value !== null || isFocalPopoverOpen.value);

function placeOpenPopover(): void {
  const element = popover.value;
  const host = element?.offsetParent as HTMLElement | null | undefined;
  if (!element || !host || !isPopoverOpen.value) return;
  const anchor =
    frame.value?.querySelector(".slot.sel .marg-hit") ?? frame.value?.querySelector(".slot.sel .block");
  if (!anchor) {
    track.closePopover();
    return;
  }
  const position = placePopover(
    anchor.getBoundingClientRect(),
    { ...host.getBoundingClientRect().toJSON(), clientWidth: host.clientWidth },
    element.offsetWidth,
  );
  popoverStyle.value = { left: `${position.leftPx}px`, top: `${position.topPx}px` };
}

watch([openPopoverSlot, isFocalPopoverOpen, drawable], async () => {
  await nextTick();
  placeOpenPopover();
});

function onDocumentClick(event: MouseEvent): void {
  if (!isPopoverOpen.value) return;
  if (popover.value?.contains(event.target as Node)) return;
  track.closePopover();
}

function onDocumentKeydown(event: KeyboardEvent): void {
  if (event.key === "Escape" && isPopoverOpen.value) track.closePopover();
}

let scroller: Element | null = null;
onMounted(() => {
  document.addEventListener("click", onDocumentClick);
  document.addEventListener("keydown", onDocumentKeydown);
  window.addEventListener("resize", placeOpenPopover);
});
// The scroller is rendered by `GeneTrack` and replaced when the track first appears, so it is found
// after each draw rather than once.
watch(
  drawable,
  async () => {
    await nextTick();
    const next = frame.value?.querySelector(".track-scroll") ?? null;
    if (next === scroller) return;
    scroller?.removeEventListener("scroll", placeOpenPopover);
    scroller = next;
    scroller?.addEventListener("scroll", placeOpenPopover);
  },
  { immediate: true },
);
onBeforeUnmount(() => {
  document.removeEventListener("click", onDocumentClick);
  document.removeEventListener("keydown", onDocumentKeydown);
  window.removeEventListener("resize", placeOpenPopover);
  scroller?.removeEventListener("scroll", placeOpenPopover);
});

function walk(locus: string, direction: WalkDirection): void {
  track.closePopover();
  void navigation.navigateTo(locus, direction);
}

function jump(locus: string): void {
  void navigation.navigateTo(locus);
}
</script>

<template>
  <section class="track-panel">
    <div class="wrap">
      <!-- Heading and breadcrumb share ONE row (David, 2026-08-25): stacked they spent two lines on
           ~20 px of text. `.trail:not(:empty)` draws the divider, so it appears with the trail. -->
      <div class="panel-bar">
        <h2 class="panel-head">Structural locus browser</h2>
        <LocusTrail :trail="trail" :display-names="displayNames" @go="jump" />
      </div>

      <div ref="frame" class="track-frame">
        <div v-if="view.status === 'pending' || view.status === 'idle'" class="track-scroll track-waiting">
          <p class="muted">Loading the locus…</p>
        </div>
        <GeneTrack
          v-else-if="drawable !== null"
          :detail="drawable"
          :collection-genome-count="props.collectionGenomeCount"
          :is-dimmed="isDimmed"
        />
      </div>

      <!-- ⛔ A failure is SAID, beside whatever is still drawn — never an empty track. -->
      <div v-if="failure !== null" class="pop-error track-error" role="alert">
        <span>
          {{ failure.kind === "not_found" ? "No such locus in this catalogue" : "The locus did not load" }}
          — {{ failure.detail }}.
          <template v-if="drawable !== null">The track below is still the previous locus.</template>
        </span>
        <button v-if="failure.kind !== 'not_found'" type="button" class="pop-retry" @click="navigation.retry()">
          Try again
        </button>
      </div>

      <div
        id="pop"
        ref="popover"
        class="pop"
        role="dialog"
        aria-label="Position detail"
        :hidden="!isPopoverOpen || drawable === null"
        :style="popoverStyle"
      >
        <template v-if="drawable !== null">
          <OffsetPopover
            v-if="openPopoverSlot !== null && openPopoverMarginal !== null && openPopoverHeading !== null"
            :marginal="openPopoverMarginal"
            :labelled-offset="openPopoverHeading.labelledOffset"
            :recorded-offset="openPopoverHeading.recordedOffset"
            :display-mirror="displayMirror"
            :drawn-locus="openPopoverDrawnLocus"
            :focal-gene-count="drawable.locus.gene_count"
            :neighbours-by-label="neighboursByLabel"
            :top-neighbour-count="null"
            @walk="walk"
            @close="track.closePopover()"
          />
          <ArrangementPopover
            v-else-if="isFocalPopoverOpen"
            :locus="drawable.locus"
            :arrangements="browser.rows"
            :total="browser.total"
            :selected-rank="drawnArrangement?.rank ?? null"
            :anchor-ranks="drawable.anchor.arrangement_ranks"
            :members-without-a-neighbourhood="drawable.arrangements.members_without_a_neighbourhood"
            :walk-direction="walkDirection"
            :arrangements-not-shown="browser.arrangementsNotShown"
            :load-status="browser.status"
            :load-failure-detail="browser.lastFailure?.detail ?? null"
            @load-more="browser.loadMore()"
            @close="track.closePopover()"
          />
        </template>
      </div>

      <!-- The switcher, ANCHORED UNDER THE FOCAL GENE (David, 2026-08-23): the neighbourhoods are
           choices for that one locus. The anchor box sits in its left gutter and the channel key in
           its right, so the options stay centred under the focal gene whichever is occupied. -->
      <div v-if="drawable !== null" class="arr-wrap">
        <AnchorGenomeBox :species-key="speciesKey" placement="track" />
        <ArrangementSwitcher
          :locus="drawable.locus"
          :arrangements="drawable.arrangements.listed"
          :total="drawable.arrangements.total"
          :selected-index="selectedArrangementIndex"
          :anchor-ranks="drawable.anchor.arrangement_ranks"
          :anchor-genome-name="anchorSampleId"
          :membership-is-complete="drawable.arrangements.membership_is_complete"
          :walk-direction="walkDirection"
          @select="track.selectArrangement($event)"
        />
        <BandKey />
      </div>
    </div>
  </section>
</template>
